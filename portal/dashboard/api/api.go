package api

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
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
	// ProactiveAlertFn is injected from main package (jarvis_api.go TriggerJarvisProactiveAnnounce).
	// Called as a goroutine when new HIGH/CRITICAL incidents are created.
	ProactiveAlertFn func(eventType, severity, title, details, device, incidentID, siteID string, extra map[string]interface{})
}

func NewHandler(db *gorm.DB, rdb *redis.Client, natsConn *nats.Conn, baseDir string, settingsFile string) *Handler {
	aiConfigFile := settingsFile
	// Locate ai_config.json next to remote_settings.json
	if dir := filepath.Dir(settingsFile); dir != "" {
		candidate := filepath.Join(dir, "ai_config.json")
		aiConfigFile = candidate
	}
	h := &Handler{
		db:           db,
		rdb:          rdb,
		natsConn:     natsConn,
		baseDir:      baseDir,
		settingsFile: settingsFile,
		aiConfigFile: aiConfigFile,
	}

	// Start automatic 1-day telemetry data retention & cache cleanup worker
	go h.StartTelemetryRetentionJob()

	return h
}

func (h *Handler) RegisterRoutes(r *gin.Engine) {
	// Serve static files for agent distribution downloads
	r.Static("/05_SIAP_DISTRIBUSI", "./CLIENT_DISTRIBUSI_GO/05_SIAP_DISTRIBUSI")
	r.Static("/CLIENT_DISTRIBUSI_GO", "./CLIENT_DISTRIBUSI_GO")

	r.GET("/health", h.Health)
	r.GET("/api/health", h.Health)
	r.GET("/api/health/services", h.GetSystemHealth)
	r.GET("/api/printers", h.GetPrintersLive)
	r.POST("/api/ai_command", h.AICommand)
	r.POST("/api/admin/cleanup_telemetry", h.CleanupTelemetryData)
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
	r.GET("/api/system/agent_health", h.GetAgentHealth)
	r.GET("/api/ai/stats", h.GetAIStats)
	r.GET("/api/ai_status", h.GetAIStatus)
	r.GET("/api/ai_config", h.GetAIConfig)
	r.POST("/api/ai_config", h.SaveAIConfig)
	r.GET("/api/feedback", h.GetFeedback)
	r.POST("/api/feedback", h.SubmitFeedback)
	r.GET("/api/feedback/stats", h.GetFeedbackStats)
	r.POST("/api/feedback/approve", h.ApproveFeedback)
	r.POST("/api/feedback/reject", h.RejectFeedback)
	r.GET("/api/feedback/export", h.ExportFeedbackHistory)
	r.GET("/api/system/audits", h.GetSystemAudits)
	r.POST("/api/system/audit/run", h.RunSystemAudit)
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
	r.POST("/api/remote/launch", h.RemoteLaunch)
	r.GET("/api/remote/launch", h.RemoteLaunch)
	r.POST("/api/remote/launch/:type", h.RemoteLaunch)
	r.GET("/api/remote/launch/:type", h.RemoteLaunch)
	r.POST("/api/fleet/notify", h.PushNotificationEndpoint)
	r.POST("/api/fleet/push_notification", h.PushNotificationEndpoint)
	r.GET("/api/agent_deep_diagnostics/:device", h.GetAgentDeepDiagnostics)

	// Enterprise Browser Monitoring Endpoints
	r.POST("/api/telemetry/browser_tabs", h.SubmitBrowserTelemetry)
	r.GET("/api/browser_monitoring/live", h.GetLiveBrowserTabs)
	r.GET("/api/browser_monitoring/summary", h.GetBrowserSummary)
	r.GET("/api/browser_monitoring/timeline", h.GetBrowserTimeline)
	r.GET("/api/browser_monitoring/analytics", h.GetBrowserAnalytics)
	r.GET("/api/browser_monitoring/tab_detail/:uuid", h.GetBrowserTabDetail)
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
	r.GET("/api/printers/hardware_discovery", h.GetPrinterHardwareDiscovery)
	r.POST("/api/printers/hardware_diagnostic_test", h.RunPrinterHardwareDiagnosticTest)
	r.GET("/api/fleet/admin/printers/hardware_discovery", h.GetPrinterHardwareDiscovery)
	r.POST("/api/fleet/admin/printers/hardware_diagnostic_test", h.RunPrinterHardwareDiagnosticTest)
	r.POST("/api/printers/ping/:ip", h.PingPrinter)
	r.POST("/api/printers/ping_all", h.PingAllPrinters)
	r.POST("/api/printers/clear_queue", h.ClearPrinterQueue)
	r.POST("/api/printers/update_metrics", h.UpdatePrinterMetrics)
	r.GET("/api/rca/trace/:id", h.GetDecisionTrace)
	r.GET("/api/rca/analyze/:id", h.AnalyzeRCA)
	r.GET("/api/event_correlation", h.GetEventCorrelation)
	r.POST("/api/rca/reanalyze/:id", h.ReanalyzeRCA)
	r.GET("/api/incidents/:incident_id/counterfactual", h.GetCounterfactualSimulation)
	r.GET("/api/incidents/:incident_id/post_mortem", h.GetPostMortemReport)
	r.POST("/api/offline/diagnose", h.OfflineDiagnose)
	r.POST("/api/dashboard_chat/send", h.SendChatMessage)
	// Missing Fleet & Chat Endpoints
	r.POST("/api/fleet/admin/devices/save", h.SaveDevice)
	r.DELETE("/api/fleet/admin/devices/delete/:device", h.DeleteDevice)
	r.POST("/api/fleet/admin/devices/delete/:device", h.DeleteDevice)
	r.DELETE("/api/fleet/admin/devices/:device", h.DeleteDevice)
	r.GET("/api/dashboard_chat/suggest", h.ChatSuggest)
	r.POST("/api/dashboard_chat/sessions/:client_id/status", h.UpdateChatSessionStatus)
	r.GET("/api/fleet/update/manifest", h.GetUpdateManifest)
	r.GET("/api/server/time", h.GetServerTime)
	r.GET("/api/fleet/ota/download", h.DownloadOTABinary)
	r.POST("/api/fleet/ota/trigger", h.TriggerOTAUpdate)
	r.GET("/api/learning_gate_policy", h.GetLearningGatePolicy)
	r.POST("/api/learning_gate_policy/update", h.UpdateLearningGatePolicy)
	r.POST("/api/learning_gate_policy/rollback", h.RollbackLearningGatePolicy)
	r.GET("/api/learning_gate_policy/history", h.GetLearningGateHistory)
	r.POST("/api/fleet/sites/save", h.SaveFleetSite)
	r.DELETE("/api/fleet/sites/delete/:id", h.DeleteSite)
	r.POST("/api/fleet/sites/delete/:id", h.DeleteSite)
	r.DELETE("/api/fleet/admin/sites/:id", h.DeleteSite)
	r.POST("/api/fleet/admin/sites/delete", h.DeleteSite)

	// ── Dedicated Isolated RAG Knowledge Base Pipeline ──────────────────────────
	r.GET("/api/ai/knowledge/list", h.ListKnowledgeBase)
	r.POST("/api/ai/knowledge/search", h.SearchKnowledgeBase)
	r.POST("/api/ai/knowledge/import", h.ImportKnowledgeBase)

	// ── Dedicated n8n Workflow Integration Endpoints ─────────────────────────
	r.POST("/api/n8n/trigger", h.TriggerN8NWorkflow)
	r.POST("/api/n8n/vault_sync", h.TriggerN8NVaultSyncV41)
	r.POST("/api/n8n/publish_postmortem", h.PublishPostMortemV42)
	r.GET("/api/n8n/health", h.GetN8NHealth)

	// ── RBAC Sub-Tabs Endpoints (Superadmin Full Control) ──
	r.POST("/api/rbac/policies/save", h.SaveRBACPolicies)

	r.POST("/api/rbac/users/save", h.SaveRBACUser)
	r.DELETE("/api/rbac/users/delete/:username", h.DeleteRBACUser)

	r.GET("/api/rbac/role_templates", h.GetRoleTemplates)
	r.POST("/api/rbac/role_templates", h.SaveRoleTemplate)
	r.POST("/api/rbac/role_templates/save", h.SaveRoleTemplate)

	r.GET("/api/rbac/overrides", h.GetRBACOverrides)
	r.DELETE("/api/rbac/overrides/:username", h.DeleteRBACOverride)
	r.DELETE("/api/rbac/overrides/delete/:username", h.DeleteRBACOverride)
	r.POST("/api/rbac/session_policies/save", h.SaveSessionPolicy)

	// ── AI File System (Storage Panel) ──
	r.GET("/api/ai_file/read", h.GetAIFile)
	r.GET("/api/ai_file/download", h.DownloadAIFile)
	r.POST("/api/ai_file/save", h.SaveAIFile)
	r.GET("/api/ai_file/validate", h.ValidateAIFile)

	// Missing Enterprise UI & Audit Endpoints
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

// processRAMTelemetry evaluates RAM usage, applies 15-minute deduplication cooldown, auto-resolves when recovered.
func (h *Handler) processRAMTelemetry(pcName string, ramVal float64) {
	if ramVal <= 0 {
		return
	}

	// 1. Recovery Check: If RAM drops below 75%, auto-resolve any open HIGH_RAM incident
	if ramVal < 75.0 {
		var openCount int64
		h.db.Raw(`
			SELECT COUNT(*) FROM fleet_incidents 
			WHERE LOWER(pc_name) = LOWER(?) AND status = 'OPEN' AND (description LIKE '%RAM%' OR description LIKE '%Memory%')
		`, pcName).Scan(&openCount)

		if openCount > 0 {
			h.db.Exec(`
				UPDATE fleet_incidents 
				SET status = 'RESOLVED', resolved_at = CURRENT_TIMESTAMP
				WHERE LOWER(pc_name) = LOWER(?) AND status = 'OPEN' AND (description LIKE '%RAM%' OR description LIKE '%Memory%')
			`, pcName)

			websocket.BroadcastWSEvent("live_telemetry", map[string]interface{}{
				"device": pcName,
				"type":   "issue_recovered",
				"data": map[string]interface{}{
					"pc_name":     pcName,
					"issue":       "HIGH_RAM",
					"status":      "RECOVERED",
					"ram":         ramVal,
					"description": fmt.Sprintf("RAM Usage normal kembali (%.1f%%)", ramVal),
				},
			})
		}
		return
	}

	// 2. High RAM Threshold Check (>= 85.0%)
	if ramVal >= 85.0 {
		severity := "HIGH"
		if ramVal >= 92.0 {
			severity = "CRITICAL"
		}
		desc := fmt.Sprintf("Penggunaan RAM tinggi terdeteksi: %.1f%% pada %s", ramVal, pcName)

		// Check for an existing OPEN incident within the last 15 minutes (900s cooldown)
		var existingID int64
		h.db.Raw(`
			SELECT incident_id FROM fleet_incidents
			WHERE LOWER(pc_name) = LOWER(?) 
			  AND status = 'OPEN' 
			  AND (description LIKE '%RAM%' OR description LIKE '%Memory%')
			  AND created_at >= NOW() - INTERVAL '15 minutes'
			LIMIT 1
		`, pcName).Scan(&existingID)

		// ⚡ JARVIS Proactive Alert Voice: trigger proactive announcement (Python cooldown will filter repeat spam)
		log.Printf("[JARVIS-PROACTIVE-GO] Triggering proactive RAM alert for %s (sev=%s, ram=%.1f%%)", pcName, severity, ramVal)
		if h.ProactiveAlertFn != nil {
			go h.ProactiveAlertFn(
				"incident_new", severity,
				fmt.Sprintf("Insiden %s Terdeteksi di %s", severity, pcName),
				desc, pcName, "", "",
				map[string]interface{}{"ram_percent": ramVal, "metric_type": "RAM"},
			)
		}

		if existingID > 0 {
			// Cooldown active: DEDUP & update description with latest timestamp
			h.db.Exec(`
				UPDATE fleet_incidents 
				SET description = ?, created_at = CURRENT_TIMESTAMP
				WHERE incident_id = ?
			`, desc, existingID)
			return
		}

		// Create NEW Incident in fleet_incidents
		h.db.Exec(`
			INSERT INTO fleet_incidents (site_id, pc_name, severity, status, description, created_at)
			VALUES (NULL, ?, ?, 'OPEN', ?, CURRENT_TIMESTAMP)
		`, pcName, severity, desc)

		// Broadcast live telemetry WebSocket event
		websocket.BroadcastWSEvent("live_telemetry", map[string]interface{}{
			"device": pcName,
			"type":   "issue",
			"data": map[string]interface{}{
				"pc_name":     pcName,
				"issue":       "HIGH_RAM",
				"severity":    severity,
				"ram":         ramVal,
				"description": desc,
			},
		})
	}
}

// dedupAndInsertIssue avoids inserting duplicate rows for open issues within 15 minutes.
func (h *Handler) dedupAndInsertIssue(pcName string, severity string, details string) {
	sev := strings.ToUpper(severity)
	if sev != "HIGH" && sev != "CRITICAL" {
		return
	}

	prefix := details
	if idx := strings.Index(details, ":"); idx > 0 {
		prefix = details[:idx]
	} else if len(details) > 20 {
		prefix = details[:20]
	}

	var existingID int64
	h.db.Raw(`
		SELECT incident_id FROM fleet_incidents
		WHERE LOWER(pc_name) = LOWER(?)
		  AND status = 'OPEN'
		  AND (
		    LOWER(description) = LOWER(?)
		    OR description LIKE ?
		    OR (description LIKE '%RAM%' AND ? LIKE '%RAM%')
		    OR (description LIKE '%CPU%' AND ? LIKE '%CPU%')
		    OR (description LIKE '%Disk%' AND ? LIKE '%Disk%')
		  )
		  AND created_at >= NOW() - INTERVAL '15 minutes'
		ORDER BY incident_id DESC
		LIMIT 1
	`, pcName, details, prefix+"%", details, details, details).Scan(&existingID)

	if existingID > 0 {
		// Cooldown active (15 minutes): Update existing incident timestamp & latest description to prevent duplicate row creation
		h.db.Exec(`UPDATE fleet_incidents SET description = ?, created_at = CURRENT_TIMESTAMP WHERE incident_id = ?`, details, existingID)
		return
	}

	h.db.Exec(`
		INSERT INTO fleet_incidents (site_id, pc_name, severity, status, description, created_at)
		VALUES (NULL, ?, ?, 'OPEN', ?, CURRENT_TIMESTAMP)
	`, pcName, sev, details)

	// ⚡ JARVIS Proactive Alert Voice: callback injected from main package
	fmt.Printf("[JARVIS-DEBUG] dedupAndInsertIssue: sev=%s, pcName=%s, ProactiveAlertFn is nil? %v\n", sev, pcName, h.ProactiveAlertFn == nil)
	if h.ProactiveAlertFn != nil {
		fmt.Printf("[JARVIS-DEBUG] Launching ProactiveAlertFn goroutine from dedupAndInsertIssue for %s...\n", pcName)
		go h.ProactiveAlertFn(
			"incident_new", sev,
			fmt.Sprintf("Insiden %s: %s", sev, pcName),
			details, pcName, "", "", nil,
		)
	}
}

func (h *Handler) Telemetry(c *gin.Context) {
	var payload map[string]interface{}
	if err := c.ShouldBindJSON(&payload); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": err.Error()})
		return
	}
	pcName, _ := payload["pc_name"].(string)
	if pcName == "" {
		pcName, _ = payload["device"].(string)
	}
	if pcName == "" {
		pcName, _ = payload["device_name"].(string)
	}
	if pcName == "" {
		pcName, _ = payload["agent_id"].(string)
	}
	if pcName == "" {
		pcName = "unknown-device"
	}
	metaBytes, _ := json.Marshal(payload)

	clientIP := c.ClientIP()
	if clientIP == "::1" || clientIP == "127.0.0.1" {
		clientIP = ""
	}
	if ipPayload, ok := payload["ip"].(string); ok && ipPayload != "" && ipPayload != "127.0.0.1" {
		clientIP = ipPayload
	}

	// Ensure the device is marked as ONLINE with current IP in fleet_devices (MUST be before telemetry_logs due to FK constraint)
	if h.db != nil {
		h.db.Exec(`
		INSERT INTO fleet_devices (pc_name, ip, status, online, last_seen)
		VALUES (?, ?, 'ONLINE', true, CURRENT_TIMESTAMP)
		ON CONFLICT (pc_name) DO UPDATE SET
			ip = CASE WHEN EXCLUDED.ip != '' THEN EXCLUDED.ip ELSE fleet_devices.ip END,
			status = 'ONLINE',
			online = true,
			last_seen = CURRENT_TIMESTAMP
	`, pcName, clientIP)

		h.db.Exec(`
		INSERT INTO telemetry_logs (device_name, metric_type, metric_value, metadata, tenant_id)
		VALUES (?, 'telemetry_bundle', 1.0, ?, 'default_tenant')
	`, pcName, string(metaBytes))

		// Extract RAM value & evaluate alert / cooldown
		var ramVal float64
		if r, ok := payload["memory_percent"].(float64); ok {
			ramVal = r
		} else if r, ok := payload["mem_percent"].(float64); ok {
			ramVal = r
		} else if r, ok := payload["ram"].(float64); ok {
			ramVal = r
		} else if r, ok := payload["ram_usage"].(float64); ok {
			ramVal = r
		} else if dataMap, ok := payload["data"].(map[string]interface{}); ok {
			if r, ok := dataMap["memory_percent"].(float64); ok {
				ramVal = r
			} else if r, ok := dataMap["mem_percent"].(float64); ok {
				ramVal = r
			} else if r, ok := dataMap["ram"].(float64); ok {
				ramVal = r
			}
		}

		fmt.Printf("[JARVIS-DEBUG] Telemetry received for %s: ramVal=%.2f\n", pcName, ramVal)
		if ramVal > 0 {
			h.processRAMTelemetry(pcName, ramVal)
		}
	} // end if h.db != nil

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
		pcName, _ = payload["device"].(string)
	}
	if pcName == "" {
		pcName, _ = payload["device_name"].(string)
	}
	if pcName == "" {
		pcName, _ = payload["agent_id"].(string)
	}
	if pcName == "" {
		pcName = "unknown-device"
	}
	metaBytes, _ := json.Marshal(payload)

	clientIP := c.ClientIP()
	if clientIP == "::1" || clientIP == "127.0.0.1" {
		clientIP = ""
	}

	// Update device status & IP in fleet_devices
	if h.db != nil {
		h.db.Exec(`
		INSERT INTO fleet_devices (pc_name, ip, status, last_seen)
		VALUES (?, ?, 'ONLINE', CURRENT_TIMESTAMP)
		ON CONFLICT (pc_name) DO UPDATE SET
			ip = CASE WHEN EXCLUDED.ip != '' THEN EXCLUDED.ip ELSE fleet_devices.ip END,
			status = 'ONLINE',
			last_seen = CURRENT_TIMESTAMP
	`, pcName, clientIP)

		metricType := "active_app"
		if pType, ok := payload["type"].(string); ok && pType == "web_activity" {
			metricType = "web_activity"
		} else if payload["url"] != nil || payload["domain"] != nil {
			metricType = "web_activity"
		}

		h.db.Exec(`
		INSERT INTO telemetry_logs (device_name, metric_type, metric_value, metadata, tenant_id)
		VALUES (?, ?, 1.0, ?, 'default_tenant')
	`, pcName, metricType, string(metaBytes))
	} // end if h.db != nil

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

	// Use deduplication helper instead of direct INSERT
	if h.db != nil {
		h.dedupAndInsertIssue(pcName, severity, details)

		metaBytes, _ := json.Marshal(payload)
		h.db.Exec(`
		INSERT INTO telemetry_logs (device_name, metric_type, metric_value, metadata, tenant_id)
		VALUES (?, 'browser_issue', 1.0, ?, 'default_tenant')
	`, pcName, string(metaBytes))
	}

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
		pcName, _ = payload["device"].(string)
	}
	if pcName == "" {
		pcName, _ = payload["device_name"].(string)
	}
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
	if h.db != nil {
		h.db.Exec(`
		INSERT INTO telemetry_logs (device_name, metric_type, metric_value, metadata, tenant_id)
		VALUES (?, 'web_activity', ?, ?, 'default_tenant')
	`, pcName, loadTime, string(metaBytes))
	}

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

	if h.db != nil {
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
	}

	toItems := func(rows []LogRow) []map[string]interface{} {
		result := make([]map[string]interface{}, 0, len(rows))
		for _, r := range rows {
			var meta map[string]interface{}
			_ = json.Unmarshal([]byte(r.Metadata), &meta)
			if meta == nil {
				meta = make(map[string]interface{})
			}

			// Enrich all items with device info if missing
			var fd struct {
				IP           string `gorm:"column:ip"`
				HardwareInfo string `gorm:"column:hardware_info"`
			}
			h.db.Raw(`SELECT ip, hardware_info FROM fleet_devices WHERE pc_name = ? LIMIT 1`, r.DeviceName).Scan(&fd)
			if fd.IP != "" && meta["ip_address"] == nil {
				meta["ip_address"] = fd.IP
			}
			if fd.HardwareInfo != "" {
				var hw map[string]interface{}
				if err := json.Unmarshal([]byte(fd.HardwareInfo), &hw); err == nil {
					for _, k := range []string{"os_version", "cpu", "ram", "disk", "gateway", "dns", "mac"} {
						if meta[k] == nil && hw[k] != nil {
							meta[k] = hw[k]
						}
					}
				}
			}

			// ENRICH METADATA IF IT IS A WATCHDOG ALERT, NOTIFICATION OR MISSING FIELDS
			if meta["type"] != nil || r.MetricType == "browser_issue" || r.MetricType == "fleet_incident" {
				var lastWeb struct{ Metadata string }
				h.db.Raw(`SELECT metadata::text FROM telemetry_logs WHERE device_name = ? AND metric_type = 'web_activity' AND timestamp <= ? ORDER BY timestamp DESC LIMIT 1`, r.DeviceName, r.Timestamp).Scan(&lastWeb)
				if lastWeb.Metadata != "" {
					var webMeta map[string]interface{}
					if err := json.Unmarshal([]byte(lastWeb.Metadata), &webMeta); err == nil {
						for k, v := range webMeta {
							if meta[k] == nil {
								meta[k] = v
							}
						}
					}
				}

				var lastSys struct{ Metadata string }
				h.db.Raw(`SELECT metadata::text FROM telemetry_logs WHERE device_name = ? AND metric_type = 'telemetry_bundle' AND timestamp <= ? ORDER BY timestamp DESC LIMIT 1`, r.DeviceName, r.Timestamp).Scan(&lastSys)
				if lastSys.Metadata != "" {
					var sysMeta map[string]interface{}
					if err := json.Unmarshal([]byte(lastSys.Metadata), &sysMeta); err == nil {
						for k, v := range sysMeta {
							if meta[k] == nil {
								meta[k] = v
							}
						}
					}
				}

				var rca struct {
					RootCause    string  `gorm:"column:root_cause"`
					Resolution   string  `gorm:"column:resolution"`
					AiConfidence float64 `gorm:"column:ai_confidence"`
				}
				h.db.Raw(`SELECT root_cause, resolution, ai_confidence FROM incident_post_mortems WHERE incident_id = ? LIMIT 1`, r.LogID).Scan(&rca)
				if rca.RootCause != "" && meta["suggested_rca"] == nil {
					meta["suggested_rca"] = rca.RootCause
				}
				if rca.Resolution != "" && meta["recommended_action"] == nil {
					meta["recommended_action"] = rca.Resolution
				}
				if rca.AiConfidence > 0 && meta["ai_confidence"] == nil {
					meta["ai_confidence"] = fmt.Sprintf("%.1f%%", rca.AiConfidence)
				}
			}

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

	if h.db != nil {
		h.db.Exec("UPDATE fleet_sites SET default_remote_tool = ?", defaultTool)
	}
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
		c.JSON(http.StatusOK, gin.H{"status": "offline", "message": fmt.Sprintf("Launcher binary not found at %s", launcherExe)})
		return
	}

	cmd := exec.Command(launcherExe)
	cmd.Dir = launcherDir
	SetSysProcAttr(cmd)

	err := cmd.Start()
	if err != nil {
		c.JSON(http.StatusOK, gin.H{"status": "offline", "message": err.Error()})
		return
	}

	websocket.AddInternalLog("INFO", "LAUNCHER", "Initiated Launcher Service local auto-start")
	c.JSON(http.StatusOK, gin.H{"status": "starting", "message": "Launcher service started"})
}

func (h *Handler) computeLiveSystemHealth() (int, string, []string, gin.H, int) {
	tStart := time.Now()
	comps := h.liveComponentCheck()
	healthScore := 0
	okCount := 0
	total := len(comps)
	var failedList []string
	for name, v := range comps {
		if m, ok := v.(gin.H); ok {
			if m["status"] == "OK" {
				okCount++
			} else {
				failedList = append(failedList, name)
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
	durMs := int(time.Since(tStart).Milliseconds())
	if durMs < 1 {
		durMs = 1
	}
	return healthScore, status, failedList, comps, durMs
}

func (h *Handler) GetSystemHealth(c *gin.Context) {
	var audit core.SystemAudit
	var err error
	if h.db != nil {
		err = h.db.Order("timestamp DESC").First(&audit).Error
	} else {
		err = fmt.Errorf("db connection is nil")
	}
	// Only use stored system_audit if it is fresh (within 60 seconds) AND has valid component details; otherwise run live checks
	if err == nil && !audit.Timestamp.IsZero() && time.Since(audit.Timestamp) <= 60*time.Second {
		var comps map[string]interface{}
		_ = json.Unmarshal([]byte(audit.RawJSON), &comps)
		hasDetails := false
		for _, v := range comps {
			if m, ok := v.(map[string]interface{}); ok {
				if det, _ := m["detail"].(string); det != "" {
					hasDetails = true
					break
				}
			}
		}
		if len(comps) == 0 || !hasDetails {
			liveComps := h.liveComponentCheck()
			c.JSON(http.StatusOK, gin.H{
				"health_score":      audit.HealthScore,
				"status":            audit.Status,
				"failed_components": audit.FailedComponents,
				"root_cause":        audit.RootCause,
				"confidence":        audit.Confidence,
				"recommendation":    audit.Recommendation,
				"components":        liveComps,
				"duration_ms":       audit.AuditDurationMs,
				"timestamp":         audit.Timestamp.Format(time.RFC3339),
				"auditor_version":   "v2.2",
			})
			return
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

	// Compute live health score and component checks so stale audits never mask current component state
	healthScore, status, failedList, comps, durMs := h.computeLiveSystemHealth()
	c.JSON(http.StatusOK, gin.H{
		"health_score":      healthScore,
		"status":            status,
		"failed_components": strings.Join(failedList, ", "),
		"components":        comps,
		"duration_ms":       durMs,
		"auditor_version":   "v2.2",
		"timestamp":         time.Now().Format(time.RFC3339),
	})
}

// RunSystemAudit executes a live SystemAuditor v2.2 check across all infrastructure components and persists the audit record.
func (h *Handler) RunSystemAudit(c *gin.Context) {
	healthScore, status, failedList, comps, durMs := h.computeLiveSystemHealth()
	failedStr := strings.Join(failedList, ", ")
	if failedStr == "" {
		failedStr = "None"
	}
	rootCause := "Seluruh komponen infrastruktur AI NOC beroperasi optimal"
	rec := "Tidak ada tindakan korektif diperlukan"
	if len(failedList) > 0 {
		rootCause = "Degradasi terdeteksi pada komponen: " + failedStr
		rec = "Periksa konektivitas dan log container untuk: " + failedStr
	}

	rawBytes, _ := json.Marshal(comps)
	now := time.Now()
	audit := core.SystemAudit{
		Timestamp:        now,
		HealthScore:      healthScore,
		Status:           status,
		FailedComponents: failedStr,
		RootCause:        rootCause,
		Confidence:       98,
		Recommendation:   rec,
		RawJSON:          string(rawBytes),
		AuditDurationMs:  durMs,
		AuditorVersion:   "v2.2",
	}

	if h.db != nil {
		if err := h.db.Create(&audit).Error; err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"status": "error", "message": err.Error()})
			return
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"status":            status,
		"health_score":      healthScore,
		"failed_components": failedStr,
		"root_cause":        rootCause,
		"recommendation":    rec,
		"components":        comps,
		"duration_ms":       durMs,
		"auditor_version":   "v2.2",
		"timestamp":         now.Format(time.RFC3339),
	})
}

// liveComponentCheck performs real-time health checks with measured latency/capacity details for all pipeline components.
func (h *Handler) liveComponentCheck() gin.H {
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()

	makeComp := func(ok bool, detail string) gin.H {
		st := "ERROR"
		if ok {
			st = "OK"
		}
		return gin.H{"status": st, "detail": detail}
	}
	tcpCheck := func(addrs ...string) (bool, string, int64) {
		for _, addr := range addrs {
			t0 := time.Now()
			conn, err := net.DialTimeout("tcp", addr, 800*time.Millisecond)
			if err == nil {
				conn.Close()
				return true, addr, time.Since(t0).Milliseconds()
			}
		}
		return false, "", 0
	}

	// 1. PostgreSQL
	var dbPing int
	dbOk := false
	dbDetail := "Connection unavailable"
	if h.db != nil {
		t0 := time.Now()
		if h.db.WithContext(ctx).Raw("SELECT 1").Scan(&dbPing).Error == nil {
			dbOk = true
			ms := float64(time.Since(t0).Microseconds()) / 1000.0
			var conns int64
			h.db.WithContext(ctx).Raw("SELECT COUNT(*) FROM pg_stat_activity WHERE datname = current_database()").Scan(&conns)
			dbDetail = fmt.Sprintf("RTT %.1f ms · %d active conns", ms, conns)
		}
	}

	// 2. Redis
	redisOk := false
	redisDetail := "Connection unavailable"
	if h.rdb != nil {
		t0 := time.Now()
		if h.rdb.Ping(ctx).Err() == nil {
			redisOk = true
			ms := float64(time.Since(t0).Microseconds()) / 1000.0
			keysCnt, _ := h.rdb.DBSize(ctx).Result()
			redisDetail = fmt.Sprintf("RTT %.1f ms · %d keys", ms, keysCnt)
		}
	}

	// 3. NATS JetStream
	natsOk := false
	natsDetail := "Disconnected"
	if h.natsConn != nil && h.natsConn.IsConnected() {
		natsOk = true
		rtt, err := h.natsConn.RTT()
		if err == nil {
			natsDetail = fmt.Sprintf("Connected · RTT %.1f ms", float64(rtt.Microseconds())/1000.0)
		} else {
			natsDetail = "Connected (" + h.natsConn.ConnectedUrl() + ")"
		}
	} else if ok, addr, ms := tcpCheck("osi-nats:4222", "nats:4222", "127.0.0.1:4222"); ok {
		natsOk = true
		natsDetail = fmt.Sprintf("Reachable %s (%d ms)", addr, ms)
	}

	// 4. Dashboard (self)
	dashboardOk := true
	dashDetail := fmt.Sprintf("Portal Go v2.2 · %s", runtime.Version())

	// 5. Ingestion Server (port 18800)
	ingestionOk, ingAddr, ingMs := tcpCheck("osi-ingestion-server:18800", "ingestion-server:18800", "host.docker.internal:18800", "127.0.0.1:18800")
	ingDetail := "Port 18800 unreachable"
	if ingestionOk {
		ingDetail = fmt.Sprintf("%s · TCP %d ms", ingAddr, ingMs)
	}

	// 6. RAG Engine (pgvector knowledge_vectors)
	var ragCount int64
	ragOk := false
	ragDetail := "0 vectors indexed"
	if h.db != nil {
		if err := h.db.WithContext(ctx).Table("knowledge_vectors").Count(&ragCount).Error; err == nil {
			ragOk = ragCount > 0
			ragDetail = fmt.Sprintf("%d pgvector embeddings", ragCount)
		}
	}

	// 7. AI API (check ai_config.json and enabled providers)
	aiOk := false
	aiDetail := "No active AI provider"
	if data, err := readAIConfigFile(h.aiConfigFile); err == nil && len(data) > 0 {
		var enabledProviders []string
		for name, cfg := range data {
			if en, _ := cfg["enabled"].(bool); en {
				enabledProviders = append(enabledProviders, name)
			}
		}
		if len(enabledProviders) > 0 {
			aiOk = true
			aiDetail = fmt.Sprintf("%d active (%s)", len(enabledProviders), strings.Join(enabledProviders, ", "))
		} else {
			aiOk = true
			aiDetail = fmt.Sprintf("%d providers configured", len(data))
		}
	}

	// 8. Hardware (CPU / RAM / Disk)
	cpuPct, ramPct, diskPct := readHostStats()
	hwOk := cpuPct >= 0 && ramPct >= 0 && ramPct < 95.0 && diskPct < 95.0
	hwDetail := fmt.Sprintf("CPU %.1f%% · RAM %.1f%% · Disk %.1f%%", cpuPct, ramPct, diskPct)

	return gin.H{
		"PostgreSQL": makeComp(dbOk, dbDetail),
		"Redis":      makeComp(redisOk, redisDetail),
		"NATS":       makeComp(natsOk, natsDetail),
		"Dashboard":  makeComp(dashboardOk, dashDetail),
		"Ingestion":  makeComp(ingestionOk, ingDetail),
		"RAG Engine": makeComp(ragOk, ragDetail),
		"AI API":     makeComp(aiOk, aiDetail),
		"Hardware":   makeComp(hwOk, hwDetail),
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

// runtimeMonitorProcessStart records portal process start for real uptime reporting.
var runtimeMonitorProcessStart = time.Now()

// GetRuntimeMonitor returns LIVE runtime status of platform engines.
// [AUDIT C1] All values are measured: Go runtime stats, real DB/Redis/NATS probes,
// and AI engine heartbeats from agent_heartbeats. No static/fabricated metrics.
// Engines without telemetry are reported as NO_HEARTBEAT / UNAVAILABLE ("—" values).
func (h *Handler) GetRuntimeMonitor(c *gin.Context) {
	type RuntimeEngineItem struct {
		Engine       string `json:"engine"`
		Status       string `json:"status"`
		Latency      string `json:"latency"`
		Memory       string `json:"memory"`
		CPU          string `json:"cpu"`
		Queue        string `json:"queue"`
		LastRun      string `json:"last_run"`
		Caller       string `json:"caller"`
		Subscriber   string `json:"subscriber"`
		PublishCount int    `json:"publish_count"`
		ErrorCount   int    `json:"error_count"`
		RestartCount int    `json:"restart_count"`
	}
	const na = "—"
	fmtAgo := func(t time.Time) string {
		if t.IsZero() {
			return na
		}
		d := time.Since(t)
		switch {
		case d < 2*time.Second:
			return "Just now"
		case d < time.Minute:
			return fmt.Sprintf("%ds ago", int(d.Seconds()))
		case d < time.Hour:
			return fmt.Sprintf("%dm ago", int(d.Minutes()))
		default:
			return fmt.Sprintf("%dh ago", int(d.Hours()))
		}
	}
	fmtLatency := func(d time.Duration) string {
		return fmt.Sprintf("%.1f ms", float64(d.Microseconds())/1000.0)
	}

	engines := make([]RuntimeEngineItem, 0, 16)

	// 1. Dashboard server (this process) — Go runtime stats
	var m runtime.MemStats
	runtime.ReadMemStats(&m)
	engines = append(engines, RuntimeEngineItem{
		Engine:     "osi-dashboard-server",
		Status:     "ACTIVE",
		Latency:    na,
		Memory:     fmt.Sprintf("%d MB", m.Alloc/1024/1024),
		CPU:        na,
		Queue:      fmt.Sprintf("%d goroutines", runtime.NumGoroutine()),
		LastRun:    fmt.Sprintf("uptime %s", time.Since(runtimeMonitorProcessStart).Truncate(time.Second)),
		Caller:     "Nginx Reverse Proxy",
		Subscriber: "ws.telemetry.live",
	})

	ctx, cancel := context.WithTimeout(c.Request.Context(), 2*time.Second)
	defer cancel()

	// 2. PostgreSQL — real ping + active connections
	pg := RuntimeEngineItem{Engine: "osi-postgres", Status: "UNAVAILABLE", Latency: na, Memory: na, CPU: na, Queue: na, LastRun: na,
		Caller: "Dashboard / AI Supervisor", Subscriber: "osi_system DB Connection Pool"}
	if h.db != nil {
		var one int
		t0 := time.Now()
		if err := h.db.WithContext(ctx).Raw("SELECT 1").Scan(&one).Error; err == nil {
			pg.Status = "ACTIVE"
			pg.Latency = fmtLatency(time.Since(t0))
			pg.LastRun = "Just now"
			var active int64
			if h.db.WithContext(ctx).Raw("SELECT COUNT(*) FROM pg_stat_activity WHERE state = 'active'").Scan(&active).Error == nil {
				pg.Queue = fmt.Sprintf("%d active tx", active)
			}
		} else {
			pg.ErrorCount = 1
		}
	}
	engines = append(engines, pg)

	// 3. Redis — real PING + key count
	rd := RuntimeEngineItem{Engine: "osi-redis", Status: "UNAVAILABLE", Latency: na, Memory: na, CPU: na, Queue: na, LastRun: na,
		Caller: "Distributed Locks / Session Cache", Subscriber: "redis.pubsub.cluster"}
	if h.rdb != nil {
		t0 := time.Now()
		if err := h.rdb.Ping(ctx).Err(); err == nil {
			rd.Status = "ACTIVE"
			rd.Latency = fmtLatency(time.Since(t0))
			rd.LastRun = "Just now"
			if n, err := h.rdb.DBSize(ctx).Result(); err == nil {
				rd.Queue = fmt.Sprintf("%d keys", n)
			}
		} else {
			rd.ErrorCount = 1
		}
	}
	engines = append(engines, rd)

	// 4. NATS — real connection state, RTT and message counters
	nt := RuntimeEngineItem{Engine: "osi-nats", Status: "UNAVAILABLE", Latency: na, Memory: na, CPU: na, Queue: na, LastRun: na,
		Caller: "Core Microservices", Subscriber: "* (JetStream Global Bus)"}
	if h.natsConn != nil {
		if h.natsConn.IsConnected() {
			nt.Status = "ACTIVE"
			nt.LastRun = "Just now"
			if rtt, err := h.natsConn.RTT(); err == nil {
				nt.Latency = fmtLatency(rtt)
			}
		} else {
			nt.Status = "DISCONNECTED"
		}
		st := h.natsConn.Stats()
		nt.PublishCount = int(st.OutMsgs)
		nt.Queue = fmt.Sprintf("%d in msgs", st.InMsgs)
		nt.RestartCount = int(st.Reconnects)
		if h.natsConn.LastError() != nil {
			nt.ErrorCount = 1
		}
	}
	engines = append(engines, nt)

	// 5. AI engines — from agent_heartbeats (written by the engines themselves)
	type hbRow struct {
		Agent      string    `gorm:"column:agent"`
		Status     string    `gorm:"column:status"`
		Uptime     int64     `gorm:"column:uptime"`
		QueueDepth int       `gorm:"column:queue_depth"`
		CPU        float64   `gorm:"column:cpu"`
		LastSeen   time.Time `gorm:"column:last_seen"`
	}
	heartbeats := map[string]hbRow{}
	if h.db != nil {
		var rows []hbRow
		if err := h.db.WithContext(ctx).Raw(`SELECT agent, COALESCE(status,'') AS status, COALESCE(uptime,0) AS uptime,
			COALESCE(queue_depth,0) AS queue_depth, COALESCE(cpu,0) AS cpu, last_seen
			FROM agent_heartbeats ORDER BY last_seen DESC LIMIT 200`).Scan(&rows).Error; err == nil {
			for _, r := range rows {
				heartbeats[strings.ToLower(strings.TrimSpace(r.Agent))] = r
			}
		}
	}

	aiEngines := []struct{ name, caller, subject string }{
		{"osi-python-ai-core", "NATS Broker / API", "ai.consensus.v3"},
		{"osi-ingestion-server", "Telemetry Agents / Syslog", "telemetry.logs.v1"},
		{"osi-ai-consensus", "RAG Engine / Supervisor", "ai.policy.gate"},
		{"osi-ai-daemons", "Scheduler Service", "autonomous.remediation"},
		{"osi-ai-rag", "Embeddings Vector Search", "rag.vector.query"},
		{"ai-supervisor", "Python AI Supervisor Core", "ai.supervisor.control"},
		{"intent-router", "Multi-LLM Intent Router", "ai.intent.route"},
		{"ai-planner", "AI Planning Engine", "ai.plan.formulate"},
		{"ai-verifier", "Double-Gate Verifier Engine", "ai.verify.gate"},
		{"ai-executor", "AI Execution Dispatcher", "ai.execute.command"},
		{"ai-reflector", "RLHF & Feedback Collector", "ai.reflect.rlhf"},
		{"osi-secure-relay", "Remote Control Protocol", "secure.relay.channel"},
	}
	for _, e := range aiEngines {
		item := RuntimeEngineItem{Engine: e.name, Status: "NO_HEARTBEAT", Latency: na, Memory: na, CPU: na, Queue: na, LastRun: na,
			Caller: e.caller, Subscriber: e.subject}
		hb, ok := heartbeats[e.name]
		if !ok {
			// tolerate short agent names (e.g. "rag" for "osi-ai-rag")
			short := strings.TrimPrefix(strings.TrimPrefix(e.name, "osi-"), "ai-")
			hb, ok = heartbeats[short]
		}
		if ok {
			age := time.Since(hb.LastSeen)
			switch {
			case hb.LastSeen.IsZero():
				item.Status = "NO_HEARTBEAT"
			case age <= 90*time.Second && strings.EqualFold(hb.Status, "ONLINE") || age <= 90*time.Second && strings.EqualFold(hb.Status, "ACTIVE"):
				item.Status = "ACTIVE"
			case age <= 5*time.Minute:
				item.Status = "STALE"
			default:
				item.Status = "OFFLINE"
			}
			item.CPU = fmt.Sprintf("%.1f%%", hb.CPU)
			item.Queue = fmt.Sprintf("%d jobs", hb.QueueDepth)
			item.LastRun = fmtAgo(hb.LastSeen)
		}
		engines = append(engines, item)
	}

	c.JSON(http.StatusOK, engines)
}

func getN8NBaseURL() string {
	if envURL := os.Getenv("N8N_URL"); envURL != "" {
		return strings.TrimRight(envURL, "/")
	}
	if host := os.Getenv("N8N_HOST"); host != "" {
		return fmt.Sprintf("http://%s:5678", host)
	}
	candidates := []string{
		"http://n8n:5678",
		"http://n8n_workflow_engine:5678",
		"http://localhost:5678",
	}
	client := &http.Client{Timeout: 1 * time.Second}
	for _, target := range candidates {
		resp, err := client.Get(target + "/healthz")
		if err == nil {
			resp.Body.Close()
			return target
		}
	}
	return "http://n8n:5678"
}

func (h *Handler) GetN8NHealth(c *gin.Context) {
	n8nURL := getN8NBaseURL()
	client := &http.Client{Timeout: 3 * time.Second}
	resp, err := client.Get(n8nURL + "/healthz")
	if err != nil {
		c.JSON(http.StatusOK, gin.H{
			"status":    "OFFLINE",
			"engine":    "n8n Workflow Automation Engine",
			"error":     err.Error(),
			"url":       n8nURL,
			"timestamp": time.Now().Format(time.RFC3339),
		})
		return
	}
	defer resp.Body.Close()
	var n8nData map[string]interface{}
	_ = json.NewDecoder(resp.Body).Decode(&n8nData)

	c.JSON(http.StatusOK, gin.H{
		"status":    "ONLINE",
		"engine":    "n8n Workflow Automation Engine",
		"http_code": resp.StatusCode,
		"url":       n8nURL,
		"n8n_raw":   n8nData,
		"timestamp": time.Now().Format(time.RFC3339),
	})
}

func (h *Handler) TriggerN8NWorkflow(c *gin.Context) {
	var body map[string]interface{}
	_ = c.ShouldBindJSON(&body)

	correlationID := fmt.Sprintf("corr_n8n_%d", time.Now().UnixNano())
	payloadBytes, _ := json.Marshal(body)

	n8nURL := getN8NBaseURL()
	client := &http.Client{Timeout: 5 * time.Second}
	req, err := http.NewRequest("POST", n8nURL+"/webhook/incident-trigger", strings.NewReader(string(payloadBytes)))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"status":         "FAILED",
			"error":          err.Error(),
			"correlation_id": correlationID,
			"timestamp":      time.Now().Format(time.RFC3339),
		})
		return
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Correlation-ID", correlationID)
	req.Header.Set("X-N8N-WEBHOOK-ID", "incident-trigger")
	resp, pErr := client.Do(req)
	if pErr != nil {
		c.JSON(http.StatusBadGateway, gin.H{
			"status":         "FAILED",
			"message":        "Failed to reach n8n webhook endpoint",
			"error":          pErr.Error(),
			"correlation_id": correlationID,
			"timestamp":      time.Now().Format(time.RFC3339),
		})
		return
	}
	defer resp.Body.Close()
	var resData map[string]interface{}
	_ = json.NewDecoder(resp.Body).Decode(&resData)
	c.JSON(http.StatusOK, gin.H{
		"status":         "SUCCESS",
		"message":        "n8n Live Workflow Triggered Successfully",
		"correlation_id": correlationID,
		"n8n_response":   resData,
		"http_status":    resp.StatusCode,
		"timestamp":      time.Now().Format(time.RFC3339),
	})
}

func (h *Handler) TriggerN8NVaultSyncV41(c *gin.Context) {
	var body map[string]interface{}
	_ = c.ShouldBindJSON(&body)

	correlationID := fmt.Sprintf("corr_sync_%d", time.Now().UnixNano())
	payloadBytes, _ := json.Marshal(body)

	n8nURL := getN8NBaseURL()
	client := &http.Client{Timeout: 5 * time.Second}
	req, err := http.NewRequest("POST", n8nURL+"/webhook/obsidian-sync", strings.NewReader(string(payloadBytes)))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"status":         "FAILED",
			"error":          err.Error(),
			"correlation_id": correlationID,
			"timestamp":      time.Now().Format(time.RFC3339),
		})
		return
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Correlation-ID", correlationID)
	resp, pErr := client.Do(req)
	if pErr != nil {
		c.JSON(http.StatusBadGateway, gin.H{
			"status":         "FAILED",
			"message":        "Failed to reach n8n Obsidian sync webhook endpoint",
			"error":          pErr.Error(),
			"correlation_id": correlationID,
			"timestamp":      time.Now().Format(time.RFC3339),
		})
		return
	}
	defer resp.Body.Close()
	var resData map[string]interface{}
	_ = json.NewDecoder(resp.Body).Decode(&resData)
	c.JSON(http.StatusOK, gin.H{
		"status":         "SUCCESS",
		"message":        "n8n Workflow v4.1 (Obsidian Vault Sync) Triggered Successfully",
		"correlation_id": correlationID,
		"workflow":       "v4.1",
		"n8n_response":   resData,
		"timestamp":      time.Now().Format(time.RFC3339),
	})
}

func (h *Handler) PublishPostMortemV42(c *gin.Context) {
	var body map[string]interface{}
	_ = c.ShouldBindJSON(&body)

	correlationID := fmt.Sprintf("corr_pm_%d", time.Now().UnixNano())
	payloadBytes, _ := json.Marshal(body)

	n8nURL := getN8NBaseURL()
	client := &http.Client{Timeout: 5 * time.Second}
	req, err := http.NewRequest("POST", n8nURL+"/webhook/publish-postmortem", strings.NewReader(string(payloadBytes)))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"status":         "FAILED",
			"error":          err.Error(),
			"correlation_id": correlationID,
			"timestamp":      time.Now().Format(time.RFC3339),
		})
		return
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Correlation-ID", correlationID)
	resp, pErr := client.Do(req)
	if pErr != nil {
		c.JSON(http.StatusBadGateway, gin.H{
			"status":         "FAILED",
			"message":        "Failed to reach n8n post-mortem publisher webhook endpoint",
			"error":          pErr.Error(),
			"correlation_id": correlationID,
			"timestamp":      time.Now().Format(time.RFC3339),
		})
		return
	}
	defer resp.Body.Close()
	var resData map[string]interface{}
	_ = json.NewDecoder(resp.Body).Decode(&resData)
	c.JSON(http.StatusOK, gin.H{
		"status":         "SUCCESS",
		"message":        "n8n Workflow v4.2 (Auto Post-Mortem Publisher) Triggered Successfully",
		"correlation_id": correlationID,
		"workflow":       "v4.2",
		"n8n_response":   resData,
		"timestamp":      time.Now().Format(time.RFC3339),
	})
}
