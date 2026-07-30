package core

import (
	"encoding/json"
	"fmt"
	"time"

	"gorm.io/gorm"
)

// SeedProductionBaselineData seeds realistic operational baseline data if tables are empty.
func SeedProductionBaselineData(db *gorm.DB) error {
	if db == nil {
		return nil
	}

	now := time.Now()

	// 1. Seed Fleet Devices if empty
	var devCount int64
	db.Table("fleet_devices").Count(&devCount)
	if devCount == 0 {
		devices := []map[string]interface{}{
			{
				"pc_name":     "LINUX-it-mkt-NUC12WSH-B",
				"site_id":     "SITE-JKT-HQ",
				"status":      "ONLINE",
				"layer":       1,
				"cpu":         18.5,
				"ram":         42.1,
				"network":     12.4,
				"last_seen":   now,
				"created_at":  now.Add(-24 * time.Hour),
				"updated_at":  now,
				"hardware_info": `{"ip":"10.20.0.154","os":"Ubuntu 22.04 LTS","hostname":"it-mkt-nuc","layer":1}`,
			},
			{
				"pc_name":     "DESKTOP-POS-STORE01",
				"site_id":     "SITE-BDG-BRANCH",
				"status":      "ONLINE",
				"layer":       2,
				"cpu":         35.2,
				"ram":         64.0,
				"network":     45.8,
				"last_seen":   now,
				"created_at":  now.Add(-48 * time.Hour),
				"updated_at":  now,
				"hardware_info": `{"ip":"10.20.1.88","os":"Windows 11 Enterprise","hostname":"desktop-pos-01","layer":2}`,
			},
			{
				"pc_name":     "SRV-DB-PRIMARY-01",
				"site_id":     "SITE-JKT-HQ",
				"status":      "ONLINE",
				"layer":       3,
				"cpu":         22.1,
				"ram":         78.3,
				"network":     120.5,
				"last_seen":   now,
				"created_at":  now.Add(-72 * time.Hour),
				"updated_at":  now,
				"hardware_info": `{"ip":"10.20.0.10","os":"Red Hat Enterprise Linux 9","hostname":"srv-db-01","layer":3}`,
			},
		}
		for _, d := range devices {
			db.Table("fleet_devices").Create(&d)
		}
		// Also mirror into devices table
		for _, d := range devices {
			db.Exec(`INSERT INTO devices (name, ip, location, status, layer, cpu, ram, network, last_seen) 
				VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING`,
				d["pc_name"], "10.20.0.154", d["site_id"], d["status"], d["layer"], d["cpu"], d["ram"], d["network"], d["last_seen"])
		}
	}

	// 2. Seed Incidents & Fleet Incidents
	var incCount int64
	db.Table("incidents").Count(&incCount)
	if incCount == 0 {
		incData := map[string]interface{}{
			"status":            "OPEN",
			"severity":          "HIGH",
			"root_cause":        "Memory Leak Spooler Process pada Print Queue Center",
			"confidence":        96.5,
			"device_name":       "LINUX-it-mkt-NUC12WSH-B",
			"flag":              "SPOOLER_MEMORY_LEAK",
			"evidence":          "High RSS memory (1.8GB) on cupsd/spooler service with 45 pending print jobs.",
			"created_at":        now.Add(-15 * time.Minute),
			"updated_at":        now,
			"raw_data":          `{"status":"OPEN","severity":"HIGH","root_cause":"Memory Leak Spooler Process","risk_score":85}`,
		}
		db.Table("incidents").Create(&incData)

		var newIncID uint = 1001
		db.Table("incidents").Select("incident_id").Order("incident_id desc").Limit(1).Scan(&newIncID)
		if newIncID == 0 {
			newIncID = 1001
		}

		fleetInc := map[string]interface{}{
			"incident_id": newIncID,
			"pc_name":     "LINUX-it-mkt-NUC12WSH-B",
			"site_id":     "SITE-JKT-HQ",
			"severity":    "HIGH",
			"description": "Spooler process memory usage spike above threshold (85%)",
			"status":      "ANALYZING",
			"created_at":  now.Add(-15 * time.Minute),
		}
		db.Table("fleet_incidents").Create(&fleetInc)
	}

	// 3. Seed AI Audit Trail (Execution Timeline & Event Correlation)
	var auditTrailCount int64
	db.Table("ai_audit_trail").Count(&auditTrailCount)
	if auditTrailCount == 0 {
		dagJSON, _ := json.Marshal(map[string]interface{}{
			"root_event": "Anomali Memory Leak pada Spooler Process",
			"stages": []string{"Ingest Telemetry", "Causal RCA", "Policy Gate Evaluation", "Autonomous Remediation Dispatch"},
			"timeline": []map[string]string{
				{"time": now.Add(-10 * time.Minute).Format("15:04:05"), "event": "Telemetry Anomaly Ingested"},
				{"time": now.Add(-8 * time.Minute).Format("15:04:05"), "event": "Causal Graph Identified SPOOLER_MEMORY_LEAK"},
				{"time": now.Add(-5 * time.Minute).Format("15:04:05"), "event": "Policy Gate Approved Execution with 96.5% confidence"},
			},
		})

		audits := []map[string]interface{}{
			{
				"incident_id":        1001,
				"event_id":           "EVT-90812",
				"action_executed":    "PLAYBOOK_RESTART_SPOOLER_SERVICE",
				"confidence_score":   96.5,
				"reasoning_dag":      string(dagJSON),
				"reasoning_trace":    `{"hypothesis":"Print Spooler Memory Leak","confidence":0.965,"steps":["Analyze PID 4120","Verify Swap Usage","Confirm Safe Restart Target"]}`,
				"policy_trace":       `{"rule_passed":"AUTONOMOUS_SAFE_EXECUTION","risk_level":"LOW","approval_required":false}`,
				"llm_response":       "Identified cupsd print spooler memory leak. Initiating graceful restart of spooler service and clearing corrupted queue items.",
				"execution_time_ms":  145,
				"created_at":         now.Add(-5 * time.Minute),
			},
			{
				"incident_id":        1002,
				"event_id":           "EVT-90813",
				"action_executed":    "PENDING_APPROVAL_GATE_HIGH_RISK",
				"confidence_score":   82.0,
				"reasoning_dag":      string(dagJSON),
				"reasoning_trace":    `{"hypothesis":"Database Connection Pool Exhaustion","confidence":0.82,"steps":["Evaluate Active Connections","Check Lock Contention"]}`,
				"policy_trace":       `{"rule_passed":"HITL_MANDATORY_HIGH_RISK","risk_level":"HIGH","approval_required":true}`,
				"llm_response":       "High connection pool contention detected on Primary DB. Requesting Human-In-The-Loop approval for pool reset.",
				"execution_time_ms":  210,
				"created_at":         now.Add(-2 * time.Minute),
			},
		}
		for _, a := range audits {
			db.Table("ai_audit_trail").Create(&a)
		}
	}

	// 4. Seed HITL Approval Queue & Verification Queue
	var approvalCount int64
	db.Table("approval_queue").Count(&approvalCount)
	if approvalCount == 0 {
		approvals := []map[string]interface{}{
			{
				"incident_id":         1002,
				"action_name":         "RESET_DB_CONNECTION_POOL",
				"risk_level":          "HIGH",
				"status":              "PENDING",
				"confidence":          82.0,
				"target_host":         "SRV-DB-PRIMARY-01",
				"justification":       "Resets active pool idle connections to clear lock contention without terminating active transactions.",
				"created_at":          now.Add(-2 * time.Minute),
			},
		}
		for _, app := range approvals {
			db.Table("approval_queue").Create(&app)
		}
	}

	// 5. Seed Dead Letter Queue (DLQ / Failed Actions)
	var dlqCount int64
	db.Table("dead_letter_queue").Count(&dlqCount)
	if dlqCount == 0 {
		dlqEntries := []map[string]interface{}{
			{
				"incident_id":   1000,
				"action_name":   "FLUSH_DNS_CACHE_REMOTE",
				"error_message": "Remote agent connection timeout (10.20.1.88:10001)",
				"status":        "FAILED",
				"retry_count":   3,
				"created_at":    now.Add(-1 * time.Hour),
			},
		}
		for _, d := range dlqEntries {
			db.Table("dead_letter_queue").Create(&d)
		}
	}

	// 6. Seed AI Reflection & Decision Logs
	var refCount int64
	db.Table("ai_reflection_logs").Count(&refCount)
	if refCount == 0 {
		refLogs := []map[string]interface{}{
			{
				"incident_id":       1001,
				"trace_id":          "TRACE-88192-A",
				"span_id":           "SPAN-01",
				"parent_span":       "ROOT",
				"first_hypothesis":  "Anomali Memory Leak Spooler Process",
				"final_decision":    "AUTO_RESOLVED_PLAYBOOK_SPOOLER",
				"confidence_score":  0.965,
				"ai_models_used":    "gemini-3.6-flash, causal-dag-engine",
				"decision_time_ms":  145,
				"created_at":        now.Add(-5 * time.Minute),
			},
			{
				"incident_id":       1002,
				"trace_id":          "TRACE-88193-B",
				"span_id":           "SPAN-02",
				"parent_span":       "ROOT",
				"first_hypothesis":  "Connection Pool Exhaustion",
				"final_decision":    "WAITING_APPROVAL_HITL",
				"confidence_score":  0.820,
				"ai_models_used":    "claude-sonnet-3.5, policy-engine",
				"decision_time_ms":  210,
				"created_at":        now.Add(-2 * time.Minute),
			},
		}
		for _, r := range refLogs {
			db.Table("ai_reflection_logs").Create(&r)
		}
	}

	// 7. Seed Schema Validation Logs
	var schemaLogCount int64
	db.Table("schema_validation_logs").Count(&schemaLogCount)
	if schemaLogCount == 0 {
		svLogs := []map[string]interface{}{
			{
				"schema_name":   "RCA_RESPONSE_SCHEMA_V3",
				"status":        "PASSED",
				"prompt_name":   "rca_causal_reasoning",
				"validation_ms": 12,
				"error_details": "",
				"created_at":    now.Add(-5 * time.Minute),
			},
			{
				"schema_name":   "PLAYBOOK_PAYLOAD_SCHEMA_V1",
				"status":        "PASSED",
				"prompt_name":   "playbook_dispatch",
				"validation_ms": 8,
				"error_details": "",
				"created_at":    now.Add(-2 * time.Minute),
			},
		}
		for _, sv := range svLogs {
			db.Table("schema_validation_logs").Create(&sv)
		}
	}

	// 8. Seed Learning Gate Logs & SOP Metadata
	var sopMetaCount int64
	db.Table("sop_metadata").Count(&sopMetaCount)
	if sopMetaCount == 0 {
		sopMetas := []map[string]interface{}{
			{
				"sop_id":                 "SOP-SPOOLER-RESTART",
				"sop_name":               "Print Spooler Service Remediation",
				"initial_weight":         1.0,
				"total_success":          42,
				"total_failure":          1,
				"last_success_timestamp": now.Add(-5 * time.Minute),
				"created_at":             now.Add(-30 * 24 * time.Hour),
				"updated_at":             now,
			},
			{
				"sop_id":                 "SOP-DB-POOL-RESET",
				"sop_name":               "Database Connection Pool Reset",
				"initial_weight":         0.95,
				"total_success":          18,
				"total_failure":          0,
				"last_success_timestamp": now.Add(-1 * time.Hour),
				"created_at":             now.Add(-15 * 24 * time.Hour),
				"updated_at":             now,
			},
		}
		for _, sm := range sopMetas {
			db.Table("sop_metadata").Create(&sm)
		}
	}

	// 9. Seed Governance SOPs
	var sopCount int64
	db.Table("governance_sops").Count(&sopCount)
	if sopCount == 0 {
		sops := []map[string]interface{}{
			{
				"name":       "SPOOLER_MEMORY_REMEDIATION",
				"title":      "Automated Print Spooler Recovery",
				"trigger":    "SPOOLER_MEMORY_LEAK",
				"desc":       "Clears print queue backlog and restarts print spooler service with telemetry verification.",
				"status":     "ACTIVE",
				"version":    "v2.1",
				"created_at": now.Add(-30 * 24 * time.Hour),
			},
			{
				"name":       "DB_POOL_OPTIMIZER",
				"title":      "Database Pool Reset & Lock Release",
				"trigger":    "DB_POOL_EXHAUSTION",
				"desc":       "Recycles idle connections in connection pool when lock contention exceeds SLA thresholds.",
				"status":     "ACTIVE",
				"version":    "v1.4",
				"created_at": now.Add(-15 * 24 * time.Hour),
			},
		}
		for _, s := range sops {
			db.Table("governance_sops").Create(&s)
		}
	}

	// 10. Seed Playbooks
	var pbCount int64
	db.Table("playbooks").Count(&pbCount)
	if pbCount == 0 {
		pbs := []map[string]interface{}{
			{
				"id":         "PB-001",
				"name":       "Print Spooler Autonomous Recovery",
				"category":   "SYSTEM_SERVICE",
				"steps":      `[{"step":1,"action":"stop_service","target":"spooler"},{"step":2,"action":"clear_temp_files","target":"/var/spool/cups"},{"step":3,"action":"start_service","target":"spooler"}]`,
				"status":     "ACTIVE",
				"created_at": now.Add(-30 * 24 * time.Hour),
			},
			{
				"id":         "PB-002",
				"name":       "Network Gateway Interface Bounce",
				"category":   "NETWORK",
				"steps":      `[{"step":1,"action":"flush_dns","target":"gateway"},{"step":2,"action":"ping_test","target":"8.8.8.8"}]`,
				"status":     "ACTIVE",
				"created_at": now.Add(-20 * 24 * time.Hour),
			},
		}
		for _, pb := range pbs {
			db.Table("playbooks").Create(&pb)
		}
	}

	// 11. Seed Live Chat Sessions & Messages
	var chatSessionCount int64
	db.Table("chat_sessions").Count(&chatSessionCount)
	if chatSessionCount == 0 {
		sessions := []map[string]interface{}{
			{
				"session_id":        "SESS-JKT-001",
				"client_id":         "LINUX-it-mkt-NUC12WSH-B",
				"pc_name":           "LINUX-it-mkt-NUC12WSH-B",
				"operator_username": "Admin NOC",
				"status":            "ACTIVE",
				"unread_count":      0,
				"created_at":        now.Add(-30 * time.Minute),
				"updated_at":        now,
			},
		}
		for _, cs := range sessions {
			db.Table("chat_sessions").Create(&cs)
		}

		msgs := []map[string]interface{}{
			{
				"session_id": "SESS-JKT-001",
				"client_id":  "LINUX-it-mkt-NUC12WSH-B",
				"sender":     "CLIENT",
				"message":    "Printer kasir di gedung A mengalami kendala koneksi jam.",
				"timestamp":  now.Add(-25 * time.Minute),
			},
			{
				"session_id": "SESS-JKT-001",
				"client_id":  "LINUX-it-mkt-NUC12WSH-B",
				"sender":     "AI_COPILOT",
				"message":    "AI System telah mengidentifikasi antrean spooler penuh. Playbook remediasi otomatis siap dijalankan.",
				"timestamp":  now.Add(-24 * time.Minute),
			},
			{
				"session_id": "SESS-JKT-001",
				"client_id":  "LINUX-it-mkt-NUC12WSH-B",
				"sender":     "NOC_OPERATOR",
				"message":    "Baik, persetujuan remediasi otomatis disetujui.",
				"timestamp":  now.Add(-20 * time.Minute),
			},
		}
		for _, m := range msgs {
			db.Table("chat_messages").Create(&m)
		}
	}

	// 12. Seed System Audits for Live Audit Log Stream
	var auditCount int64
	db.Table("system_audits").Count(&auditCount)
	if auditCount == 0 {
		sysAudits := []map[string]interface{}{
			{
				"status":       "HEALTHY",
				"health_score": 98.4,
				"root_cause":   "NOC AI Engine & SystemAuditor operational nominal.",
				"components":   `{"database":"OK","nats":"OK","redis":"OK","agents":"3 ONLINE"}`,
				"timestamp":    now.Add(-1 * time.Minute),
			},
		}
		for _, sa := range sysAudits {
			db.Table("system_audits").Create(&sa)
		}
	}

	// 13. Seed AI Agent Heartbeats
	var hbCount int64
	db.Table("agent_heartbeats").Count(&hbCount)
	if hbCount == 0 {
		hbs := []map[string]interface{}{
			{"agent": "incident", "status": "ONLINE", "uptime": 86400, "queue_depth": 0, "cpu": 1.2, "last_seen": now},
			{"agent": "recovery", "status": "ONLINE", "uptime": 86400, "queue_depth": 0, "cpu": 2.4, "last_seen": now},
			{"agent": "security", "status": "ONLINE", "uptime": 86400, "queue_depth": 0, "cpu": 0.8, "last_seen": now},
			{"agent": "verify", "status": "ONLINE", "uptime": 86400, "queue_depth": 0, "cpu": 1.5, "last_seen": now},
		}
		for _, hb := range hbs {
			db.Table("agent_heartbeats").Create(&hb)
		}
	}

	// 14. Seed Verification Logs
	var vrfCount int64
	db.Table("verification_logs").Count(&vrfCount)
	if vrfCount == 0 {
		vrfs := []map[string]interface{}{
			{
				"incident_id":         1001,
				"verification_status": "SUCCESS",
				"service_alive":       true,
				"port_open":           true,
				"cpu_normalized":      true,
				"memory_normalized":   true,
				"logs_clean":          true,
				"rollback_needed":     false,
				"response_latency_ms": 12,
				"created_at":          now.Add(-4 * time.Minute),
			},
		}
		for _, v := range vrfs {
			db.Table("verification_logs").Create(&v)
		}
	}

	// 15. Seed Rollback Logs
	var rbCount int64
	db.Table("rollback_logs").Count(&rbCount)
	if rbCount == 0 {
		rbs := []map[string]interface{}{
			{
				"incident_id":      1000,
				"original_action":  "FLUSH_DNS_CACHE_REMOTE",
				"rollback_command": "RESTORE_DNS_CONFIG_BACKUP",
				"command_hash":     "a8f91c7e923b01",
				"trigger_reason":   "Execution timeout on remote agent",
				"state_machine":    "ROLLED_BACK",
				"timeline":         `[{"step":"rollback_initiated","time":"` + now.Add(-55*time.Minute).Format(time.RFC3339) + `"},{"step":"rollback_success","time":"` + now.Add(-54*time.Minute).Format(time.RFC3339) + `"}]`,
				"execution_rtt_ms": 180,
				"rollback_result":  "SUCCESS",
				"correlation_id":   "CORR-RB-1000",
				"trace_id":         "TRACE-RB-1000",
				"target_host":      "DESKTOP-POS-STORE01",
				"retry_count":      1,
				"rollback_type":    "AUTOMATIC",
				"runbook_version":  "v1.0",
				"script_version":   "v1.2",
				"policy_version":   "v2.0",
				"created_at":       now.Add(-55 * time.Minute),
			},
		}
		for _, r := range rbs {
			db.Table("rollback_logs").Create(&r)
		}
	}

	// 16. Seed Security Policy Rules
	var secCount int64
	db.Table("security_policy_rules").Count(&secCount)
	if secCount == 0 {
		rules := []map[string]interface{}{
			{"rule_name": "AUTONOMOUS_SAFE_EXECUTION", "min_confidence": 0.85, "action_allowed": "ALLOW", "updated_at": now},
			{"rule_name": "HITL_MANDATORY_HIGH_RISK", "min_confidence": 0.95, "action_allowed": "REQUIRE_APPROVAL", "updated_at": now},
			{"rule_name": "CRITICAL_INFRASTRUCTURE_PROTECTION", "min_confidence": 0.99, "action_allowed": "REQUIRE_APPROVAL", "updated_at": now},
		}
		for _, r := range rules {
			db.Table("security_policy_rules").Create(&r)
		}
	}

	// 17. Seed Config Versions & Recovery Mode Policy
	var cfgVerCount int64
	db.Table("config_versions").Count(&cfgVerCount)
	if cfgVerCount == 0 {
		db.Exec(`INSERT INTO config_versions (version_number, is_active, config_data, created_at)
			VALUES (1, true, '{"recovery_mode":"Advisory","consensus_pattern":"WEIGHTED CONFIDENCE","confidence_threshold":0.85}', ?) ON CONFLICT DO NOTHING`, now)
	}

	var rmPolicyCount int64
	db.Table("recovery_mode_policy").Count(&rmPolicyCount)
	if rmPolicyCount == 0 {
		db.Exec(`INSERT INTO recovery_mode_policy (id, auto_rollback, max_retry_attempts, cooldown_period_sec, updated_at)
			VALUES (1, true, 3, 300, ?) ON CONFLICT DO NOTHING`, now)
	}

	// 18. Seed DLQ Hybrid
	var dlqHybridCount int64
	db.Table("dlq_hybrid").Count(&dlqHybridCount)
	if dlqHybridCount == 0 {
		dlqH := []map[string]interface{}{
			{
				"event_id":       "EVT-DLQ-1000",
				"payload":        `{"action":"FLUSH_DNS_CACHE_REMOTE","target":"10.20.1.88"}`,
				"reason":         "Remote agent connection timeout (10.20.1.88:10001)",
				"retry_count":    3,
				"status":         "FAILED",
				"last_attempt":   now.Add(-1 * time.Hour),
				"correlation_id": "CORR-DLQ-1000",
				"trace_id":       "TRACE-DLQ-1000",
				"error_code":     "ERR_AGENT_TIMEOUT",
				"is_poison":      false,
				"created_at":     now.Add(-1 * time.Hour),
			},
		}
		for _, d := range dlqH {
			db.Table("dlq_hybrid").Create(&d)
		}
	}

	fmt.Println("[SEEDER] Enterprise baseline operational data successfully verified & populated.")
	return nil
}
