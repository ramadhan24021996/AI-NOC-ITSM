package websocket

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"time"

	"sort"

	"github.com/gin-gonic/gin"
	"github.com/gorilla/websocket"
	"gorm.io/gorm"
)

// WebSocket upgrader
var Upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool {
		return true // Allow all origins for the dashboard
	},
}

type wsClient struct {
	conn *websocket.Conn
	mu   sync.Mutex
}

// WebSocket client registry
var (
	wsClients   = make(map[*wsClient]bool)
	wsClientsMu sync.Mutex
)

// In-memory logs buffer
var (
	internalLogs   = []map[string]interface{}{}
	internalLogsMu sync.Mutex
)

// Replay buffer for missed WebSocket events
var (
	eventBuffer   = []map[string]interface{}{}
	eventBufferMu sync.Mutex
)

const (
	// writeWait is the maximum time allowed to write a single message.
	writeWait = 10 * time.Second
	// pongWait is the maximum time to wait for a Pong reply after sending Ping.
	// The read deadline is reset to this value on every Pong received.
	pongWait = 60 * time.Second
	// pingPeriod controls how often the server sends Ping frames.
	// Must be strictly less than pongWait.
	pingPeriod = (pongWait * 9) / 10
	// maxMessageSize caps the size of messages sent by the client.
	maxMessageSize = 4096
)

func removeClient(client *wsClient) {
	wsClientsMu.Lock()
	if _, ok := wsClients[client]; ok {
		delete(wsClients, client)
		client.conn.Close()
	}
	wsClientsMu.Unlock()
}

func GetClientCount() int {
	wsClientsMu.Lock()
	defer wsClientsMu.Unlock()
	return len(wsClients)
}

func GetInternalLogs() []map[string]interface{} {
	internalLogsMu.Lock()
	defer internalLogsMu.Unlock()
	// Return a copy to avoid concurrency issues
	cpy := make([]map[string]interface{}, len(internalLogs))
	copy(cpy, internalLogs)
	return cpy
}

func AddInternalLog(logType, category, message string) {
	internalLogsMu.Lock()
	defer internalLogsMu.Unlock()

	logEntry := map[string]interface{}{
		"timestamp": time.Now().Format("2006-01-02 15:04:05"),
		"type":      logType,
		"category":  category,
		"message":   message,
	}

	internalLogs = append([]map[string]interface{}{logEntry}, internalLogs...)
	if len(internalLogs) > 500 {
		internalLogs = internalLogs[:500]
	}

	// Broadcast to all WS clients
	BroadcastWSEvent("system_log", map[string]interface{}{
		"message":   message,
		"type":      strings.ToLower(logType),
		"timestamp": logEntry["timestamp"],
		"category":  category,
	})
}

func BroadcastWSEvent(event string, data interface{}) {
	payload := map[string]interface{}{
		"event":     event,
		"data":      data,
		"timestamp": time.Now().UnixMilli(),
	}

	eventBufferMu.Lock()
	eventBuffer = append(eventBuffer, payload)
	if len(eventBuffer) > 100 {
		eventBuffer = eventBuffer[1:]
	}
	eventBufferMu.Unlock()

	payloadBytes, err := json.Marshal(payload)
	if err != nil {
		return
	}

	wsClientsMu.Lock()
	clients := make([]*wsClient, 0, len(wsClients))
	for client := range wsClients {
		clients = append(clients, client)
	}
	wsClientsMu.Unlock()

	for _, client := range clients {
		client.mu.Lock()
		client.conn.SetWriteDeadline(time.Now().Add(writeWait))
		err := client.conn.WriteMessage(websocket.TextMessage, payloadBytes)
		client.mu.Unlock()
		if err != nil {
			removeClient(client)
		}
	}
}

// WS Handler
type Handler struct {
	db *gorm.DB
}

func NewHandler(db *gorm.DB) *Handler {
	return &Handler{db: db}
}

func (h *Handler) RegisterRoutes(r *gin.Engine) {
	r.GET("/ws/logs", h.WSLogs)
	r.GET("/api/server/logs", h.GetServerLogs)
}

func (h *Handler) GetServerLogs(c *gin.Context) {
	logs := GetInternalLogs()

	// Fetch real DB logs if DB is available
	if h.db != nil {
		// 1. AUDIT (system_audits)
		type auditLog struct {
			Timestamp  time.Time `json:"timestamp"`
			Status     string    `json:"status"`
			HealthScore float64   `json:"health_score"`
			RootCause  string    `json:"root_cause"`
		}
		var audits []auditLog
		if err := h.db.Table("system_audits").Select("timestamp, status, health_score, root_cause").Order("timestamp DESC").Limit(50).Find(&audits).Error; err == nil {
			for _, a := range audits {
				logType := "INFO"
				if a.Status == "CRITICAL" {
					logType = "ERROR"
				} else if a.Status == "DEGRADED" {
					logType = "WARN"
				}
				logs = append(logs, map[string]interface{}{
					"timestamp": a.Timestamp.Format("2006-01-02 15:04:05"),
					"type":      logType,
					"category":  "AUDIT",
					"message":   fmt.Sprintf("Audit %s (Score: %.1f): %s", a.Status, a.HealthScore, a.RootCause),
				})
			}
		}

		// 2. AI AUDIT TRAIL (ai_audit_trail)
		type aiAudit struct {
			CreatedAt      time.Time `json:"created_at"`
			IncidentID     uint      `json:"incident_id"`
			ActionExecuted string    `json:"action_executed"`
			LLMResponse    string    `json:"llm_response"`
		}
		var aiAudits []aiAudit
		if err := h.db.Table("ai_audit_trail").Select("created_at, incident_id, action_executed, llm_response").Order("created_at DESC").Limit(50).Find(&aiAudits).Error; err == nil {
			for _, a := range aiAudits {
				logs = append(logs, map[string]interface{}{
					"timestamp": a.CreatedAt.Format("2006-01-02 15:04:05"),
					"type":      "INFO",
					"category":  "AI_ENGINE",
					"message":   fmt.Sprintf("[Incident #%d] Executed: %s - %s", a.IncidentID, a.ActionExecuted, a.LLMResponse),
				})
			}
		}

		// 3. INGEST (telemetry_logs / fleet_devices)
		type deviceLog struct {
			PCName    string    `json:"pc_name"`
			Status    string    `json:"status"`
			UpdatedAt time.Time `json:"updated_at"`
		}
		var devs []deviceLog
		if err := h.db.Table("fleet_devices").Select("pc_name, status, updated_at").Order("updated_at DESC").Limit(30).Find(&devs).Error; err == nil {
			for _, d := range devs {
				logs = append(logs, map[string]interface{}{
					"timestamp": d.UpdatedAt.Format("2006-01-02 15:04:05"),
					"type":      "INFO",
					"category":  "TELEMETRY",
					"message":   fmt.Sprintf("Agent Heartbeat from %s [Status: %s]", d.PCName, d.Status),
				})
			}
		}
	}

	// Sort logs by timestamp descending
	sort.Slice(logs, func(i, j int) bool {
		t1, _ := logs[i]["timestamp"].(string)
		t2, _ := logs[j]["timestamp"].(string)
		return t1 > t2
	})

	limit := 200
	if l := c.Query("limit"); l != "" {
		if n, err := strconv.Atoi(l); err == nil && n > 0 && n <= 500 {
			limit = n
		}
	}
	if len(logs) > limit {
		logs = logs[:limit]
	}
	c.JSON(http.StatusOK, logs)
}

func (h *Handler) WSLogs(c *gin.Context) {
	conn, err := Upgrader.Upgrade(c.Writer, c.Request, nil)
	if err != nil {
		fmt.Printf("[WS ERROR] Failed to upgrade WebSocket: %v\n", err)
		return
	}

	client := &wsClient{conn: conn}

	// Configure connection limits and handlers BEFORE writing anything.
	conn.SetReadLimit(maxMessageSize)
	conn.SetReadDeadline(time.Now().Add(pongWait))
	conn.SetPongHandler(func(string) error {
		// Each Pong from the client resets the read deadline, keeping the
		// connection alive as long as the client is responsive.
		conn.SetReadDeadline(time.Now().Add(pongWait))
		return nil
	})

	// Register client BEFORE spawning goroutines so BroadcastWSEvent can
	// reach this connection immediately.
	wsClientsMu.Lock()
	wsClients[client] = true
	wsClientsMu.Unlock()

	// ── Send initial welcome (protected by write mutex) ────────────────────
	welcome := map[string]interface{}{
		"event": "system_log",
		"data": map[string]interface{}{
			"message":   "WebSocket log stream connected successfully (Go Backend)",
			"type":      "ok",
			"timestamp": time.Now().Format("2006-01-02 15:04:05"),
		},
	}
	if welcomeBytes, jerr := json.Marshal(welcome); jerr == nil {
		client.mu.Lock()
		conn.SetWriteDeadline(time.Now().Add(writeWait))
		_ = conn.WriteMessage(websocket.TextMessage, welcomeBytes)
		client.mu.Unlock()
	}

	// ── Replay missed events from buffer (protected by write mutex) ──────────
	eventBufferMu.Lock()
	bufferedEvents := make([]map[string]interface{}, len(eventBuffer))
	copy(bufferedEvents, eventBuffer)
	eventBufferMu.Unlock()

	for _, p := range bufferedEvents {
		pBytes, jerr := json.Marshal(p)
		if jerr != nil {
			continue
		}
		client.mu.Lock()
		conn.SetWriteDeadline(time.Now().Add(writeWait))
		_ = conn.WriteMessage(websocket.TextMessage, pBytes)
		client.mu.Unlock()
	}

	// ── Ping goroutine ───────────────────────────────────────────────────────
	// Sends a Ping frame every pingPeriod. If the client does not send back a
	// Pong within pongWait, SetReadDeadline causes ReadMessage to return an
	// error, which exits the read loop below and triggers cleanup.
	pingDone := make(chan struct{})
	go func() {
		ticker := time.NewTicker(pingPeriod)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				client.mu.Lock()
				conn.SetWriteDeadline(time.Now().Add(writeWait))
				pingErr := conn.WriteMessage(websocket.PingMessage, nil)
				client.mu.Unlock()
				if pingErr != nil {
					// Write failed; connection is gone. Read loop will also
					// detect this and handle cleanup.
					return
				}
			case <-pingDone:
				return
			}
		}
	}()

	// ── Read loop (blocking) ─────────────────────────────────────────────────
	// Exits on any read error: normal close, peer reset, or read deadline
	// exceeded (i.e., Pong not received within pongWait).
	for {
		if _, _, readErr := conn.ReadMessage(); readErr != nil {
			break
		}
	}

	// Signal ping goroutine to stop, then clean up.
	close(pingDone)
	removeClient(client)
}
