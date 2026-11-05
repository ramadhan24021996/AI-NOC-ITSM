# DATABASE AUDIT
## OSI NOC IT AI — Database Forensic Audit
**Primary File:** SERVER/go_core/database/schema.go (1422 lines), database.go (342 lines)  
**Database:** PostgreSQL 15 with pgvector extension  
**ORM:** GORM (Go), psycopg2 (Python)  
**Status:** VERIFIED from source code analysis

---

## DATABASE CONNECTION

### Go Connection (database.go)
```go
dsn = "host={DB_HOST} port={DB_PORT} user={DB_USER} password={DB_PASS} dbname={DB_NAME} sslmode=disable TimeZone=UTC"
gorm.Open(postgres.Open(dsn), &gorm.Config{Logger: logger.Default.LogMode(logger.Info)})

Pool Settings:
  SetMaxIdleConns(5)
  SetMaxOpenConns(50)
  SetConnMaxLifetime(time.Hour)
```

**Risks:**
- `sslmode=disable` — NO TLS in transit between services
- MaxOpenConns(50) — could exhaust at high load
- No connection retry logic on startup failure (fail-fast: os.Exit(1))

### Python Connection (db_connector.py via psycopg2)
- Uses environment variables DB_HOST, DB_NAME, DB_USER, DB_PASSWORD
- Connection via NOC bridge also auto-discovers from DB

---

## TABLE INVENTORY (60+ tables)

### Core Infrastructure Tables

| Table | Primary Key | Key Columns | FK References | Status |
|-------|-------------|-------------|---------------|--------|
| devices | device_id SERIAL | name, ip, layer, status, metadata JSONB, tenant_id | — | VERIFIED |
| fleet_sites | site_id TEXT | site_name, router_ip, dns_primary, dns_secondary | — | VERIFIED |
| fleet_devices | pc_name TEXT | site_id, status, is_approved, hardware_info JSONB, rustdesk_id | fleet_sites | VERIFIED |
| fleet_printers | printer_id SERIAL | site_id, name, ip, status, toner_pct | fleet_sites | VERIFIED |
| fleet_usbs | usb_id SERIAL | fingerprint UNIQUE, risk_level, status | fleet_sites | VERIFIED |
| dependency_map | dependency_id SERIAL | source_node, target_node, dependency_type | devices | VERIFIED |
| cmdb_assets | asset_id TEXT | parent_id, site_id, asset_type, name, status | fleet_sites | VERIFIED |

### Incident Tables

| Table | Primary Key | Key Columns | FK References | Status |
|-------|-------------|-------------|---------------|--------|
| incidents | incident_id SERIAL | device_name, layer, flag, evidence, raw_data JSONB, confidence, rag_status | devices | VERIFIED |
| fleet_incidents | incident_id SERIAL | site_id, pc_name, severity, status, description, trace_id | fleet_sites, fleet_devices | VERIFIED |
| incident_states | state_id SERIAL | incident_id UNIQUE, status, severity, sla_minutes, sla_deadline, sla_breached | incidents | VERIFIED |
| incident_events | event_id SERIAL | incident_id TEXT, event_type, payload JSONB, trace_id, causal_chain | — | VERIFIED |
| fleet_evidence | evidence_id SERIAL | incident_id, evidence_type, s3_path | fleet_incidents | VERIFIED |

### AI/ML Tables

| Table | Primary Key | Key Columns | Status |
|-------|-------------|-------------|--------|
| knowledge_vectors | incident_id TEXT | title, symptoms, root_cause, resolution, embedding vector(768), confidence, tags | VERIFIED |
| knowledge_edges | (source_id, target_id, relationship_type) | weight, co_occurrence_count, last_reinforced_at | VERIFIED |
| ai_audit_trail | audit_id SERIAL | event_id UNIQUE, reasoning_dag JSONB, raw_prompt, llm_response, confidence_score | VERIFIED |
| ai_reflection_logs | id SERIAL | incident_id, first_hypothesis, second_hypothesis, final_decision, confidence_score | VERIFIED |
| ai_evidence_logs | id SERIAL | incident_id, evidence_type, evidence_data JSONB, evidence_hash | VERIFIED |
| ai_approval_logs | id SERIAL | incident_id, risk_level, action_name, approved_by, approval_status | VERIFIED |
| ai_blast_radius_logs | id SERIAL | incident_id, impacted_sites, impacted_pcs, impact_level | VERIFIED |
| ai_metrics | metric_id SERIAL | event_id, model_used, latency_ms, prompt_tokens, completion_tokens, hallucination_score | VERIFIED |
| ai_confidence_calibration | root_cause_detail TEXT PK | penalty, consecutive_failures | VERIFIED |

### Governance/Policy Tables

| Table | Primary Key | Key Columns | Status |
|-------|-------------|-------------|--------|
| governance_approvals | approval_id SERIAL | audit_id, required_role, approved_by, status | VERIFIED |
| approval_queue | id SERIAL | incident_id, action_name, risk_level, status, version | VERIFIED |
| approval_outbox | id BIGSERIAL | event_type, aggregate_id, payload JSONB, status, retry_count, publish_ack | VERIFIED |
| approval_events | event_id SERIAL | approval_id, event_type, actor, payload JSONB, trace_id | VERIFIED |
| opa_policy_rules | id SERIAL | rule_name UNIQUE, condition_expr, effect, priority | VERIFIED |
| preapproved_action_catalog | action_id TEXT PK | name, category, command_template, is_preapproved | VERIFIED |
| pdp_audit_logs | log_id SERIAL | profile_name, total_steps, max_risk_score, decision, explainability JSONB | VERIFIED |

### RBAC / Auth Tables

| Table | Primary Key | Key Columns | Security Issue | Status |
|-------|-------------|-------------|----------------|--------|
| rbac_users | user_id SERIAL | username UNIQUE, password TEXT, role_name, api_token TEXT | **PLAINTEXT PASSWORD** | VERIFIED |
| rbac_policies | role_id SERIAL | role_name UNIQUE, permissions JSONB | — | VERIFIED |
| rbac_audit_logs | log_id SERIAL | username, action, target, details, ip_address | — | VERIFIED |
| rbac_session_policies | role_name TEXT PK | session_timeout_minutes, max_concurrent_sessions, enforce_mfa | MFA config only | VERIFIED |
| rbac_dashboard_templates | role_name TEXT PK | layout JSONB | — | VERIFIED |

### Chat / Communication Tables

| Table | Primary Key | Key Columns | Status |
|-------|-------------|-------------|--------|
| chat_sessions | id SERIAL | client_id TEXT UNIQUE, pc_name, status, assigned_operator, unread_count | VERIFIED |
| chat_messages | id SERIAL | client_id, sender, message, read_status, incident_id, thread_type | VERIFIED |
| telegram_chat_mappings | id SERIAL | telegram_message_id BIGINT UNIQUE, client_id, chat_message_id | VERIFIED |
| operator_presence | operator_id TEXT PK | status, last_seen, typing_to | VERIFIED |
| chat_feedback | id SERIAL | session_client_id, resolution_status, operator_notes, ai_recommendation_used | VERIFIED |

### Observability / Audit Tables

| Table | Primary Key | Key Columns | Status |
|-------|-------------|-------------|--------|
| telemetry_logs | (log_id, timestamp) PK PARTITIONED | device_name, metric_type, metric_value, metadata JSONB, tenant_id | VERIFIED |
| immutable_audit_log | log_id SERIAL | timestamp, action_type, actor, target, payload JSONB, prev_hash, hash_signature | VERIFIED |
| system_audits | id SERIAL | health_score, status, failed_components, root_cause, audit_hash, previous_audit_hash | VERIFIED |
| agent_heartbeats | agent TEXT PK | status, uptime, queue_depth, cpu, last_seen | VERIFIED |

### Learning / Reliability Tables

| Table | Primary Key | Key Columns | Status |
|-------|-------------|-------------|--------|
| incident_feedback | feedback_id SERIAL | incident_id, ai_root_cause, human_root_cause, score, feedback_state | VERIFIED |
| incident_post_mortems | post_mortem_id SERIAL | incident_id UNIQUE, mttr_seconds, blast_radius, rca_summary, prevention_steps | VERIFIED |
| post_incident_debriefs | id SERIAL | incident_id TEXT, is_rca_correct, operator_feedback | VERIFIED |
| golden_solutions | solution_id SERIAL | tag, solution_data JSONB, confidence | VERIFIED |
| golden_resolutions | resolution_id SERIAL | incident_layer, incident_flag, resolution_data JSONB, execution_count | VERIFIED |
| dlq_hybrid | dlq_id SERIAL | payload JSONB, reason, retry_count, status, is_poison | VERIFIED |
| retry_history | id BIGSERIAL | dlq_id, attempt_number, success, error_reason, retry_strategy | VERIFIED |

### Advanced Tables

| Table | Primary Key | Key Columns | Status |
|-------|-------------|-------------|--------|
| execution_ledger | execution_id TEXT PK | incident_id, command_hash, dispatch_state, verify_state, trace_hash | VERIFIED |
| host_execution_locks | host_name TEXT PK | locked_by_execution_id, acquired_at, expires_at | VERIFIED |
| proposed_dag_changes | id SERIAL | source_node, target_node, change_type, statistical_score, current_status | VERIFIED |
| anomaly_predictions | id BIGSERIAL | device_id, risk_score, predicted_failure, confidence, prediction_horizon | VERIFIED |
| agent_trust_scores | id BIGSERIAL | agent_name UNIQUE, trust_score, false_positive_penalty, spoof_detection_flag | VERIFIED |
| decision_graphs | id SERIAL | incident_id, root_incident JSONB, consensus_output JSONB, final_action_taken | VERIFIED |
| policy_snapshots | id SERIAL | policy_snapshot_id UNIQUE, policy_version, policy_content JSONB, signature_hash | VERIFIED |

---

## TELEMETRY PARTITIONING

```sql
-- Partitioned table (RANGE by timestamp)
telemetry_logs PARTITION BY RANGE (timestamp)

-- Monthly partitions: 2025 to 2031 (6 years forward + 1 year back)
telemetry_logs_y2025m01  ... telemetry_logs_y2031m12
telemetry_logs_default  -- catch-all partition for out-of-range dates

-- Trigger: notify_telemetry_insert()
-- On INSERT: PERFORM pg_notify('telemetry_stream', payload::text)
```
**Status:** VERIFIED — 84 partitions created (7 years × 12 months) + default

---

## CRITICAL DATABASE SECURITY FINDINGS

### CRITICAL: Plaintext Passwords
```sql
-- schema.go line 931-934
INSERT INTO rbac_users (username, password, role_name, display_name, dashboard_settings) 
VALUES ('admin', 'admin', 'admin', 'Administrator', '{}')
VALUES ('noc', 'noc', 'noc_engineering', 'NOC Engineer', '{}')
```
**Severity:** CRITICAL  
**Evidence:** schema.go lines 931-934  
**Impact:** Default credentials allow immediate unauthorized access

### HIGH: No Password Hashing
```go
// database.go ChatMessage — password stored as TEXT
password TEXT NOT NULL
```
Passwords are stored and compared in plaintext. No bcrypt/argon2/scrypt.

### MEDIUM: SQL Injection Risk
```go
// incident_service.go line 113
database.DB.Exec("INSERT INTO fleet_incidents (site_id, pc_name, severity, status, description, created_at) VALUES (?, ?, ?, 'OPEN', ?, NOW())",
    dbSiteID, pcName, severity, description)
```
Uses parameterized queries (?) — **safe**. However, `description` comes directly from agent input without sanitization.

---

## DATABASE INDEXES (VERIFIED)

| Table | Index | Columns | Type |
|-------|-------|---------|------|
| telemetry_logs | idx_telemetry_logs_dev_metric_time | (device_name, metric_type, timestamp DESC) | BTREE |
| telemetry_logs | idx_telemetry_logs_metadata_gin | metadata | GIN |
| knowledge_vectors | idx_kv_fts | FTS tsvector | GIN |
| knowledge_vectors | idx_kv_hnsw | embedding | HNSW (vector_cosine_ops) |
| fleet_incidents | idx_fleet_incidents_status_created | (status, created_at DESC) | BTREE |
| chat_messages | idx_chat_messages_client_id | client_id | BTREE |
| chat_messages | idx_chat_messages_client_created | (client_id, created_at DESC) | BTREE |
| approval_queue | idx_approval_queue_status | status | BTREE |
| dlq_hybrid | idx_dlq_status_retry | (status, retry_count) WHERE status='PENDING' | PARTIAL |
| agent_trust_scores | idx_trust_scores_agent | agent_name | BTREE |
| anomaly_predictions | idx_anomaly_risk | risk_score DESC | BTREE |

---

## DATABASE RISKS SUMMARY

| Risk | Severity | Evidence |
|------|----------|---------|
| Plaintext passwords in seed + storage | CRITICAL | schema.go L931-934, rbac_users DDL |
| sslmode=disable between services | HIGH | database.go L258 |
| No read replica routing (code prepared but disabled) | MEDIUM | database.go L269-274 (readDSN unused) |
| advisory lock timeout risk on schema migration | MEDIUM | schema.go L26 |
| incident_events.incident_id is TEXT not INTEGER FK | MEDIUM | schema.go L825 |
| No automated vacuuming tuning for partitioned tables | LOW | Not in config |
| Global DB singleton — no connection isolation per request | LOW | database.go L17 |
| MIGRATE_DB env needed for schema changes | INFO | database.go L279 |
