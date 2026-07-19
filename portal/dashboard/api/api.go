package api

import (
	"context"
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/go-redis/redis/v8"
	"github.com/nats-io/nats.go"
	"gorm.io/gorm"

	"go_incident_analysis/SERVER/go_core/security"
	"go_incident_analysis/portal/dashboard/core"
	"go_incident_analysis/portal/dashboard/middleware"
	"go_incident_analysis/portal/dashboard/websocket"
)

type Handler struct {
	db           *gorm.DB
	rdb          *redis.Client
	natsConn     *nats.Conn
	baseDir      string
	settingsFile string
	aiConfigFile string
}

func NewHandler(db *gorm.DB, rdb *redis.Client, natsConn *nats.Conn, baseDir string, settingsFile string) *Handler {
	aiConfigFile := settingsFile
	// Locate ai_config.json next to remote_settings.json
	if dir := filepath.Dir(settingsFile); dir != "" {
		candidate := filepath.Join(dir, "ai_config.json")
		aiConfigFile = candidate
	}
	return &Handler{
		db:           db,
		rdb:          rdb,
		natsConn:     natsConn,
		baseDir:      baseDir,
		settingsFile: settingsFile,
		aiConfigFile: aiConfigFile,
	}
}

func (h *Handler) RegisterRoutes(r *gin.Engine) {
	r.GET("/health", h.Health)
	r.POST("/api/telemetry", h.Telemetry)
	r.POST("/api/activity", h.Activity)
	r.POST("/api/issues", h.Issues)
	r.POST("/api/browser-events", h.BrowserEvents)
	r.GET("/api/activity-log", h.ActivityLog)
	r.GET("/api/remote/settings", h.GetSettings)
	r.POST("/api/remote/settings/save", h.SaveSettings)
	r.GET("/api/remote/detect", h.DetectRemoteTool)
	r.GET("/api/launcher/status", h.GetLauncherStatus)
	r.POST("/api/launcher/start", h.StartLauncherService)
	r.GET("/api/system/health", h.GetSystemHealth)
	r.GET("/api/system/runtime_monitor", h.GetRuntimeMonitor)

	// ── NEW: Missing endpoints from frontend audit ──
	r.GET("/api/storage/stats", h.GetStorageStats)
	r.GET("/api/system/queues", h.GetSystemQueues)
	r.GET("/api/ai/stats", h.GetAIStats)
	r.GET("/api/ai_status", h.GetAIStatus)
	r.GET("/api/ai_config", h.GetAIConfig)
	r.POST("/api/ai_config", h.SaveAIConfig)
	r.GET("/api/feedback", h.GetFeedback)
	r.POST("/api/feedback", h.SubmitFeedback)
	r.GET("/api/feedback/stats", h.GetFeedbackStats)
	r.GET("/api/system/audits", h.GetSystemAudits)
	r.GET("/api/governance/sops", h.GetSOPs)
	r.POST("/api/governance/sops/create", h.CreateSOP)
	r.POST("/api/governance/sops/promote", h.PromoteSOP)
	r.POST("/api/governance/sops/delete", h.DeleteSOP)
	r.POST("/api/governance/sops/execute", h.ExecuteSOP)
	r.GET("/api/host_metrics", h.GetHostMetrics)
	r.GET("/api/ping_sites", h.PingSites)
	r.POST("/api/orchestrator/command", h.OrchestratorCommand)
	r.POST("/api/remote/test/:tool", h.TestRemoteTool) // Fix: Frontend uses POST, not GET
	r.POST("/api/remote/routes/sync", h.SyncRemoteRoutes)
	r.GET("/api/agent_deep_diagnostics/:device", h.GetAgentDeepDiagnostics)
	r.GET("/api/kb_stats", h.GetKBStats)
	r.GET("/api/governance/top_resolutions", h.GetTopResolutions)
	r.GET("/api/governance/sla_compliance", h.GetSLACompliance)
	r.GET("/api/dashboard_chat/device_context/:client_id", h.GetChatDeviceContext)
	r.GET("/api/fleet/admin/printers", h.GetPrinters)
	r.POST("/api/fleet/admin/printers", h.CreatePrinter)
	r.DELETE("/api/fleet/admin/printers/:name", h.DeletePrinter)
	r.PUT("/api/printers/:id", h.UpdatePrinter)
	r.DELETE("/api/printers/:id", h.DeletePrinterByID)
	r.GET("/api/printers/live", h.GetPrintersLive)
	r.POST("/api/printers/ping/:ip", h.PingPrinter)
	r.POST("/api/printers/ping_all", h.PingAllPrinters)
	r.POST("/api/printers/clear_queue", h.ClearPrinterQueue)
	r.POST("/api/printers/update_metrics", h.UpdatePrinterMetrics)
	r.GET("/api/rca/trace/:id", h.GetDecisionTrace)
	r.GET("/api/rca/analyze/:id", h.AnalyzeRCA)
	r.GET("/api/event_correlation", h.GetEventCorrelation)
	r.POST("/api/rca/reanalyze/:id", h.ReanalyzeRCA)
	r.POST("/api/offline/diagnose", h.OfflineDiagnose)
	r.POST("/api/dashboard_chat/send", h.SendChatMessage)
	// Missing Fleet & Chat Endpoints
	r.POST("/api/fleet/admin/devices/save", h.SaveDevice)
	r.GET("/api/dashboard_chat/suggest", h.ChatSuggest)
	r.POST("/api/dashboard_chat/sessions/:client_id/status", h.UpdateChatSessionStatus)
	r.GET("/api/fleet/update/manifest", h.GetUpdateManifest)
	r.GET("/api/server/time", h.GetServerTime)

	// ── AI File System (Storage Panel) ──
	r.GET("/api/ai_file/read", h.GetAIFile)
	r.GET("/api/ai_file/download", h.DownloadAIFile)
	r.POST("/api/ai_file/save", h.SaveAIFile)
	r.GET("/api/ai_file/validate", h.ValidateAIFile)

}


func (h *Handler) Health(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status":    "UP",
		"timestamp": time.Now().Format(time.RFC3339),
		"service":   "OSI AI Go Dashboard",
	})
}

func (h *Handler) GetServerTime(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status":    "SUCCESS",
		"timestamp": time.Now().UnixMilli(),
		"rfc3339":   time.Now().Format(time.RFC3339),
	})
}


func (h *Handler) Telemetry(c *gin.Context) {
	var payload map[string]interface{}
	if err := c.ShouldBindJSON(&payload); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": err.Error()})
		return
	}
	pcName, _ := payload["pc_name"].(string)
	if pcName == "" {
		pcName, _ = payload["agent_id"].(string)
	}
	if pcName == "" {
		pcName = "unknown-device"
	}
	metaBytes, _ := json.Marshal(payload)
	
	// Ensure the device is marked as ONLINE in fleet_devices
	h.db.Exec(`
		INSERT INTO fleet_devices (pc_name, status, last_seen)
		VALUES (?, 'ONLINE', CURRENT_TIMESTAMP)
		ON CONFLICT (pc_name) DO UPDATE SET
			status = 'ONLINE',
			last_seen = CURRENT_TIMESTAMP
	`, pcName)

	h.db.Exec(`
		INSERT INTO telemetry_logs (device_name, metric_type, metric_value, metadata, tenant_id)
		VALUES (?, 'telemetry_bundle', 1.0, ?, 'default_tenant')
	`, pcName, string(metaBytes))
	
	websocket.BroadcastWSEvent("live_telemetry", map[string]interface{}{
		"device": pcName,
		"type":   "telemetry",
		"data":   payload,
	})

	if h.rdb != nil {
		h.rdb.Del(c.Request.Context(), "cache:incidents", "cache:last_telemetry")
	}

	c.JSON(http.StatusOK, gin.H{"status": "SUCCESS"})
}

func (h *Handler) Activity(c *gin.Context) {
	var payload map[string]interface{}
	if err := c.ShouldBindJSON(&payload); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": err.Error()})
		return
	}
	pcName, _ := payload["pc_name"].(string)
	if pcName == "" {
		pcName, _ = payload["agent_id"].(string)
	}
	if pcName == "" {
		pcName = "unknown-device"
	}
	metaBytes, _ := json.Marshal(payload)
	h.db.Exec(`
		INSERT INTO telemetry_logs (device_name, metric_type, metric_value, metadata, tenant_id)
		VALUES (?, 'active_app', 1.0, ?, 'default_tenant')
	`, pcName, string(metaBytes))
	
	websocket.BroadcastWSEvent("live_telemetry", map[string]interface{}{
		"device": pcName,
		"type":   "activity",
		"data":   payload,
	})

	if h.rdb != nil {
		h.rdb.Del(c.Request.Context(), "cache:incidents", "cache:last_telemetry")
	}

	c.JSON(http.StatusOK, gin.H{"status": "SUCCESS"})
}

func (h *Handler) Issues(c *gin.Context) {
	var payload map[string]interface{}
	if err := c.ShouldBindJSON(&payload); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": err.Error()})
		return
	}
	pcName, _ := payload["pc_name"].(string)
	if pcName == "" {
		pcName, _ = payload["agent_id"].(string)
	}
	if pcName == "" {
		pcName = "unknown-device"
	}
	severity, _ := payload["severity"].(string)
	if severity == "" {
		severity = "medium"
	}
	details, _ := payload["details"].(string)
	if details == "" {
		details, _ = payload["issue"].(string)
	}
	if strings.ToUpper(severity) == "HIGH" || strings.ToUpper(severity) == "CRITICAL" {
		h.db.Exec(`
			INSERT INTO fleet_incidents (site_id, pc_name, severity, status, description)
			VALUES (NULL, ?, ?, 'OPEN', ?)
		`, pcName, strings.ToUpper(severity), details)
	}
	metaBytes, _ := json.Marshal(payload)
	h.db.Exec(`
		INSERT INTO telemetry_logs (device_name, metric_type, metric_value, metadata, tenant_id)
		VALUES (?, 'browser_issue', 1.0, ?, 'default_tenant')
	`, pcName, string(metaBytes))
	
	websocket.BroadcastWSEvent("live_telemetry", map[string]interface{}{
		"device": pcName,
		"type":   "issue",
		"data":   payload,
	})

	if h.rdb != nil {
		h.rdb.Del(c.Request.Context(), "cache:incidents", "cache:last_telemetry")
	}

	c.JSON(http.StatusOK, gin.H{"status": "SUCCESS"})
}

func (h *Handler) BrowserEvents(c *gin.Context) {
	var payload map[string]interface{}
	if err := c.ShouldBindJSON(&payload); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": err.Error()})
		return
	}
	pcName, _ := payload["pc_name"].(string)
	if pcName == "" {
		pcName, _ = payload["agent_id"].(string)
	}
	if pcName == "" {
		pcName = "unknown-device"
	}
	issues := []string{}
	loadTime, _ := payload["load_time_ms"].(float64)
	if loadTime > 3000 {
		issues = append(issues, "SLOW_PAGE")
	}
	crash, _ := payload["crash"].(bool)
	tabState, _ := payload["tab_state"].(string)
	if crash || tabState == "crash" {
		issues = append(issues, "TAB_CRASH")
	}
	latency, _ := payload["latency_ms"].(float64)
	if latency > 1000 {
		issues = append(issues, "HIGH_LATENCY")
	}
	dnsFailure, _ := payload["dns_failure"].(bool)
	if dnsFailure {
		issues = append(issues, "DNS_FAILURE")
	}
	if len(issues) > 0 {
		payload["issues"] = issues
	}
	metaBytes, _ := json.Marshal(payload)
	h.db.Exec(`
		INSERT INTO telemetry_logs (device_name, metric_type, metric_value, metadata, tenant_id)
		VALUES (?, 'web_activity', ?, ?, 'default_tenant')
	`, pcName, loadTime, string(metaBytes))
	
	websocket.BroadcastWSEvent("live_telemetry", map[string]interface{}{
		"device": pcName,
		"type":   "web_activity",
		"data":   payload,
	})
	c.JSON(http.StatusOK, gin.H{"status": "SUCCESS"})
}

func (h *Handler) ActivityLog(c *gin.Context) {
	type LogRow struct {
		LogID      int64     `gorm:"column:log_id"`
		DeviceName string    `gorm:"column:device_name"`
		MetricType string    `gorm:"column:metric_type"`
		MetricVal  float64   `gorm:"column:metric_value"`
		Timestamp  time.Time `gorm:"column:timestamp"`
		Metadata   string    `gorm:"column:metadata"`
	}

	if h.rdb != nil {
		if cachedVal, err := h.rdb.Get(c.Request.Context(), "cache:last_telemetry").Result(); err == nil && cachedVal != "" {
			var cachedResp map[string]interface{}
			if errJson := json.Unmarshal([]byte(cachedVal), &cachedResp); errJson == nil {
				c.JSON(http.StatusOK, cachedResp)
				return
			}
		}
	}

	var activities []LogRow
	var webEvents []LogRow
	var issues []LogRow

	h.db.Raw(`
		SELECT log_id, device_name, metric_type, metric_value, timestamp, metadata::text
		FROM telemetry_logs
		WHERE metric_type = 'active_app'
		ORDER BY log_id DESC LIMIT 50
	`).Scan(&activities)

	h.db.Raw(`
		SELECT log_id, device_name, metric_type, metric_value, timestamp, metadata::text
		FROM telemetry_logs
		WHERE metric_type = 'web_activity'
		ORDER BY log_id DESC LIMIT 50
	`).Scan(&webEvents)

	h.db.Raw(`
		SELECT log_id, device_name, metric_type, metric_value, timestamp, metadata
		FROM (
			SELECT log_id, device_name, metric_type, metric_value, timestamp, metadata::text
			FROM telemetry_logs
			WHERE metric_type = 'browser_issue'
			UNION ALL
			SELECT incident_id AS log_id, COALESCE(pc_name, 'UNKNOWN') AS device_name, 'fleet_incident' AS metric_type, 1.0 AS metric_value, created_at AS timestamp,
			       json_build_object('type', 'WATCHDOG_ALERT', 'severity', LOWER(severity), 'details', description, 'pc_name', pc_name, 'source', 'Fleet Incident')::text AS metadata
			FROM fleet_incidents
		) combined
		ORDER BY timestamp DESC LIMIT 50
	`).Scan(&issues)

	toItems := func(rows []LogRow) []map[string]interface{} {
		result := make([]map[string]interface{}, 0, len(rows))
		for _, r := range rows {
			var meta map[string]interface{}
			_ = json.Unmarshal([]byte(r.Metadata), &meta)
			result = append(result, map[string]interface{}{
				"log_id":       r.LogID,
				"device":       r.DeviceName,
				"metric_type":  r.MetricType,
				"metric_value": r.MetricVal,
				"timestamp":    r.Timestamp.Format("15:04:05"),
				"data":         meta,
			})
		}
		return result
	}

	respPayload := gin.H{
		"activities": toItems(activities),
		"web_events": toItems(webEvents),
		"issues":     toItems(issues),
	}

	if h.rdb != nil {
		if bytesVal, errJson := json.Marshal(respPayload); errJson == nil {
			h.rdb.Set(c.Request.Context(), "cache:last_telemetry", string(bytesVal), 30*time.Second)
		}
	}

	c.JSON(http.StatusOK, respPayload)
}

func (h *Handler) GetSettings(c *gin.Context) {
	settings := core.GetGlobalSettings()
	if settings.Passwords != nil {
		for k := range settings.Passwords {
			settings.Passwords[k] = "********"
		}
	}
	c.JSON(http.StatusOK, settings)
}

func (h *Handler) SaveSettings(c *gin.Context) {
	roleVal, _ := c.Get("role")
	role, _ := roleVal.(string)
	if !middleware.CheckPermission(h.db, role, "access_config") {
		c.JSON(http.StatusForbidden, gin.H{"error": "Forbidden", "message": "Role does not have permission: access_config"})
		return
	}
	var incoming core.RemoteSettings
	if err := c.ShouldBindJSON(&incoming); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid payload format"})
		return
	}

	current := core.GetGlobalSettings()
	if incoming.General != nil {
		current.General = incoming.General
	}
	if incoming.AnyDesk != nil {
		current.AnyDesk = incoming.AnyDesk
	}
	if incoming.RustDesk != nil {
		current.RustDesk = incoming.RustDesk
	}
	if incoming.VNC != nil {
		current.VNC = incoming.VNC
	}

	sm, err := security.GetSecurityManager()
	if incoming.Passwords != nil && err == nil {
		if current.Passwords == nil {
			current.Passwords = make(map[string]string)
		}
		for pkey, pval := range incoming.Passwords {
			if pval != "" {
				if strings.HasPrefix(pval, "gAAAAAB") {
					current.Passwords[pkey] = pval
				} else {
					enc, errEnc := sm.Encrypt(pval)
					if errEnc == nil {
						current.Passwords[pkey] = enc
					}
				}
			}
		}
	}

	err = core.SaveSettings(h.settingsFile, current)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	core.ReloadSettings()

	defaultTool, exists := current.General["defaultTool"].(string)
	if !exists {
		defaultTool = "rustdesk"
	}

	h.db.Exec("UPDATE fleet_sites SET default_remote_tool = ?", defaultTool)
	_ = core.WriteAuditLog(h.db, "SETTINGS_MUTATION", "admin", "remote_settings", incoming)

	c.JSON(http.StatusOK, gin.H{"status": "SUCCESS", "ok": true})
}

func (h *Handler) DetectRemoteTool(c *gin.Context) {
	tool := c.Query("tool")
	if tool == "" {
		tool = "all"
	}

	client := &http.Client{Timeout: 1500 * time.Millisecond}
	resp, err := client.Post(core.GetLauncherURL("/detect"), "application/json", nil)
	if err == nil && resp.StatusCode == 200 {
		defer resp.Body.Close()
		var lResult map[string]interface{}
		if json.NewDecoder(resp.Body).Decode(&lResult) == nil {
			if tool == "all" {
				c.JSON(http.StatusOK, lResult)
				return
			}
			if toolDetails, ok := lResult[tool].(map[string]interface{}); ok {
				if installed, _ := toolDetails["installed"].(bool); installed {
					c.JSON(http.StatusOK, gin.H{
						"found": true,
						"path":  toolDetails["exe_path"],
					})
					return
				}
			} else if tool == "vnc" {
				if vncDetails, ok := lResult["vnc"].(map[string]interface{}); ok {
					for _, detailsVal := range vncDetails {
						if details, ok := detailsVal.(map[string]interface{}); ok {
							if inst, _ := details["installed"].(bool); inst {
								c.JSON(http.StatusOK, gin.H{
									"found": true,
									"path":  details["exe_path"],
								})
								return
							}
						}
					}
				}
			}
		}
	}

	c.JSON(http.StatusOK, gin.H{"found": false})
}

func (h *Handler) GetLauncherStatus(c *gin.Context) {
	url := core.GetLauncherURL("/health")
	client := &http.Client{Timeout: 2 * time.Second}
	resp, err := client.Get(url)
	if err == nil && resp.StatusCode == 200 {
		resp.Body.Close()
		c.JSON(http.StatusOK, gin.H{"status": "online", "running": true})
		return
	}
	c.JSON(http.StatusOK, gin.H{"status": "offline", "running": false})
}

func (h *Handler) StartLauncherService(c *gin.Context) {
	roleVal, _ := c.Get("role")
	role, _ := roleVal.(string)
	if !middleware.CheckPermission(h.db, role, "access_config") {
		c.JSON(http.StatusForbidden, gin.H{"error": "Forbidden", "message": "Role does not have permission: access_config"})
		return
	}
	var launcherDir string
	var launcherExe string

	if runtime.GOOS == "windows" {
		launcherDir = filepath.Clean(filepath.Join(h.baseDir, "..", "release_binaries", "windows_amd64"))
		launcherExe = filepath.Join(launcherDir, "launcher.exe")
	} else {
		launcherDir = filepath.Clean(filepath.Join(h.baseDir, "..", "release_binaries", "linux_amd64"))
		launcherExe = filepath.Join(launcherDir, "launcher")
	}

	if !core.FileExists(launcherExe) {
		c.JSON(http.StatusNotFound, gin.H{"status": "error", "message": fmt.Sprintf("Launcher binary not found at %s", launcherExe)})
		return
	}

	cmd := exec.Command(launcherExe)
	cmd.Dir = launcherDir
	SetSysProcAttr(cmd)

	err := cmd.Start()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"status": "error", "message": err.Error()})
		return
	}

	websocket.AddInternalLog("INFO", "LAUNCHER", "Initiated Launcher Service local auto-start")
	c.JSON(http.StatusOK, gin.H{"status": "starting", "message": "Launcher service started"})
}

func (h *Handler) GetSystemHealth(c *gin.Context) {
	var audit core.SystemAudit
	err := h.db.Order("timestamp DESC").First(&audit).Error
	if err == nil {
		var comps map[string]interface{}
		_ = json.Unmarshal([]byte(audit.RawJSON), &comps)
		if len(comps) == 0 {
			// BUG-05 fix: if stored components empty, add live checks
			comps = h.liveComponentCheck()
		}
		c.JSON(http.StatusOK, gin.H{
			"health_score":      audit.HealthScore,
			"status":            audit.Status,
			"failed_components": audit.FailedComponents,
			"root_cause":        audit.RootCause,
			"confidence":        audit.Confidence,
			"recommendation":    audit.Recommendation,
			"components":        comps,
			"duration_ms":       audit.AuditDurationMs,
			"timestamp":         audit.Timestamp.Format(time.RFC3339),
			"auditor_version":   "v2.2",
		})
		return
	}
	// BUG-01 fix: no audit record yet — compute live health score
	comps := h.liveComponentCheck()
	healthScore := 0
	okCount := 0
	total := len(comps)
	for _, v := range comps {
		if m, ok := v.(gin.H); ok {
			if m["status"] == "OK" {
				okCount++
			}
		}
	}
	if total > 0 {
		healthScore = (okCount * 100) / total
	}
	status := "HEALTHY"
	if healthScore < 80 {
		status = "DEGRADED"
	}
	if healthScore < 50 {
		status = "CRITICAL"
	}
	c.JSON(http.StatusOK, gin.H{
		"health_score":      healthScore,
		"status":            status,
		"failed_components": "",
		"components":        comps,
		"auditor_version":   "v2.2",
		"timestamp":         time.Now().Format(time.RFC3339),
	})
}

// liveComponentCheck performs real-time health checks for all pipeline components.
// BUG-05 fix: replaces fake "always OK" defaults.
func (h *Handler) liveComponentCheck() gin.H {
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()

	check := func(ok bool) gin.H {
		if ok {
			return gin.H{"status": "OK"}
		}
		return gin.H{"status": "ERROR"}
	}
	tcpCheck := func(addr string) bool {
		conn, err := net.DialTimeout("tcp", addr, 1*time.Second)
		if err == nil {
			conn.Close()
			return true
		}
		return false
	}

	// PostgreSQL
	var dbPing int
	dbOk := h.db.WithContext(ctx).Raw("SELECT 1").Scan(&dbPing).Error == nil

	// Redis
	redisOk := false
	if h.rdb != nil {
		redisOk = h.rdb.Ping(ctx).Err() == nil
	}

	// Dashboard (self)
	dashboardOk := true

	// Ingestion (port 18800)
	ingestionOk := tcpCheck("ingestion-server:18800") || tcpCheck("localhost:18800")

	// RAG Engine (check knowledge_vectors count > 0)
	var ragCount int64
	ragOk := false
	if h.db != nil {
		h.db.WithContext(ctx).Table("knowledge_vectors").Count(&ragCount)
		ragOk = ragCount > 0
	}

	// AI API (check ai_config.json and model availability)
	aiOk := false
	var aiCfg map[string]map[string]interface{}
	if data, err := readAIConfigFile(h.aiConfigFile); err == nil {
		aiOk = len(data) > 0
		for _, cfg := range data {
			if en, _ := cfg["enabled"].(bool); en {
				aiOk = true
				break
			}
		}
		aiCfg = data
	}
	_ = aiCfg

	// Hardware (read /proc/stat)
	cpuPct, ramPct, _ := readHostStats()
	hwOk := cpuPct >= 0 && ramPct >= 0

	return gin.H{
		"PostgreSQL": check(dbOk),
		"Redis":      check(redisOk),
		"Dashboard":  check(dashboardOk),
		"Ingestion":  check(ingestionOk),
		"RAG Engine": check(ragOk),
		"AI API":     check(aiOk),
		"Hardware":   check(hwOk),
	}
}

func readAIConfigFile(path string) (map[string]map[string]interface{}, error) {
	var cfg map[string]map[string]interface{}
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	if err := json.Unmarshal(data, &cfg); err != nil {
		return nil, err
	}
	return cfg, nil
}

func (h *Handler) GetRuntimeMonitor(c *gin.Context) {
	var m runtime.MemStats
	runtime.ReadMemStats(&m)

	wsCount := websocket.GetClientCount()

	c.JSON(http.StatusOK, gin.H{
		"timestamp":        time.Now().Format(time.RFC3339),
		"goroutines":       runtime.NumGoroutine(),
		"memory_alloc_mb":  m.Alloc / 1024 / 1024,
		"memory_sys_mb":    m.Sys / 1024 / 1024,
		"gc_cycles":        m.NumGC,
		"ws_clients_count": wsCount,
		"status":           "ONLINE",
	})
}
