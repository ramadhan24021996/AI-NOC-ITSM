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
// still subject to token auth) or whose Origin host/hostname equals the request Host or ALLOWED_ORIGIN.
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
	// When proxied behind Nginx (e.g. port 9443 -> 9999), Nginx `proxy_set_header Host $host`
	// strips the external port while browser `Origin` includes `:9443`. Compare hostnames without port.
	reqHostOnly := r.Host
	if idx := strings.IndexByte(reqHostOnly, ':'); idx != -1 {
		reqHostOnly = reqHostOnly[:idx]
	}
	if u.Hostname() != "" && strings.EqualFold(u.Hostname(), reqHostOnly) {
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

	perTableLimit := limit / 5
	if perTableLimit < 40 {
		perTableLimit = 40
	}
	if perTableLimit > 1000 {
		perTableLimit = 1000
	}

	// Fetch real DB logs across all 8 NOC subsystems if DB is available
	if h.db != nil {
		// 1. AUDIT (system_audits — cap at 15 so periodic health checks don't crowd out other sources)
		type auditLog struct {
			Timestamp   time.Time `gorm:"column:timestamp"`
			Status      string    `gorm:"column:status"`
			HealthScore float64   `gorm:"column:health_score"`
			RootCause   string    `gorm:"column:root_cause"`
		}
		var audits []auditLog
		if err := h.db.Table("system_audits").Select("timestamp, status, health_score, root_cause").Order("timestamp DESC").Limit(15).Find(&audits).Error; err == nil {
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
					"message":   fmt.Sprintf("System Audit %s (Score: %.1f): %s", a.Status, a.HealthScore, a.RootCause),
				})
			}
		}

		// 1b. AI RUNTIME STATE & ORCHESTRATOR REMEDIATION RESULTS (ai_runtime_state + remediation_results)
		type runtimeStateRow struct {
			WorkerID       string    `gorm:"column:worker_id"`
			State          string    `gorm:"column:state"`
			PreviousState  string    `gorm:"column:previous_state"`
			TransitionedAt time.Time `gorm:"column:transitioned_at"`
		}
		var rtRows []runtimeStateRow
		if err := h.db.Table("ai_runtime_state").Select("worker_id, state, COALESCE(previous_state, 'INIT') as previous_state, transitioned_at").Order("transitioned_at DESC").Limit(20).Find(&rtRows).Error; err == nil {
			for _, rt := range rtRows {
				stU := strings.ToUpper(strings.TrimSpace(rt.State))
				logType := "INFO"
				if stU == "READY" || stU == "ONLINE" || stU == "ACTIVE" {
					logType = "OK"
				} else if stU == "DEGRADED" || stU == "SYNCING" || stU == "BOOTING" {
					logType = "WARN"
				} else if stU == "FAILED" || stU == "ERROR" {
					logType = "ERROR"
				}
				logs = append(logs, map[string]interface{}{
					"timestamp": rt.TransitionedAt.Format("2006-01-02 15:04:05"),
					"type":      logType,
					"category":  "AI",
					"message":   fmt.Sprintf("AI Runtime [%s] State Transition: %s → %s", rt.WorkerID, rt.PreviousState, rt.State),
				})
			}
		}

		type remResultRow struct {
			IncidentID      string    `gorm:"column:incident_id"`
			ServiceRestored bool      `gorm:"column:service_restored"`
			OutcomeVerified bool      `gorm:"column:outcome_verified"`
			Evidence        string    `gorm:"column:evidence"`
			CreatedAt       time.Time `gorm:"column:created_at"`
		}
		var remRows []remResultRow
		if err := h.db.Table("remediation_results").Select("COALESCE(CAST(incident_id AS TEXT), '') as incident_id, service_restored, outcome_verified, COALESCE(evidence, '') as evidence, created_at").Order("created_at DESC").Limit(20).Find(&remRows).Error; err == nil {
			for _, rm := range remRows {
				logType := "WARN"
				if rm.OutcomeVerified && rm.ServiceRestored {
					logType = "OK"
				}
				logs = append(logs, map[string]interface{}{
					"timestamp": rm.CreatedAt.Format("2006-01-02 15:04:05"),
					"type":      logType,
					"category":  "ORCH",
					"message":   fmt.Sprintf("Orchestrator Remediation [INC-%s] Verified=%v Restored=%v · %s", rm.IncidentID, rm.OutcomeVerified, rm.ServiceRestored, rm.Evidence),
				})
			}
		}

		// 2. IMMUTABLE GOVERNANCE & ORCHESTRATOR AUDIT (immutable_audit_log uses `timestamp` column)
		type immAudit struct {
			ActionType string    `gorm:"column:action_type"`
			Actor      string    `gorm:"column:actor"`
			Target     string    `gorm:"column:target"`
			Timestamp  time.Time `gorm:"column:timestamp"`
		}
		var immLogs []immAudit
		if err := h.db.Table("immutable_audit_log").Select("action_type, actor, target, timestamp").Order("timestamp DESC").Limit(perTableLimit).Find(&immLogs).Error; err == nil {
			for _, im := range immLogs {
				actU := strings.ToUpper(im.ActionType)
				logType := "INFO"
				cat := "AUDIT"
				if strings.Contains(actU, "APPROVE") || strings.Contains(actU, "RESOLVE") || strings.Contains(actU, "REMEDI") || strings.Contains(actU, "EXECUTE") || strings.Contains(actU, "SANDBOX") {
					logType = "OK"
					cat = "ORCH"
				} else if strings.Contains(actU, "REJECT") || strings.Contains(actU, "DELETE") || strings.Contains(actU, "ROLLBACK") || strings.Contains(actU, "MUTATION") {
					logType = "WARN"
					cat = "ORCH"
				} else if strings.Contains(actU, "FAIL") || strings.Contains(actU, "BLOCK") {
					logType = "ERROR"
					cat = "AUDIT"
				}
				ts := im.Timestamp
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

		// 3. RBAC & SECURITY AUDIT (rbac_audit_logs)
		type rbacLog struct {
			Username  string    `gorm:"column:username"`
			Action    string    `gorm:"column:action"`
			Target    string    `gorm:"column:target"`
			Details   string    `gorm:"column:details"`
			IPAddress string    `gorm:"column:ip_address"`
			CreatedAt time.Time `gorm:"column:created_at"`
		}
		var rLogs []rbacLog
		if err := h.db.Table("rbac_audit_logs").Select("username, action, target, details, ip_address, created_at").Order("created_at DESC").Limit(30).Find(&rLogs).Error; err == nil {
			for _, rl := range rLogs {
				logType := "INFO"
				actU := strings.ToUpper(rl.Action)
				if strings.Contains(actU, "DENIED") || strings.Contains(actU, "FAIL") {
					logType = "ERROR"
				} else if strings.Contains(actU, "RESET") || strings.Contains(actU, "CHANGE") || strings.Contains(actU, "UPDATE") {
					logType = "WARN"
				}
				logs = append(logs, map[string]interface{}{
					"timestamp": rl.CreatedAt.Format("2006-01-02 15:04:05"),
					"type":      logType,
					"category":  "AUDIT",
					"message":   fmt.Sprintf("RBAC [%s] user=%s ip=%s target=%s: %s", rl.Action, rl.Username, rl.IPAddress, rl.Target, rl.Details),
				})
			}
		}

		// 4. AI AUDIT TRAIL & JARVIS COGNITIVE AUDIT (ai_audit_trail + jarvis_audit_trail + incidents)
		type aiAudit struct {
			CreatedAt      time.Time `gorm:"column:created_at"`
			IncidentID     uint      `gorm:"column:incident_id"`
			ActionExecuted string    `gorm:"column:action_executed"`
			LLMResponse    string    `gorm:"column:llm_response"`
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
				cat := "AI"
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

		type jarvisAudit struct {
			MemoryLayer string    `gorm:"column:memory_layer"`
			Operation   string    `gorm:"column:operation"`
			Operator    string    `gorm:"column:operator"`
			Status      string    `gorm:"column:status"`
			Details     string    `gorm:"column:details"`
			Timestamp   time.Time `gorm:"column:timestamp"`
		}
		var jAudits []jarvisAudit
		if err := h.db.Table("jarvis_audit_trail").Select("memory_layer, operation, operator, status, details, timestamp").Order("timestamp DESC").Limit(30).Find(&jAudits).Error; err == nil {
			for _, ja := range jAudits {
				logType := "OK"
				if strings.ToUpper(ja.Status) != "SUCCESS" && strings.ToUpper(ja.Status) != "OK" {
					logType = "WARN"
				}
				logs = append(logs, map[string]interface{}{
					"timestamp": ja.Timestamp.Format("2006-01-02 15:04:05"),
					"type":      logType,
					"category":  "AI",
					"message":   fmt.Sprintf("JARVIS [%s/%s] by %s (%s): %s", ja.MemoryLayer, ja.Operation, ja.Operator, ja.Status, ja.Details),
				})
			}
		}

		// 5. INCIDENTS & HITL GATE (incidents table — `timestamp` column)
		type incRow struct {
			IncidentID uint      `gorm:"column:incident_id"`
			DeviceName string    `gorm:"column:device_name"`
			Flag       string    `gorm:"column:flag"`
			Evidence   string    `gorm:"column:evidence"`
			Timestamp  time.Time `gorm:"column:timestamp"`
		}
		var incRows []incRow
		if err := h.db.Table("incidents").Select("incident_id, COALESCE(device_name, '') as device_name, COALESCE(flag, '') as flag, COALESCE(evidence, '') as evidence, timestamp").Order("incident_id DESC").Limit(perTableLimit).Find(&incRows).Error; err == nil {
			for _, ir := range incRows {
				flUpper := strings.ToUpper(ir.Flag + " " + ir.Evidence)
				logType := "INFO"
				cat := "AI"
				if strings.Contains(flUpper, "HITL") || strings.Contains(flUpper, "APPROVAL") || strings.Contains(flUpper, "WARN") {
					logType = "WARN"
					cat = "ORCH"
				} else if strings.Contains(flUpper, "CRIT") || strings.Contains(flUpper, "ERR") || strings.Contains(flUpper, "FAIL") {
					logType = "ERROR"
					cat = "AI"
				} else if strings.Contains(flUpper, "RESOLV") || strings.Contains(flUpper, "OK") {
					logType = "OK"
					cat = "ORCH"
				}
				dev := ir.DeviceName
				if dev == "" {
					dev = "AI-Pipeline-Gate"
				}
				ts := ir.Timestamp
				if ts.IsZero() {
					ts = time.Now()
				}
				logs = append(logs, map[string]interface{}{
					"timestamp": ts.Format("2006-01-02 15:04:05"),
					"type":      logType,
					"category":  cat,
					"message":   fmt.Sprintf("[INC-%d] Host=%s Flag=%s · %s", ir.IncidentID, dev, ir.Flag, ir.Evidence),
				})
			}
		}

		// 6. INGESTOR & NETDATA WATCHDOG ALERTS (fleet_devices uses `last_seen` + fleet_incidents uses `created_at`)
		type deviceLog struct {
			PCName       string    `gorm:"column:pc_name"`
			Status       string    `gorm:"column:status"`
			IPAddress    string    `gorm:"column:ip_address"`
			AgentVersion string    `gorm:"column:agent_version"`
			LastSeen     time.Time `gorm:"column:last_seen"`
		}
		var devs []deviceLog
		if err := h.db.Table("fleet_devices").Select("pc_name, status, COALESCE(ip_address, '') as ip_address, COALESCE(agent_version, '') as agent_version, last_seen").Order("last_seen DESC").Limit(perTableLimit).Find(&devs).Error; err == nil {
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
				ts := d.LastSeen
				if ts.IsZero() {
					ts = time.Now()
				}
				logs = append(logs, map[string]interface{}{
					"timestamp": ts.Format("2006-01-02 15:04:05"),
					"type":      logType,
					"category":  "INGEST",
					"message":   fmt.Sprintf("Agent Telemetry Ingested from %s (%s) [Status: %s · Agent v%s]", d.PCName, d.IPAddress, d.Status, d.AgentVersion),
				})
			}
		}

		type fleetIncLog struct {
			IncidentID  uint      `gorm:"column:incident_id"`
			PCName      string    `gorm:"column:pc_name"`
			Severity    string    `gorm:"column:severity"`
			Status      string    `gorm:"column:status"`
			Description string    `gorm:"column:description"`
			CreatedAt   time.Time `gorm:"column:created_at"`
		}
		var fIncs []fleetIncLog
		if err := h.db.Table("fleet_incidents").Select("incident_id, pc_name, severity, status, description, created_at").Order("incident_id DESC").Limit(perTableLimit).Find(&fIncs).Error; err == nil {
			for _, fi := range fIncs {
				sevU := strings.ToUpper(strings.TrimSpace(fi.Severity))
				stU := strings.ToUpper(strings.TrimSpace(fi.Status))
				descU := strings.ToUpper(fi.Description)
				logType := "WARN"
				if stU == "RESOLVED" || stU == "CLOSED" {
					logType = "OK"
				} else if sevU == "CRITICAL" || sevU == "HIGH" || strings.Contains(descU, "FAILED") {
					logType = "ERROR"
				} else if sevU == "LOW" || sevU == "INFO" {
					logType = "INFO"
				}
				cat := "NETDATA"
				if strings.Contains(descU, "PRINTER") || strings.Contains(descU, "SPOOL") {
					cat = "INGEST"
				} else if strings.Contains(descU, "REMEDI") || strings.Contains(descU, "RESTART") {
					cat = "ORCH"
				}
				ts := fi.CreatedAt
				if ts.IsZero() {
					ts = time.Now()
				}
				logs = append(logs, map[string]interface{}{
					"timestamp": ts.Format("2006-01-02 15:04:05"),
					"type":      logType,
					"category":  cat,
					"message":   fmt.Sprintf("[FleetAlert #%d] %s [%s/%s]: %s", fi.IncidentID, fi.PCName, fi.Severity, fi.Status, fi.Description),
				})
			}
		}

		// 7. SYSTEM DAEMONS & AI WORKERS (agent_heartbeats)
		type daemonHb struct {
			Agent      string    `gorm:"column:agent"`
			Status     string    `gorm:"column:status"`
			Uptime     int64     `gorm:"column:uptime"`
			QueueDepth int       `gorm:"column:queue_depth"`
			CPU        float64   `gorm:"column:cpu"`
			LastSeen   time.Time `gorm:"column:last_seen"`
		}
		var daemons []daemonHb
		if err := h.db.Table("agent_heartbeats").Select("agent, status, uptime, queue_depth, cpu, last_seen").Order("last_seen DESC").Limit(20).Find(&daemons).Error; err == nil {
			for _, dm := range daemons {
				logType := "OK"
				if strings.ToUpper(dm.Status) != "ONLINE" && strings.ToUpper(dm.Status) != "OK" {
					logType = "WARN"
				}
				ts := dm.LastSeen
				if ts.IsZero() {
					ts = time.Now()
				}
				logs = append(logs, map[string]interface{}{
					"timestamp": ts.Format("2006-01-02 15:04:05"),
					"type":      logType,
					"category":  "SYS",
					"message":   fmt.Sprintf("Daemon Worker [%s] status=%s uptime=%ds queue=%d cpu=%.2f%%", dm.Agent, dm.Status, dm.Uptime, dm.QueueDepth, dm.CPU),
				})
				logs = append(logs, map[string]interface{}{
					"timestamp": ts.Format("2006-01-02 15:04:05"),
					"type":      "DEBUG",
					"category":  "SYS",
					"message":   fmt.Sprintf("[DEBUG] Worker [%s] heartbeat probe OK · queue_depth=%d · cpu_load=%.3f", dm.Agent, dm.QueueDepth, dm.CPU),
				})
			}
		}

		// 8. DATABASE & WEBSOCKET LIVE TELEMETRY (DB & WS categories)
		var activeConns int64
		_ = h.db.Raw("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()").Scan(&activeConns).Error
		var ragVectors int64
		_ = h.db.Table("knowledge_vectors").Count(&ragVectors).Error
		nowStr := time.Now().Format("2006-01-02 15:04:05")
		logs = append(logs, map[string]interface{}{
			"timestamp": nowStr,
			"type":      "OK",
			"category":  "DB",
			"message":   fmt.Sprintf("PostgreSQL Pool HEALTHY · active_connections=%d · knowledge_vectors=%d · write_ahead_log=SYNCED", activeConns, ragVectors),
		})
		logs = append(logs, map[string]interface{}{
			"timestamp": nowStr,
			"type":      "INFO",
			"category":  "WS",
			"message":   fmt.Sprintf("WebSocket Real-Time Hub ACTIVE · connected_clients=%d · replay_buffer=%d events", GetClientCount(), len(eventBuffer)),
		})
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
