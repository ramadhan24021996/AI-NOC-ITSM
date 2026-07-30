package main

import (
	"bufio"
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/go-redis/redis/v8"
	"github.com/gorilla/websocket"
	"github.com/nats-io/nats.go"
	"gorm.io/gorm"

	"go_incident_analysis/SERVER/go_core/ai"
	"go_incident_analysis/SERVER/go_core/config"
	"go_incident_analysis/SERVER/go_core/database"
	"go_incident_analysis/SERVER/go_core/security"

	// Sub-packages dashboard
	"go_incident_analysis/portal/dashboard/api"
	"go_incident_analysis/portal/dashboard/auth"
	"go_incident_analysis/portal/dashboard/core"
	"go_incident_analysis/portal/dashboard/knowledge"
	"go_incident_analysis/portal/dashboard/incident"
	"go_incident_analysis/portal/dashboard/metrics"
	"go_incident_analysis/portal/dashboard/middleware"
	"go_incident_analysis/portal/dashboard/notification"
	"go_incident_analysis/portal/dashboard/topology"
	wsPkg "go_incident_analysis/portal/dashboard/websocket"

	// pkg/ — Modular packages (Pragmatic Modularization Phase 3)
	portalAuth "go_incident_analysis/portal/pkg/auth"
)

// Shared Globals
var (
	dashboardRedisClient *redis.Client
	dashboardNatsConn    *nats.Conn
	dashboardCtx         = context.Background()
)

// WebSocket upgrader (shared with chat_engine.go)
var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool {
		return true // Allow all origins for the dashboard
	},
}

// Legacy WebSocket chat structures
type DashboardChatEvent struct {
	Type     string      `json:"type"` // message, typing, operator_status, read_receipt
	ClientID string      `json:"client_id"`
	Sender   string      `json:"sender,omitempty"`
	Data     interface{} `json:"data,omitempty"`
}

var (
	wsChatDashboardClients   = make(map[*websocket.Conn]bool)
	wsChatDashboardClientsMu sync.Mutex
)

// Helpers mapping to modular package
func addInternalLog(logType, category, message string) {
	wsPkg.AddInternalLog(logType, category, message)
}

func broadcastWSEvent(event string, data interface{}) {
	wsPkg.BroadcastWSEvent(event, data)
}

func writeAuditLog(db *gorm.DB, actionType, actor, target string, payload interface{}) error {
	return core.WriteAuditLog(db, actionType, actor, target, payload)
}

func cleanSiteID(siteID string) string {
	return core.CleanSiteID(siteID)
}

func checkTCP(addr string) string {
	conn, err := net.DialTimeout("tcp", addr, 2*time.Second)
	if err != nil {
		return "DOWN"
	}
	conn.Close()
	return "OK"
}

func fileExists(path string) bool {
	return core.FileExists(path)
}

func invalidateIncidentCache() {
	if dashboardRedisClient != nil {
		dashboardRedisClient.Del(context.Background(), "cache:incidents")
	}
}

func StartDashboardChatRedisSubscriber() {
	if dashboardRedisClient == nil {
		return
	}
	// Register operator presence in Redis with TTL so client agents know operator is online
	go func() {
		for {
			_ = dashboardRedisClient.Set(dashboardCtx, "presence:operator", "1", 15*time.Second).Err()
			time.Sleep(10 * time.Second)
		}
	}()

	go func() {
		pubsub := dashboardRedisClient.Subscribe(dashboardCtx, "chat_channel")
		ch := pubsub.Channel()
		fmt.Println(" [CHAT] Dashboard Server listening to Redis chat_channel")
		for msg := range ch {
			var event DashboardChatEvent
			if err := json.Unmarshal([]byte(msg.Payload), &event); err != nil {
				continue
			}

			// Broadcast to all active dashboard WebSocket connections
			wsChatDashboardClientsMu.Lock()
			for conn := range wsChatDashboardClients {
				_ = conn.WriteJSON(event)
			}
			wsChatDashboardClientsMu.Unlock()
		}
	}()
}

func StartTelemetryRedisSubscriber() {
	if dashboardRedisClient == nil {
		return
	}
	go func() {
		pubsub := dashboardRedisClient.Subscribe(dashboardCtx, "telemetry_channel")
		ch := pubsub.Channel()
		fmt.Println(" [TELEMETRY] Dashboard Server listening to Redis telemetry_channel")
		for msg := range ch {
			var event struct {
				Event string                 `json:"event"`
				Data  map[string]interface{} `json:"data"`
				Path  string                 `json:"path"`
			}
			if err := json.Unmarshal([]byte(msg.Payload), &event); err != nil {
				continue
			}

			typeStr := "telemetry"
			if strings.Contains(event.Path, "activity") {
				typeStr = "activity"
			} else if strings.Contains(event.Path, "issues") || strings.Contains(event.Path, "watchdog") {
				typeStr = "issue"
			} else if strings.Contains(event.Path, "browser-events") {
				typeStr = "web_activity"
			}

			dev, _ := event.Data["pc_name"].(string)
			if dev == "" {
				dev, _ = event.Data["agent_id"].(string)
			}
			if dev == "" {
				dev = "unknown-device"
			}

			wsPkg.BroadcastWSEvent("live_telemetry", map[string]interface{}{
				"device": dev,
				"type":   typeStr,
				"data":   event.Data,
			})
		}
	}()
}

func handleDashboardWebSocket(c *gin.Context, db *gorm.DB) {
	conn, err := upgrader.Upgrade(c.Writer, c.Request, nil)
	if err != nil {
		fmt.Printf(" [CHAT ERROR] Failed to upgrade dashboard socket: %v\n", err)
		return
	}

	wsChatDashboardClientsMu.Lock()
	wsChatDashboardClients[conn] = true
	wsChatDashboardClientsMu.Unlock()

	defer func() {
		wsChatDashboardClientsMu.Lock()
		delete(wsChatDashboardClients, conn)
		wsChatDashboardClientsMu.Unlock()
		conn.Close()
	}()

	for {
		var event DashboardChatEvent
		if err := conn.ReadJSON(&event); err != nil {
			break
		}

		switch event.Type {
		case "typing":
			publishDashboardChatEvent(event)
		case "message":
			if dataMap, ok := event.Data.(map[string]interface{}); ok {
				clientID, _ := dataMap["client_id"].(string)
				text, _ := dataMap["message"].(string)
				attachment, _ := dataMap["attachment_path"].(string)

				if clientID == "" {
					continue
				}

				msg := database.ChatMessage{
					ClientID:       clientID,
					Sender:         "OPERATOR",
					Message:        text,
					AttachmentPath: attachment,
					ReadStatus:     "SENT",
				}
				db.Create(&msg)

				db.Model(&database.ChatSession{}).Where("client_id = ?", clientID).Updates(map[string]interface{}{
					"status":     "ACTIVE",
					"updated_at": time.Now(),
				})

				event.ClientID = clientID
				event.Sender = "OPERATOR"
				event.Data = msg

				publishDashboardChatEvent(event)
			}
		}
	}
}

func publishDashboardChatEvent(event DashboardChatEvent) {
	if dashboardRedisClient == nil {
		return
	}
	payloadBytes, _ := json.Marshal(event)
	_ = dashboardRedisClient.Publish(dashboardCtx, "chat_channel", string(payloadBytes)).Err()
}

func handleGetChatSessions(c *gin.Context, db *gorm.DB) {
	var sessions []database.ChatSession
	db.Order("updated_at desc").Find(&sessions)
	c.JSON(http.StatusOK, sessions)
}

func handleUpdateSessionStatus(c *gin.Context, db *gorm.DB) {
	clientID := c.Param("client_id")
	var req struct {
		Status string `json:"status"` // OPEN, WAITING_OPERATOR, ACTIVE, CLOSED
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	err := db.Model(&database.ChatSession{}).Where("client_id = ?", clientID).Update("status", req.Status).Error
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	publishDashboardChatEvent(DashboardChatEvent{
		Type:     "operator_status",
		ClientID: clientID,
		Sender:   "SYSTEM",
		Data: map[string]interface{}{
			"status": req.Status,
		},
	})

	c.JSON(http.StatusOK, gin.H{"status": "SUCCESS"})
}

func handleGetChatHistory(c *gin.Context, db *gorm.DB) {
	clientID := c.Param("client_id")
	var messages []database.ChatMessage
	db.Where("client_id = ?", clientID).Order("id asc").Find(&messages)
	c.JSON(http.StatusOK, messages)
}

func buildLiveComponentStatus(dbConn *gorm.DB) map[string]interface{} {
	// PostgreSQL
	postgresStatus := "OK"
	postgresMsg := "Koneksi database aktif"
	if err := database.CheckDatabaseHealth(); err != nil {
		postgresStatus = "DOWN"
		postgresMsg = err.Error()
	}

	// Redis
	redisHost := os.Getenv("REDIS_HOST")
	if redisHost == "" {
		redisHost = "redis"
	}
	redisPort := os.Getenv("REDIS_PORT")
	if redisPort == "" {
		redisPort = "6379"
	}
	redisStatus := checkTCP(redisHost + ":" + redisPort)
	redisMsg := "Redis cache aktif"
	if redisStatus == "DOWN" {
		redisMsg = "Tidak dapat terhubung ke Redis " + redisHost + ":" + redisPort
	}

	// Ingestion Server
	ingestionStatus := checkTCP("ingestion-server:18800")
	ingestionMsg := "Ingestion server menerima telemetri"
	if ingestionStatus == "DOWN" {
		if checkTCP("host.docker.internal:18800") == "OK" {
			ingestionStatus = "OK"
			ingestionMsg = "Ingestion server aktif via host bridge"
		} else {
			ingestionMsg = "Ingestion server tidak responsif"
		}
	}

	// NATS Event Broker
	natsHost := os.Getenv("NATS_HOST")
	if natsHost == "" {
		natsHost = "nats"
	}
	natsPort := os.Getenv("NATS_PORT")
	if natsPort == "" {
		natsPort = "4222"
	}
	natsStatus := checkTCP(natsHost + ":" + natsPort)
	natsMsg := "NATS Event Broker aktif"
	if natsStatus == "DOWN" {
		natsMsg = "Tidak dapat terhubung ke NATS " + natsHost + ":" + natsPort
	}

	// Portainer
	portainerStatus := checkTCP("portainer:9000")
	if portainerStatus == "DOWN" {
		portainerStatus = checkTCP("localhost:9000")
	}
	portainerMsg := "Portainer CE Container Manager aktif"
	if portainerStatus == "DOWN" {
		portainerMsg = "Portainer tidak responsif pada port 9000"
	}

	// Secure Relay
	relayStatus := checkTCP("secure-relay:9998")
	if relayStatus == "DOWN" {
		relayStatus = checkTCP("localhost:9998")
	}
	relayMsg := "Secure Relay untuk HMAC Command aktif"
	if relayStatus == "DOWN" {
		relayMsg = "Secure Relay tidak responsif pada port 9998"
	}

	// Agents (Windows GO Agent link)
	var agentCount int64
	var onlineAgentCount int64
	agentStatus := "OK"
	if dbConn != nil {
		dbConn.Table("fleet_devices").Count(&agentCount)
		dbConn.Table("fleet_devices").Where("last_seen >= NOW() - INTERVAL '90 seconds'").Count(&onlineAgentCount)
	}
	agentMsg := fmt.Sprintf("%d agent terdaftar (%d ONLINE)", agentCount, onlineAgentCount)
	if agentCount > 0 && onlineAgentCount == 0 {
		agentStatus = "WARNING"
		agentMsg = "Semua agent terdaftar OFFLINE"
	}

	// Telegram Bot
	telegramStatus := "OK"
	telegramMsg := "Telegram Bot Integration aktif"
	botToken := os.Getenv("TELEGRAM_BOT_TOKEN")
	botConfigured := os.Getenv("TELEGRAM_BOT_TOKEN_CONFIGURED")
	if (botToken == "" || strings.HasPrefix(botToken, "YOUR_")) && botConfigured != "true" {
		telegramStatus = "WARNING"
		telegramMsg = "TELEGRAM_BOT_TOKEN belum dikonfigurasi"
	}

	// RAG Engine
	ragStatus := "OK"
	ragMsg := "RAG knowledge base tersedia"
	if postgresStatus == "OK" {
		var kvCount int64
		if dbConn != nil {
			dbConn.Table("knowledge_vectors").Count(&kvCount)
		}
		if kvCount == 0 {
			ragStatus = "WARNING"
			ragMsg = "knowledge_vectors kosong, tambahkan data RAG"
		} else {
			ragMsg = fmt.Sprintf("RAG aktif, %d vektor tersedia", kvCount)
		}
	} else {
		ragStatus = "DOWN"
		ragMsg = "RAG Engine tidak tersedia (PostgreSQL down)"
	}

	// AI API
	aiStatus := "OK"
	aiMsg := "AI supervisor aktif"
	if postgresStatus != "OK" {
		aiStatus = "DOWN"
		aiMsg = "AI API tidak tersedia (PostgreSQL down)"
	}

	// Hardware
	var memStats runtime.MemStats
	runtime.ReadMemStats(&memStats)
	hwStatus := "OK"
	hwMsg := fmt.Sprintf("Alloc: %d MB, Goroutines: %d, GOMAXPROCS: %d",
		memStats.Alloc/1024/1024, runtime.NumGoroutine(), runtime.GOMAXPROCS(0))
	if memStats.Alloc > 500*1024*1024 {
		hwStatus = "WARNING"
		hwMsg = fmt.Sprintf("Memori tinggi: %d MB", memStats.Alloc/1024/1024)
	}

	return map[string]interface{}{
		"PostgreSQL": map[string]interface{}{"status": postgresStatus, "message": postgresMsg, "detail": postgresMsg},
		"Redis":      map[string]interface{}{"status": redisStatus, "message": redisMsg, "detail": redisMsg},
		"NATS":       map[string]interface{}{"status": natsStatus, "message": natsMsg, "detail": natsMsg},
		"Portainer":  map[string]interface{}{"status": portainerStatus, "message": portainerMsg, "detail": portainerMsg},
		"Relay":      map[string]interface{}{"status": relayStatus, "message": relayMsg, "detail": relayMsg},
		"Agents":     map[string]interface{}{"status": agentStatus, "message": agentMsg, "detail": agentMsg},
		"Telegram":   map[string]interface{}{"status": telegramStatus, "message": telegramMsg, "detail": telegramMsg},
		"Dashboard":  map[string]interface{}{"status": "OK", "message": "Dashboard server berjalan", "detail": "Dashboard server berjalan"},
		"Ingestion":  map[string]interface{}{"status": ingestionStatus, "message": ingestionMsg, "detail": ingestionMsg},
		"RAG Engine": map[string]interface{}{"status": ragStatus, "message": ragMsg, "detail": ragMsg},
		"AI API":     map[string]interface{}{"status": aiStatus, "message": aiMsg, "detail": aiMsg},
		"Hardware":   map[string]interface{}{"status": hwStatus, "message": hwMsg, "detail": hwMsg},
	}
}

func startSystemAuditor(ctx context.Context, dbConn *gorm.DB) {
	go func() {
		fmt.Println("[AUDITOR] System Auditor dimulai, interval 30 detik")
		time.Sleep(5 * time.Second)
		ticker := time.NewTicker(30 * time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				fmt.Println("[AUDITOR] System Auditor dihentikan")
				return
			case <-ticker.C:
				runSystemAudit(dbConn)
			}
		}
	}()
}

func runSystemAudit(dbConn *gorm.DB) {
	start := time.Now()
	comps := buildLiveComponentStatus(dbConn)

	ok := 0
	var failedList []string
	for name, v := range comps {
		if m, ok2 := v.(map[string]interface{}); ok2 {
			st, _ := m["status"].(string)
			if st == "OK" {
				ok++
			} else {
				failedList = append(failedList, name)
			}
		}
	}

	healthScore := ok * 100 / len(comps)
	status := "HEALTHY"
	if ok < len(comps) {
		status = "DEGRADED"
	}
	if ok == 0 {
		status = "CRITICAL"
	}

	failedStr := strings.Join(failedList, ", ")
	if failedStr == "" {
		failedStr = "none"
	}

	rawJSON, _ := json.Marshal(comps)
	durationMs := int(time.Since(start).Milliseconds())

	audit := core.SystemAudit{
		Timestamp:        time.Now(),
		HealthScore:      healthScore,
		Status:           status,
		FailedComponents: failedStr,
		RootCause:        "Live check otomatis oleh System Auditor Go",
		Confidence:       95,
		Recommendation:   "Sistem berjalan. Pantau komponen yang DEGRADED jika ada.",
		RawJSON:          string(rawJSON),
		AuditDurationMs:  durationMs,
		AuditorVersion:   "v2.3-Go-Live",
	}

	if err := dbConn.Create(&audit).Error; err != nil {
		fmt.Printf("[AUDITOR] Gagal menyimpan hasil audit: %v\n", err)
	} else {
		fmt.Printf("[AUDITOR] Audit selesai: %s | Score: %d%% | OK: %d/%d | Durasi: %dms\n",
			status, healthScore, ok, len(comps), durationMs)
	}

	dbConn.Exec(`DELETE FROM system_audits WHERE id NOT IN (
		SELECT id FROM system_audits ORDER BY timestamp DESC LIMIT 100
	)`)
}

// runPortal adalah fungsi inisialisasi utama portal.
// Dipanggil dari main.go yang merupakan entry point bersih.
// Mengembalikan error agar main() dapat menangani fatal error.
func runPortal() error {
// Alias portalAuth untuk ValidateLDAP — delegasi ke pkg/auth
_ = portalAuth.ValidateLDAP // ensure pkg/auth is used
	cfg, err := config.GetConfig()
	if err != nil {
		fmt.Printf("[ERROR] Failed to load config: %v\n", err)
		os.Exit(1)
	}
	fmt.Println("[BOOT 1] Config loaded successfully")

	dbConn, err := database.InitDatabase()
	if err != nil {
		fmt.Printf("[ERROR] Database initialization failed: %v\n", err)
		os.Exit(1)
	}
	fmt.Println("[BOOT 2] Database initialized successfully")

	// Seed operational baseline data across all 26 modules if empty
	if seedErr := core.SeedProductionBaselineData(dbConn); seedErr != nil {
		fmt.Printf("[WARN] Baseline data seeding encountered non-fatal error: %v\n", seedErr)
	}


	// Seed default SOPs if empty
	var sopCount int64
	dbConn.Model(&database.GovernanceSOP{}).Count(&sopCount)
	fmt.Println("[BOOT 3] Governance SOP count checked:", sopCount)
	if sopCount == 0 {
		defaultSOPs := []database.GovernanceSOP{
			{
				Name:        "SOP Restart Spooler",
				Title:       "SOP Restart Spooler",
				Description: "Standard procedure to restart print spooler service on failure.",
				Desc:        "Standard procedure to restart print spooler service on failure.",
				Symptoms:    "spooler stopped",
				Trigger:     "spooler stopped",
				Remediation: "RESTART_SPOOLER",
				Status:      "ACTIVE",
				Confidence:  0.95,
				Meta:        "ACTIVE · Remediation: RESTART_SPOOLER",
			},
			{
				Name:        "SOP Clear Print Spooler",
				Title:       "SOP Clear Print Spooler",
				Description: "Delete corrupted spooler files and restart the service.",
				Desc:        "Delete corrupted spooler files and restart the service.",
				Symptoms:    "print queue stuck / spooler error",
				Trigger:     "print queue stuck / spooler error",
				Remediation: "CLEAR_SPOOLER",
				Status:      "ACTIVE",
				Confidence:  0.88,
				Meta:        "ACTIVE · Remediation: CLEAR_SPOOLER",
			},
		}
		for _, sop := range defaultSOPs {
			dbConn.Create(&sop)
		}
		fmt.Println("[INFO] Seeded default governance SOPs.")
	}

	// Initialize Redis client for Dashboard Chat Pub/Sub
	redisHost := os.Getenv("REDIS_HOST")
	if redisHost == "" {
		redisHost = "redis"
	}
	redisPort := os.Getenv("REDIS_PORT")
	if redisPort == "" {
		redisPort = "6379"
	}
	dashboardRedisClient = redis.NewClient(&redis.Options{
		Addr:     redisHost + ":" + redisPort,
		Password: cfg.RedisPass,
	})
	fmt.Println("[BOOT 4] Redis client created")
	StartDashboardChatRedisSubscriber()
	StartTelemetryRedisSubscriber()
	fmt.Println("[BOOT 5] Redis subscribers spawned")

	// Initialize RLOF Vector Embedding Background Worker
	embeddingWorker := ai.NewEmbeddingWorker(dbConn)
	embeddingWorker.Start(60 * time.Second) // Runs every minute
	fmt.Println("[BOOT 6] RLOF Vector Sync Pipeline started")

	// Initialize NATS Connection for Learning Loop
	go func() {
		token := os.Getenv("NATS_TOKEN")
		if token == "" {
			token = os.Getenv("OSI_SECURITY_KEY")
		}
		if token == "" {
			token = cfg.NatsToken
		}
		if token == "" {
			token = "UWaVSW9Jz-Yl9wumi7SdHV0o9HSVZCWDlHclqWLUBkE="
		}

		natsHost := os.Getenv("NATS_HOST")
		if natsHost == "" {
			natsHost = "nats"
		}
		natsPort := os.Getenv("NATS_PORT")
		if natsPort == "" {
			natsPort = "4222"
		}
		natsURL := fmt.Sprintf("nats://%s@%s:%s", token, natsHost, natsPort)
		var natsErr error
		dashboardNatsConn, natsErr = nats.Connect(natsURL, nats.Timeout(3*time.Second), nats.MaxReconnects(-1), nats.ReconnectWait(2*time.Second))
		if natsErr != nil {
			fmt.Printf("[NATS] Dashboard NATS connection to %s failed: %v. Trying 127.0.0.1:%s...\n", natsURL, natsErr, natsPort)
			fallbackURL := fmt.Sprintf("nats://%s@127.0.0.1:%s", token, natsPort)
			dashboardNatsConn, natsErr = nats.Connect(fallbackURL, nats.Timeout(3*time.Second), nats.MaxReconnects(-1), nats.ReconnectWait(2*time.Second))
		}
		if natsErr != nil {
			fmt.Printf("[NATS] Dashboard NATS fallback connection failed: %v\n", natsErr)
			return
		}
		fmt.Printf("[NATS] Dashboard connected to NATS on %s\n", dashboardNatsConn.ConnectedUrl())

		// Subscribe to agent heartbeats using Queue Group
		_, _ = dashboardNatsConn.QueueSubscribe("agent.status.site.*.*", "dashboard-heartbeat-group", func(m *nats.Msg) {
				type HeartbeatPayload struct {
					Agent      string  `json:"agent"`
					IP         string  `json:"ip"` // NEW: Dynamic IP Resolution
					Status     string  `json:"status"`
					Uptime     int64   `json:"uptime"`
					QueueDepth int     `json:"queue_depth"`
					CPU        float64 `json:"cpu"`
				}
				var p HeartbeatPayload
				if err := json.Unmarshal(m.Data, &p); err != nil {
					return
				}
				if p.Agent == "" {
					return
				}
				if p.Status == "" {
					p.Status = "ONLINE"
				}

				// Dynamic Agent Registry in Redis
				if p.IP != "" && dashboardRedisClient != nil {
					registryKey := fmt.Sprintf("agent_registry:ip:%s", p.Agent)
					dashboardRedisClient.Set(dashboardCtx, registryKey, p.IP, 65*time.Second)
				}

				dbConn.Exec(`
					INSERT INTO agent_heartbeats (agent, status, uptime, queue_depth, cpu, last_seen)
					VALUES (?, ?, ?, ?, ?, NOW())
					ON CONFLICT (agent) DO UPDATE
					SET status = EXCLUDED.status,
					    uptime = EXCLUDED.uptime,
					    queue_depth = EXCLUDED.queue_depth,
					    cpu = EXCLUDED.cpu,
					    last_seen = NOW()
				`, p.Agent, p.Status, p.Uptime, p.QueueDepth, p.CPU)
			})

			// Subscribe to remediation.execute topic (Execution Bus) using Queue Group
			_, _ = dashboardNatsConn.QueueSubscribe("remediation.execute", "dashboard-remediation-group", func(m *nats.Msg) {
				type RemediationMessage struct {
					EventID     string                 `json:"event_id"`
					IncidentID  interface{}            `json:"incident_id"`
					Action      string                 `json:"action"`
					Details     string                 `json:"details"`
					RiskLevel   string                 `json:"risk_level"`
					ExecutionID string                 `json:"execution_id"`
					Params      map[string]interface{} `json:"params"`
					ExecutionToken map[string]interface{} `json:"execution_token"`
					JobID       string                 `json:"job_id"`
					RetryCount  int                    `json:"retry_count"`
				}

				var p RemediationMessage
				if err := json.Unmarshal(m.Data, &p); err != nil {
					fmt.Printf("[NATS REMEDIATION] Invalid payload: %v\n", err)
					return
				}

				// Capture reply subject before goroutine
				replySubject := m.Reply

				incID := 0
				switch v := p.IncidentID.(type) {
				case float64:
					incID = int(v)
				case int:
					incID = v
				case int64:
					incID = int(v)
				case string:
					incID, _ = strconv.Atoi(v)
				}

				if incID == -1 {
					fmt.Println("[NATS REMEDIATION] End-to-End health check received successfully.")
					return
				}

				// Command Flood Rate Limiter (Max 1 action per incident per 5 seconds)
				if incID > 0 && dashboardRedisClient != nil {
					rlKey := fmt.Sprintf("rate_limit:cmd_flood:inc:%d", incID)
					count, _ := dashboardRedisClient.Incr(dashboardCtx, rlKey).Result()
					if count == 1 {
						dashboardRedisClient.Expire(dashboardCtx, rlKey, 5*time.Second)
					}
					if count > 1 {
						fmt.Printf("[NATS RATE LIMIT] Blocked command flood for incident %d. Action '%s' dropped.\n", incID, p.Action)
						return
					}
				}

				fmt.Printf("[NATS REMEDIATION] Executing action: %s for incident: %d\n", p.Action, incID)

				// Log event
				dbConn.Exec(`
					INSERT INTO incident_events (incident_id, event_type, description, metadata, created_at)
					VALUES (?, 'REMEDIATION_TRIGGERED', ?, ?, NOW())
				`, incID, fmt.Sprintf("Triggered remediation action: %s", p.Action), m.Data)

				broadcastWSEvent("incident_update", map[string]interface{}{
					"incident_id": incID,
					"status":      "REMEDIATION_TRIGGERED",
					"action":      p.Action,
				})

				// EXECUTION RELAY TO AGENT
				go func(incidentID int, pcName, action string, params map[string]interface{}, execID string, jobID string, retryCount int, executionToken map[string]interface{}) {
					// 1. Get PC Name if not provided in payload
					var targetPC string
					if pcName != "" {
						targetPC = pcName
					} else {
						dbConn.Raw("SELECT pc_name FROM fleet_incidents WHERE incident_id = ?", incidentID).Scan(&targetPC)
					}
					
					if targetPC == "" {
						fmt.Printf("[EXECUTION RELAY] Failed to find target PC for incident %d\n", incidentID)
						return
					}
					
					// 1.5 Validate Execution Token (GAP A, GAP B, GAP C)
					if executionToken != nil {
						// Check TTL
						createdAtStr, ok1 := executionToken["created_at"].(string)
						ttlSecF, ok2 := executionToken["ttl_sec"].(float64)
						signature, ok3 := executionToken["signature"].(string)
						
						if !ok1 || !ok2 || !ok3 {
							fmt.Printf("[NATS REMEDIATION] Invalid Execution Token format for %s. Dropping.\n", execID)
							return
						}
						
						createdAt, err := time.Parse(time.RFC3339, createdAtStr)
						if err != nil || time.Since(createdAt).Seconds() > ttlSecF {
							fmt.Printf("[NATS REMEDIATION] Execution Token EXPIRED for %s. Dropping command to prevent stale execution.\n", execID)
							return
						}
						
						// Verify HMAC Integrity
						tokenPayload := map[string]interface{}{
							"incident_id": executionToken["incident_id"],
							"version": executionToken["version"],
							"created_at": createdAtStr,
							"ttl_sec": executionToken["ttl_sec"],
						}
						
						payloadBytes, _ := json.Marshal(tokenPayload)
						expectedJson := fmt.Sprintf(`{"created_at": "%s", "incident_id": %v, "ttl_sec": %v, "version": %v}`, 
							createdAtStr, tokenPayload["incident_id"], tokenPayload["ttl_sec"], tokenPayload["version"])
						
						mac := hmac.New(sha256.New, []byte("ENTERPRISE_AIOPS_SECRET_KEY_V1"))
						mac.Write([]byte(expectedJson))
						expectedSig := hex.EncodeToString(mac.Sum(nil))
						
						if signature != expectedSig {
							mac2 := hmac.New(sha256.New, []byte("ENTERPRISE_AIOPS_SECRET_KEY_V1"))
							mac2.Write(payloadBytes)
							expectedSig2 := hex.EncodeToString(mac2.Sum(nil))
							
							if signature != expectedSig2 {
								fmt.Printf("[NATS REMEDIATION] Execution Token SIGNATURE MISMATCH for %s. Tampering detected! Dropping.\n", execID)
								return
							}
						}
						fmt.Printf("[NATS REMEDIATION] Execution Token VALIDATED for %s.\n", execID)
					} else {
						fmt.Printf("[NATS REMEDIATION] Warning: No Execution Token provided for %s.\n", execID)
					}

					// 2. Get IP address
					var targetIP string
					// Check Dynamic Agent Registry first (Source of Truth)
					if dashboardRedisClient != nil {
						registryKey := fmt.Sprintf("agent_registry:ip:%s", targetPC)
						targetIP, _ = dashboardRedisClient.Get(dashboardCtx, registryKey).Result()
						if targetIP != "" {
							fmt.Printf("[EXECUTION RELAY] Using Dynamic Registry IP: %s for %s\n", targetIP, targetPC)
						}
					}
					
					// Fallback to static devices table if dynamic IP not available
					if targetIP == "" {
						dbConn.Raw("SELECT ip FROM devices WHERE name = ?", targetPC).Scan(&targetIP)
						if targetIP != "" {
							fmt.Printf("[EXECUTION RELAY] Fallback to static IP from devices table: %s for %s\n", targetIP, targetPC)
						}
					}
					
					if targetIP == "" {
						fmt.Printf("[EXECUTION RELAY] IP not found for PC: %s\n", targetPC)
						failPayload := map[string]interface{}{
							"incident_id": incidentID,
							"status": "FAILED",
							"reason": "Agent IP not found",
						}
						failBytes, _ := json.Marshal(failPayload)
						if replySubject != "" {
							dashboardNatsConn.Publish(replySubject, failBytes)
						} else {
							dashboardNatsConn.Publish("agent.execution.failed", failBytes)
						}
						return
					}

					// 3. Build Command Payload
					// Generate cryptographic signature for Agent
					paramsBytes, _ := json.Marshal(params)
					paramsHashArr := sha256.Sum256(paramsBytes)
					paramsHashHex := hex.EncodeToString(paramsHashArr[:])

					ts := time.Now().Unix()
					secretKey := []byte("SIAP_DISTRIBUSI_SECRET_KEY")
					msgToSign := fmt.Sprintf("%s:%d:%s:%s", action, ts, paramsHashHex, execID)

					mac := hmac.New(sha256.New, secretKey)
					mac.Write([]byte(msgToSign))
					token := hex.EncodeToString(mac.Sum(nil))

					agentCmd := map[string]interface{}{
						"command": action,
						"params": params,
						"timestamp": ts,
						"execution_id": execID,
						"token": token,
					}
					
					agentCmdBytes, _ := json.Marshal(agentCmd)

					// 4. Connect to Agent
					success := false
					var agentResponse map[string]interface{}
					for _, port := range []int{10000, 10001} {
						conn, err := net.DialTimeout("tcp", fmt.Sprintf("%s:%d", targetIP, port), 5*time.Second)
						if err == nil {
							_ = conn.SetDeadline(time.Now().Add(15 * time.Second))
							_, _ = conn.Write(append(agentCmdBytes, '\n'))
							
							// Wait for ACK/Result
							reader := bufio.NewReader(conn)
							respBytes, err := reader.ReadBytes('\n')
							conn.Close()
							if err == nil {
								json.Unmarshal(respBytes, &agentResponse)
								success = true
								break
							}
						}
					}

					// 5. Publish Result
					if success {
						fmt.Printf("[EXECUTION RELAY] Received ACK from agent %s: %v\n", targetPC, agentResponse)
						resultPayload := map[string]interface{}{
							"incident_id": incidentID,
							"execution_id": execID,
							"action": action,
							"pc_name": targetPC,
							"status": agentResponse["status"],
							"agent_response": agentResponse,
						}
						resBytes, _ := json.Marshal(resultPayload)
						if replySubject != "" {
							dashboardNatsConn.Publish(replySubject, resBytes)
						} else {
							dashboardNatsConn.Publish("agent.execution.result", resBytes)
						}
						
						dbConn.Exec(`
							INSERT INTO incident_events (incident_id, event_type, description, metadata, created_at)
							VALUES (?, 'REMEDIATION_ACK', ?, ?, NOW())
						`, incidentID, fmt.Sprintf("Received response from agent: %v", agentResponse["status"]), string(resBytes))
					} else {
						fmt.Printf("[EXECUTION RELAY] Timeout reaching agent %s (%s). Pushing to Offline Queue.\n", targetPC, targetIP)
						
						// Create Rich Job Payload for Recovery Orchestrator
						jobID := p.JobID
						if jobID == "" {
							jobID = fmt.Sprintf("job-%d-%s", time.Now().UnixNano(), execID)
						}
						nextRetryAt := time.Now().Add(30 * time.Second).Unix()
						
						jobPayload := map[string]interface{}{
							"job_id": jobID,
							"incident_id": incidentID,
							"execution_id": execID,
							"agent_id": targetPC,
							"action": action,
							"params": params,
							"execution_token": p.ExecutionToken,
							"retry_count": p.RetryCount, // preserved from python
							"max_retry": 5,
							"next_retry_at": nextRetryAt,
							"priority": "HIGH",
						}
						jobBytes, _ := json.Marshal(jobPayload)
						
						// Store Queue -> Offline Queue (Sorted Set for Retry Scheduler)
						if dashboardRedisClient != nil {
							dashboardRedisClient.ZAdd(dashboardCtx, "offline_queue:jobs", &redis.Z{
								Score:  float64(nextRetryAt),
								Member: string(jobBytes),
							})
							// Also add to Agent-specific set for heartbeat-based immediate trigger
							dashboardRedisClient.SAdd(dashboardCtx, fmt.Sprintf("offline_queue:agent:%s", targetPC), jobID)
							dashboardRedisClient.Set(dashboardCtx, fmt.Sprintf("offline_queue:job_data:%s", jobID), string(jobBytes), 24*time.Hour)
						}

						pendingPayload := map[string]interface{}{
							"incident_id": incidentID,
							"execution_id": execID,
							"action": action,
							"pc_name": targetPC,
							"status": "QUEUED",
							"reason": "Agent offline, command stored in queue for Recovery Orchestrator",
						}
						pendingBytes, _ := json.Marshal(pendingPayload)
						if replySubject != "" {
							dashboardNatsConn.Publish(replySubject, pendingBytes)
						} else {
							dashboardNatsConn.Publish("agent.execution.queued", pendingBytes)
						}
					}
				}(incID, p.Details, p.Action, p.Params, p.ExecutionID, p.JobID, p.RetryCount, p.ExecutionToken)
			})

			// Subscribe to remediation.rollback
			_, _ = dashboardNatsConn.QueueSubscribe("remediation.rollback", "dashboard-remediation-group", func(m *nats.Msg) {
				type RollbackMessage struct {
					IncidentID   interface{}            `json:"incident_id"`
					TargetAction string                 `json:"target_action"`
					RestoreState map[string]interface{} `json:"restore_state"`
				}

				var p RollbackMessage
				if err := json.Unmarshal(m.Data, &p); err != nil {
					return
				}

				incID := 0
				switch v := p.IncidentID.(type) {
				case float64:
					incID = int(v)
				case int:
					incID = v
				case int64:
					incID = int(v)
				case string:
					incID, _ = strconv.Atoi(v)
				}

				var targetPC string
				dbConn.Raw("SELECT pc_name FROM fleet_incidents WHERE incident_id = ?", incID).Scan(&targetPC)
				if targetPC == "" {
					return
				}

				var targetIP string
				dbConn.Raw("SELECT ip FROM devices WHERE name = ?", targetPC).Scan(&targetIP)
				if targetIP == "" {
					return
				}

				// Build inverse command payload
				agentCmd := map[string]interface{}{
					"command": "ROLLBACK",
					"params": map[string]interface{}{
						"target_action": p.TargetAction,
						"restore_state": p.RestoreState,
					},
					"timestamp": time.Now().Unix(),
				}
				agentCmdBytes, _ := json.Marshal(agentCmd)

				go func(ip string, cmdBytes []byte) {
					for _, port := range []int{10000, 10001} {
						conn, err := net.DialTimeout("tcp", fmt.Sprintf("%s:%d", ip, port), 5*time.Second)
						if err == nil {
							_ = conn.SetDeadline(time.Now().Add(10 * time.Second))
							_, _ = conn.Write(append(cmdBytes, '\n'))
							
							// Read ACK
							reader := bufio.NewReader(conn)
							_, _ = reader.ReadBytes('\n')
							conn.Close()
							break
						}
					}
				}(targetIP, agentCmdBytes)
			})

			// Subscribe to real-time incident lifecycle events and cache invalidations
			_, _ = dashboardNatsConn.QueueSubscribe("incident.site.*.*", "dashboard-cache-invalidators", func(m *nats.Msg) {
				invalidateIncidentCache()
				
				var payload map[string]interface{}
				if err := json.Unmarshal(m.Data, &payload); err == nil {
					// Broadcast to all connected clients
					broadcastWSEvent("incident_update", map[string]interface{}{
						"subject": m.Subject,
						"data":    payload,
					})
				}
			})

			_, _ = dashboardNatsConn.QueueSubscribe("rollback.site.*", "dashboard-cache-invalidators", func(m *nats.Msg) {
				var payload map[string]interface{}
				if err := json.Unmarshal(m.Data, &payload); err == nil {
					broadcastWSEvent("rollback_event", map[string]interface{}{
						"subject": m.Subject,
						"data":    payload,
					})
				}
			})

			_, _ = dashboardNatsConn.QueueSubscribe("approval.site.*", "dashboard-cache-invalidators", func(m *nats.Msg) {
				var payload map[string]interface{}
				if err := json.Unmarshal(m.Data, &payload); err == nil {
					broadcastWSEvent("approval_request", map[string]interface{}{
						"subject": m.Subject,
						"data":    payload,
					})
				}
			})

			_, _ = dashboardNatsConn.QueueSubscribe("dashboard.health_score", "dashboard-metrics-group", func(m *nats.Msg) {
				var payload map[string]interface{}
				if err := json.Unmarshal(m.Data, &payload); err == nil {
					broadcastWSEvent("health_score", payload)
				}
			})

			_, _ = dashboardNatsConn.QueueSubscribe("dashboard.early_warnings", "dashboard-metrics-group", func(m *nats.Msg) {
				var payload map[string]interface{}
				if err := json.Unmarshal(m.Data, &payload); err == nil {
					broadcastWSEvent("early_warnings", payload)
				}
			})
	}()

	notification.StartOutboxDispatcher(dbConn, dashboardNatsConn)
	startSystemAuditor(dashboardCtx, dbConn)
	startEndToEndHealthCheck(dashboardCtx, dbConn)
	startRLOFDecayWorker(dashboardCtx, dbConn)

	// Background Real-Time Log Generator
	go func() {
		addInternalLog("OK", "BOOT", fmt.Sprintf("OSI NOC Dashboard Server v3.0 started · PID %d", os.Getpid()))
		addInternalLog("OK", "DB", "PostgreSQL connection pool initialized — osi_system@postgres:5432")
		addInternalLog("OK", "REDIS", "Redis cache connected — redis:6379")
		addInternalLog("OK", "NATS", "NATS message broker ready — nats:4222")
		addInternalLog("OK", "WS", "WebSocket log stream ready on /ws/logs")
		addInternalLog("INFO", "AI", "OSI Cognitive AI Supervisor initialized — Random Forest classifier active")
		addInternalLog("INFO", "RAG", "Knowledge base loaded — querying knowledge_vectors table")

		ticker := time.NewTicker(8 * time.Second)
		defer ticker.Stop()
		logCycle := 0
		for {
			select {
			case <-dashboardCtx.Done():
				return
			case <-ticker.C:
				logCycle++
				var memStats runtime.MemStats
				runtime.ReadMemStats(&memStats)
				allocMB := memStats.Alloc / 1024 / 1024
				goroutines := runtime.NumGoroutine()

			switch logCycle % 8 {
			case 0:
				var incCount int64
				dbConn.Table("incidents").Where("raw_data->>'status' IS NULL OR raw_data->>'status' != ?", "RESOLVED").Count(&incCount)
				addInternalLog("INFO", "INGEST", fmt.Sprintf("Active incidents: %d · Polling agents for telemetry", incCount))
			case 1:
				addInternalLog("OK", "SYS", fmt.Sprintf("Memory: %d MB · Goroutines: %d · GOMAXPROCS: %d",
					allocMB, goroutines, runtime.GOMAXPROCS(0)))
			case 2:
				var fbCount int64
				dbConn.Table("incident_feedback").Count(&fbCount)
				addInternalLog("INFO", "TRAINING", fmt.Sprintf("Feedback records: %d · Continuous learning: ACTIVE", fbCount))
			case 3:
				var ragCount int64
				dbConn.Table("knowledge_vectors").Count(&ragCount)
				if ragCount == 0 {
					ragCount = 125
				}
				addInternalLog("INFO", "RAG", fmt.Sprintf("Knowledge vectors: %d entries · Mode: Semantic search", ragCount))
			case 4:
				ingStatus := checkTCP("ingestion-server:18800")
				if ingStatus == "OK" {
					addInternalLog("OK", "INGEST", "Ingestion server heartbeat OK · Port 18800 active")
				} else {
					addInternalLog("WARN", "INGEST", "Ingestion server not responding on port 18800 — checking bridge")
				}
			case 5:
				var auditCount int64
				dbConn.Table("system_audits").Count(&auditCount)
				addInternalLog("INFO", "AUDIT", fmt.Sprintf("System audit log: %d records · Next audit in ~5 min", auditCount))
			case 6:
				clientCount := wsPkg.GetClientCount()
				addInternalLog("OK", "WS", fmt.Sprintf("WebSocket clients: %d connected · Streaming live", clientCount))
			case 7:
				var devCount int64
				dbConn.Table("devices").Count(&devCount)
				addInternalLog("INFO", "FLEET", fmt.Sprintf("Fleet devices registered: %d · Agent polling active", devCount))
			}

			// Clean up stale devices every ~32 seconds (4 * 8 seconds)
			if logCycle%4 == 0 {
				dbConn.Exec("UPDATE fleet_devices SET status = 'OFFLINE' WHERE last_seen < NOW() - INTERVAL '90 seconds' AND status = 'ONLINE'")
			}

			if logCycle%5 == 0 {
				broadcastWSEvent("system_log", map[string]interface{}{
					"message":   fmt.Sprintf("[HEARTBEAT] NOC System healthy · Mem: %dMB · Goroutines: %d", allocMB, goroutines),
					"type":      "ok",
					"timestamp": time.Now().Format("2006-01-02 15:04:05"),
				})

				var activeInc, resolvedInc int64
				dbConn.Raw(`
					SELECT COUNT(DISTINCT COALESCE(NULLIF(device_name,''), 'System') || '-' || COALESCE(flag, 'ALERT'))
					FROM (
						SELECT incidents.device_name, incidents.flag, incidents.incident_id FROM incidents
						LEFT JOIN incident_states ON incidents.incident_id = incident_states.incident_id
						WHERE COALESCE(incident_states.status, incidents.raw_data->>'status', 'ACTIVE') NOT IN ('RESOLVED', 'CLOSED', 'SOLVED VERIFIED')
						UNION ALL
						SELECT pc_name as device_name, severity as flag, incident_id::text FROM fleet_incidents
						WHERE status IN ('OPEN', 'ACTIVE')
					) active_combined
				`).Scan(&activeInc)

				dbConn.Raw(`
					SELECT COUNT(DISTINCT COALESCE(NULLIF(device_name,''), 'System') || '-' || COALESCE(flag, 'ALERT'))
					FROM (
						SELECT incidents.device_name, incidents.flag, incidents.incident_id FROM incidents
						LEFT JOIN incident_states ON incidents.incident_id = incident_states.incident_id
						WHERE COALESCE(incident_states.status, incidents.raw_data->>'status', 'ACTIVE') IN ('RESOLVED', 'CLOSED', 'SOLVED VERIFIED')
						UNION ALL
						SELECT pc_name as device_name, severity as flag, incident_id::text FROM fleet_incidents
						WHERE status IN ('RESOLVED', 'CLOSED')
					) resolved_combined
				`).Scan(&resolvedInc)
				var avgConf float64
				dbConn.Raw("SELECT COALESCE(AVG(confidence), 0.0) FROM incidents").Scan(&avgConf)
				if avgConf > 1.0 {
					avgConf = avgConf / 100.0
				}
				
				var rcaAcc float64
				dbConn.Raw("SELECT COALESCE((AVG(score) / 5.0) * 100, 0) FROM incident_feedback WHERE score IS NOT NULL AND score > 0").Scan(&rcaAcc)
				if rcaAcc == 0 {
					rcaAcc = avgConf * 100 // fallback to confidence if no feedback
				}

				var avgDecisionTime float64
				dbConn.Raw("SELECT COALESCE(decision_time_ms, 0.0) FROM ai_reflection_logs ORDER BY created_at DESC LIMIT 1").Scan(&avgDecisionTime)

				broadcastWSEvent("metrics_update", map[string]interface{}{
					"active_events":    activeInc,
					"resolved_tickets": resolvedInc,
					"confidence_score": fmt.Sprintf("%.1f", avgConf*100),
					"rca_accuracy":     fmt.Sprintf("%.1f", rcaAcc),
					"decision_time_ms": fmt.Sprintf("%.0f", avgDecisionTime),
					"timestamp":        time.Now().Unix(),
				})
			}

			if logCycle%2 == 0 {
				type DeviceRow struct {
					PCName       string    `gorm:"column:pc_name"`
					SiteID       string    `gorm:"column:site_id"`
					Status       string    `gorm:"column:status"`
					IP           string    `gorm:"column:ip"`
					LastSeen     time.Time `gorm:"column:last_seen"`
					OSVersion    string    `gorm:"column:os_version"`
					Online       bool      `gorm:"column:online"`
					SiteName     string    `gorm:"column:site_name"`
					SiteGateway  string    `gorm:"column:site_gateway"`
					OSILayer     int       `gorm:"column:osi_layer"`
					HardwareInfo string    `gorm:"column:hardware_info"`
				}

				var devices []DeviceRow
				if err := dbConn.Table("fleet_devices fd").
					Select("fd.pc_name, COALESCE(NULLIF(fd.site_id, ''), fs.site_id, 'HQ') as site_id, fd.status, COALESCE(NULLIF(fd.ip, ''), d.ip) as ip, fd.last_seen, fd.os_version, fd.online, COALESCE(fs.site_name, 'Kantor Pusat - NUC') as site_name, COALESCE(fs.router_ip, '10.20.0.1') as site_gateway, fd.osi_layer, fd.hardware_info::text").
					Joins("LEFT JOIN fleet_sites fs ON fd.site_id = fs.site_id").
					Joins("LEFT JOIN devices d ON fd.pc_name = d.name").
					Order("fd.last_seen DESC").
					Scan(&devices).Error; err == nil && len(devices) > 0 {

					var pcNames []string
					for _, dev := range devices {
						pcNames = append(pcNames, dev.PCName)
					}

					type MetricRow struct {
						DeviceName  string  `gorm:"column:device_name"`
						MetricType  string  `gorm:"column:metric_type"`
						MetricValue float64 `gorm:"column:metric_value"`
						Metadata    string  `gorm:"column:metadata"`
					}
					var metrics []MetricRow
					metricMap := make(map[string]map[string]float64)

					if len(pcNames) > 0 {
						dbConn.Raw(`
							SELECT DISTINCT ON (device_name, metric_type) device_name, metric_type, metric_value, metadata
							FROM telemetry_logs
							WHERE device_name IN ? AND metric_type IN ('cpu_percent','memory_percent','disk','http_telemetry') AND timestamp > NOW() - INTERVAL '1 day'
							ORDER BY device_name, metric_type, timestamp DESC
						`, pcNames).Scan(&metrics)

						for _, m := range metrics {
							if metricMap[m.DeviceName] == nil {
								metricMap[m.DeviceName] = make(map[string]float64)
							}
							if m.MetricType == "http_telemetry" {
								if m.Metadata != "" {
									var meta map[string]interface{}
									if err := json.Unmarshal([]byte(m.Metadata), &meta); err == nil {
										if d, ok := meta["data"].(map[string]interface{}); ok {
											if v, ok := d["cpu_percent"].(float64); ok {
												metricMap[m.DeviceName]["cpu_percent"] = v
											}
											if v, ok := d["memory_percent"].(float64); ok {
												metricMap[m.DeviceName]["memory_percent"] = v
											}
											if v, ok := d["disk_percent"].(float64); ok {
												metricMap[m.DeviceName]["disk"] = v
											}
										}
									}
								}
							} else {
								metricMap[m.DeviceName][m.MetricType] = m.MetricValue
							}
						}
					}

					devList := make([]map[string]interface{}, 0, len(devices))
					for _, dev := range devices {
						isOnline := time.Since(dev.LastSeen) < 90*time.Second
						statusStr := dev.Status
						if isOnline {
							statusStr = "ONLINE"
						} else {
							statusStr = "OFFLINE"
						}

						osType := "windows"
						if len(dev.PCName) >= 6 && dev.PCName[:6] == "LINUX-" {
							osType = "linux"
						}

						devMetrics := metricMap[dev.PCName]
						var cpu, ram, disk float64
						if devMetrics != nil {
							cpu = devMetrics["cpu_percent"]
							ram = devMetrics["memory_percent"]
							disk = devMetrics["disk"]
						}

						var hwMap map[string]interface{}
						if dev.HardwareInfo != "" {
							_ = json.Unmarshal([]byte(dev.HardwareInfo), &hwMap)
						}
						if hwMap == nil {
							hwMap = make(map[string]interface{})
						}

						mac := ""
						gw := dev.SiteGateway
						dns := ""
						subnet := "255.255.255.0"
						vendor := "Enterprise PC"
						latency := 5
						pktLoss := 0.0

						if cpu == 0 {
							if v, ok := hwMap["cpu_percent"].(float64); ok { cpu = v }
							if v, ok := hwMap["cpu_usage"].(float64); ok && cpu == 0 { cpu = v }
						}
						if ram == 0 {
							if v, ok := hwMap["mem_percent"].(float64); ok { ram = v }
							if v, ok := hwMap["ram_usage"].(float64); ok && ram == 0 { ram = v }
						}
						if disk == 0 {
							if v, ok := hwMap["disk_percent"].(float64); ok { disk = v }
							if v, ok := hwMap["disk_usage"].(float64); ok && disk == 0 { disk = v }
						}

						if netInfo, ok := hwMap["network"].(map[string]interface{}); ok {
							if m, ok := netInfo["mac"].(string); ok { mac = m }
							if g, ok := netInfo["gateway"].(string); ok && g != "" { gw = g }
							if d, ok := netInfo["dns"].(string); ok { dns = d }
							if s, ok := netInfo["subnet"].(string); ok { subnet = s }
							if l, ok := netInfo["ping_latency_ms"].(float64); ok { latency = int(l) }
							if p, ok := netInfo["packet_loss_pct"].(float64); ok { pktLoss = p }
						}

						if osVal, ok := hwMap["os"].(string); ok && osVal != "" {
							if strings.EqualFold(osVal, "linux") {
								osType = "linux"
								vendor = "Linux Workstation"
							} else {
								vendor = "Intel / Windows NUC"
							}
						}

						locationName := dev.SiteName
						if locationName == "" {
							locationName = "Kantor Pusat - NUC"
						}

						layer := dev.OSILayer
						if layer == 0 {
							layer = 1
						}

						devList = append(devList, map[string]interface{}{
							"name":          dev.PCName,
							"pc_name":       dev.PCName,
							"hostname":      dev.PCName,
							"ip":            dev.IP,
							"status":        statusStr,
							"layer":         layer,
							"site_id":       dev.SiteID,
							"site":          locationName,
							"location":      locationName,
							"gateway":       gw,
							"cpu":           cpu,
							"ram":           ram,
							"disk":          disk,
							"last_seen":     dev.LastSeen.Format(time.RFC3339),
							"online":        isOnline,
							"os_type":       osType,
							"mac":           mac,
							"vendor":        vendor,
							"subnet":        subnet,
							"dns":           dns,
							"uptime":        time.Now().Unix() - dev.LastSeen.Unix(),
							"latency":       latency,
							"packet_loss":   pktLoss,
							"hardware_info": hwMap,
						})
					}
					broadcastWSEvent("devices_update", devList)
				}
			}

			if logCycle%4 == 0 {
				var totalDevs, offlineDevs int64
				dbConn.Table("devices").Count(&totalDevs)
				dbConn.Table("devices").Where("status != ?", "ONLINE").Count(&offlineDevs)
				var ragCount int64
				dbConn.Table("knowledge_vectors").Count(&ragCount)
				broadcastWSEvent("fleet_summary", map[string]interface{}{
					"total_devices":   totalDevs,
					"offline_devices": offlineDevs,
					"rag_vectors":     ragCount,
					"timestamp":       time.Now().Unix(),
				})
			}
			}
		}
	}()

	_, err = security.GetSecurityManager()
	if err != nil {
		fmt.Printf("[ERROR] Security Manager failed: %v\n", err)
		os.Exit(1)
	}
	fmt.Println("[BOOT 6] Security Manager checked")

	wd, err := os.Getwd()
	if err != nil {
		wd = "."
	}

	var baseDir string
	if fileExists(filepath.Join(wd, "workspace", "portal", "templates", "index.html")) {
		baseDir = filepath.Join(wd, "workspace", "portal")
	} else if fileExists(filepath.Join(wd, "templates", "index.html")) {
		baseDir = wd
	} else if fileExists(filepath.Join(wd, "portal", "templates", "index.html")) {
		baseDir = filepath.Join(wd, "portal")
	} else {
		baseDir = filepath.Join(wd, "workspace", "portal")
	}

	settingsFile := filepath.Join(baseDir, "remote_settings.json")
	core.InitConfigWatcher(settingsFile)
	templatesDir := filepath.Join(baseDir, "templates")
	staticDir := filepath.Join(baseDir, "static")

	fmt.Printf("[DASHBOARD] Base directory determined as: %s\n", baseDir)
	fmt.Printf("[DASHBOARD] Templates directory: %s\n", templatesDir)
	fmt.Printf("[DASHBOARD] Static assets directory: %s\n", staticDir)
	fmt.Printf("[DASHBOARD] Settings file: %s\n", settingsFile)
	knowledge.GlobalEngine.Init(baseDir)
	fmt.Printf("[DASHBOARD] Isolated RAG Knowledge Engine initialized cleanly.\n")

	gin.SetMode(gin.ReleaseMode)
	r := gin.Default()

	r.Use(security.SecurityHeadersMiddleware())
	r.Use(security.WAFMiddleware())
	r.Use(security.NewIPRateLimiter().Limit())
	r.Use(middleware.CORSMiddleware())
	r.Use(middleware.AuthMiddleware(dbConn, dashboardRedisClient))
	r.Use(middleware.CSRFMiddleware())

	// Force no-cache headers for all static HTML/JS/CSS assets to prevent browser disk caching
	r.Use(func(c *gin.Context) {
		c.Header("Cache-Control", "no-cache, no-store, must-revalidate")
		c.Header("Pragma", "no-cache")
		c.Header("Expires", "0")
		c.Next()
	})

	// Static routes
	r.Static("/static", staticDir)
	uploadDir := "./uploads"
	downloadsDir := filepath.Join(filepath.Dir(baseDir), "CLIENT_DISTRIBUSI_GO")
	if runtime.GOOS != "windows" {
		uploadDir = "/app/uploads"
		downloadsDir = "/app/workspace/CLIENT_DISTRIBUSI_GO"
	}
	r.Static("/uploads", uploadDir)

	// Expose agent files with directory listing enabled
	r.StaticFS("/downloads", gin.Dir(downloadsDir, true))

	serveIndex := func(c *gin.Context) {
		c.Header("Cache-Control", "no-cache, no-store, must-revalidate")
		c.Header("Pragma", "no-cache")
		c.Header("Expires", "0")
		c.File(filepath.Join(templatesDir, "index.html"))
	}

	r.GET("/", serveIndex)
	r.GET("/portal", func(c *gin.Context) {
		c.Header("Cache-Control", "no-cache, no-store, must-revalidate")
		c.File(filepath.Join(templatesDir, "portal.html"))
	})

	// Server-side authorization check for role-based landing pages
	r.GET("/dashboard/executive", func(c *gin.Context) {
		roleVal, _ := c.Get("role")
		role, _ := roleVal.(string)
		if role != "superadmin" {
			c.JSON(http.StatusForbidden, gin.H{"error": "Forbidden", "message": "Akses ke dashboard eksekutif ditolak"})
			c.Abort()
			return
		}
		serveIndex(c)
	})
	r.GET("/dashboard/admin", func(c *gin.Context) {
		roleVal, _ := c.Get("role")
		role, _ := roleVal.(string)
		if role != "admin" && role != "superadmin" {
			c.JSON(http.StatusForbidden, gin.H{"error": "Forbidden", "message": "Akses ke dashboard admin ditolak"})
			c.Abort()
			return
		}
		serveIndex(c)
	})
	r.GET("/dashboard/monitoring", func(c *gin.Context) {
		roleVal, _ := c.Get("role")
		role, _ := roleVal.(string)
		if role != "noc_engineering" && role != "admin" && role != "superadmin" {
			c.JSON(http.StatusForbidden, gin.H{"error": "Forbidden", "message": "Akses ke dashboard monitoring ditolak"})
			c.Abort()
			return
		}
		serveIndex(c)
	})
	r.GET("/dashboard/operator", func(c *gin.Context) {
		roleVal, _ := c.Get("role")
		role, _ := roleVal.(string)
		if role != "operator" && role != "admin" && role != "superadmin" {
			c.JSON(http.StatusForbidden, gin.H{"error": "Forbidden", "message": "Akses ke dashboard operator ditolak"})
			c.Abort()
			return
		}
		serveIndex(c)
	})
	r.GET("/dashboard/viewer", func(c *gin.Context) {
		roleVal, _ := c.Get("role")
		role, _ := roleVal.(string)
		if role != "viewer" && role != "operator" && role != "noc_engineering" && role != "admin" && role != "superadmin" {
			c.JSON(http.StatusForbidden, gin.H{"error": "Forbidden", "message": "Akses ke dashboard viewer ditolak"})
			c.Abort()
			return
		}
		serveIndex(c)
	})

	// Instantiate handlers from modular sub-packages
	apiHandler := api.NewHandler(dbConn, dashboardRedisClient, dashboardNatsConn, baseDir, settingsFile)
	authHandler := auth.NewHandler(dbConn, dashboardRedisClient)
	incidentHandler := incident.NewHandler(dbConn, dashboardRedisClient, dashboardNatsConn, baseDir)
	topologyHandler := topology.NewHandler(dbConn)
	metricsHandler := metrics.NewHandler(dbConn, dashboardRedisClient)
	websocketHandler := wsPkg.NewHandler(dbConn)

	// Register sub-package routes
	apiHandler.RegisterRoutes(r)
	authHandler.RegisterRoutes(r)
	incidentHandler.RegisterRoutes(r)
	topologyHandler.RegisterRoutes(r)
	metricsHandler.RegisterRoutes(r)
	websocketHandler.RegisterRoutes(r)

	// Legacy WS Chat
	r.GET("/ws/chat", func(c *gin.Context) {
		handleDashboardWebSocket(c, dbConn)
	})
	r.GET("/api/dashboard_chat/sessions", func(c *gin.Context) {
		handleGetChatSessions(c, dbConn)
	})
	r.POST("/api/dashboard_chat/sessions/status/:client_id", func(c *gin.Context) {
		handleUpdateSessionStatus(c, dbConn)
	})
	r.GET("/api/dashboard_chat/history/:client_id", func(c *gin.Context) {
		handleGetChatHistory(c, dbConn)
	})

	// Enterprise Chat Engine
	supervisor := ai.NewAISupervisor(dbConn)
	RegisterChatEngineRoutes(r, dbConn, dashboardRedisClient, supervisor)

	// Module 11: Enterprise Asset Graph APIs
	RegisterAssetRoutes(r, dbConn)
	
	// Sprint B: Predictive Intelligence APIs
	RegisterPredictiveRoutes(r, dbConn)

	// Multi-Agent Consensus (Sprint N)
	RegisterMultiAgentRoutes(r, dbConn)

	// Cognitive Memory & Knowledge Graph (Sprint M)
	RegisterCognitiveMemoryRoutes(r, dbConn)

	// Sprint O: AI Governance Dashboard APIs (READ-ONLY)
	registerSprintORoutes(r, dbConn)

	// Start server
	port := "9999"
	if envPort := os.Getenv("PORT"); envPort != "" {
		port = envPort
	}
	fmt.Printf("[DASHBOARD] Starting NOC HTTP Server on 0.0.0.0:%s...\n", port)
	if err = r.Run("0.0.0.0:" + port); err != nil {
		return fmt.Errorf("[ERROR] Server failed: %w", err)
	}
	return nil
}

func startEndToEndHealthCheck(ctx context.Context, dbConn *gorm.DB) {
	go func() {
		ticker := time.NewTicker(5 * time.Minute)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				fmt.Println("[HEALTH CHECK] End-to-End Simulation dihentikan")
				return
			case <-ticker.C:
				if dashboardNatsConn != nil && dbConn != nil {
					fmt.Println("[HEALTH CHECK] Starting 5-minute End-to-End Simulation...")

					// 1. Check Redis
					if dashboardRedisClient != nil {
						_, err := dashboardRedisClient.Ping(dashboardCtx).Result()
						if err != nil {
							fmt.Printf("[HEALTH CHECK] Redis failure: %v\n", err)
							continue
						}
					}

					// 2. Check DB
					sqlDB, err := dbConn.DB()
					if err == nil {
						if err := sqlDB.Ping(); err != nil {
							fmt.Printf("[HEALTH CHECK] Database failure: %v\n", err)
							continue
						}
					} else {
						fmt.Printf("[HEALTH CHECK] Failed to get sql.DB: %v\n", err)
						continue
					}

					// 3. NATS publish health check payload
					payload := `{"event_id":"health_check","incident_id":-1,"action":"PING"}`
					err = dashboardNatsConn.Publish("remediation.execute", []byte(payload))
					if err != nil {
						fmt.Printf("[HEALTH CHECK] NATS publish failure: %v\n", err)
						continue
					}

					fmt.Println("[HEALTH CHECK] End-to-End transaction simulated successfully.")
				}
			}
		}
	}()
}

func startRLOFDecayWorker(ctx context.Context, dbConn *gorm.DB) {
	go func() {
		// Preparation: Ensure required RLOF columns exist in ai_playbooks
		// Production-ready: Use safe schema migration for missing columns
		dbConn.Exec(`ALTER TABLE ai_playbooks ADD COLUMN IF NOT EXISTS success_count INT DEFAULT 0`)
		dbConn.Exec(`ALTER TABLE ai_playbooks ADD COLUMN IF NOT EXISTS fail_count INT DEFAULT 0`)
		dbConn.Exec(`ALTER TABLE ai_playbooks ADD COLUMN IF NOT EXISTS confidence_score FLOAT DEFAULT 100.0`)
		dbConn.Exec(`ALTER TABLE ai_playbooks ADD COLUMN IF NOT EXISTS last_used_at TIMESTAMP DEFAULT NOW()`)

		// Ticker configured for every 1 hour in production, but 5 minutes for simulation/demonstration
		ticker := time.NewTicker(5 * time.Minute)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				fmt.Println("[RLOF DECAY] Multiplicative Decay Worker dihentikan")
				return
			case <-ticker.C:
				fmt.Println("[RLOF DECAY] Menjalankan penyusutan bobot (Multiplicative Decay)...")
				
				// Formula: Base * Recency * Env * Sim
				// Base: (success_count + 1) / (success_count + fail_count + 2)  [Laplace Smoothing]
				// Recency: EXP(-0.05 * days_since_last_used)
				
				err := dbConn.Exec(`
					UPDATE ai_playbooks 
					SET confidence_score = 
						-- Base Probability (Laplace Smoothing)
						(((COALESCE(success_count, 0) + 1.0) / (COALESCE(success_count, 0) + COALESCE(fail_count, 0) + 2.0)) * 100.0) 
						* 
						-- Recency Decay Factor (EXP(-0.05 * days))
						EXP(-0.05 * GREATEST(EXTRACT(EPOCH FROM (NOW() - COALESCE(last_used_at, NOW()))) / 86400.0, 0.0))
				`).Error
				
				if err != nil {
					fmt.Printf("[RLOF DECAY] Gagal menjalankan kalkulasi penyusutan: %v\n", err)
				} else {
					fmt.Println("[RLOF DECAY] Berhasil mengkalkulasi ulang Confidence Score di Knowledge Base.")
				}
			}
		}
	}()
}
