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
		// 1. INGEST (telemetry_logs)
		rows1, err := h.db.Raw("SELECT timestamp, 'INFO' as type, 'INGEST' as category, concat('Telemetry: ', metric_type, ' from ', device_name) as message FROM telemetry_logs ORDER BY timestamp DESC LIMIT 50").Rows()
		if err == nil {
			for rows1.Next() {
				var ts time.Time
				var t, cat, msg string
				rows1.Scan(&ts, &t, &cat, &msg)
				logs = append(logs, map[string]interface{}{"timestamp": ts.Format("2006-01-02 15:04:05"), "type": t, "category": cat, "message": msg})
			}
			rows1.Close()
		}

		// 2. AUDIT (system_audits)
		rows2, err := h.db.Raw("SELECT timestamp, CASE WHEN status='CRITICAL' THEN 'ERROR' WHEN status='DEGRADED' THEN 'WARN' ELSE 'INFO' END as type, 'AUDIT' as category, concat('Audit ', status, ' (Score: ', health_score, '): ', root_cause) as message FROM system_audits ORDER BY timestamp DESC LIMIT 50").Rows()
		if err == nil {
			for rows2.Next() {
				var ts time.Time
				var t, cat, msg string
				rows2.Scan(&ts, &t, &cat, &msg)
				logs = append(logs, map[string]interface{}{"timestamp": ts.Format("2006-01-02 15:04:05"), "type": t, "category": cat, "message": msg})
			}
			rows2.Close()
		}

		// 3. ORCH / AI (incident_events)
		rows3, err := h.db.Raw("SELECT created_at as timestamp, CASE WHEN event_type LIKE '%FAIL%' THEN 'ERROR' ELSE 'INFO' END as type, CASE WHEN event_type LIKE '%AI%' OR description ILIKE '%ai%' THEN 'AI' ELSE 'ORCH' END as category, concat('[Inc ', incident_id, '] ', event_type, ': ', description) as message FROM incident_events ORDER BY created_at DESC LIMIT 50").Rows()
		if err == nil {
			for rows3.Next() {
				var ts time.Time
				var t, cat, msg string
				rows3.Scan(&ts, &t, &cat, &msg)
				logs = append(logs, map[string]interface{}{"timestamp": ts.Format("2006-01-02 15:04:05"), "type": t, "category": cat, "message": msg})
			}
			rows3.Close()
		}

		// 4. DB (database activity)
		rows4, err := h.db.Raw("SELECT now() as timestamp, 'INFO' as type, 'DB' as category, concat('Active Query: ', substr(query, 1, 60)) as message FROM pg_stat_activity WHERE state = 'active' AND query NOT LIKE '%pg_stat_activity%' LIMIT 10").Rows()
		if err == nil {
			for rows4.Next() {
				var ts time.Time
				var t, cat, msg string
				rows4.Scan(&ts, &t, &cat, &msg)
				logs = append(logs, map[string]interface{}{"timestamp": ts.Format("2006-01-02 15:04:05"), "type": t, "category": cat, "message": msg})
			}
			rows4.Close()
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
