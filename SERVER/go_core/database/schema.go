package database

import (
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"gorm.io/gorm"
)

// InitializeSchema sets up all required PostgreSQL tables, partitions, triggers, and indices.
func InitializeSchema(db *gorm.DB) error {
	// Install pgvector if available (runs in autocommit mode outside the DDL transaction)
	_ = db.Exec("CREATE EXTENSION IF NOT EXISTS vector")

	// 0. advisory lock or direct execution
	tx := db.Begin()
	defer func() {
		if r := recover(); r != nil {
			tx.Rollback()
		}
	}()

	// Acquire a session/transaction advisory lock to prevent concurrent schema migrations
	if err := tx.Exec("SELECT pg_advisory_xact_lock(74283921)").Error; err != nil {
		tx.Rollback()
		return fmt.Errorf("failed to acquire schema migration advisory lock: %w", err)
	}

	// Devices Table
	if err := tx.Exec(`
		CREATE TABLE IF NOT EXISTS devices (
			device_id SERIAL PRIMARY KEY,
			name TEXT UNIQUE NOT NULL,
			ip TEXT,
			layer INTEGER,
			location TEXT,
			status TEXT DEFAULT 'ONLINE',
			metadata JSONB,
			tenant_id TEXT DEFAULT 'default_tenant'
		)
	`).Error; err != nil {
		tx.Rollback()
		return fmt.Errorf("failed to create devices table: %w", err)
	}

	// Check if telemetry_logs is already created and if it's partitioned
	var isPartitioned bool
	row := tx.Raw(`
		SELECT relkind FROM pg_class 
		WHERE relname = 'telemetry_logs' 
		AND relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
	`).Row()
	var relkind string
	if err := row.Scan(&relkind); err == nil {
		if relkind != "p" {
			// Drop non-partitioned table
			if err := tx.Exec("DROP TABLE telemetry_logs CASCADE").Error; err != nil {
				tx.Rollback()
				return fmt.Errorf("failed to drop non-partitioned telemetry_logs: %w", err)
			}
		} else {
			isPartitioned = true
		}
	}

	if !isPartitioned {
		if err := tx.Exec(`
			CREATE TABLE IF NOT EXISTS telemetry_logs (
				log_id SERIAL,
				device_name TEXT REFERENCES devices(name) ON DELETE CASCADE,
				metric_type TEXT NOT NULL,
				metric_value FLOAT NOT NULL,
				timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
				metadata JSONB,
				tenant_id TEXT DEFAULT 'default_tenant',
				PRIMARY KEY (log_id, timestamp)
			) PARTITION BY RANGE (timestamp)
		`).Error; err != nil {
			tx.Rollback()
			return fmt.Errorf("failed to create telemetry_logs table: %w", err)
		}
	}

	// Create notify trigger
	if err := tx.Exec(`
		CREATE OR REPLACE FUNCTION notify_telemetry_insert() RETURNS trigger AS $$
		BEGIN
			PERFORM pg_notify('telemetry_stream', row_to_json(NEW)::text);
			RETURN NEW;
		END;
		$$ LANGUAGE plpgsql;
	`).Error; err != nil {
		tx.Rollback()
		return fmt.Errorf("failed to create notify_telemetry_insert function: %w", err)
	}

	// Check trigger
	var triggerExists int
	if err := tx.Raw(`
		SELECT COUNT(*) FROM pg_trigger 
		WHERE tgname = 'telemetry_notify_trigger' 
		  AND tgrelid = 'telemetry_logs'::regclass
	`).Scan(&triggerExists).Error; err != nil {
		tx.Rollback()
		return fmt.Errorf("failed to check trigger: %w", err)
	}

	if triggerExists == 0 {
		if err := tx.Exec("DROP TRIGGER IF EXISTS telemetry_notify_trigger ON telemetry_logs").Error; err != nil {
			tx.Rollback()
			return fmt.Errorf("failed to drop trigger: %w", err)
		}
		if err := tx.Exec(`
			CREATE TRIGGER telemetry_notify_trigger
			AFTER INSERT ON telemetry_logs
			FOR EACH ROW EXECUTE FUNCTION notify_telemetry_insert();
		`).Error; err != nil {
			tx.Rollback()
			return fmt.Errorf("failed to create trigger: %w", err)
		}
	}

	// Performance Optimization for API Dashboard queries
	if err := tx.Exec(`
		CREATE INDEX IF NOT EXISTS idx_telemetry_logs_dev_metric_time 
		ON telemetry_logs (device_name, metric_type, timestamp DESC);
	`).Error; err != nil {
		tx.Rollback()
		return fmt.Errorf("failed to create index on telemetry_logs: %w", err)
	}

	// Table DDLs
	tableDDLs := []struct {
		Name string
		DDL  string
	}{
		{"fleet_sites", `
			CREATE TABLE IF NOT EXISTS fleet_sites (
				site_id TEXT PRIMARY KEY,
				site_name TEXT NOT NULL,
				router_ip TEXT,
				router_port INTEGER DEFAULT 10001,
				dns_primary TEXT,
				dns_secondary TEXT,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
				default_remote_tool TEXT DEFAULT 'rustdesk'
			)
		`},
		{"fleet_printers", `
			CREATE TABLE IF NOT EXISTS fleet_printers (
				printer_id SERIAL PRIMARY KEY,
				site_id TEXT REFERENCES fleet_sites(site_id) ON DELETE CASCADE,
				pc_name TEXT,
				name TEXT NOT NULL,
				ip TEXT NOT NULL,
				status TEXT NOT NULL DEFAULT 'ONLINE',
				updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"incidents", `
			CREATE TABLE IF NOT EXISTS incidents (
				incident_id SERIAL PRIMARY KEY,
				timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
				device_name TEXT REFERENCES devices(name) ON DELETE SET NULL,
				layer INTEGER,
				flag TEXT,
				evidence TEXT,
				raw_data JSONB,
				confidence FLOAT,
				rag_status TEXT DEFAULT 'GREEN'
			)
		`},
		{"golden_solutions", `
			CREATE TABLE IF NOT EXISTS golden_solutions (
				solution_id SERIAL PRIMARY KEY,
				tag TEXT NOT NULL,
				solution_data JSONB NOT NULL,
				confidence FLOAT DEFAULT 1.0,
				status TEXT DEFAULT 'GOLDEN'
			)
		`},
		{"golden_resolutions", `
			CREATE TABLE IF NOT EXISTS golden_resolutions (
				resolution_id SERIAL PRIMARY KEY,
				incident_layer INTEGER,
				incident_flag TEXT NOT NULL,
				resolution_data JSONB NOT NULL,
				execution_count INTEGER DEFAULT 1,
				confidence FLOAT DEFAULT 1.0,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
				verified_by TEXT DEFAULT 'SYSTEM_ORCHESTRATOR'
			)
		`},
		{"incident_states", `
			CREATE TABLE IF NOT EXISTS incident_states (
				state_id SERIAL PRIMARY KEY,
				incident_id INTEGER UNIQUE REFERENCES incidents(incident_id) ON DELETE CASCADE,
				device_name TEXT REFERENCES devices(name) ON DELETE CASCADE,
				flag TEXT NOT NULL,
				status TEXT NOT NULL DEFAULT 'TRIGGERED',
				severity TEXT DEFAULT 'MEDIUM',
				sla_minutes INTEGER DEFAULT 60,
				sla_deadline TIMESTAMP,
				sla_breached BOOLEAN DEFAULT FALSE,
				reopen_window_end TIMESTAMP,
				last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
				resolved_at TIMESTAMP,
				rag_status TEXT DEFAULT 'GREEN'
			)
		`},
		{"rag_historical_logs", `
			CREATE TABLE IF NOT EXISTS rag_historical_logs (
				log_id SERIAL PRIMARY KEY,
				incident_id INTEGER REFERENCES incidents(incident_id) ON DELETE CASCADE,
				old_rag_status TEXT,
				new_rag_status TEXT,
				reason TEXT,
				changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"config_versions", `
			CREATE TABLE IF NOT EXISTS config_versions (
				version_id SERIAL PRIMARY KEY,
				version_number INTEGER UNIQUE NOT NULL,
				config_data JSONB NOT NULL,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
				is_active BOOLEAN DEFAULT FALSE,
				description TEXT
			)
		`},
		{"incident_post_mortems", `
			CREATE TABLE IF NOT EXISTS incident_post_mortems (
				post_mortem_id SERIAL PRIMARY KEY,
				incident_id INTEGER UNIQUE REFERENCES incidents(incident_id) ON DELETE CASCADE,
				device_name TEXT REFERENCES devices(name) ON DELETE CASCADE,
				flag TEXT,
				mttr_seconds INTEGER,
				blast_radius TEXT,
				rca_summary TEXT,
				remediation_effectiveness TEXT,
				prevention_steps TEXT[],
				report_data JSONB,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"knowledge_vectors", `
			CREATE TABLE IF NOT EXISTS knowledge_vectors (
				incident_id TEXT PRIMARY KEY,
				title TEXT,
				symptoms TEXT,
				root_cause TEXT,
				resolution TEXT,
				embedding vector(768),
				confidence FLOAT,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
				tags TEXT[]
			)
		`},
		{"knowledge_edges", `
			CREATE TABLE IF NOT EXISTS knowledge_edges (
				source_id TEXT REFERENCES knowledge_vectors(incident_id) ON DELETE CASCADE,
				target_id TEXT REFERENCES knowledge_vectors(incident_id) ON DELETE CASCADE,
				relationship_type VARCHAR(50) NOT NULL,
				weight DOUBLE PRECISION DEFAULT 1.0,
				co_occurrence_count INTEGER DEFAULT 1,
				last_reinforced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
				PRIMARY KEY (source_id, target_id, relationship_type)
			)
		`},
		{"incident_feedback", `
			CREATE TABLE IF NOT EXISTS incident_feedback (
				feedback_id SERIAL PRIMARY KEY,
				incident_id INTEGER REFERENCES incidents(incident_id) ON DELETE CASCADE,
				ai_root_cause TEXT,
				human_root_cause TEXT,
				score FLOAT,
				reviewer TEXT,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"dependency_map", `
			CREATE TABLE IF NOT EXISTS dependency_map (
				dependency_id SERIAL PRIMARY KEY,
				source_node TEXT NOT NULL REFERENCES devices(name) ON DELETE CASCADE,
				target_node TEXT NOT NULL REFERENCES devices(name) ON DELETE CASCADE,
				dependency_type TEXT
			)
		`},
		{"cmdb_assets", `
			CREATE TABLE IF NOT EXISTS cmdb_assets (
				asset_id TEXT PRIMARY KEY,
				parent_id TEXT REFERENCES cmdb_assets(asset_id) ON DELETE SET NULL,
				site_id TEXT REFERENCES fleet_sites(site_id) ON DELETE CASCADE,
				asset_type TEXT NOT NULL,
				name TEXT NOT NULL,
				status TEXT DEFAULT 'ONLINE',
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"health_scores", `
			CREATE TABLE IF NOT EXISTS health_scores (
				site_id TEXT PRIMARY KEY REFERENCES fleet_sites(site_id) ON DELETE CASCADE,
				score FLOAT NOT NULL,
				status TEXT NOT NULL,
				updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"fleet_devices", `
			CREATE TABLE IF NOT EXISTS fleet_devices (
				pc_name TEXT PRIMARY KEY,
				site_id TEXT REFERENCES fleet_sites(site_id) ON DELETE SET NULL,
				status TEXT DEFAULT 'PENDING',
				is_approved BOOLEAN DEFAULT FALSE,
				hardware_info JSONB,
				last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
				config_version INTEGER DEFAULT 0,
				rustdesk_id TEXT,
				rustdesk_version TEXT,
				rustdesk_running BOOLEAN DEFAULT FALSE
			)
		`},
		{"fleet_usbs", `
			CREATE TABLE IF NOT EXISTS fleet_usbs (
				usb_id SERIAL PRIMARY KEY,
				site_id TEXT REFERENCES fleet_sites(site_id) ON DELETE CASCADE,
				pc_name TEXT,
				name TEXT NOT NULL,
				manufacturer TEXT,
				fingerprint TEXT UNIQUE,
				status TEXT DEFAULT 'UNKNOWN',
				risk_level TEXT,
				first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
				last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"immutable_audit_log", `
			CREATE TABLE IF NOT EXISTS immutable_audit_log (
				log_id SERIAL PRIMARY KEY,
				timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
				action_type TEXT NOT NULL,
				actor TEXT NOT NULL,
				target TEXT,
				payload JSONB,
				prev_hash TEXT,
				hash_signature TEXT NOT NULL
			)
		`},
		{"system_audits", `
			CREATE TABLE IF NOT EXISTS system_audits (
				id SERIAL PRIMARY KEY,
				timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
				health_score INTEGER,
				status VARCHAR(50),
				failed_components TEXT,
				root_cause TEXT,
				confidence INTEGER,
				recommendation TEXT,
				raw_json TEXT,
				audit_duration_ms INTEGER,
				auditor_version VARCHAR(50),
				audit_hash TEXT,
				previous_audit_hash TEXT
			)
		`},
		{"ai_reflection_logs", `
			CREATE TABLE IF NOT EXISTS ai_reflection_logs (
				id SERIAL PRIMARY KEY,
				incident_id INTEGER REFERENCES incidents(incident_id) ON DELETE CASCADE,
				timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
				stage_version TEXT,
				first_hypothesis TEXT,
				second_hypothesis TEXT,
				final_decision TEXT,
				confidence_score REAL,
				ai_models_used TEXT,
				decision_time_ms INTEGER
			)
		`},
		{"ai_evidence_logs", `
			CREATE TABLE IF NOT EXISTS ai_evidence_logs (
				id SERIAL PRIMARY KEY,
				incident_id INTEGER REFERENCES incidents(incident_id) ON DELETE CASCADE,
				evidence_type TEXT,
				evidence_data JSONB,
				validation_status TEXT,
				source_system TEXT,
				evidence_hash TEXT
			)
		`},
		{"ai_approval_logs", `
			CREATE TABLE IF NOT EXISTS ai_approval_logs (
				id SERIAL PRIMARY KEY,
				incident_id INTEGER REFERENCES incidents(incident_id) ON DELETE CASCADE,
				risk_level TEXT,
				action_name TEXT,
				approved_by TEXT,
				approved_role TEXT,
				approved_at TIMESTAMP,
				approval_expiry TIMESTAMP,
				approval_status TEXT
			)
		`},
		{"ai_blast_radius_logs", `
			CREATE TABLE IF NOT EXISTS ai_blast_radius_logs (
				id SERIAL PRIMARY KEY,
				incident_id INTEGER REFERENCES incidents(incident_id) ON DELETE CASCADE,
				impacted_sites INTEGER,
				impacted_pcs INTEGER,
				impacted_printers INTEGER,
				impacted_dashboards INTEGER,
				impact_level TEXT
			)
		`},
		{"fleet_services", `
			CREATE TABLE IF NOT EXISTS fleet_services (
				service_id SERIAL PRIMARY KEY,
				pc_name TEXT REFERENCES fleet_devices(pc_name) ON DELETE CASCADE,
				service_name TEXT NOT NULL,
				status TEXT DEFAULT 'UNKNOWN',
				start_type TEXT,
				last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
				UNIQUE(pc_name, service_name)
			)
		`},
		{"fleet_processes", `
			CREATE TABLE IF NOT EXISTS fleet_processes (
				process_id SERIAL PRIMARY KEY,
				pc_name TEXT REFERENCES fleet_devices(pc_name) ON DELETE CASCADE,
				pid INTEGER,
				name TEXT NOT NULL,
				cpu_percent FLOAT,
				memory_mb FLOAT,
				last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
				UNIQUE(pc_name, pid, name)
			)
		`},
		{"fleet_networks", `
			CREATE TABLE IF NOT EXISTS fleet_networks (
				network_id SERIAL PRIMARY KEY,
				pc_name TEXT REFERENCES fleet_devices(pc_name) ON DELETE CASCADE,
				interface_name TEXT NOT NULL,
				ip_address TEXT,
				status TEXT,
				rx_bytes BIGINT,
				tx_bytes BIGINT,
				last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
				UNIQUE(pc_name, interface_name)
			)
		`},
		{"fleet_incidents", `
			CREATE TABLE IF NOT EXISTS fleet_incidents (
				incident_id SERIAL PRIMARY KEY,
				site_id TEXT REFERENCES fleet_sites(site_id) ON DELETE SET NULL,
				pc_name TEXT REFERENCES fleet_devices(pc_name) ON DELETE SET NULL,
				severity TEXT DEFAULT 'LOW',
				status TEXT DEFAULT 'OPEN',
				description TEXT,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
				resolved_at TIMESTAMP
			)
		`},
		{"fleet_evidence", `
			CREATE TABLE IF NOT EXISTS fleet_evidence (
				evidence_id SERIAL PRIMARY KEY,
				incident_id INTEGER REFERENCES fleet_incidents(incident_id) ON DELETE CASCADE,
				evidence_type TEXT,
				s3_path TEXT,
				timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"incident_acknowledgements", `
			CREATE TABLE IF NOT EXISTS incident_acknowledgements (
				id SERIAL PRIMARY KEY,
				timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
				agent_name TEXT,
				incident TEXT,
				rca TEXT,
				evidence TEXT,
				handling_steps TEXT,
				incharge TEXT,
				status TEXT
			)
		`},
		{"ai_confidence_calibration", `
			CREATE TABLE IF NOT EXISTS ai_confidence_calibration (
				root_cause_detail TEXT PRIMARY KEY,
				penalty REAL DEFAULT 0,
				consecutive_failures INTEGER DEFAULT 0,
				last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"remote_sessions", `
			CREATE TABLE IF NOT EXISTS remote_sessions (
				session_id SERIAL PRIMARY KEY,
				incident_id INTEGER REFERENCES incidents(incident_id) ON DELETE SET NULL,
				device_id TEXT NOT NULL,
				operator TEXT NOT NULL,
				start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
				end_time TIMESTAMP,
				duration INTEGER,
				status TEXT DEFAULT 'ACTIVE',
				reason TEXT,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"ai_audit_trail", `
			CREATE TABLE IF NOT EXISTS ai_audit_trail (
				audit_id SERIAL PRIMARY KEY,
				incident_id INTEGER REFERENCES incidents(incident_id) ON DELETE CASCADE,
				event_id TEXT UNIQUE NOT NULL,
				reasoning_dag JSONB,
				rag_vectors_retrieved JSONB,
				raw_prompt TEXT,
				llm_response TEXT,
				confidence_score REAL,
				action_executed TEXT,
				operator_feedback TEXT,
				reasoning_trace JSONB,
				planning_trace JSONB,
				policy_trace JSONB,
				memory_trace JSONB,
				worker_state TEXT,
				execution_time_ms INTEGER,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"ai_runtime_state", `
			CREATE TABLE IF NOT EXISTS ai_runtime_state (
				id SERIAL PRIMARY KEY,
				worker_id TEXT NOT NULL,
				state TEXT NOT NULL,
				previous_state TEXT,
				metadata JSONB,
				transitioned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"ai_metrics", `
			CREATE TABLE IF NOT EXISTS ai_metrics (
				metric_id SERIAL PRIMARY KEY,
				event_id TEXT NOT NULL,
				model_used TEXT NOT NULL,
				latency_ms INTEGER,
				prompt_tokens INTEGER,
				completion_tokens INTEGER,
				hallucination_score REAL,
				cache_hit BOOLEAN,
				vector_recall_count INTEGER,
				confidence REAL,
				timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"rbac_policies", `
			CREATE TABLE IF NOT EXISTS rbac_policies (
				role_id SERIAL PRIMARY KEY,
				role_name TEXT UNIQUE NOT NULL,
				permissions JSONB NOT NULL,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"rbac_users", `
			CREATE TABLE IF NOT EXISTS rbac_users (
				user_id SERIAL PRIMARY KEY,
				username TEXT UNIQUE NOT NULL,
				password TEXT NOT NULL,
				role_name TEXT NOT NULL,
				display_name TEXT DEFAULT '',
				avatar TEXT DEFAULT '',
				api_token TEXT DEFAULT '',
				dashboard_settings JSONB NOT NULL DEFAULT '{}',
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"rbac_dashboard_templates", `
			CREATE TABLE IF NOT EXISTS rbac_dashboard_templates (
				role_name TEXT PRIMARY KEY,
				layout JSONB NOT NULL,
				updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"rbac_user_dashboard_overrides", `
			CREATE TABLE IF NOT EXISTS rbac_user_dashboard_overrides (
				username TEXT PRIMARY KEY,
				layout JSONB NOT NULL,
				updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"rbac_audit_logs", `
			CREATE TABLE IF NOT EXISTS rbac_audit_logs (
				log_id SERIAL PRIMARY KEY,
				username TEXT NOT NULL,
				action TEXT NOT NULL,
				target TEXT NOT NULL,
				details TEXT NOT NULL,
				ip_address TEXT DEFAULT '',
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"rbac_session_policies", `
			CREATE TABLE IF NOT EXISTS rbac_session_policies (
				role_name TEXT PRIMARY KEY,
				session_timeout_minutes INT DEFAULT 30,
				max_concurrent_sessions INT DEFAULT 5,
				enforce_mfa BOOLEAN DEFAULT FALSE,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"governance_approvals", `
			CREATE TABLE IF NOT EXISTS governance_approvals (
				approval_id SERIAL PRIMARY KEY,
				audit_id INTEGER,
				required_role TEXT NOT NULL,
				approved_by TEXT,
				status TEXT DEFAULT 'PENDING',
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
				resolved_at TIMESTAMP
			)
		`},
		{"dlq_hybrid", `
			CREATE TABLE IF NOT EXISTS dlq_hybrid (
				dlq_id SERIAL PRIMARY KEY,
				payload JSONB NOT NULL,
				reason TEXT,
				retry_count INTEGER DEFAULT 0,
				last_attempt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
				status TEXT DEFAULT 'PENDING',
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"chat_sessions", `
			CREATE TABLE IF NOT EXISTS chat_sessions (
				id SERIAL PRIMARY KEY,
				client_id TEXT UNIQUE NOT NULL,
				pc_name TEXT,
				status TEXT DEFAULT 'OPEN',
				metadata JSONB,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
				updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"chat_messages", `
			CREATE TABLE IF NOT EXISTS chat_messages (
				id SERIAL PRIMARY KEY,
				client_id TEXT NOT NULL,
				sender TEXT NOT NULL,
				message TEXT,
				attachment_path TEXT,
				read_status TEXT DEFAULT 'SENT',
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"telegram_chat_mappings", `
			CREATE TABLE IF NOT EXISTS telegram_chat_mappings (
				id SERIAL PRIMARY KEY,
				telegram_message_id BIGINT UNIQUE NOT NULL,
				client_id TEXT NOT NULL,
				chat_message_id INTEGER,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"approval_outbox", `
			CREATE TABLE IF NOT EXISTS approval_outbox (
				id BIGSERIAL PRIMARY KEY,
				event_type TEXT NOT NULL,
				aggregate_id BIGINT NOT NULL,
				payload JSONB NOT NULL,
				status TEXT DEFAULT 'PENDING',
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
				sent_at TIMESTAMP NULL,
				retry_count INTEGER DEFAULT 0,
				publish_ack BOOLEAN DEFAULT FALSE,
				last_error TEXT NULL
			)
		`},
		{"verification_logs", `
			CREATE TABLE IF NOT EXISTS verification_logs (
				id SERIAL PRIMARY KEY,
				incident_id INTEGER,
				verification_status TEXT,
				service_alive BOOLEAN DEFAULT TRUE,
				port_open BOOLEAN DEFAULT TRUE,
				cpu_normalized BOOLEAN DEFAULT TRUE,
				memory_normalized BOOLEAN DEFAULT TRUE,
				logs_clean BOOLEAN DEFAULT TRUE,
				rollback_needed BOOLEAN DEFAULT FALSE,
				response_latency_ms INTEGER DEFAULT 0,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"rollback_logs", `
			CREATE TABLE IF NOT EXISTS rollback_logs (
				id SERIAL PRIMARY KEY,
				incident_id INTEGER REFERENCES incidents(incident_id) ON DELETE CASCADE,
				original_action TEXT,
				rollback_command TEXT,
				trigger_reason TEXT,
				rollback_result TEXT,
				state_machine TEXT DEFAULT 'INITIATED',
				timeline JSONB NULL,
				execution_rtt_ms INTEGER DEFAULT 0,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"processed_messages", `
			CREATE TABLE IF NOT EXISTS processed_messages (
				message_id TEXT PRIMARY KEY,
				subject TEXT NOT NULL,
				processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"approval_queue", `
			CREATE TABLE IF NOT EXISTS approval_queue (
				id SERIAL PRIMARY KEY,
				incident_id INTEGER REFERENCES incidents(incident_id) ON DELETE CASCADE,
				action_name TEXT NOT NULL,
				risk_level TEXT NOT NULL,
				status TEXT DEFAULT 'PENDING',
				version INTEGER DEFAULT 1,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"agent_heartbeats", `
			CREATE TABLE IF NOT EXISTS agent_heartbeats (
				agent TEXT PRIMARY KEY,
				status TEXT NOT NULL,
				uptime BIGINT,
				queue_depth INTEGER,
				cpu NUMERIC(5,2),
				last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"learning_gate_policy", `
			CREATE TABLE IF NOT EXISTS learning_gate_policy (
				id INT PRIMARY KEY,
				confidence_threshold NUMERIC(4,2) DEFAULT 0.75,
				require_human_confirmation BOOLEAN DEFAULT TRUE,
				require_success_verification BOOLEAN DEFAULT TRUE,
				updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"security_policy_rules", `
			CREATE TABLE IF NOT EXISTS security_policy_rules (
				id SERIAL PRIMARY KEY,
				rule_name TEXT UNIQUE NOT NULL,
				min_confidence NUMERIC(4,2) DEFAULT 0.80,
				action_allowed TEXT DEFAULT 'AUTO_EXECUTE',
				updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"recovery_mode_policy", `
			CREATE TABLE IF NOT EXISTS recovery_mode_policy (
				id INT PRIMARY KEY,
				auto_rollback BOOLEAN DEFAULT TRUE,
				max_retry_attempts INTEGER DEFAULT 3,
				cooldown_period_sec INTEGER DEFAULT 300,
				updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"incident_events", `
			CREATE TABLE IF NOT EXISTS incident_events (
				event_id SERIAL PRIMARY KEY,
				incident_id TEXT NOT NULL,
				event_type TEXT NOT NULL,
				payload JSONB,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"approval_events", `
			CREATE TABLE IF NOT EXISTS approval_events (
				event_id SERIAL PRIMARY KEY,
				approval_id INTEGER NOT NULL REFERENCES governance_approvals(approval_id) ON DELETE CASCADE,
				event_type TEXT NOT NULL,
				actor TEXT,
				payload JSONB,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"verification_events", `
			CREATE TABLE IF NOT EXISTS verification_events (
				event_id SERIAL PRIMARY KEY,
				verification_id INTEGER NOT NULL,
				event_type TEXT NOT NULL,
				payload JSONB,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"rollback_events", `
			CREATE TABLE IF NOT EXISTS rollback_events (
				event_id SERIAL PRIMARY KEY,
				rollback_id INTEGER NOT NULL,
				event_type TEXT NOT NULL,
				payload JSONB,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"security_events", `
			CREATE TABLE IF NOT EXISTS security_events (
				event_id SERIAL PRIMARY KEY,
				rule_name TEXT NOT NULL,
				event_type TEXT NOT NULL,
				payload JSONB,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"opa_policy_rules", `
			CREATE TABLE IF NOT EXISTS opa_policy_rules (
				id SERIAL PRIMARY KEY,
				rule_name TEXT UNIQUE NOT NULL,
				condition_expr TEXT NOT NULL,
				effect TEXT NOT NULL,
				priority INTEGER DEFAULT 1,
				updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
		{"idempotency_registry", `
			CREATE TABLE IF NOT EXISTS idempotency_registry (
				execution_id TEXT PRIMARY KEY,
				command TEXT NOT NULL,
				target TEXT NOT NULL,
				params JSONB,
				response JSONB,
				status TEXT DEFAULT 'COMPLETED',
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		`},
	}

	for _, item := range tableDDLs {
		tbl := item.Name
		ddl := item.DDL
		// Replace vector(384) with TEXT if vector is not active
		if tbl == "knowledge_vectors" {
			var vecExt int
			tx.Raw("SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector'").Scan(&vecExt)
			if vecExt == 0 {
				ddl = strings.Replace(ddl, "vector(384)", "TEXT", 1)
			}
		}

		if err := tx.Exec(ddl).Error; err != nil {
			tx.Rollback()
			return fmt.Errorf("failed to create table %s: %w", tbl, err)
		}
	}

	// Seed default values for policies
	tx.Exec("INSERT INTO learning_gate_policy (id, confidence_threshold) VALUES (1, 0.75) ON CONFLICT (id) DO NOTHING")
	tx.Exec("INSERT INTO recovery_mode_policy (id, auto_rollback) VALUES (1, true) ON CONFLICT (id) DO NOTHING")
	tx.Exec("INSERT INTO security_policy_rules (rule_name, min_confidence, action_allowed) VALUES ('LOW_SEVERITY', 0.40, 'AUTO_EXECUTE') ON CONFLICT (rule_name) DO NOTHING")
	tx.Exec("INSERT INTO security_policy_rules (rule_name, min_confidence, action_allowed) VALUES ('HIGH_SEVERITY', 0.80, 'REQUIRE_APPROVAL') ON CONFLICT (rule_name) DO NOTHING")
	tx.Exec("INSERT INTO opa_policy_rules (rule_name, condition_expr, effect, priority) VALUES ('Force HITL on high risk and low confidence', 'risk >= HIGH and confidence < 0.85', 'FORCE_HITL', 10) ON CONFLICT (rule_name) DO UPDATE SET condition_expr = EXCLUDED.condition_expr")
	tx.Exec("INSERT INTO opa_policy_rules (rule_name, condition_expr, effect, priority) VALUES ('Force HITL on critical severity', 'severity == CRITICAL', 'FORCE_HITL', 9) ON CONFLICT (rule_name) DO UPDATE SET condition_expr = EXCLUDED.condition_expr")
	tx.Exec("INSERT INTO opa_policy_rules (rule_name, condition_expr, effect, priority) VALUES ('Auto execution default', 'confidence >= 0.90 and risk == LOW', 'AUTO_EXECUTE', 1) ON CONFLICT (rule_name) DO UPDATE SET condition_expr = EXCLUDED.condition_expr")

	// Seed default RBAC policies
	tx.Exec(`INSERT INTO rbac_policies (role_name, permissions) VALUES ('superadmin', '{"all": true}') ON CONFLICT (role_name) DO UPDATE SET permissions = EXCLUDED.permissions`)
	tx.Exec(`INSERT INTO rbac_policies (role_name, permissions) VALUES ('admin', '{"all": true, "access_config": true, "remote_access": true, "access_governance": true, "restart_containers": true, "user_management": true, "monitoring": true, "incident": true, "approval": true, "dashboard": true, "ai": true, "report": true, "configuration": true, "view_audit": true, "server_health": true, "device_management": true, "rca": true, "live_logs": true}') ON CONFLICT (role_name) DO UPDATE SET permissions = EXCLUDED.permissions`)
	tx.Exec(`INSERT INTO rbac_policies (role_name, permissions) VALUES ('noc_engineering', '{"all": true, "access_config": true, "remote_access": true, "access_governance": true, "restart_containers": true, "user_management": true, "monitoring": true, "incident": true, "approval": true, "dashboard": true, "ai": true, "report": true, "configuration": true, "view_audit": true, "server_health": true, "device_management": true, "rca": true, "live_logs": true}') ON CONFLICT (role_name) DO UPDATE SET permissions = EXCLUDED.permissions`)
	tx.Exec(`INSERT INTO rbac_policies (role_name, permissions) VALUES ('operator', '{"monitoring": true, "incident_create": true, "incident_update": true, "live_logs": true, "approval_request": true}') ON CONFLICT (role_name) DO UPDATE SET permissions = EXCLUDED.permissions`)
	tx.Exec(`INSERT INTO rbac_policies (role_name, permissions) VALUES ('viewer', '{"read_only": true, "monitoring": true, "report": true, "incident_history": true}') ON CONFLICT (role_name) DO UPDATE SET permissions = EXCLUDED.permissions`)

	// Apply schema migrations for existing tables
	tx.Exec("ALTER TABLE rbac_users ADD COLUMN IF NOT EXISTS display_name TEXT DEFAULT ''")
	tx.Exec("ALTER TABLE rbac_users ADD COLUMN IF NOT EXISTS avatar TEXT DEFAULT ''")
	tx.Exec("ALTER TABLE rbac_users ADD COLUMN IF NOT EXISTS api_token TEXT DEFAULT ''")

	// Seed default RBAC users
	tx.Exec("INSERT INTO rbac_users (username, password, role_name, display_name, dashboard_settings) VALUES ('superadmin', 'superadmin123', 'superadmin', 'Super Administrator', '{}') ON CONFLICT (username) DO NOTHING")
	tx.Exec("INSERT INTO rbac_users (username, password, role_name, display_name, dashboard_settings) VALUES ('admin', 'admin', 'admin', 'Administrator', '{}') ON CONFLICT (username) DO NOTHING")
	tx.Exec("INSERT INTO rbac_users (username, password, role_name, display_name, dashboard_settings) VALUES ('noc', 'noc', 'noc_engineering', 'NOC Engineer', '{}') ON CONFLICT (username) DO NOTHING")
	tx.Exec("INSERT INTO rbac_users (username, password, role_name, display_name, dashboard_settings) VALUES ('mkt', 'mkt123', 'viewer', 'Viewer Account', '{}') ON CONFLICT (username) DO NOTHING")
	tx.Exec("INSERT INTO rbac_users (username, password, role_name, display_name, dashboard_settings) VALUES ('operator', 'operator123', 'operator', 'Operator Team', '{}') ON CONFLICT (username) DO NOTHING")

	// Seed session policies
	tx.Exec("INSERT INTO rbac_session_policies (role_name, session_timeout_minutes, max_concurrent_sessions, enforce_mfa) VALUES ('superadmin', 15, 2, true) ON CONFLICT (role_name) DO NOTHING")
	tx.Exec("INSERT INTO rbac_session_policies (role_name, session_timeout_minutes, max_concurrent_sessions, enforce_mfa) VALUES ('admin', 30, 3, false) ON CONFLICT (role_name) DO NOTHING")
	tx.Exec("INSERT INTO rbac_session_policies (role_name, session_timeout_minutes, max_concurrent_sessions, enforce_mfa) VALUES ('noc_engineering', 60, 5, false) ON CONFLICT (role_name) DO NOTHING")
	tx.Exec("INSERT INTO rbac_session_policies (role_name, session_timeout_minutes, max_concurrent_sessions, enforce_mfa) VALUES ('operator', 120, 10, false) ON CONFLICT (role_name) DO NOTHING")
	tx.Exec("INSERT INTO rbac_session_policies (role_name, session_timeout_minutes, max_concurrent_sessions, enforce_mfa) VALUES ('viewer', 240, 99, false) ON CONFLICT (role_name) DO NOTHING")
	tx.Exec("CREATE UNIQUE INDEX IF NOT EXISTS idx_processed_msg_id ON processed_messages(message_id)")
	tx.Exec("ALTER TABLE approval_outbox ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0")
	tx.Exec("ALTER TABLE approval_outbox ADD COLUMN IF NOT EXISTS publish_ack BOOLEAN DEFAULT FALSE")
	tx.Exec("ALTER TABLE approval_outbox ADD COLUMN IF NOT EXISTS last_error TEXT")
	tx.Exec("ALTER TABLE verification_logs ADD COLUMN IF NOT EXISTS response_latency_ms INTEGER DEFAULT 0")
	tx.Exec("ALTER TABLE rollback_logs ADD COLUMN IF NOT EXISTS state_machine TEXT DEFAULT 'INITIATED'")
	tx.Exec("ALTER TABLE rollback_logs ADD COLUMN IF NOT EXISTS timeline JSONB")
	tx.Exec("ALTER TABLE rollback_logs ADD COLUMN IF NOT EXISTS execution_rtt_ms INTEGER DEFAULT 0")
	tx.Exec("ALTER TABLE incident_feedback ADD COLUMN IF NOT EXISTS feedback_state TEXT DEFAULT 'PENDING'")
	tx.Exec("CREATE INDEX IF NOT EXISTS idx_fleet_incidents_status_created ON fleet_incidents (status, created_at DESC)")
	tx.Exec("INSERT INTO dependency_map (source_node, target_node, dependency_type) SELECT 'agents', 'ingestion', 'telemetry' WHERE NOT EXISTS (SELECT 1 FROM dependency_map)")

	// Create monthly partitions for telemetry_logs
	now := time.Now()
	for delta := -1; delta <= 3; delta++ {
		tMonth := now.AddDate(0, delta, 0)
		y := tMonth.Year()
		m := tMonth.Month()

		partitionName := fmt.Sprintf("telemetry_logs_y%dm%02d", y, m)
		startVal := fmt.Sprintf("%d-%02d-01 00:00:00", y, m)

		tNext := tMonth.AddDate(0, 1, 0)
		ny := tNext.Year()
		nm := tNext.Month()
		endVal := fmt.Sprintf("%d-%02d-01 00:00:00", ny, nm)

		partitionDDL := fmt.Sprintf(`
			CREATE TABLE IF NOT EXISTS %s 
			PARTITION OF telemetry_logs
			FOR VALUES FROM ('%s') TO ('%s')
		`, partitionName, startVal, endVal)

		if err := tx.Exec(partitionDDL).Error; err != nil {
			tx.Rollback()
			return fmt.Errorf("failed to create partition %s: %w", partitionName, err)
		}
	}

	// Create indices for chat tables
	tx.Exec("CREATE INDEX IF NOT EXISTS idx_chat_messages_client_id ON chat_messages (client_id)")
	tx.Exec("CREATE INDEX IF NOT EXISTS idx_telegram_chat_mappings_telegram_message_id ON telegram_chat_mappings (telegram_message_id)")

	// 7. Seed initial default config if empty
	var configCount int64
	tx.Table("config_versions").Count(&configCount)
	if configCount == 0 {
		defaultConfig := map[string]interface{}{
			"orchestrator_host":       "127.0.0.1",
			"orchestrator_port":       18800,
			"dashboard_port":          9999,
			"nats_host":               "127.0.0.1",
			"nats_port":               4222,
			"db_host":                 "localhost",
			"db_port":                 5432,
			"db_name":                 "osi_system",
			"latency_threshold":       200,
			"packet_loss_threshold":   20,
			"printer_queue_threshold": 10,
			"check_interval":          300,
			"recovery_mode":           "Semi-Auto",
			"netdata_master_url":      "http://127.0.0.1:19999",
		}
		configBytes, _ := json.Marshal(defaultConfig)
		if err := tx.Exec(`
			INSERT INTO config_versions (version_number, config_data, is_active, description)
			VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING
		`, 1, configBytes, true, "Initial Default Configuration").Error; err != nil {
			tx.Rollback()
			return fmt.Errorf("failed to seed initial config: %w", err)
		}
	}

	// --- ENTERPRISE LIVE CHAT ENGINE SCHEMA (cloude.md) ---

	// operator_presence: real-time presence tracking (Redis TTL mirrors this)
	if err := tx.Exec(`
		CREATE TABLE IF NOT EXISTS operator_presence (
			operator_id    TEXT PRIMARY KEY,
			status         TEXT NOT NULL DEFAULT 'OFFLINE',
			last_seen      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			typing_to      TEXT DEFAULT ''
		)
	`).Error; err != nil {
		tx.Rollback()
		return fmt.Errorf("failed to create operator_presence table: %w", err)
	}

	// chat_feedback: session resolution & AI suggestion tracking
	if err := tx.Exec(`
		CREATE TABLE IF NOT EXISTS chat_feedback (
			id                      SERIAL PRIMARY KEY,
			session_client_id       TEXT NOT NULL,
			resolution_status       TEXT DEFAULT 'PENDING',
			operator_notes          TEXT DEFAULT '',
			ai_recommendation_used  BOOLEAN DEFAULT FALSE,
			successful              BOOLEAN DEFAULT FALSE,
			escalation_level        TEXT DEFAULT 'L1',
			created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)
	`).Error; err != nil {
		tx.Rollback()
		return fmt.Errorf("failed to create chat_feedback table: %w", err)
	}

	// Enhance chat_sessions with missing enterprise fields
	tx.Exec(`ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS priority TEXT DEFAULT 'NORMAL'`)
	tx.Exec(`ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS issue_category TEXT DEFAULT ''`)
	tx.Exec(`ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS assigned_operator TEXT DEFAULT ''`)
	tx.Exec(`ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS closed_at TIMESTAMP`)
	tx.Exec(`ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS escalation_level TEXT DEFAULT 'L1'`)
	tx.Exec(`ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS unread_count INTEGER DEFAULT 0`)

	// Enhance chat_messages with delivery/read receipt fields
	tx.Exec(`ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMP`)
	tx.Exec(`ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS read_at TIMESTAMP`)
	tx.Exec(`ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS attachment_type TEXT DEFAULT ''`)
	tx.Exec(`ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS attachment_url TEXT DEFAULT ''`)

	// Enhance approval_queue with version column for versioned optimistic locking
	tx.Exec(`ALTER TABLE approval_queue ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1`)

	// Indices for performance
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_chat_sessions_status ON chat_sessions(status)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_chat_sessions_operator ON chat_sessions(assigned_operator)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_chat_messages_client_created ON chat_messages(client_id, created_at DESC)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_chat_messages_read_status ON chat_messages(read_status)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_operator_presence_status ON operator_presence(status)`)

	// ================================================================
	// PHASE 3: DATABASE HARDENING
	// ================================================================

	// retry_history: full audit trail of DLQ retry attempts
	tx.Exec(`CREATE TABLE IF NOT EXISTS retry_history (
		id              BIGSERIAL PRIMARY KEY,
		dlq_id          INTEGER REFERENCES dlq_hybrid(dlq_id) ON DELETE CASCADE,
		attempt_number  INTEGER NOT NULL DEFAULT 1,
		attempted_at    TIMESTAMP NOT NULL DEFAULT NOW(),
		success         BOOLEAN NOT NULL DEFAULT FALSE,
		error_reason    TEXT,
		response_code   TEXT,
		retry_strategy  TEXT DEFAULT 'exponential_backoff',
		site_id         TEXT DEFAULT 'global',
		event_id        TEXT,
		created_at      TIMESTAMP NOT NULL DEFAULT NOW()
	)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_retry_history_dlq_id    ON retry_history(dlq_id)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_retry_history_site_id   ON retry_history(site_id)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_retry_history_event_id  ON retry_history(event_id)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_retry_history_attempted ON retry_history(attempted_at DESC)`)

	// trace_integrity_reports: output of automated trace orphan auditor (Phase 11)
	tx.Exec(`CREATE TABLE IF NOT EXISTS trace_integrity_reports (
		id                  BIGSERIAL PRIMARY KEY,
		report_type         TEXT NOT NULL,
		trace_id            TEXT,
		parent_trace_id     TEXT,
		event_id            TEXT,
		incident_id         INTEGER,
		site_id             TEXT DEFAULT 'global',
		severity            TEXT DEFAULT 'WARNING',
		description         TEXT,
		detected_at         TIMESTAMP NOT NULL DEFAULT NOW(),
		resolved            BOOLEAN DEFAULT FALSE,
		resolved_at         TIMESTAMP,
		resolver            TEXT,
		scan_run_id         TEXT,
		raw_data            JSONB DEFAULT '{}'
	)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_trace_reports_trace_id   ON trace_integrity_reports(trace_id)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_trace_reports_type       ON trace_integrity_reports(report_type)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_trace_reports_site       ON trace_integrity_reports(site_id)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_trace_reports_detected   ON trace_integrity_reports(detected_at DESC)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_trace_reports_unresolved ON trace_integrity_reports(resolved) WHERE resolved = FALSE`)

	// agent_trust_scores: per-agent trust scoring for policy decisions (Phase 6)
	tx.Exec(`CREATE TABLE IF NOT EXISTS agent_trust_scores (
		id                         BIGSERIAL PRIMARY KEY,
		agent_name                 TEXT NOT NULL UNIQUE,
		site_id                    TEXT DEFAULT 'global',
		trust_score                NUMERIC(5,2) NOT NULL DEFAULT 100.0,
		heartbeat_score            NUMERIC(5,2) DEFAULT 100.0,
		false_positive_penalty     NUMERIC(5,2) DEFAULT 0.0,
		execution_success_bonus    NUMERIC(5,2) DEFAULT 0.0,
		rollback_frequency_penalty NUMERIC(5,2) DEFAULT 0.0,
		telemetry_integrity_score  NUMERIC(5,2) DEFAULT 100.0,
		spoof_detection_flag       BOOLEAN DEFAULT FALSE,
		total_events_processed     INTEGER DEFAULT 0,
		total_false_positives      INTEGER DEFAULT 0,
		total_rollbacks            INTEGER DEFAULT 0,
		total_successes            INTEGER DEFAULT 0,
		last_seen_at               TIMESTAMP,
		last_scored_at             TIMESTAMP NOT NULL DEFAULT NOW(),
		score_version              INTEGER DEFAULT 1,
		notes                      TEXT,
		created_at                 TIMESTAMP NOT NULL DEFAULT NOW(),
		updated_at                 TIMESTAMP NOT NULL DEFAULT NOW()
	)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_trust_scores_agent ON agent_trust_scores(agent_name)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_trust_scores_site  ON agent_trust_scores(site_id)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_trust_scores_score ON agent_trust_scores(trust_score)`)

	// anomaly_predictions: predictive intelligence output (Phase 10)
	tx.Exec(`CREATE TABLE IF NOT EXISTS anomaly_predictions (
		id                  BIGSERIAL PRIMARY KEY,
		device_id           TEXT NOT NULL,
		site_id             TEXT DEFAULT 'global',
		risk_score          NUMERIC(5,2) NOT NULL DEFAULT 0.0,
		predicted_failure   TEXT NOT NULL,
		confidence          NUMERIC(5,2) NOT NULL DEFAULT 0.0,
		recommended_action  TEXT,
		evidence_window_hrs INTEGER DEFAULT 24,
		prediction_horizon  INTEGER DEFAULT 4,
		model_version       TEXT DEFAULT '1.0',
		feature_snapshot    JSONB DEFAULT '{}',
		status              TEXT DEFAULT 'ACTIVE',
		predicted_at        TIMESTAMP NOT NULL DEFAULT NOW(),
		resolved_at         TIMESTAMP,
		acknowledged_by     TEXT,
		created_at          TIMESTAMP NOT NULL DEFAULT NOW()
	)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_anomaly_device    ON anomaly_predictions(device_id)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_anomaly_site      ON anomaly_predictions(site_id)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_anomaly_risk      ON anomaly_predictions(risk_score DESC)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_anomaly_status    ON anomaly_predictions(status)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_anomaly_predicted ON anomaly_predictions(predicted_at DESC)`)

	// Phase 3: hardening indexes on critical tables
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_approval_queue_status   ON approval_queue(status)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_approval_queue_incident ON approval_queue(incident_id)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_processed_messages_id   ON processed_messages(message_id)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_dlq_status_retry        ON dlq_hybrid(status, retry_count) WHERE status = 'PENDING'`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_rollback_logs_incident  ON rollback_logs(incident_id)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_verification_logs_incid ON verification_logs(incident_id)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_incident_events_incident ON incident_events(incident_id)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_incident_events_type     ON incident_events(event_type)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_ai_audit_trail_created_at ON ai_audit_trail(created_at DESC)`)

	// Phase 3: event sourcing — add trace_id + site_id to event tables
	tx.Exec(`ALTER TABLE incident_events    ADD COLUMN IF NOT EXISTS trace_id TEXT`)
	tx.Exec(`ALTER TABLE incident_events    ADD COLUMN IF NOT EXISTS site_id  TEXT DEFAULT 'global'`)
	tx.Exec(`ALTER TABLE incident_events    ADD COLUMN IF NOT EXISTS causal_chain TEXT[]`)
	tx.Exec(`ALTER TABLE approval_events    ADD COLUMN IF NOT EXISTS trace_id TEXT`)
	tx.Exec(`ALTER TABLE approval_events    ADD COLUMN IF NOT EXISTS site_id  TEXT DEFAULT 'global'`)
	tx.Exec(`ALTER TABLE rollback_events    ADD COLUMN IF NOT EXISTS trace_id TEXT`)
	tx.Exec(`ALTER TABLE rollback_events    ADD COLUMN IF NOT EXISTS site_id  TEXT DEFAULT 'global'`)
	tx.Exec(`ALTER TABLE verification_events ADD COLUMN IF NOT EXISTS trace_id TEXT`)
	tx.Exec(`ALTER TABLE verification_events ADD COLUMN IF NOT EXISTS site_id  TEXT DEFAULT 'global'`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_incident_events_trace ON incident_events(trace_id) WHERE trace_id IS NOT NULL`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_approval_events_trace ON approval_events(trace_id) WHERE trace_id IS NOT NULL`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_rollback_events_trace ON rollback_events(trace_id) WHERE trace_id IS NOT NULL`)

	// Phase 3: DLQ hardening — add site_id, event_id, resolved_at
	tx.Exec(`ALTER TABLE dlq_hybrid ADD COLUMN IF NOT EXISTS site_id    TEXT DEFAULT 'global'`)
	tx.Exec(`ALTER TABLE dlq_hybrid ADD COLUMN IF NOT EXISTS event_id   TEXT`)
	tx.Exec(`ALTER TABLE dlq_hybrid ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMP`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_dlq_site ON dlq_hybrid(site_id)`)

	// Phase 5: Policy Engine Hardening DDL
	tx.Exec(`ALTER TABLE fleet_sites ADD COLUMN IF NOT EXISTS criticality TEXT DEFAULT 'MEDIUM'`)
	tx.Exec(`CREATE TABLE IF NOT EXISTS policy_versions (
		id SERIAL PRIMARY KEY,
		version INTEGER NOT NULL UNIQUE,
		rules_json JSONB NOT NULL,
		description TEXT,
		is_active BOOLEAN DEFAULT FALSE,
		created_by TEXT DEFAULT 'system',
		created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
	)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_policy_versions_active ON policy_versions(is_active) WHERE is_active = TRUE`)

	tx.Exec(`CREATE TABLE IF NOT EXISTS policy_audit_trail (
		id SERIAL PRIMARY KEY,
		incident_id INTEGER,
		policy_version INTEGER,
		input_context JSONB NOT NULL,
		matched_rule TEXT,
		effect TEXT NOT NULL,
		evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
	)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_policy_audit_incident ON policy_audit_trail(incident_id)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_policy_audit_effect ON policy_audit_trail(effect)`)

	tx.Exec(`CREATE TABLE IF NOT EXISTS rollback_policies (
		id SERIAL PRIMARY KEY,
		action_type TEXT NOT NULL UNIQUE,
		max_rollback_attempts INTEGER DEFAULT 1,
		trigger_on_verification_failure BOOLEAN DEFAULT TRUE,
		trigger_on_trust_drop BOOLEAN DEFAULT TRUE,
		trust_threshold NUMERIC(5,2) DEFAULT 70.0,
		created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
	)`)

	tx.Exec(`CREATE TABLE IF NOT EXISTS execution_ledger (
		execution_id TEXT PRIMARY KEY,
		incident_id INTEGER,
		decision_epoch BIGINT,
		command_hash TEXT,
		dispatch_state TEXT,
		agent_ack_state TEXT,
		verify_state TEXT,
		rollback_state TEXT,
		final_state TEXT,
		trace_hash TEXT,
		pre_state_hash TEXT,
		post_state_hash TEXT,
		nonce TEXT,
		agent_signature TEXT,
		created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
	)`)
	tx.Exec(`ALTER TABLE execution_ledger ADD COLUMN IF NOT EXISTS pre_state_hash TEXT`)
	tx.Exec(`ALTER TABLE execution_ledger ADD COLUMN IF NOT EXISTS post_state_hash TEXT`)
	tx.Exec(`ALTER TABLE execution_ledger ADD COLUMN IF NOT EXISTS nonce TEXT`)
	tx.Exec(`ALTER TABLE execution_ledger ADD COLUMN IF NOT EXISTS agent_signature TEXT`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_execution_ledger_incident ON execution_ledger(incident_id)`)

	tx.Exec(`CREATE TABLE IF NOT EXISTS host_execution_locks (
		host_name TEXT PRIMARY KEY,
		locked_by_execution_id TEXT,
		acquired_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		expires_at TIMESTAMP
	)`)

	// NOC IT AI v3.0 - Audit Governance Gaps (GAP 1 & GAP 6)
	tx.Exec(`CREATE TABLE IF NOT EXISTS decision_graphs (
		id SERIAL PRIMARY KEY,
		incident_id BIGINT,
		root_incident JSONB,
		consensus_output JSONB,
		critic_feedback JSONB,
		evidence_used JSONB,
		policy_applied JSONB,
		hitl_details JSONB,
		final_action_taken TEXT,
		created_at TIMESTAMPTZ DEFAULT NOW()
	)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_decision_graphs_incident ON decision_graphs(incident_id)`)

	tx.Exec(`CREATE TABLE IF NOT EXISTS policy_snapshots (
		id SERIAL PRIMARY KEY,
		policy_snapshot_id TEXT UNIQUE NOT NULL,
		policy_version INTEGER NOT NULL,
		policy_content JSONB NOT NULL,
		signature_hash TEXT NOT NULL,
		created_at TIMESTAMPTZ DEFAULT NOW()
	)`)
	tx.Exec(`CREATE INDEX IF NOT EXISTS idx_policy_snapshots_sid ON policy_snapshots(policy_snapshot_id)`)

	tx.Exec(`ALTER TABLE incidents ADD COLUMN IF NOT EXISTS policy_snapshot_id TEXT`)
	tx.Exec(`ALTER TABLE fleet_incidents ADD COLUMN IF NOT EXISTS policy_snapshot_id TEXT`)
	tx.Exec(`ALTER TABLE fleet_incidents ADD COLUMN IF NOT EXISTS state_version INTEGER DEFAULT 1`)

	if err := tx.Commit().Error; err != nil {
		return fmt.Errorf("failed to commit DDL transaction: %w", err)
	}

	return nil
}
