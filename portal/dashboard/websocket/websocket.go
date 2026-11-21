package websocket

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	"sort"

	"github.com/gin-gonic/gin"
	"github.com/gorilla/websocket"
	"gorm.io/gorm"
)

// CheckSameOrigin accepts requests with no Origin header (non-browser clients, which are
// still subject to token auth) or whose Origin host equals the request Host or ALLOWED_ORIGIN.
func CheckSameOrigin(r *http.Request) bool {
	origin := r.Header.Get("Origin")
	if origin == "" {
		return true
	}
	u, err := url.Parse(origin)
	if err != nil {
		return false
	}
	if strings.EqualFold(u.Host, r.Host) {
		return true
	}
	if allowed := os.Getenv("ALLOWED_ORIGIN"); allowed != "" && strings.EqualFold(origin, allowed) {
		return true
	}
	return false
}

// WebSocket upgrader. Token is carried in Sec-WebSocket-Protocol: "bearer, <jwt>" (see middleware).
var Upgrader = websocket.Upgrader{
	CheckOrigin:  CheckSameOrigin,
	Subprotocols: []string{"bearer"},
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
	if len(internalLogs) > 2000 {
		internalLogs = internalLogs[:2000]
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

func (h *Handler) WSOperatorChat(c *gin.Context) {
	conn, err := Upgrader.Upgrade(c.Writer, c.Request, nil)
	if err != nil {
		fmt.Printf("[WS ERROR] Failed to upgrade Operator Chat WebSocket: %v\n", err)
		return
	}
	client := &wsClient{conn: conn}
	conn.SetReadLimit(maxMessageSize)
	conn.SetReadDeadline(time.Now().Add(pongWait))
	conn.SetPongHandler(func(string) error {
		conn.SetReadDeadline(time.Now().Add(pongWait))
		return nil
	})

	wsClientsMu.Lock()
	wsClients[client] = true
	wsClientsMu.Unlock()

	welcome := map[string]interface{}{
		"event": "chat_welcome",
		"data":  map[string]interface{}{"role": "operator", "status": "CONNECTED"},
	}
	if b, jerr := json.Marshal(welcome); jerr == nil {
		client.mu.Lock()
		conn.SetWriteDeadline(time.Now().Add(writeWait))
		_ = conn.WriteMessage(websocket.TextMessage, b)
		client.mu.Unlock()
	}

	pingDone := make(chan struct{})
	go func() {
		ticker := time.NewTicker(pingPeriod)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				client.mu.Lock()
				conn.SetWriteDeadline(time.Now().Add(writeWait))
				if err := conn.WriteMessage(websocket.PingMessage, nil); err != nil {
					client.mu.Unlock()
					return
				}
				client.mu.Unlock()
			case <-pingDone:
				return
			}
		}
	}()

	for {
		if _, _, err := conn.ReadMessage(); err != nil {
			break
		}
	}
	close(pingDone)
	removeClient(client)
}

func (h *Handler) WSClientChat(c *gin.Context) {
	conn, err := Upgrader.Upgrade(c.Writer, c.Request, nil)
	if err != nil {
		fmt.Printf("[WS ERROR] Failed to upgrade Client Chat WebSocket: %v\n", err)
		return
	}
	client := &wsClient{conn: conn}
	conn.SetReadLimit(maxMessageSize)
	conn.SetReadDeadline(time.Now().Add(pongWait))
	conn.SetPongHandler(func(string) error {
		conn.SetReadDeadline(time.Now().Add(pongWait))
		return nil
	})

	wsClientsMu.Lock()
	wsClients[client] = true
	wsClientsMu.Unlock()

	welcome := map[string]interface{}{
		"event": "chat_welcome",
		"data":  map[string]interface{}{"role": "client", "status": "CONNECTED"},
	}
	if b, jerr := json.Marshal(welcome); jerr == nil {
		client.mu.Lock()
		conn.SetWriteDeadline(time.Now().Add(writeWait))
		_ = conn.WriteMessage(websocket.TextMessage, b)
		client.mu.Unlock()
	}

	pingDone := make(chan struct{})
	go func() {
		ticker := time.NewTicker(pingPeriod)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				client.mu.Lock()
				conn.SetWriteDeadline(time.Now().Add(writeWait))
				if err := conn.WriteMessage(websocket.PingMessage, nil); err != nil {
					client.mu.Unlock()
					return
				}
				client.mu.Unlock()
			case <-pingDone:
				return
			}
		}
	}()

	for {
		if _, _, err := conn.ReadMessage(); err != nil {
			break
		}
	}
	close(pingDone)
	removeClient(client)
}

func (h *Handler) GetServerLogs(c *gin.Context) {
	logs := GetInternalLogs()

	limit := 500
	if l := c.Query("limit"); l != "" {
		if n, err := strconv.Atoi(l); err == nil && n > 0 {
			if n > 5000 {
				n = 5000
			}
			limit = n
		}
	}

	perTableLimit := limit / 3
	if perTableLimit < 60 {
		perTableLimit = 60
	}
	if perTableLimit > 1500 {
		perTableLimit = 1500
	}

	// Fetch real DB logs if DB is available
	if h.db != nil {
		// 1. AUDIT (system_audits)
		type auditLog struct {
			Timestamp   time.Time `json:"timestamp"`
			Status      string    `json:"status"`
			HealthScore float64   `json:"health_score"`
			RootCause   string    `json:"root_cause"`
		}
		var audits []auditLog
		if err := h.db.Table("system_audits").Select("timestamp, status, health_score, root_cause").Order("timestamp DESC").Limit(perTableLimit).Find(&audits).Error; err == nil {
			for _, a := range audits {
				var logType string
				switch strings.ToUpper(strings.TrimSpace(a.Status)) {
				case "CRITICAL", "ERROR", "DOWN":
					logType = "ERROR"
				case "DEGRADED", "WARNING", "WARN":
					logType = "WARN"
				case "HEALTHY", "OK", "ONLINE":
					logType = "OK"
				default:
					logType = "INFO"
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
		if err := h.db.Table("ai_audit_trail").Select("created_at, incident_id, action_executed, llm_response").Order("created_at DESC").Limit(perTableLimit).Find(&aiAudits).Error; err == nil {
			for _, a := range aiAudits {
				actUpper := strings.ToUpper(a.ActionExecuted + " " + a.LLMResponse)
				logType := "INFO"
				switch {
				case strings.Contains(actUpper, "FAIL") || strings.Contains(actUpper, "ERROR") || strings.Contains(actUpper, "BLOCK") || strings.Contains(actUpper, "REJECT") || strings.Contains(actUpper, "INVALID"):
					logType = "ERROR"
				case strings.Contains(actUpper, "PENDING") || strings.Contains(actUpper, "WAIT") || strings.Contains(actUpper, "HIGH_RISK") || strings.Contains(actUpper, "WARN"):
					logType = "WARN"
				case strings.Contains(actUpper, "APPROVED") || strings.Contains(actUpper, "RESOLVED") || strings.Contains(actUpper, "VERIFIED") || strings.Contains(actUpper, "SOP_EXECUTED") || strings.Contains(actUpper, "SOP_PROMOTED") || strings.Contains(actUpper, "PLAYBOOK") || strings.Contains(actUpper, "REMEDIATION_DISPATCHED"):
					logType = "OK"
				}
				cat := "AI_ENGINE"
				if strings.Contains(actUpper, "PLAYBOOK") || strings.Contains(actUpper, "REMEDIATION") || strings.Contains(actUpper, "SOP_EXECUTED") {
					cat = "ORCH"
				}
				logs = append(logs, map[string]interface{}{
					"timestamp": a.CreatedAt.Format("2006-01-02 15:04:05"),
					"type":      logType,
					"category":  cat,
					"message":   fmt.Sprintf("[Incident #%d] Executed: %s - %s", a.IncidentID, a.ActionExecuted, a.LLMResponse),
				})
			}
		}

		// 3. INGESTOR & TELEMETRY (fleet_devices)
		type deviceLog struct {
			PCName    string    `json:"pc_name"`
			Status    string    `json:"status"`
			UpdatedAt time.Time `json:"updated_at"`
		}
		var devs []deviceLog
		if err := h.db.Table("fleet_devices").Select("pc_name, status, updated_at").Order("updated_at DESC").Limit(perTableLimit).Find(&devs).Error; err == nil {
			for _, d := range devs {
				stUpper := strings.ToUpper(strings.TrimSpace(d.Status))
				logType := "INFO"
				switch stUpper {
				case "ONLINE", "OK", "HEALTHY":
					logType = "OK"
				case "OFFLINE", "WARN", "WARNING", "DEGRADED":
					logType = "WARN"
				case "CRITICAL", "ERROR", "FAILED":
					logType = "ERROR"
				}
				logs = append(logs, map[string]interface{}{
					"timestamp": d.UpdatedAt.Format("2006-01-02 15:04:05"),
					"type":      logType,
					"category":  "INGEST",
					"message":   fmt.Sprintf("Agent Telemetry Heartbeat from %s [Status: %s]", d.PCName, d.Status),
				})
			}
		}

		// 4. ORCHESTRATOR & IMMUTABLE GOVERNANCE AUDIT (immutable_audit_log)
		type immAudit struct {
			ActionType string    `gorm:"column:action_type"`
			Actor      string    `gorm:"column:actor"`
			Target     string    `gorm:"column:target"`
			CreatedAt  time.Time `gorm:"column:created_at"`
		}
		var immLogs []immAudit
		if err := h.db.Table("immutable_audit_log").Select("action_type, actor, target, created_at").Order("created_at DESC").Limit(perTableLimit / 2).Find(&immLogs).Error; err == nil {
			for _, im := range immLogs {
				actU := strings.ToUpper(im.ActionType)
				logType := "INFO"
				cat := "AUDIT"
				if strings.Contains(actU, "APPROVE") || strings.Contains(actU, "REMEDI") || strings.Contains(actU, "EXECUTE") || strings.Contains(actU, "SANDBOX") {
					logType = "OK"
					cat = "ORCH"
				} else if strings.Contains(actU, "REJECT") || strings.Contains(actU, "DELETE") || strings.Contains(actU, "ROLLBACK") {
					logType = "WARN"
					cat = "ORCH"
				} else if strings.Contains(actU, "FAIL") || strings.Contains(actU, "BLOCK") {
					logType = "ERROR"
					cat = "AUDIT"
				}
				ts := im.CreatedAt
				if ts.IsZero() {
					ts = time.Now()
				}
				logs = append(logs, map[string]interface{}{
					"timestamp": ts.Format("2006-01-02 15:04:05"),
					"type":      logType,
					"category":  cat,
					"message":   fmt.Sprintf("[%s] Actor: %s → Target: %s", im.ActionType, im.Actor, im.Target),
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
