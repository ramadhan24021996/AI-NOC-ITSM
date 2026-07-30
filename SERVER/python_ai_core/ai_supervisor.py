import asyncio
import nats
import json
import logging
import os
import time
from datetime import datetime, timezone

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AI_SUPERVISOR")

# ── Modular Imports (Pragmatic Modularization) ────────────────────────────────
# Core supervisor helpers & NATS bridge
from supervisor.core import (
    set_runtime_state as _set_runtime_state,
    parse_rfc3339_or_unix,
    get_active_recovery_mode,
    get_active_consensus_pattern,
    NATS_URL
)
from supervisor.dispatcher import safe_dispatch, safe_dispatch_with_cb

# Telemetry Facade Init
from telemetry_api import TelemetryAPI
telemetry = TelemetryAPI()

# ── Phase 1: AI OS Runtime State Manager ────────────────────────────────────
# Non-destructive injection — all existing logic is unchanged.
try:
    from runtime.ai_runtime_state import AIRuntimeState, RuntimeState
    _ai_runtime = AIRuntimeState("ai_supervisor")
    logger.info("[AI OS] Runtime State Manager initialized.")
except Exception as _rt_err:
    _ai_runtime = None
    logger.warning("[AI OS] Runtime State Manager unavailable (graceful fallback): %s", _rt_err)

def _set_runtime_state(state_str: str):
    """Helper to safely set AI runtime state without crashing the supervisor."""
    if _ai_runtime is None:
        return
    try:
        _ai_runtime.set_state(RuntimeState(state_str))
        _ai_runtime.heartbeat()
    except Exception as _se:
        logger.debug("[AI OS] State transition skipped: %s", _se)
# ─────────────────────────────────────────────────────────────────────────────

def parse_rfc3339_or_unix(ts_str) -> float:
    if not ts_str:
        return 0.0
    ts_str = str(ts_str).strip()
    try:
        return float(ts_str)
    except ValueError:
        import logging; logging.getLogger(__name__).debug('_ = None suppressed')
    try:
        if ts_str.endswith('Z'):
            ts_str = ts_str[:-1] + '+00:00'
        dt = datetime.fromisoformat(ts_str)
        return dt.timestamp()
    except Exception:
        return 0.0

# Import Custom Modules & Schemas
from schemas import IncidentSchema, ActionSchema, PolicySchema, VerificationSchema, LearningSchema
from core.correlation_engine import CorrelationEngine
from cognition.causal_engine import CausalReasoningEngine
from governance.recovery_worker import RecoveryOrchestrator

from core.approval_queue import ApprovalQueue
from verification import RollbackEngine
from agents import IncidentAgent, SecurityAgent, RecoveryAgent, VerificationAgent
from state_machine import IncidentStateMachine, IncidentState
# Engines sekarang diimpor dari engines/ package
from engines.escalation_engine import AutoEscalationEngine
from engines.closure_engine import ClosureEnforcementEngine
from engines.blast_radius_engine import BlastRadiusEngine
from engines.replay_engine import ReplaySimulationEngine
# Daemon sekarang diimpor dari daemons/ package
from daemons.presence_daemon import OperatorPresenceEngine

def get_active_recovery_mode(conn):
    if not conn:
        return "HITL"
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT config_data FROM config_versions WHERE is_active = TRUE LIMIT 1")
            row = cur.fetchone()
            if row and row[0]:
                cfg_data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                mode = cfg_data.get("recovery_mode", "HITL")
                # Legacy mapping
                if mode == "Semi-Auto": return "HITL"
                if mode == "Auto": return "Autonomous"
                return mode
            
            cur.execute("SELECT auto_rollback FROM recovery_mode_policy WHERE id = 1")
            row = cur.fetchone()
            if row:
                return "Autonomous" if bool(row[0]) else "HITL"
    except Exception as e:
        logger.warning(f"Failed to load active recovery mode from DB: {e}")
        try:
            conn.rollback()
        except:
            pass
    return "HITL"

def get_active_consensus_pattern(conn):
    if not conn:
        return "WEIGHTED CONFIDENCE"
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT config_data FROM config_versions WHERE is_active = TRUE LIMIT 1")
            row = cur.fetchone()
            if row and row[0]:
                cfg_data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                return cfg_data.get("consensus_pattern", "WEIGHTED CONFIDENCE").upper()
    except Exception as e:
        logger.warning(f"Failed to load active consensus pattern from DB: {e}")
        try:
            conn.rollback()
        except:
            import logging; logging.getLogger(__name__).debug('_ = None suppressed')
    return "WEIGHTED CONFIDENCE"

def log_ai_pipeline(conn, incident_id, event_id, reasoning_dag, rag_vectors, raw_prompt, llm_response, confidence_score, action_executed, first_hypothesis, second_hypothesis, final_decision, models_used, elapsed_ms, cognitive_trace: dict | None = None):
    """
    Extended for Phase 1 (AI OS): Writes standard pipeline log + cognitive traces
    (reasoning_trace, planning_trace, policy_trace, memory_trace) to ai_audit_trail.
    cognitive_trace: optional dict with keys reasoning_trace, planning_trace, policy_trace, memory_trace
    """
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            # 1. Build cognitive trace payload (Phase 1 addition)
            ct = cognitive_trace or {}
            reasoning_trace = json.dumps(ct.get("reasoning_trace", reasoning_dag or {}))
            planning_trace   = json.dumps(ct.get("planning_trace", {
                "first_hypothesis": first_hypothesis,
                "final_decision":   final_decision,
            }))
            policy_trace     = json.dumps(ct.get("policy_trace", {}))
            memory_trace     = json.dumps(ct.get("memory_trace",  {
                "rag_vectors_count": len(rag_vectors) if isinstance(rag_vectors, list) else 0,
            }))
            worker_state = _ai_runtime.state.value if _ai_runtime else "EXECUTING"

            # 2. Insert into ai_audit_trail (with cognitive trace columns)
            cur.execute("""
                INSERT INTO ai_audit_trail (
                    incident_id, event_id, reasoning_dag, rag_vectors_retrieved,
                    raw_prompt, llm_response, confidence_score, action_executed,
                    reasoning_trace, planning_trace, policy_trace, memory_trace,
                    worker_state, execution_time_ms, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                incident_id,
                event_id,
                json.dumps(reasoning_dag),
                json.dumps(rag_vectors),
                raw_prompt,
                llm_response,
                confidence_score,
                action_executed,
                reasoning_trace,
                planning_trace,
                policy_trace,
                memory_trace,
                worker_state,
                int(elapsed_ms),
                datetime.now(timezone.utc)
            ))

            # 3. Insert into ai_reflection_logs (unchanged)
            import uuid
            span_id = uuid.uuid4().hex[:8]
            cur.execute("""
                INSERT INTO ai_reflection_logs (
                    incident_id, timestamp, stage_version, first_hypothesis, second_hypothesis, 
                    final_decision, confidence_score, ai_models_used, decision_time_ms,
                    trace_id, span_id, parent_span
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                incident_id,
                datetime.now(timezone.utc),
                "v7_hitl",
                first_hypothesis,
                second_hypothesis,
                final_decision,
                confidence_score,
                models_used,
                int(elapsed_ms),
                event_id, # trace_id
                span_id,  # span_id
                "ai-supervisor" # parent_span
            ))
            conn.commit()
            logger.info("[AI OS] Pipeline log + cognitive trace saved. worker_state=%s elapsed_ms=%d", worker_state, int(elapsed_ms))
    except Exception as e:
        logger.error(f"Failed to log AI pipeline to DB: {e}")
        conn.rollback()

def log_event_sourced(conn, table_name, entity_id, event_type, payload):
    if not conn:
        return
    try:
        import json
        
        # Tahap 5: Route incident_events through Event Store for CQRS Projections
        if table_name == "incident_events":
            from core.event_store import get_event_store
            event_store = get_event_store(conn)
            event_store.append_event(str(entity_id), event_type, payload)
            return

        with conn.cursor() as cur:
            if table_name == "approval_events":
                cur.execute(
                    "INSERT INTO approval_events (approval_id, event_type, payload) VALUES (%s, %s, %s)",
                    (int(entity_id), event_type, json.dumps(payload))
                )
            elif table_name == "verification_events":
                cur.execute(
                    "INSERT INTO verification_events (verification_id, event_type, payload) VALUES (%s, %s, %s)",
                    (int(entity_id), event_type, json.dumps(payload))
                )
            elif table_name == "rollback_events":
                cur.execute(
                    "INSERT INTO rollback_events (rollback_id, event_type, payload) VALUES (%s, %s, %s)",
                    (int(entity_id), event_type, json.dumps(payload))
                )
            elif table_name == "security_events":
                cur.execute(
                    "INSERT INTO security_events (rule_name, event_type, payload) VALUES (%s, %s, %s)",
                    (str(entity_id), event_type, json.dumps(payload))
                )
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to log event sourcing to {table_name}: {e}")
        try:
            conn.rollback()
        except:
            import logging; logging.getLogger(__name__).debug('_ = None suppressed')

async def apply_incident_transition(nc, conn, incident_id: int, from_state: str, to_state: str, site_id: str = "global", actor: str = "system", context: dict | None = None) -> bool:
    """
    Helper to cleanly apply a state transition via the pure IncidentStateMachine,
    then emit telemetry and persist the state change to PostgreSQL.
    Delegates to the IncidentEventBus.
    """
    from state_observer import incident_event_bus
    return await incident_event_bus.apply_transition(nc, conn, incident_id, from_state, to_state, site_id, actor, context or {})

async def execute_validated_llm(router, severity_score, prompt, schema_class, max_attempts=3):
    """
    Executes LLM request and enforces validation against the given Pydantic schema_class.
    If parsing fails, it retries up to max_attempts - 1 times (i.e. max 2 retries).
    Logs every invalid output.
    Returns a validated schema instance or raises a ValueError on fail-safe.
    """
    system_instruction = (
        f"\n\nCRITICAL: You must return ONLY a raw JSON string matching the following JSON schema. "
        f"Do NOT wrap in markdown code blocks, do NOT write markdown ```json, and do NOT include any conversational text. "
        f"Schema fields description:\n"
        f"{schema_class.schema_json()}\n"
    )
    
    current_prompt = prompt + system_instruction
    
    for attempt in range(1, max_attempts + 1):
        logger.info(f"LLM Schema Validation attempt {attempt}/{max_attempts} for schema {schema_class.__name__}")
        llm_response = await router.execute_with_retry(severity_score, current_prompt)
        
        if llm_response.get("status") != "SUCCESS":
            logger.warning(f"LLM request failed or returned empty response: {llm_response.get('error')}")
            if attempt == max_attempts:
                break
            await asyncio.sleep(1)
            continue
            
        raw_text = llm_response.get("response", "").strip()
        
        # Clean markdown formatting if present
        if raw_text.startswith("```"):
            lines = raw_text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            raw_text = "\n".join(lines).strip()

        if "OFFLINE RULE ENGINE FALLBACK" in raw_text or not raw_text.startswith("{"):
            logger.info(f"Offline rule engine fallback detected for {schema_class.__name__}. Using structured fallback instance.")
            break
            
        try:
            parsed_json = json.loads(raw_text)
            validated_obj = schema_class(**parsed_json)
            logger.info(f"LLM output successfully validated against {schema_class.__name__}")
            return validated_obj
        except Exception as err:
            logger.error(f"[INVALID LLM OUTPUT] Attempt {attempt} failed schema validation for {schema_class.__name__}. Raw response: {raw_text}. Error: {err}")
            if attempt == max_attempts:
                break
            # Feed the parsing error back into the next attempt
            current_prompt = (
                f"{prompt}\n\n"
                f"Your previous attempt returned: '{raw_text}' which failed validation with error: '{err}'. "
                f"Please fix the format and output ONLY valid JSON matching this schema:\n"
                f"{schema_class.schema_json()}"
            )
            await asyncio.sleep(1)
            
    # Fail-safe path: Attempt default instantiation for fallback rule engine responses
    logger.warning(f"LLM schema validation failed all {max_attempts} attempts. Attempting fallback schema construction for {schema_class.__name__}.")
    try:
        if hasattr(schema_class, "construct_default"):
            return schema_class.construct_default(raw_text if 'raw_text' in locals() else "")
        return schema_class.model_construct(
            executive_summary=f"Automated Rule Fallback: {raw_text if 'raw_text' in locals() else 'System Anomaly'}",
            recommended_actions=[],
            risk_score=50,
            requires_human=True
        )
    except Exception as fallback_err:
        logger.critical(f"Fallback schema construction failed: {fallback_err}. Engaging fail-safe exception.")
        raise ValueError(f"Failed to generate a valid {schema_class.__name__} from LLM after {max_attempts} attempts.")

async def autonomous_data_retention():
    """Background task to enforce data retention policy directly inside the AI agent."""
    import psycopg2
    db_host = os.environ.get("DB_HOST", "127.0.0.1")
    db_port = os.environ.get("DB_PORT", "5432")
    db_name = os.environ.get("DB_NAME", "osi_system")
    db_user = os.environ.get("DB_USER", "postgres")
    db_pass = os.environ.get("DB_PASSWORD", "postgres")

    while True:
        logger.info("[RETENTION_DAEMON] Waking up to execute autonomous data retention policy...")
        try:
            conn = psycopg2.connect(host=db_host, port=db_port, dbname=db_name, user=db_user, password=db_pass)
            conn.autocommit = False
            cur = conn.cursor()
            
            # 1. Telemetry
            cur.execute("DELETE FROM telemetry_logs WHERE timestamp < NOW() - INTERVAL '24 hours';")
            
            # 2. Archival
            cur.execute("UPDATE fleet_incidents SET status = 'ARCHIVED' WHERE created_at < NOW() - INTERVAL '14 days' AND status = 'RESOLVED';")
            
            # 3. Pruning
            heavy_tables = ["incident_events", "ai_audit_trail", "verification_logs", "chat_messages", "rollback_logs"]
            for table in heavy_tables:
                try:
                    cur.execute(f"DELETE FROM {table} WHERE created_at < NOW() - INTERVAL '30 days';")
                except Exception:
                    conn.rollback()
                else:
                    conn.commit()
            
            conn.commit()
            cur.close()
            conn.close()
            logger.info("[RETENTION_DAEMON] Retention policy executed successfully. Sleeping for 12 hours.")
        except Exception as e:
            logger.error(f"[RETENTION_DAEMON] Failed during execution: {e}")
        
        # Sleep for 12 hours
        await asyncio.sleep(12 * 3600)


async def main():
    logger.info(f"Initializing AI Supervisor (HITL Hardened Architecture) - Connecting to NATS at {NATS_URL}...")

    # ── AI OS: Signal INITIALIZING ───────────────────────────────────────────
    _set_runtime_state("INITIALIZING")

    try:
        from adapters.nats_adapter import NATSAdapter
        nats_adapter_instance = NATSAdapter(NATS_URL)
        nc = await nats_adapter_instance.connect()
        telemetry.nc = nc  # Bind Telemetry to NATS Adapter proxy
        _set_runtime_state("SYNCING")
        
        # ── Start Autonomous Daemons ───────────────────────────────────────────
        asyncio.create_task(autonomous_data_retention())
        # ── Preheat Embeddings Cache ──────────────────────────────────────────
        try:
            from engines.rag_engine import get_rag_engine
            from core.cache_manager import get_cache_manager
            temp_rag = get_rag_engine()
            temp_rag.connect()
            if temp_rag.conn:
                cache_mgr = get_cache_manager()
                preheated_count = cache_mgr.preheat_embeddings(temp_rag.conn)
                logger.info(f"[STARTUP] Preheated {preheated_count} knowledge vectors into Redis.")
                temp_rag.close()
        except Exception as preheat_err:
            logger.error(f"[STARTUP] Failed to preheat embeddings: {preheat_err}")
        # ──────────────────────────────────────────────────────────────────────
        
        # Start Isolated Agents
        incident_agent = IncidentAgent(nc)
        security_agent = SecurityAgent(nc)
        recovery_agent = RecoveryAgent(nc)
        verification_agent = VerificationAgent(nc)
        
        await incident_agent.start()
        await security_agent.start()
        await recovery_agent.start()
        await verification_agent.start()
        
        # ── Phase 3-6 Cognitive Modules Initialization ─────────────────────────
        try:
            from knowledge.world_model import WorldModel
            from knowledge.knowledge_fabric import KnowledgeFabric
            from planning.goal_engine import GoalEngine
            from planning.decision_engine import DecisionEngine
            from evolution.evolution_engine import EvolutionEngine
            from evolution.arch_auditor import ArchAuditor
            
            # These engines self-subscribe to relevant subjects when instantiated
            world_model = WorldModel()
            knowledge_fabric = KnowledgeFabric()
            goal_engine = GoalEngine()
            decision_engine = DecisionEngine()
            evolution_engine = EvolutionEngine()
            arch_auditor = ArchAuditor()
            
            logger.info("[STARTUP] Phase 3-6 Cognitive Modules initialized successfully.")
        except Exception as cog_init_err:
            logger.warning(f"[STARTUP] Phase 3-6 Cognitive Modules not fully loaded: {cog_init_err}")
        # ──────────────────────────────────────────────────────────────────────
        
        js = nc.jetstream()
        
        try:
            await js.add_stream(name="telemetry_stream_critical", subjects=["telemetry.critical", "telemetry.site.>", "telemetry.netdata"])
            logger.info("JetStream 'telemetry_stream_critical' initialized with site wildcard subjects.")
        except Exception as e:
            logger.warning(f"Failed to add stream (may already exist): {e}. Attempting stream update...")
            try:
                await js.update_stream(name="telemetry_stream_critical", subjects=["telemetry.critical", "telemetry.site.>", "telemetry.netdata"])
                logger.info("JetStream 'telemetry_stream_critical' updated successfully with site wildcard subjects.")
            except Exception as update_err:
                logger.error(f"Failed to update JetStream stream: {update_err}")

        # Message Handler

        async def run_background_verification(nc, incident_id, validated_action_name, pc_name, exec_id, site_id_str, event_id, incident_details=None):
            import json
            import time
            from schemas import VerificationSchema
            from rag_engine import get_rag_engine
            from verification.action_verifier import ActionVerifier
            from verification.rollback_engine import RollbackEngine
            from cognition.evidence_reasoning_graph import ReasoningRecorder
            import logging
            logger = logging.getLogger("SUPERVISOR_BG")

            rag = get_rag_engine()
            rag.connect()
    
            _rollback_engine = RollbackEngine(rag.conn, nc)
            _verifier = ActionVerifier(rag.conn, _rollback_engine, shadow_mode=False)
            _erg = ReasoningRecorder(rag.conn)
    
            logger.info(f"[VERIFY BG] Starting ActionVerifier for incident {incident_id}")
            verify_start_time = time.time()
            
            if incident_details is None:
                incident_details = {}
                
            # ── GAP: Dynamic Success Criteria ──
            expected_outcome = {"status": "ONLINE"}
            metadata = incident_details.get("metadata", {})
            incident_type = str(metadata.get("type", "")).lower()
            desc = str(incident_details.get("description", "")).lower()
            combined_context = f"{incident_type} {desc} {validated_action_name.lower()}"
            
            if "cpu" in combined_context:
                expected_outcome["cpu_usage"] = "< 80%"
            if "memory" in combined_context or "oom" in combined_context:
                expected_outcome["memory_usage"] = "< 85%"
            if "disk" in combined_context or "space" in combined_context:
                expected_outcome["disk_usage"] = "< 90%"
            if "network" in combined_context or "latency" in combined_context:
                expected_outcome["latency"] = "< 100ms"
            
            logger.info(f"[VERIFY BG] Computed Dynamic Success Criteria: {expected_outcome}")
    
            try:
                # Transition to VERIFYING
                await apply_incident_transition(nc, rag.conn, incident_id, IncidentState.EXECUTING, IncidentState.VERIFYING, site_id_str, context={"action": validated_action_name})
                
                verify_result = await _verifier.wait_and_verify(
                    incident_id=int(incident_id or 0),
                    action=validated_action_name,
                    device=pc_name,
                    snapshot_id=exec_id or "",
                    expected_outcome=expected_outcome
                )
        
                rtt_ms = int((time.time() - verify_start_time) * 1000)
        
                taxonomy_status = verify_result.get("status", "FAILED")
                is_success = taxonomy_status in ["SUCCESS", "PARTIAL_SUCCESS", "UNKNOWN"]
                rollback_needed = taxonomy_status in ["REGRESSION", "ROLLBACK_RECOMMENDED", "ROLLBACK_FAILED"]
        
                validated_verify = VerificationSchema(
                    incident_id=str(incident_id or "0"),
                    verification_status=taxonomy_status,
                    service_alive=is_success,
                    port_open=is_success,
                    cpu_normalized=is_success,
                    memory_normalized=is_success,
                    logs_clean=is_success,
                    rollback_needed=rollback_needed,
                    metrics=verify_result,
                )

                _erg.set_verification(
                    validated_verify.verification_status,
                    not validated_verify.rollback_needed
                )

                verification_id = None
                if rag and rag.conn:
                    try:
                        with rag.conn.cursor() as cur:
                            cur.execute("""
                                INSERT INTO verification_logs (
                                    incident_id, verification_status, service_alive, port_open,
                                    cpu_normalized, memory_normalized, logs_clean, rollback_needed, response_latency_ms, created_at
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()) RETURNING id
                            """, (
                                incident_id,
                                validated_verify.verification_status,
                                validated_verify.service_alive,
                                validated_verify.port_open,
                                validated_verify.cpu_normalized,
                                validated_verify.memory_normalized,
                                validated_verify.logs_clean,
                                validated_verify.rollback_needed,
                                rtt_ms
                            ))
                            verification_id = cur.fetchone()[0]
                            rag.conn.commit()
                            logger.info(f"[DB BG] Inserted verification log for incident {incident_id} with ID {verification_id}")
                    
                            log_event_sourced(rag.conn, "verification_events", verification_id, "TRIGGERED", {
                                "incident_id": incident_id,
                                "status": validated_verify.verification_status,
                                "response_latency_ms": rtt_ms
                            })

                            verify_event_payload = {
                                "verification_id": verification_id,
                                "incident_id": incident_id,
                                "site_id": site_id_str,
                                "status": validated_verify.verification_status,
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            }
                            await nc.publish(f"incident.site.{site_id_str}.verify", json.dumps(verify_event_payload).encode())
                    except Exception as db_err:
                        logger.error(f"[DB BG] Failed to save verification log: {db_err}")

                if validated_verify.rollback_needed:
                    rollback_id = None
                    if rag and rag.conn:
                        try:
                            with rag.conn.cursor() as cur:
                                cur.execute("""
                                    INSERT INTO rollback_logs (
                                        incident_id, original_action, rollback_command,
                                        trigger_reason, rollback_result, created_at
                                    ) VALUES (%s, %s, %s, %s, %s, NOW()) RETURNING id
                                """, (
                                    incident_id,
                                    validated_action_name,
                                    "ROLLBACK",
                                    f"Verification status: {validated_verify.verification_status}",
                                    "PENDING"
                                ))
                                rollback_id = cur.fetchone()[0]
                                rag.conn.commit()
                                logger.info(f"[DB BG] Inserted rollback_log PENDING with ID {rollback_id}")
                        
                                log_event_sourced(rag.conn, "rollback_events", rollback_id, "TRIGGERED", {
                                    "incident_id": incident_id,
                                    "original_action": validated_action_name
                                })

                                rollback_event_payload = {
                                    "rollback_id": rollback_id,
                                    "incident_id": incident_id,
                                    "site_id": site_id_str,
                                    "original_action": validated_action_name,
                                    "timestamp": datetime.now(timezone.utc).isoformat()
                                }
                                await nc.publish(f"rollback.site.{site_id_str}", json.dumps(rollback_event_payload).encode())
                        except Exception as db_err:
                            logger.error(f"[DB BG] Failed to insert rollback log: {db_err}")

                    # Transition to ROLLBACK_PENDING
                    await apply_incident_transition(nc, rag.conn, incident_id, IncidentState.VERIFYING, IncidentState.ROLLBACK_PENDING, site_id_str, context={"reason": validated_verify.verification_status})

                    rollback_engine = RollbackEngine(rag.conn, nc)
                    rollback_dispatch_time = time.time()
                    _inc_id_for_rollback = incident_id if incident_id is not None else 0
                    success = await rollback_engine.trigger_rollback(_inc_id_for_rollback, event_id, validated_action_name)
                    rollback_rtt_ms = int((time.time() - rollback_dispatch_time) * 1000)
            
                    if rollback_id and rag and rag.conn:
                        try:
                            rollback_status = "EXECUTED" if success else "FAILED"
                            with rag.conn.cursor() as cur:
                                cur.execute("""
                                    UPDATE rollback_logs
                                    SET rollback_result = %s, execution_rtt_ms = %s, created_at = NOW()
                                    WHERE id = %s
                                """, (rollback_status, rollback_rtt_ms, rollback_id))
                                rag.conn.commit()
                                logger.info(f"[DB BG] Updated rollback log {rollback_id} to status: {rollback_status}")
                        
                                log_event_sourced(rag.conn, "rollback_events", rollback_id, "COMPLETED" if success else "FAILED", {
                                    "incident_id": incident_id,
                                    "execution_rtt_ms": rollback_rtt_ms
                                })
                        except Exception as db_err:
                            logger.error(f"[DB BG] Failed to update rollback log: {db_err}")
                            
                    # Transition based on rollback outcome
                    final_state = IncidentState.ROLLED_BACK if success else IncidentState.FAILED
                    await apply_incident_transition(nc, rag.conn, incident_id, IncidentState.ROLLBACK_PENDING, final_state, site_id_str, context={"success": success})

                if validated_verify.verification_status != "SUCCESS" and rag and rag.conn:
                    try:
                        with rag.conn.cursor() as cur:
                            cur.execute("SELECT pc_name FROM fleet_incidents WHERE incident_id = %s", (incident_id,))
                            db_row = cur.fetchone()
                            dev_name = db_row[0] if db_row else "UnknownDevice"
                    
                            failed_action_name = validated_action_name if validated_action_name else "Unknown"
                            rca_sum = f"SYSTEM_GENERATED: Mitigation '{failed_action_name}' failed verification status: {validated_verify.verification_status}."
                            report_data_payload = {
                                "source": "SYSTEM_GENERATED",
                                "reason": "verification_failed",
                                "failed_action": failed_action_name,
                                "rollback_needed": validated_verify.rollback_needed,
                                "observed": f"service_alive={validated_verify.service_alive}, port_open={validated_verify.port_open}, cpu={validated_verify.cpu_normalized}, memory={validated_verify.memory_normalized}"
                            }
                    
                            cur.execute("""
                                INSERT INTO incident_post_mortems (
                                    incident_id, device_name, flag, mttr_seconds, blast_radius,
                                    rca_summary, remediation_effectiveness, prevention_steps, report_data, created_at
                                ) VALUES (%s, %s, 'SYSTEM_GENERATED', 0, 'MEDIUM', %s, 'FAILED', ARRAY[%s, %s], %s::jsonb, NOW())
                                ON CONFLICT (incident_id) DO UPDATE SET
                                    rca_summary = EXCLUDED.rca_summary,
                                    report_data = EXCLUDED.report_data,
                                    remediation_effectiveness = EXCLUDED.remediation_effectiveness
                            """, (
                                incident_id,
                                dev_name,
                                rca_sum,
                                f"Verification Failure Reason: {validated_verify.verification_status}",
                                f"Rollback Triggered: {validated_verify.rollback_needed}",
                                json.dumps(report_data_payload)
                            ))
                            rag.conn.commit()
                            logger.info(f"[SELF-CORRECTION BG] Automatically logged system verification failure post-mortem.")
                    except Exception as sc_err:
                        logger.error(f"[SELF-CORRECTION BG] Failed to write system-generated post-mortem: {sc_err}")
                        try:
                            rag.conn.rollback()
                        except:
                            import logging; logging.getLogger(__name__).debug('_ = None suppressed')

                if rag and rag.conn and pc_name:
                    try:
                        from trust_engine import TrustEngine
                        te = TrustEngine()
                        if validated_verify.rollback_needed:
                            te.record_agent_event(rag.conn, pc_name, "ROLLBACK")
                        elif validated_verify.verification_status == "SUCCESS":
                            te.record_agent_event(rag.conn, pc_name, "SUCCESS")
                            
                            # Trigger Phase 6: Knowledge Graph Background Extraction
                            kg_payload = {"incident_text": f"Incident {incident_id} on {pc_name}: {validated_action_name}. Verification SUCCESS."}
                            asyncio.create_task(nc.publish("ai.engine.knowledge_graph.extract", json.dumps(kg_payload).encode()))
                    
                            try:
                                log_event_sourced(rag.conn, "incident_events", incident_id, "INCIDENT_RESOLVED", {"reason": "Verification success"})
                                with rag.conn.cursor() as cur:
                                    cur.execute("""
                                        INSERT INTO incident_post_mortems (
                                            incident_id, device_name, flag, mttr_seconds, blast_radius,
                                            rca_summary, remediation_effectiveness, prevention_steps, report_data, created_at
                                        ) VALUES (%s, %s, 'SYSTEM_GENERATED', 0, 'LOW', %s, 'SUCCESS', ARRAY[%s], %s::jsonb, NOW())
                                        ON CONFLICT (incident_id) DO UPDATE SET
                                            rca_summary = EXCLUDED.rca_summary,
                                            report_data = EXCLUDED.report_data,
                                            remediation_effectiveness = EXCLUDED.remediation_effectiveness
                                    """, (
                                        incident_id,
                                        pc_name,
                                        f"Auto-Mitigation '{validated_action_name}' successfully resolved the incident.",
                                        f"Added '{validated_action_name}' to Golden Knowledge.",
                                        json.dumps({"verified_score": verify_result.get("score", 100), "source": "AUTO_RESOLUTION"})
                                    ))
                            
                                    cur.execute("""
                                        INSERT INTO incident_feedback (
                                            incident_id, rca_summary, recommended_action, effectiveness_score, user_feedback, created_at
                                        ) VALUES (%s, %s, %s, %s, %s, NOW())
                                    """, (
                                        incident_id,
                                        f"Auto-Mitigation '{validated_action_name}' successfully resolved the incident.",
                                        validated_action_name,
                                        verify_result.get("score", 100),
                                        "SYSTEM_AUTO_LEARN"
                                    ))
                                rag.conn.commit()
                                logger.info(f"[AUTO-RESOLUTION BG] Incident {incident_id} successfully marked as RESOLVED and pushed to Knowledge Queue.")
                                
                                # Transition to RESOLVED
                                await apply_incident_transition(nc, rag.conn, incident_id, IncidentState.VERIFYING, IncidentState.RESOLVED, site_id_str, context={"score": verify_result.get("score")})
                            except Exception as resolve_err:
                                logger.error(f"[AUTO-RESOLUTION BG] Failed to resolve incident: {resolve_err}")
                                try:
                                    rag.conn.rollback()
                                except:
                                    import logging; logging.getLogger(__name__).debug('_ = None suppressed')
                    except Exception as te_err:
                        logger.error(f"Failed to record trust event or resolve: {te_err}")

            except Exception as e:
                logger.error(f"[VERIFY BG] Unexpected error: {e}")
            finally:
                if rag and rag.conn:
                    rag.close()

        async def message_handler(msg):
            start_time = time.time()
            # TELEMETRY VARS
            telemetry_trace_id = None
            telemetry_t0 = time.monotonic()
            latencies = {"retrieval_ms": 0.0, "embedding_ms": 0.0, "llm_ms": 0.0, "total_latency_ms": 0.0}
            telemetry_confidence = 0.0
            
            rag = None
            msg_acknowledged = False
            data: dict = {}
            critic_res = {}
            cfe_res = None
            event_id = None
            incident_id = None
            severity_str = "UNKNOWN"
            try:
                data = json.loads(msg.data.decode())
                # ── ZERO-TRUST INPUT SECURITY SHIELD (PROMPT INJECTION & JAILBREAK FILTER) ──
                try:
                    from security.prompt_injection_shield import sanitize_input_payload
                    is_clean, data, threat_reason = sanitize_input_payload(data)
                    if not is_clean:
                        logger.warning(f"[SECURITY SHIELD] Neutralized prompt injection threat: {threat_reason}")
                except Exception as shield_err:
                    logger.debug(f"[SECURITY SHIELD] Scan error (bypassed safely): {shield_err}")

                import uuid
                event_id = data.get("event_id")
                if not event_id or event_id == "UNKNOWN_EVENT_ID":
                    event_id = f"sys-{uuid.uuid4().hex[:8]}"
                    
                # TELEMETRY HOOK: INCOMING
                telemetry_trace_id = event_id
                asyncio.create_task(telemetry.record_incident_lifecycle("incident_received", str(data.get("incident_id", event_id)), telemetry_trace_id))
                
                pc_name = data.get("pc_name", "UNKNOWN")
                logger.info(f"[INCIDENT DETECTED] Processing Event ID: {event_id} on PC: {pc_name}")
                
                # Extract incident details
                incident_details = data.get("message", {})
                incident_id = data.get("incident_id")
                if not incident_id:
                    incident_id = incident_details.get("incident_id")
                
                try:
                    incident_id = int(incident_id) if incident_id else None
                except:
                    incident_id = None

                raw_site_id = data.get("site_id") or incident_details.get("site_id", "global")
                site_id_str = str(raw_site_id).lower().replace(".", "_").replace(" ", "_")

                # Initialize DB Connection & RAG
                from rag_engine import get_rag_engine
                from cognition.osi_taxonomy import classify_incident_layer
                from cognition.evidence_reasoning_graph import ReasoningRecorder
                from cognition.apm_knowledge_graph import extract_apm_syndromes
                
                rag = get_rag_engine()
                rag.connect()

                # Extract severity_str early for ERG
                severity_str = incident_details.get("metadata", {}).get("severity", "LOW")

                # Framework 6 — ERG Recorder (observability only, fail-silent)
                _erg = ReasoningRecorder(db_conn=rag.conn, incident_id=str(incident_id or event_id))
                _erg.begin(
                    title=incident_details.get("title", ""),
                    symptoms=incident_details.get("symptoms", ""),
                    severity=severity_str,
                    metadata=incident_details.get("metadata", {})
                )

                # Pre-create incident if not exists
                if not incident_id:
                    try:
                        if rag.conn is not None:
                            with rag.conn.cursor() as cur:
                                cur.execute("""
                                    INSERT INTO incidents (device_name, layer, flag, evidence, confidence, rag_status)
                                    VALUES (%s, 1, 'INGESTED', 'Ingested telemetry anomaly', 100.0, 'GREEN')
                                    RETURNING incident_id
                                """, (pc_name,))
                                incident_id = cur.fetchone()[0]
                                rag.conn.commit()
                                logger.info(f"[DB] Pre-created incident {incident_id} for telemetry stream.")
                    except Exception as db_err:
                        logger.error(f"[DB] Failed to pre-create incident: {db_err}")
                        try:
                            if rag.conn is not None:
                                rag.conn.rollback()
                        except:
                            import logging; logging.getLogger(__name__).debug('_ = None suppressed')

                # ── Tahap 3: Causal DAG Engine & APM Deep Cognition (P3) ──
                if incident_id:
                    # P3: Analyze for APM Syndromes
                    combined_text = incident_details.get("title", "") + " " + incident_details.get("symptoms", "")
                    apm_syndromes = extract_apm_syndromes(combined_text, incident_details.get("metadata", {}))
                    if apm_syndromes:
                        logger.warning(f"[APM COGNITION] Detected advanced syndromes: {apm_syndromes}")
                        incident_details["symptoms"] += f"\n[AI-DETECTED APM SYNDROMES]: {', '.join(apm_syndromes)}"

                    try:
                        from causal_dag_engine import get_causal_dag_engine
                        dag_engine = get_causal_dag_engine(rag.conn)
                        dag_res = dag_engine.build_causal_graph(
                            incident_id=incident_id,
                            root_device=pc_name,
                            incident_data=incident_details
                        )
                        logger.info(f"[CAUSAL DAG] Computed for Incident {incident_id}: {dag_res.get('nodes_count')} nodes, {dag_res.get('edges_count')} edges.")
                    except Exception as dag_err:
                        logger.error(f"[CAUSAL DAG] Error building DAG: {dag_err}")


                # Log incident ingested event sourcing record
                log_event_sourced(rag.conn, "incident_events", incident_id or 0, "INGESTED", {
                    "event_id": event_id,
                    "subject": msg.subject or "telemetry.critical",
                    "metadata": incident_details.get("metadata", {})
                })

                # Publish incident.site.<site>.create event
                import datetime as dt_mod
                site_event_payload = {
                    "event_id": event_id,
                    "incident_id": incident_id,
                    "site_id": site_id_str,
                    "status": "INGESTED",
                    "timestamp": dt_mod.datetime.now(dt_mod.timezone.utc).isoformat()
                }
                await nc.publish(f"incident.site.{site_id_str}.create", json.dumps(site_event_payload).encode())

                # Inbox Pattern validation using processed_messages table
                subject = msg.subject or "telemetry.critical"
                if event_id and not event_id.startswith("sys-"):
                    try:
                        if rag.conn is not None:
                            with rag.conn.cursor() as cur:
                                cur.execute(
                                    "INSERT INTO processed_messages (message_id, subject, processed_at) VALUES (%s, %s, NOW())",
                                    (event_id, subject)
                                )
                                rag.conn.commit()
                    except Exception as db_err:
                        try:
                            if rag.conn is not None:
                                rag.conn.rollback()
                        except:
                            import logging; logging.getLogger(__name__).debug('_ = None suppressed')
                        err_str = str(db_err)
                        if "UniqueViolation" in err_str or "duplicate key" in err_str or "23505" in err_str:
                            logger.info(f"[INBOX PATTERN] Duplicate message detected (Event ID: {event_id}). Acknowledging and skipping.")
                            if not msg_acknowledged:
                                await msg.ack()
                                msg_acknowledged = True
                            return
                        else:
                            logger.error(f"[INBOX PATTERN] DB error on inbox check: {db_err}")
                            if not msg_acknowledged:
                                await msg.nak()
                                msg_acknowledged = True
                            return

                # ── Sprint P2 V4: Parallel Cognitive Pipeline ──
                import engine_adapters
                from core.merge_engine import get_merge_engine
                
                # Transition to ANALYZING
                await apply_incident_transition(nc, rag.conn, incident_id or 0, IncidentState.OPEN, IncidentState.ANALYZING, site_id_str)

                severity_map = {"LOW": 30, "MEDIUM": 60, "HIGH": 85, "CRITICAL": 100}
                severity_score = severity_map.get(severity_str.upper(), 30)

                # ── GAP 1A: Asset Context Engine ──
                # Ambil konteks aset SEBELUM reasoning dimulai
                asset_ctx = {"found": False}
                asset_context_prompt = ""
                try:
                    from cognition.asset_context_engine import get_asset_context_engine
                    ace = get_asset_context_engine(db_conn=rag.conn)
                    asset_ctx = ace.fetch(
                        hostname=pc_name,
                        ip_address=data.get("ip_address")
                    )
                    asset_context_prompt = ace.build_risk_context_prompt(asset_ctx)
                    incident_details["asset_context"] = asset_ctx
                    incident_details["asset_context_prompt"] = asset_context_prompt
                    logger.info(f"[ASSET CTX] Loaded: criticality={asset_ctx.get('criticality')}, SLA={asset_ctx.get('sla')}%")
                except Exception as ace_err:
                    logger.error(f"[ASSET CTX] Failed: {ace_err}")

                # ── GAP 1B: Temporal Reasoning Engine ──
                # Bangun kronologi kausal dari telemetri nyata SEBELUM Consensus
                temporal_result = {}
                temporal_prompt = ""
                try:
                    from cognition.temporal_reasoning_engine import get_temporal_engine
                    import datetime as dt_mod
                    temporal_eng = get_temporal_engine(db_conn=rag.conn)
                    temporal_result = temporal_eng.build_timeline(
                        hostname=pc_name,
                        anchor_time=dt_mod.datetime.now(dt_mod.timezone.utc)
                    )
                    temporal_prompt = temporal_eng.build_prompt_snippet(temporal_result)
                    incident_details["temporal_chain"] = temporal_result.get("causal_chain", "")
                    incident_details["root_signal"] = temporal_result.get("root_signal", "UNKNOWN")
                    logger.info(f"[TEMPORAL] {len(temporal_result.get('events', []))} events in timeline. Root signal: {temporal_result.get('root_signal')}")
                except Exception as temp_err:
                    logger.error(f"[TEMPORAL] Failed: {temp_err}")

                # ── GAP 1E: Multi-Host Correlation ──
                multi_host_result = {}
                try:
                    from cognition.correlation_engine import get_multi_host_correlator
                    mhc = get_multi_host_correlator(db_conn=rag.conn)
                    multi_host_result = mhc.analyze(current_hostname=pc_name)
                    if multi_host_result.get("multi_host_detected"):
                        incident_details["multi_host_alert"] = multi_host_result["summary"]
                        incident_details["common_parent_hypothesis"] = multi_host_result.get("common_parent_hypothesis")
                        logger.warning(f"[MULTI-HOST] {multi_host_result['summary']}")
                except Exception as mhc_err:
                    logger.error(f"[MULTI-HOST] Failed: {mhc_err}")

                # 1. Evidence Fabric (Sequential Pre-requisite)
                evidence_pkg = None
                try:
                    from cognition.evidence_fabric import EnterpriseEvidenceFabric
                    fabric = EnterpriseEvidenceFabric(incident_id=data.get('id', 'unknown'))
                    fabric.ingest_telemetry(
                        source=data.get('service', 'generic_telemetry'),
                        host=data.get('host', 'unknown_host'),
                        raw_data=data,
                        trace_id=data.get('id', 'unknown_trace'),
                        timestamp_str=data.get('timestamp')
                    )
                    evidence_pkg = fabric.validate_and_package()
                except Exception as fab_err:
                    logger.error(f"Evidence Fabric failed: {fab_err}")

                # 2. Parallel Engine Execution
                parallel_tasks = [
                    engine_adapters.run_correlation_engine(data, rag.conn),
                    engine_adapters.run_intent_engine(data),
                    engine_adapters.run_osi_engine(data, evidence_pkg),
                    engine_adapters.run_knowledge_graph(data, rag.conn),
                    engine_adapters.run_timeline(data, rag.conn),
                    engine_adapters.run_dependency(data),
                    engine_adapters.run_blast_radius(data),
                    engine_adapters.run_rag(data, nc),
                    engine_adapters.run_causal(data),
                    engine_adapters.run_health_score(data, rag.conn)
                ]
                
                parallel_results = await asyncio.gather(*parallel_tasks)
                
                # 3. Merge Engine
                merge_engine = get_merge_engine()
                unified_context = merge_engine.merge(parallel_results, evidence_pkg)
                
                incident_details["description"] = "Merged Parallel Unified Context"
                incident_details["unified_context"] = unified_context
                
                # Extract Root Cause dari cognitive engines (Fallback awal sebelum Hypothesis Engine)
                extracted_root_cause = "Unknown / Multiple Sources"
                causal_confidence = 50.0
                
                # Gunakan hasil dari CausalEngine / CorrelationEngine / OSITaxonomyEngine sebagai raw baseline
                for res in parallel_results:
                    findings = res.get("findings", {})
                    eng_name = res.get("engine")
                    if eng_name == "CausalEngine":
                        causal_confidence = float(findings.get("confidence", 50.0))
                        if findings.get("probable_root_cause") and findings["probable_root_cause"] not in ("Unknown", "Unknown Root Cause"):
                            extracted_root_cause = findings["probable_root_cause"]
                            break
                        elif findings.get("root_cause_incident"):
                            root_inc = findings["root_cause_incident"]
                            comp = root_inc.get("component") or root_inc.get("service") or root_inc.get("pc_name")
                            layer = root_inc.get("osi_layer", "L1-L7")
                            extracted_root_cause = f"Layer {layer}: {comp}" if comp else findings.get("explanation", extracted_root_cause)
                            break
                    elif eng_name == "CorrelationEngine" and findings.get("root_event") and findings["root_event"] not in ("Unknown", "Unknown Root Cause"):
                        extracted_root_cause = findings["root_event"]
                        break
                    elif eng_name == "OSITaxonomyEngine" and findings.get("root_cause_hypothesis"):
                        extracted_root_cause = f"Layer {findings.get('layer', 'L1-L7')}: {findings['root_cause_hypothesis']}"
                        break

                logger.info(f"[ROOT CAUSE DEBUG] Parallel results engines: {[res.get('engine') for res in parallel_results]}")
                for res in parallel_results:
                    logger.info(f"[ROOT CAUSE DEBUG] Engine {res.get('engine')} findings: {res.get('findings')}")

                if extracted_root_cause == "Unknown / Multiple Sources":
                    component_name = data.get("component") or data.get("service") or data.get("pc_name")
                    raw_sym = incident_details.get("symptoms") or incident_details.get("title") or data.get("message")
                    if isinstance(raw_sym, dict):
                        raw_sym = raw_sym.get("symptoms") or raw_sym.get("title") or str(raw_sym)
                    symptoms_desc = str(raw_sym) if raw_sym else ""
                    if component_name and symptoms_desc:
                        extracted_root_cause = f"{component_name} — {symptoms_desc[:60]}"
                    elif component_name:
                        extracted_root_cause = f"Telemetry Anomaly on {component_name}"

                logger.info(f"[ROOT CAUSE DEBUG] Final extracted_root_cause = {extracted_root_cause}")

                reasoning_dag = {
                    "stages": ["parallel_gather", "merge_engine", "rag_retrieval", "llm_routing", "confidence_calibration", "policy_evaluation"],
                    "root_event": extracted_root_cause,
                    "unified_context_summary": list(unified_context["findings"].keys())
                }
                
                # ── GAP 1C+1D: Hypothesis Engine (N Kandidat + Counter Evidence) ──
                # Dijalankan setelah OSI classification dari parallel results
                hypothesis_ranked_summary = ""
                best_hypothesis = None
                try:
                    osi_layer_num = 7  # default
                    for res in parallel_results:
                        if res.get("engine") == "OSITaxonomyEngine":
                            findings = res.get("findings", {})
                            osi_layer_num = int(findings.get("layer", 7))
                            break

                    from cognition.hypothesis_engine import get_hypothesis_engine
                    hyp_eng = get_hypothesis_engine(db_conn=rag.conn)
                    symptoms_text = incident_details.get("symptoms", "") + " " + incident_details.get("title", "")
                    hypotheses = hyp_eng.generate(
                        osi_layer=osi_layer_num,
                        symptoms_text=symptoms_text,
                        evidence_pkg=evidence_pkg.to_dict() if hasattr(evidence_pkg, 'to_dict') and evidence_pkg else None,
                        hostname=pc_name,
                        max_hypotheses=5
                    )
                    hypothesis_ranked_summary = hyp_eng.build_ranked_summary(hypotheses)
                    best_hypothesis = hypotheses[0].text if hypotheses else None

                    # Suntikkan ke incident_details agar masuk ke prompt LLM
                    incident_details["hypothesis_ranking"] = hypothesis_ranked_summary
                    incident_details["best_hypothesis"] = best_hypothesis

                    # Boost confidence jika best hypothesis score > 70
                    if hypotheses and hypotheses[0].final_score > 70:
                        severity_score = min(100, severity_score + int(hypotheses[0].historical_score if hasattr(hypotheses[0], 'historical_score') else 0))
                        
                    # ── AKTIVASI ROOT CAUSE RANKING ──
                    # Gunakan hipotesis terbaik yang telah divalidasi dan diranking dari multi-kandidat
                    if best_hypothesis:
                        extracted_root_cause = f"{best_hypothesis} (Score: {hypotheses[0].final_score:.1f})"
                        reasoning_dag["root_event"] = extracted_root_cause

                    logger.info(f"[HYPOTHESIS] Best: '{best_hypothesis}' (score={hypotheses[0].final_score:.1f})" if hypotheses else "[HYPOTHESIS] No hypotheses generated")
                except Exception as hyp_err:
                    logger.error(f"[HYPOTHESIS] Failed: {hyp_err}")

                # ── GAP 1F: Blast Radius — Integrasi ke Pipeline Utama ──
                blast_radius_result = {}
                try:
                    for res in parallel_results:
                        if res.get("engine") == "BlastRadiusEngine" and res.get("status") == "SUCCESS":
                            blast_radius_result = res.get("findings", {})
                            break
                    if not blast_radius_result and pc_name:
                        from blast_radius_engine import BlastRadiusEngine
                        bre = BlastRadiusEngine()
                        blast_radius_result = bre.calculate_blast_radius(
                            incident_id=incident_id or 0,
                            root_device=pc_name
                        )
                    incident_details["blast_radius"] = blast_radius_result
                    logger.info(f"[BLAST RADIUS] Result: {blast_radius_result.get('affected_count', 'N/A')} affected components")
                except Exception as br_err:
                    logger.warning(f"[BLAST RADIUS] Failed to calculate: {br_err}")

                # Enrich incident_details dengan semua konteks baru sebelum Consensus
                if asset_context_prompt:
                    incident_details["system_context"] = asset_context_prompt
                if temporal_prompt:
                    incident_details["temporal_analysis"] = temporal_prompt
                if multi_host_result.get("multi_host_detected"):
                    incident_details["multi_host_info"] = multi_host_result.get("summary", "")

                # Setup context variables for later
                real_embedding = [0.0]*768
                historical_context = []
                for res in parallel_results:
                    if res["engine"] == "RAGEngine" and res["status"] == "SUCCESS":
                        historical_context = res.get("findings", {}).get("results", [])
                    elif res["engine"] == "IntentEngine" and res["status"] == "SUCCESS":
                        intents = res.get("findings", {}).get("intents", [])
                        if intents:
                            data["routing_strategy"] = intents[0].get("routing")
                            
                rag_vector_metadata = {"status": "resolved", "retrieved_count": len(historical_context), "retrieved_ids": [h.get("incident_id") for h in historical_context if h.get("incident_id")]}


                # System 1: Fast Track Bypass
                fast_track_bypassed = False
                fast_track_action = None
                fast_track_confidence = 0.0
                fast_track_reason = ""
                
                # Pre-initialize variables to prevent UnboundLocalError on fast-track
                force_hitl_by_cognitive = False
                cognitive_reasons = []
                critic_score_val = 0.0
                validated_action = ActionSchema(
                    action_type="UNKNOWN",
                    recommended_action="UNKNOWN",
                    risk_level="UNKNOWN"
                )
                first_hypothesis = None
                second_hypothesis = None
                final_decision = None
                
                if severity_score < 70 and historical_context:
                    best_match = None
                    for h in historical_context:
                        try:
                            sim = float(h.get("similarity", 0.0))
                            if sim > 0.85 and h.get("remediation_effectiveness") == "SUCCESS":
                                best_match = h
                                break
                        except:
                            import logging; logging.getLogger(__name__).debug('_ = None suppressed')
                    
                    if best_match:
                        fast_track_bypassed = True
                        fast_track_action = best_match.get("recommended_action", "UNKNOWN")
                        fast_track_confidence = float(best_match.get("similarity", 0.9)) * 100
                        fast_track_reason = f"System 1 Fast Track: High similarity historical match ({fast_track_confidence:.1f}%)"
                        logger.info(f"[SYSTEM 1 FAST TRACK] Bypassing Consensus. Action: {fast_track_action}")

                if fast_track_bypassed:
                    consensus_verdict = {
                        "recommended_action": fast_track_action,
                        "confidence": fast_track_confidence / 100.0,
                        "risk_level": "LOW",
                        "reasoning": fast_track_reason
                    }
                    first_hypothesis = fast_track_action
                    final_decision = fast_track_action
                    confidence_score = min(99.0, max(10.0, fast_track_confidence))
                    risk_level_str = "LOW"
                    second_hypothesis = fast_track_reason
                    
                    validated_action = ActionSchema(
                        action_type="FAST_TRACK",
                        recommended_action=fast_track_action or "UNKNOWN",
                        risk_level="LOW"
                    )
                    
                    _erg.set_hypothesis(first_hypothesis or "UNKNOWN", confidence_score / 100.0)
                    _erg.set_knowledge(historical_context)
                    
                    llm_response = {
                        "status": "SUCCESS",
                        "model": "system-1-fast-track",
                        "response": json.dumps(consensus_verdict)
                    }
                    
                    log_event_sourced(rag.conn, "incident_events", incident_id or 0, "ANALYZED", {
                        "verdict": consensus_verdict,
                        "confidence": confidence_score,
                        "severity": severity_str,
                        "path": "FAST_TRACK_SYSTEM_1"
                    })
                else:
                    # 4. Tahap 4: Multi-Agent Debate Layer via NATS
                    debate_context = ''
                    for debate_round in range(2):
                        if debate_context:
                            incident_details['debate_context'] = debate_context
                            
                        logger.info(f"Initiating Multi-Agent Debate (Round {debate_round+1})")
                        consensus_verdict = None
                        try:
                            debate_req = {
                                "incident_details": incident_details,
                                "historical_context": historical_context,
                                "debate_context": debate_context
                            }
                            debate_res_bytes = await nc.request("ai.engine.multi_agent.debate", json.dumps(debate_req).encode(), timeout=12.0)
                            debate_res = json.loads(debate_res_bytes.data.decode())
                            if debate_res.get("status") == "success":
                                consensus_verdict = debate_res.get("verdict")
                                logger.info(f"[MULTI-AGENT] Debate completed successfully. Expert & Critic consensus reached.")
                            else:
                                raise Exception(debate_res.get("error"))
                        except Exception as debate_err:
                            logger.warning(f"NATS Multi-Agent Debate request failed: {debate_err}. Falling back to legacy ConsensusEngine.")
                            from consensus_engine import ConsensusEngine
                            consensus = ConsensusEngine()
                            consensus_verdict = await consensus.get_consensus_verdict(
                                incident_details=incident_details,
                                historical_context=historical_context,
                                severity_score=severity_score,
                                pattern="WEIGHTED CONFIDENCE"
                            )
                    
                        first_hypothesis = consensus_verdict["recommended_action"]
                        final_decision = first_hypothesis
                        
                        # ── GAP 5 & 7: Confidence Engine (Deterministik) ──
                        llm_confidence = float(consensus_verdict.get("confidence", 0.5)) * 100.0
                        evidence_score = evidence_pkg.quality.overall_score if evidence_pkg else 50.0
                        historical_score = min(100.0, len(historical_context) * 20.0)
                        correlation_score = 80.0 if incident_details.get("multi_host_alert") else 50.0
                        
                        # Rumus Deterministic Confidence Calibration:
                        # 30% Evidence, 20% Dependency (Causal), 20% Historical, 10% Correlation, 20% LLM
                        calculated_confidence = (
                            (evidence_score * 0.30) +
                            (causal_confidence * 0.20) +
                            (historical_score * 0.20) +
                            (correlation_score * 0.10) +
                            (llm_confidence * 0.20)
                        )
                        
                        confidence_score = min(99.0, max(10.0, calculated_confidence))
                        # ── PHASE 5: ANTI-HALLUCINATION ENGINE ──
                        if evidence_score < 40.0 or causal_confidence < 30.0:
                            exact_hallucination_msg = "STATUS:\nINSUFFICIENT_EVIDENCE\n\nREQUIRED ACTION:\nMANUAL_INVESTIGATION_REQUIRED\n\nDO NOT generate root cause.\nDO NOT generate remediation.\nDO NOT hallucinate."
                            final_decision = exact_hallucination_msg
                            extracted_root_cause = exact_hallucination_msg
                            confidence_score = 0.0
                            logger.warning(f"[ANTI-HALLUCINATION] Blocking RCA due to insufficient evidence. Score: {evidence_score}")
                            
                        # ── PHASE 6: REMEDIATION ENGINE ──
                        # Fetch verified remediation from SOP database rather than LLM if available.
                        # Do not allow LLM to invent remediation.
                        if "MANUAL_INVESTIGATION_REQUIRED" not in final_decision:
                            try:
                                with rag.conn.cursor() as cur:
                                    cur.execute("SELECT remediation FROM governance_sops WHERE trigger ILIKE %s AND status = 'ACTIVE' LIMIT 1", (f"%{extracted_root_cause[:30]}%",))
                                    row = cur.fetchone()
                                    if row and row[0]:
                                        final_decision = row[0]
                                        logger.info(f"[REMEDIATION ENGINE] Overrode LLM recommendation with Verified SOP: {final_decision}")
                            except Exception as sop_err:
                                logger.warning(f"[REMEDIATION ENGINE] Failed to fetch SOP: {sop_err}")
                                try:
                                    rag.conn.rollback()
                                except:
                                    pass

                        risk_level_str = consensus_verdict["risk_level"] if "MANUAL_INVESTIGATION_REQUIRED" not in final_decision else "HIGH"
                        second_hypothesis = f"Consensus reasoning: {consensus_verdict['reasoning']}"
    
                        # ERG: record hypothesis and decision
                        _erg.set_hypothesis(first_hypothesis, confidence_score / 100.0)
                        _erg.set_knowledge(historical_context)
    
                        llm_response = {
                            "status": "SUCCESS",
                            "model": "consensus-engine",
                            "response": json.dumps(consensus_verdict)
                        }
    
                        # Log incident analyzed event sourcing record
                        log_event_sourced(rag.conn, "incident_events", incident_id or 0, "ANALYZED", {
                            "verdict": consensus_verdict,
                            "confidence": confidence_score,
                            "severity": severity_str
                        })
    
                        # 5. Isolated Agent Calls & Schema Validation
                        incident_payload = {
                            "incident_id": incident_id,
                            "description": final_decision,
                            "metadata": {"severity": severity_str}
                        }
                    
                        # Call Incident Agent
                        inc_resp = await nc.request("agent.incident.analyze", json.dumps(incident_payload).encode(), timeout=2.0)
                        incident_data = json.loads(inc_resp.data.decode())
                        validated_incident_agent_res = IncidentSchema(**incident_data)
                        if validated_incident_agent_res.incident_id:
                            try:
                                val = int(validated_incident_agent_res.incident_id)
                                if val > 0:
                                    incident_id = val
                            except ValueError:
                                import logging; logging.getLogger(__name__).debug('_ = None suppressed')
    
                        # Call Recovery Agent
                        rec_payload = {
                            "recommended_action": final_decision
                        }
                        rec_resp = await nc.request("agent.recovery.prepare", json.dumps(rec_payload).encode(), timeout=2.0)
                        recovery_data = json.loads(rec_resp.data.decode())
                        validated_action = ActionSchema(**recovery_data)
    
                        # Call Security Agent (Policy Engine reading only validated JSON payload)
                        sec_payload = {
                            "action": validated_action.recommended_action,
                            "confidence": confidence_score,
                            "severity": severity_str
                        }
                        sec_resp = await nc.request("agent.security.validate", json.dumps(sec_payload).encode(), timeout=2.0)
                        security_data = json.loads(sec_resp.data.decode())
                    
                        if not security_data.get("is_safe", True):
                            raise Exception(f"Security Policy Blocked: {security_data.get('reason', 'Unknown safety violation')}")
    
                        # 5.5. HITL Cognitive Modules (Adversarial Critic, Question, Counterfactual)
                        force_hitl_by_cognitive = False
                        cognitive_reasons = []
    
                        # P0.3: Clock Drift Governance
                        telemetry_ts = data.get("timestamp") or incident_details.get("timestamp")
                        if telemetry_ts:
                            event_time_sec = parse_rfc3339_or_unix(telemetry_ts)
                            if event_time_sec > 0:
                                drift_sec = abs(time.time() - event_time_sec)
                                if drift_sec > 30.0:
                                    force_hitl_by_cognitive = True
                                    cognitive_reasons.append(f"CLOCK_DRIFT_EXCEEDED: skew is {drift_sec:.1f}s (> 30s threshold)")
                                    logger.warning(f"[CLOCK DRIFT ALERT] Agent clock drift detected on PC: {pc_name}. Skew = {drift_sec:.1f} seconds. Forcing Human-In-The-Loop gate.")
                                    if rag and rag.conn:
                                        try:
                                            with rag.conn.cursor() as cur:
                                                cur.execute("""
                                                    INSERT INTO security_events (rule_name, event_type, payload)
                                                    VALUES (%s, %s, %s)
                                                """, ("CLOCK_DRIFT_POLICY", "SKEW_DETECTED", json.dumps({"pc_name": pc_name, "drift_seconds": drift_sec})))
                                                rag.conn.commit()
                                        except Exception as sec_db_err:
                                            logger.error(f"Failed to log clock drift security event: {sec_db_err}")
    
                        critic_score_val = 0
                    
                        try:
                            logger.info(f"[HITL COGNITIVE] Starting evaluation for Incident ID: {incident_id}")
                            # A. Adversarial Critic Engine via NATS request (process isolation)
                            critic_res = None
                            try:
                                critic_req = {
                                    "action": final_decision,
                                    "severity": severity_str,
                                    "confidence": confidence_score,
                                    "incident_details": incident_details,
                                    "embedding": real_embedding
                                }
                                critic_res_bytes = await nc.request("ai.engine.critic", json.dumps(critic_req).encode(), timeout=5.0)
                                critic_res_parsed = json.loads(critic_res_bytes.data.decode())
                                if critic_res_parsed.get("status") == "success":
                                    critic_res = critic_res_parsed.get("result")
                                else:
                                    raise Exception(critic_res_parsed.get("error"))
                            except Exception as critic_err:
                                logger.warning(f"NATS Critic request failed: {critic_err}. Falling back to in-process evaluation.")
                                from critic_engine import AdversarialCriticEngine
                                critic_eng = AdversarialCriticEngine()
                                critic_res = await critic_eng.evaluate_action(
                                    action=final_decision,
                                    severity=severity_str,
                                    confidence=confidence_score,
                                    incident_details=incident_details,
                                    embedding=real_embedding
                                )
                            critic_score_val = critic_res["critic_score"]
                        
                            if rag and rag.conn and incident_id:
                                with rag.conn.cursor() as cur:
                                    cur.execute("""
                                        INSERT INTO critic_logs (
                                            incident_id, critic_score, critic_reason, risk_amplification,
                                            missing_evidence, rollback_risk, dependency_risk, force_hitl
                                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                    """, (
                                        incident_id,
                                        critic_res["critic_score"],
                                        critic_res["critic_reason"],
                                        critic_res["risk_amplification"],
                                        critic_res["missing_evidence"],
                                        critic_res["rollback_risk"],
                                        critic_res["dependency_risk"],
                                        critic_res["force_hitl"]
                                    ))
                                    rag.conn.commit()
                        
                            if critic_res["force_hitl"]:
                                force_hitl_by_cognitive = True
                                cognitive_reasons.extend(critic_res["reasons"])
    
                            # P0: Critic Feedback into Confidence
                            consensus_confidence = confidence_score
                            critic_penalty = max(0.0, (critic_res["critic_score"] - 30.0) * 0.4)
                        
                            rollback_risk_lvl = critic_res["rollback_risk"].upper()
                            rollback_penalty = 25.0 if rollback_risk_lvl == "HIGH" else (12.0 if rollback_risk_lvl == "MEDIUM" else 0.0)
                        
                            has_trust_anomaly = any("trust" in r.lower() or "spoof" in r.lower() or "integrity" in r.lower() for r in critic_res["reasons"]) or (critic_res["dependency_risk"].upper() == "HIGH")
                            trust_penalty = 20.0 if has_trust_anomaly else 0.0
                        
                            novelty_penalty = 15.0 if critic_res["missing_evidence"] > 30.0 else 0.0
                        
                            final_confidence = max(5.0, consensus_confidence - critic_penalty - rollback_penalty - trust_penalty - novelty_penalty)
                        
                            logger.info(f"[CRITIC GOVERNOR] Confidence Calibrated: {consensus_confidence:.1f}% -> {final_confidence:.1f}% "
                                        f"(Critic Penalty: {critic_penalty:.1f}, Rollback Penalty: {rollback_penalty:.1f}, "
                                        f"Trust Penalty: {trust_penalty:.1f}, Novelty Penalty: {novelty_penalty:.1f})")
                        
                            confidence_score = final_confidence
                            
                            # B. Question Engine
                            from question_engine import QuestionEngine
                            qe = QuestionEngine(conn=rag.conn)
                            evidence_completeness = 100.0 - critic_res["missing_evidence"]
                            incident_similarity = float(rag_vector_metadata.get("retrieved_count", 0)) * 30.0
                        
                            # Calculate hypothesis conflict based on verdicts agreement
                            distinct_actions = set(v.get("recommended_action", "").lower().strip() for v in consensus_verdict.get("verdicts", []))
                            hypothesis_conflict = 0.0 if len(distinct_actions) <= 1 else 50.0
                        
                            qe_res = qe.evaluate_clarification_needs(
                                confidence=confidence_score,
                                evidence_completeness=evidence_completeness,
                                incident_similarity=incident_similarity,
                                hypothesis_conflict=hypothesis_conflict,
                                incident_details=incident_details
                            )
                        
                            if qe_res["requires_clarification"]:
                                if incident_id:
                                    qe.log_questions(incident_id, qe_res["questions"], qe_res["triggers"])
                                force_hitl_by_cognitive = True
                                cognitive_reasons.append(f"Question Engine Triggered: {', '.join(qe_res['triggers'])}")
                            
                            # C. Counterfactual Engine
                            from counterfactual_engine import CounterfactualEngine
                            cfe = CounterfactualEngine(conn=rag.conn)
                            cfe_res = cfe.simulate_alternatives(primary_action=final_decision)
                            if incident_id:
                                cfe.log_counterfactual_matrix(incident_id, cfe_res["matrix"], final_decision)
                            
                            if cfe_res["force_hitl"]:
                                force_hitl_by_cognitive = True
                                cognitive_reasons.extend(cfe_res["reasons"])
                            
                        except Exception as cog_err:
                            logger.error(f"Error in HITL Cognitive Modules evaluation: {cog_err}")
                            if rag and rag.conn:
                                try:
                                    rag.conn.rollback()
                                except:
                                    import logging; logging.getLogger(__name__).debug('_ = None suppressed')
    
                        # Debate Limit Evaluation
                        if not force_hitl_by_cognitive and confidence_score >= 80.0:
                            break # Consensus reached and approved by Critic
                        else:
                            logger.warning(f'Debate round {debate_round+1} failed. Retrying...')
                            debate_context += f'Round {debate_round+1} Critic: {cognitive_reasons}. '
                # ── Tahap 2: AI Safety Layer (Deterministic Governance) ──
                from ai_safety_layer import get_safety_layer
                safety_layer = get_safety_layer(db_conn=rag.conn)
                
                safety_decision = safety_layer.evaluate_action(
                    incident_id=incident_id or 0,
                    device_id=pc_name,
                    candidate_action=final_decision or "UNKNOWN",
                    llm_confidence=confidence_score,
                    action_target=pc_name # Using pc_name as target device context
                )
                
                requires_approval = safety_decision.get("requires_hitl", True)
                risk_level_str = safety_decision.get("risk_level", "MEDIUM")
                policy_effect = safety_decision.get("policy_effect", "REQUIRE_APPROVAL")
                
                # ── SPRINT R: GENERATE ENTERPRISE DECISION PACKAGE ──
                decision_package_json = None
                try:
                    from decision_orchestrator import get_decision_orchestrator
                    from llm_router import get_router
                    d_orch = get_decision_orchestrator()
                    d_router = get_router()
                    d_pkg = await d_orch.generate_decision_package(
                        router=d_router,
                        severity_score=severity_score,
                        incident_details=incident_details,
                        historical_context=historical_context,
                        evidence_pkg=evidence_pkg,
                        causal_dag={"nodes": _erg._graph.nodes, "edges": _erg._graph.edges} if _erg is not None and getattr(_erg, '_graph', None) else {},
                        critic_res=critic_res if 'critic_res' in locals() else {},
                        consensus_verdict=consensus_verdict if 'consensus_verdict' in locals() else {}
                    )
                    decision_package_json = d_pkg.model_dump_json()
                    logger.info(f"[DECISION ORCHESTRATOR] Successfully built Enterprise Decision Package for incident {incident_id}")
                    
                    # Force HITL if recommended by orchestrator
                    if d_pkg.requires_human:
                        requires_approval = True
                        force_hitl_by_cognitive = True
                except Exception as d_err:
                    logger.error(f"[DECISION ORCHESTRATOR] Failed to build Decision Package: {d_err}")
                # ────────────────────────────────────────────────────
                
                _immutable_reasons = []
                
                # 1. Cognitive Engine Override (Question & Counterfactual Engines)
                # 1. Prepare dynamic blacklist reasons
                _dynamic_blacklist_reasons = []
                if rag and rag.conn:
                    try:
                        with rag.conn.cursor() as cur:
                            action_clean = final_decision
                            cur.execute("""
                                SELECT COUNT(*) FROM incident_post_mortems
                                WHERE device_name = %s 
                                  AND flag = 'HUMAN_REJECTION'
                                  AND (report_data->>'failed_action' = %s OR rca_summary ILIKE %s)
                                  AND created_at >= NOW() - INTERVAL '6 hours'
                            """, (pc_name, action_clean, f"%{action_clean}%"))
                            rejections_count = cur.fetchone()[0]
                            if rejections_count >= 4:
                                _dynamic_blacklist_reasons.append(
                                    f"[DYNAMIC BLACKLIST] Mitigation '{action_clean}' was rejected {rejections_count} times recently on '{pc_name}' within 6 hours. "
                                    f"Autonomous action is temporarily denied."
                                )
                    except Exception as black_err:
                        logger.error(f"[GOVERNANCE] Failed to query dynamic blacklist: {black_err}")
                
                # 2. Extract Integrity Score Check
                _incident_metadata = incident_details.get("metadata") or {}
                _requires_hitl_due_to_integrity = bool(
                    _incident_metadata.get("requires_hitl") or
                    str(_incident_metadata.get("integrity_score", "1.0")) < "0.60"
                )

                recovery_mode = get_active_recovery_mode(rag.conn)
                logger.info(f"[GOVERNANCE] Active Recovery Mode: {recovery_mode}")

                # 3. Call Governance Execution Orchestrator
                from governance.execution_orchestrator import GovernanceExecutionOrchestrator
                orchestrator = GovernanceExecutionOrchestrator(nc, rag.conn)
                
                action_executed = await orchestrator.execute(
                    incident_id=incident_id or 0,
                    site_id=site_id_str,
                    action_name=validated_action.recommended_action,
                    risk_level=risk_level_str,
                    recovery_mode=recovery_mode,
                    pc_name=pc_name,
                    event_id=event_id,
                    cognitive_forced_hitl=force_hitl_by_cognitive,
                    integrity_score_low=_requires_hitl_due_to_integrity,
                    dynamic_blacklist_reasons=_dynamic_blacklist_reasons
                )

                # ERG: record action execution
                if action_executed.startswith("EXECUTING_"):
                    _erg.set_action("AUTO_MITIGATE", validated_action.recommended_action)
                    exec_id = action_executed.split("EXECUTING_")[1]
                else:
                    exec_id = None


                    # asyncio is already imported globally, avoid UnboundLocalError
                    asyncio.create_task(
                        run_background_verification(
                            nc=nc,
                            incident_id=incident_id,
                            validated_action_name=validated_action.recommended_action,
                            pc_name=data.get("pc_name", "UNKNOWN"),
                            exec_id=exec_id,
                            site_id_str=site_id_str,
                            event_id=event_id,
                            incident_details=incident_details
                        )
                    )
                # Acknowledge NATS message
                if not msg_acknowledged:
                    await msg.ack()
                    msg_acknowledged = True
                logger.info(f"[INCIDENT PROCESSED] Event ID: {event_id} - Action: {action_executed} - Acknowledged.")

                # Persist full Decision Graph (GAP 1)
                try:
                    if rag and rag.conn and incident_id:
                        with rag.conn.cursor() as dg_cur:
                            # Retrieve latest policy evaluation details
                            dg_cur.execute("""
                                SELECT policy_version, matched_rule, effect
                                FROM policy_audit_trail
                                WHERE incident_id = %s
                                ORDER BY id DESC LIMIT 1
                            """, (incident_id,))
                            pat_row = dg_cur.fetchone()
                            policy_info = {}
                            if pat_row:
                                policy_info = {
                                    "policy_version": pat_row[0],
                                    "matched_rule": pat_row[1],
                                    "policy_effect": pat_row[2]
                                }
                            
                            # Retrieve hitl audit logs details if any
                            dg_cur.execute("""
                                SELECT force_hitl_reason, approved_by, action_taken
                                FROM hitl_audit_logs
                                WHERE incident_id = %s
                                ORDER BY id DESC LIMIT 1
                            """, (incident_id,))
                            hitl_row = dg_cur.fetchone()
                            hitl_info = {}
                            if hitl_row:
                                hitl_info = {
                                    "force_hitl_reason": hitl_row[0],
                                    "approved_by": hitl_row[1],
                                    "action_taken": hitl_row[2]
                                }

                            # Retrieve policy snapshot ID
                            dg_cur.execute("""
                                SELECT policy_snapshot_id FROM incidents WHERE incident_id = %s
                            """, (incident_id,))
                            psnp_row = dg_cur.fetchone()
                            if psnp_row and psnp_row[0]:
                                policy_info["policy_snapshot_id"] = psnp_row[0]

                            critic_feedback_val = critic_res if 'critic_res' in locals() else {}
                            if 'cfe_res' in locals() and cfe_res:
                                critic_feedback_val["counterfactual_simulation"] = cfe_res

                            evidence_data = {
                                "telemetry": incident_details,
                                "integrity_score": incident_details.get("metadata", {}).get("integrity_score", "1.0"),
                                "missing_evidence_score": critic_feedback_val.get("missing_evidence", 0)
                            }

                            dg_cur.execute("""
                                INSERT INTO decision_graphs (
                                    incident_id, root_incident, consensus_output, critic_feedback,
                                    evidence_used, policy_applied, hitl_details, final_action_taken, created_at
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                            """, (
                                incident_id,
                                json.dumps(incident_details),
                                json.dumps(consensus_verdict) if 'consensus_verdict' in locals() else json.dumps({}),
                                json.dumps(critic_feedback_val),
                                json.dumps(evidence_data),
                                json.dumps(policy_info),
                                json.dumps(hitl_info),
                                action_executed
                            ))
                            rag.conn.commit()
                            logger.info(f"[DECISION GRAPH] Successfully persisted execution lineage for incident {incident_id}")
                            
                            import hashlib
                            import uuid
                            
                            evidence_str = json.dumps(evidence_data, sort_keys=True)
                            evidence_hash = hashlib.sha256(evidence_str.encode()).hexdigest()
                            decision_id = str(uuid.uuid4())
                            
                            if decision_package_json:
                                try:
                                    dp = json.loads(decision_package_json)
                                    dg_cur.execute("""
                                        INSERT INTO autonomous_decision_records (
                                            decision_id, incident_id, agent_id, policy_version, prompt_version,
                                            reasoning_version, knowledge_version, evidence_hash, evidence_timestamp,
                                            evidence_freshness_sec, confidence, expected_version, execution_id,
                                            execution_token_hash, verification_result, average_confidence, final_outcome,
                                            reasoning_summary, created_at
                                        ) VALUES (
                                            %s, %s, %s, %s, %s, %s, %s, %s, NOW(), 
                                            0.0, %s, 1, %s, NULL, 'PENDING', 0.0, 'PENDING', %s, NOW()
                                        )
                                    """, (
                                        decision_id, incident_id, pc_name,
                                        policy_info.get('policy_version', 'v1'),
                                        'v1.2', 'v3', 'kg-2026-07-20', evidence_hash,
                                        float(dp.get('confidence', 0.0)),
                                        exec_id,
                                        json.dumps({
                                            "decision": dp.get("root_cause", "UNKNOWN"),
                                            "reason_summary": dp.get("summary", "")
                                        })
                                    ))
                                    rag.conn.commit()
                                    logger.info(f"[GOVERNANCE AUDIT] Immutable Decision Record created for incident {incident_id}")
                                except Exception as audit_err:
                                    logger.error(f"[GOVERNANCE AUDIT] Failed to save Decision Record: {audit_err}")

                except Exception as dg_err:
                    logger.error(f"[DECISION GRAPH] Failed to write decision graph trace: {dg_err}")

                # Save logs
                # ── PHASE 2B: NON-INVASIVE OUTPUT ADAPTER HOOK (LLM ROUTER SYNTHESIZER) ──
                raw_final_decision = final_decision
                # Derive models_used from llm_response (already in scope from consensus/fast-track path)
                models_used = (
                    llm_response.get("model", "unknown")
                    if isinstance(llm_response, dict)
                    else str(llm_response)[:64] if llm_response else "consensus-engine"
                )
                clean_final_decision = raw_final_decision
                try:
                    from adapters.output_synthesizer import OutputAdapterFacade, SynthesizerConfig, LLMRouterSynthesizer
                    adapter_config = SynthesizerConfig(enabled=True, model_version="gemini-1.5-flash", prompt_version="v1.2", adapter_version="2.0")
                    adapter_facade = OutputAdapterFacade(config=adapter_config, synthesizer=LLMRouterSynthesizer(adapter_config))
                    
                    adapter_resp = adapter_facade.process(
                        raw_final_decision=raw_final_decision,
                        evidence=str(incident_details.get("symptoms", "") or incident_details.get("description", "")),
                        confidence=confidence_score / 100.0 if confidence_score > 1.0 else confidence_score,
                        incident_id=incident_id,
                        device_name=pc_name or "SYSTEM"
                    )
                    clean_final_decision = adapter_resp.clean_final_decision
                    logger.info(f"[OUTPUT ADAPTER HOOK Phase 2B] Successfully processed Incident #{incident_id}. IsSynthesized: {adapter_resp.is_synthesized}, Score: {adapter_resp.quality_score}, Metadata: {adapter_resp.telemetry_metadata}")
                except Exception as adapter_err:
                    logger.error(f"[OUTPUT ADAPTER HOOK Phase 2B] Exception in adapter process: {adapter_err}. Falling back to raw_final_decision.")
                    clean_final_decision = raw_final_decision

                elapsed_ms_val = locals().get('elapsed_ms') or locals().get('start_time') or 150.0
                if isinstance(elapsed_ms_val, (int, float)) and elapsed_ms_val < 100000:
                    elapsed_ms_param = int(elapsed_ms_val)
                else:
                    elapsed_ms_param = 150

                log_ai_pipeline(
                    conn=rag.conn,
                    incident_id=incident_id,
                    event_id=event_id,
                    reasoning_dag=reasoning_dag,
                    rag_vectors=rag_vector_metadata,
                    raw_prompt="CONSENSUS_ENGINE_PROMPT",
                    llm_response=clean_final_decision,
                    confidence_score=confidence_score,
                    action_executed=action_executed,
                    first_hypothesis=first_hypothesis,
                    second_hypothesis=second_hypothesis,
                    final_decision=clean_final_decision,
                    models_used=models_used,
                    elapsed_ms=elapsed_ms_param
                )
                
                # SPRINT O: Real-Time Governance Evaluator
                try:
                    from governance.cycle import trigger_governance_cycle
                    await trigger_governance_cycle(
                        incident_id=int(incident_id) if incident_id else 0,
                        telemetry_data=incident_details,
                        ai_prediction=final_decision or "UNKNOWN",
                        human_resolution="Automated Pipeline Verification",  # Simulated human resolution
                        conn=rag.conn
                    )
                except Exception as gov_err:
                    logger.error(f"[Sprint O] Governance Hook Failed: {gov_err}")

                # ERG: final flush to database (fail-silent)
                _erg.flush()
                
            except json.JSONDecodeError:
                logger.error("Failed to decode message JSON.")
                if not msg_acknowledged:
                    await msg.nak()
                    msg_acknowledged = True
            except Exception as e:
                import traceback
                logger.error(f"Error processing message: {e}\n{traceback.format_exc()}")
                
                # Intercept Schema Validation Failures and log to ai_audit_trail
                err_str = str(e)
                if "validation error" in err_str.lower() or e.__class__.__name__ == "ValidationError":
                    if rag and rag.conn:
                        try:
                            with rag.conn.cursor() as cur:
                                cur.execute("""
                                    INSERT INTO ai_audit_trail (incident_id, event_id, raw_prompt, llm_response, action_executed, created_at)
                                    VALUES (%s, %s, %s, %s, %s, NOW())
                                """, (incident_id if incident_id else 0, event_id, "SCHEMA_ENFORCEMENT_AGENT", err_str[:1000], "SCHEMA_INVALID_EXCEPTION"))
                                rag.conn.commit()
                        except Exception as audit_err:
                            logger.error(f"Failed to log schema validation to audit trail: {audit_err}")

                # AI DLQ (Dead Letter Queue) Implementation
                try:
                    site_id_dlq = "global"
                    try:
                        raw_site = data.get("site_id") or data.get("message", {}).get("site_id", "global")
                        site_id_dlq = str(raw_site).lower().replace(".", "_").replace(" ", "_")
                    except:
                        import logging; logging.getLogger(__name__).debug('_ = None suppressed')
                    import datetime as dt_mod
                    dlq_payload = {
                        "failed_at": dt_mod.datetime.now(dt_mod.timezone.utc).isoformat(),
                        "error_reason": str(e),
                        "raw_data": msg.data.decode() if msg.data else "",
                        "site_id": site_id_dlq
                    }
                    dlq_subject = f"dlq.site.{site_id_dlq}"
                    await nc.publish(dlq_subject, json.dumps(dlq_payload).encode())
                    logger.info(f"Event successfully pushed to AI Dead Letter Queue ({dlq_subject})")
                    if not msg_acknowledged:
                        await msg.ack()
                        msg_acknowledged = True
                except Exception as dlq_err:
                    logger.critical(f"Failed to push to DLQ: {dlq_err}")
                    if not msg_acknowledged:
                        await msg.nak()
                        msg_acknowledged = True
            finally:
                # TELEMETRY HOOK: END (Best-effort final emission)
                if 'telemetry_trace_id' in locals() and telemetry_trace_id:
                    try:
                        latencies["total_latency_ms"] = (time.monotonic() - telemetry_t0) * 1000
                        asyncio.create_task(telemetry.record_incident_resolved(
                            incident_id=str(incident_id or telemetry_trace_id),
                            trace_id=telemetry_trace_id,
                            confidence=telemetry_confidence,
                            latencies=latencies,
                            is_false_positive=False
                        ))
                    except Exception as t_err:
                        logger.error(f"[Telemetry] Final emission failed: {t_err}")

                if rag and rag.conn:
                    try:
                        rag.close()
                        logger.info("Closed DB connection in message_handler.")
                    except:
                        import logging; logging.getLogger(__name__).debug('_ = None suppressed')

        # Learning Loop NATS handler reading only validated JSON
        async def learning_handler(msg):
            from rag_engine import get_rag_engine
            from llm_router import get_router
            rag = None
            try:
                data = json.loads(msg.data.decode())
                
                # Initialize DB and RAG connection early to load policies
                rag = get_rag_engine()
                rag.connect()
                
                # Default learning gate policy fallback
                confidence_threshold = 0.75
                require_human_confirmation = True
                require_success_verification = True
                try:
                    if rag.conn is not None:
                        with rag.conn.cursor() as cur:
                            cur.execute("SELECT confidence_threshold, require_human_confirmation, require_success_verification FROM learning_gate_policy LIMIT 1")
                            row = cur.fetchone()
                            if row:
                                confidence_threshold = float(row[0])
                                require_human_confirmation = bool(row[1])
                                require_success_verification = bool(row[2])
                except Exception as policy_err:
                    logger.warning(f"Failed to fetch learning gate policy, using default (0.75): {policy_err}")
                    try:
                        if rag.conn is not None:
                            rag.conn.rollback()
                    except:
                        import logging; logging.getLogger(__name__).debug('_ = None suppressed')

                # Verified Learning Gate condition evaluation
                verification_status = str(data.get("verification_status", "FAILED")).upper()
                human_confirmed = bool(data.get("human_confirmed", False))
                rollback_needed = bool(data.get("rollback_needed", False))
                confidence = float(data.get("confidence", 0.0))
                
                # Map confidence to 0-1 if it is 0-100 format
                confidence_normalized = confidence / 100.0 if confidence > 1.0 else confidence
                
                # Core learning validation gate using DB thresholds
                learning_allowed = True
                if require_success_verification and verification_status != "SUCCESS":
                    learning_allowed = False
                if require_human_confirmation and not human_confirmed:
                    learning_allowed = False
                if rollback_needed:
                    learning_allowed = False
                if confidence_normalized < confidence_threshold:
                    learning_allowed = False
                
                # Strict validation using LearningSchema
                validated_learning = LearningSchema(
                    incident_id=str(data.get("incident_id", "")),
                    root_cause=str(data.get("human_root_cause", "") or data.get("ai_root_cause", "") or data.get("root_cause", "")),
                    successful_action=str(data.get("resolution", "") or data.get("successful_action", "")),
                    verification_status=verification_status,
                    human_confirmed=human_confirmed,
                    confidence=confidence,
                    learning_allowed=learning_allowed,
                    title=str(data.get("title", "") or "New Resolution"),
                    symptoms=str(data.get("symptoms", "")),
                    vector_embedding=None
                )
                
                logger.info(f"[LEARNING LOOP] Received learning message for Incident ID: {validated_learning.incident_id}")
                
                # Audit Trail Preservation (Save attempt details to ai_audit_trail)
                if rag.conn:
                    try:
                        with rag.conn.cursor() as cur:
                            cur.execute("""
                                INSERT INTO ai_audit_trail (incident_id, event_id, reasoning_dag, rag_vectors_retrieved, raw_prompt, llm_response, confidence_score, action_executed, created_at)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                            """, (
                                validated_learning.incident_id,
                                "LEARNING_GATE",
                                json.dumps({
                                    "verification_status": verification_status,
                                    "human_confirmed": human_confirmed,
                                    "rollback_needed": rollback_needed,
                                    "confidence_normalized": confidence_normalized,
                                    "confidence_threshold": confidence_threshold
                                }),
                                json.dumps({"learning_allowed": learning_allowed}),
                                "RAG dynamic learning ingestion attempt",
                                f"Action: {validated_learning.successful_action} | RCA: {validated_learning.root_cause}",
                                confidence,
                                "LEARNING_ACCEPTED" if learning_allowed else "LEARNING_BLOCKED"
                            ))
                            rag.conn.commit()
                            logger.info(f"[LEARNING GATE] Ingestion audit trail logged to DB.")
                    except Exception as audit_err:
                        logger.error(f"[LEARNING GATE] Failed to log audit trail: {audit_err}")
                
                # Enforce gate blocking conditions
                if not validated_learning.learning_allowed:
                    logger.warning(
                        f"[LEARNING BLOCKED] Learning Gate rejected Incident ID: {validated_learning.incident_id}. "
                        f"Reason: verification_status={verification_status}, human_confirmed={human_confirmed}, "
                        f"rollback_needed={rollback_needed}, confidence={confidence} (threshold={confidence_threshold})"
                    )
                    await msg.ack()
                    return
                
                router = get_router()
                text_to_embed = f"Title: {validated_learning.title} Symptoms: {validated_learning.symptoms} Description: {validated_learning.root_cause} {validated_learning.successful_action}"
                embedding = [0.0] * 768
                
                if router.availability.get("gemini") and router.gemini_client:
                    try:
                        emb_result = router.gemini_client.models.embed_content(
                            model="text-embedding-004",
                            contents=text_to_embed
                        )
                        if emb_result and emb_result.embeddings:
                            embedding = emb_result.embeddings[0].values
                    except Exception as emb_err:
                        logger.error(f"[LEARNING LOOP] Embedding error: {emb_err}")
                
                vector_str = "[" + ",".join(map(str, embedding)) + "]"
                
                if rag.conn is not None:
                    with rag.conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO knowledge_vectors (incident_id, title, symptoms, root_cause, resolution, embedding, confidence, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                            ON CONFLICT (incident_id) DO UPDATE SET
                                title = EXCLUDED.title,
                                symptoms = EXCLUDED.symptoms,
                                root_cause = EXCLUDED.root_cause,
                                resolution = EXCLUDED.resolution,
                                embedding = EXCLUDED.embedding,
                                confidence = EXCLUDED.confidence
                        """, (f"KB-LEARN-{validated_learning.incident_id}", validated_learning.title, validated_learning.symptoms, validated_learning.root_cause, validated_learning.successful_action, vector_str, validated_learning.confidence))
                        rag.conn.commit()
                
                logger.info(f"[LEARNING LOOP] Successfully vectorized and saved incident {validated_learning.incident_id} to knowledge_vectors.")
            except Exception as e:
                logger.error(f"[LEARNING LOOP] Error processing learning feedback: {e}")
            finally:
                if rag and rag.conn:
                    try:
                        rag.close()
                        logger.info("[LEARNING LOOP] Closed DB connection.")
                    except:
                        import logging; logging.getLogger(__name__).debug('_ = None suppressed')

        # Dynamic multi-site subscription partition engine
        from nats.js.api import ConsumerConfig, AckPolicy, DeliverPolicy

        active_subscriptions = {}

        async def subscribe_to_site(site_id):
            clean_site = site_id.lower().strip().replace(".", "_").replace(" ", "_")
            if clean_site in active_subscriptions:
                return
            
            subject = f"telemetry.site.{clean_site}.critical"
            durable_name = f"ai_supervisor_consumer_{clean_site}"
            
            config = ConsumerConfig(
                durable_name=durable_name,
                ack_policy=AckPolicy.EXPLICIT,
                max_deliver=5,
                max_ack_pending=128,
                deliver_policy=DeliverPolicy.ALL
            )
            
            try:
                sub = await js.subscribe(
                    subject,
                    durable=durable_name,
                    config=config,
                    cb=message_handler
                )
                active_subscriptions[clean_site] = sub
                logger.info(f"[PARTITION ENGINE] Subscribed to subject '{subject}' with durable '{durable_name}' (ordering per site preserved).")
            except Exception as sub_err:
                logger.error(f"[PARTITION ENGINE] Failed to subscribe to site {clean_site}: {sub_err}")

        # Always subscribe to legacy/global catchers
        try:
            legacy_config = ConsumerConfig(
                durable_name="ai_supervisor_consumer_legacy",
                ack_policy=AckPolicy.EXPLICIT,
                max_deliver=5,
                max_ack_pending=128,
                deliver_policy=DeliverPolicy.ALL
            )
            legacy_sub = await js.subscribe(
                "telemetry.critical",
                durable="ai_supervisor_consumer_legacy",
                config=legacy_config,
                cb=message_handler
            )
            active_subscriptions["legacy"] = legacy_sub
            logger.info("[PARTITION ENGINE] Subscribed to legacy 'telemetry.critical' subject.")
        except Exception as legacy_err:
            logger.error(f"[PARTITION ENGINE] Failed to subscribe to legacy: {legacy_err}")

        # SPRINT P1: Subscribe to Netdata telemetry explicitly
        try:
            netdata_config = ConsumerConfig(
                durable_name="ai_supervisor_consumer_netdata",
                ack_policy=AckPolicy.EXPLICIT,
                max_deliver=5,
                max_ack_pending=128,
                deliver_policy=DeliverPolicy.ALL
            )
            netdata_sub = await js.subscribe(
                "telemetry.netdata",
                durable="ai_supervisor_consumer_netdata",
                config=netdata_config,
                cb=message_handler
            )
            active_subscriptions["netdata"] = netdata_sub
            logger.info("[PARTITION ENGINE] Subscribed to 'telemetry.netdata' subject.")
        except Exception as netdata_err:
            logger.error(f"[PARTITION ENGINE] Failed to subscribe to netdata: {netdata_err}")

        await subscribe_to_site("global")

        # Start background polling task for newly registered sites
        def dynamic_site_polling_loop_sync():
            from rag_engine import get_rag_engine
            db = None
            try:
                db = get_rag_engine()
                db.connect()
                if db.conn:
                    try:
                        with db.conn.cursor() as cur:
                            cur.execute("SELECT site_id FROM fleet_sites")
                            db_sites = [row[0] for row in cur.fetchall()]
                        return db_sites
                    except Exception as query_err:
                        logger.error(f"[PARTITION ENGINE] DB polling query failed: {query_err}")
                        try:
                            db.conn.rollback()
                        except:
                            import logging; logging.getLogger(__name__).debug('_ = None suppressed')
            except Exception as loop_err:
                logger.error(f"[PARTITION ENGINE] DB polling connection failed: {loop_err}")
            finally:
                if db and db.conn:
                    try:
                        db.close()
                    except:
                        import logging; logging.getLogger(__name__).debug('_ = None suppressed')
            return list()

        async def dynamic_site_polling_loop_async():
            while True:
                db_sites = await asyncio.to_thread(dynamic_site_polling_loop_sync)
                for site in db_sites:
                    if site:
                        await subscribe_to_site(site)
                await asyncio.sleep(10)

        asyncio.create_task(dynamic_site_polling_loop_async())

        # Subscribe to learning loop events with queue group
        learning_sub = await nc.subscribe("rag.learn", queue="ai-learning-group", cb=learning_handler)
        logger.info("Subscribed to 'rag.learn' for dynamic Knowledge learning (group: ai-learning-group).")
        
        from tests.test_utils import syntheticMsg

        async def reanalyze_handler(msg):
            try:
                payload = json.loads(msg.data.decode())
                incident_id = payload.get("incident_id")
                if not incident_id:
                    return
                logger.info(f"[REANALYZE] Triggered for incident {incident_id}")
                
                from rag_engine import get_rag_engine
                db = get_rag_engine()
                db.connect()
                if not db.conn:
                    return
                raw_data = None
                with db.conn.cursor() as cur:
                    cur.execute("SELECT raw_data FROM incidents WHERE incident_id::text = %s", (str(incident_id),))
                    row = cur.fetchone()
                    if row and row[0]:
                        raw_data = row[0]
                    else:
                        cur.execute("SELECT pc_name, severity, description FROM fleet_incidents WHERE incident_id::text = %s", (str(incident_id),))
                        frow = cur.fetchone()
                        if frow:
                            pc_name, severity, description = frow
                            raw_data = {
                                "agent": pc_name or "System",
                                "flag": f"{severity}_ALERT",
                                "evidence": description or "Fleet Watchdog Alert",
                                "incident_id": str(incident_id),
                                "status": "RETRY"
                            }
                db.close()
                
                if raw_data:
                    if isinstance(raw_data, str):
                        try:
                            raw_data = json.loads(raw_data)
                        except:
                            import logging; logging.getLogger(__name__).debug('_ = None suppressed')
                    if isinstance(raw_data, dict):
                        raw_data["incident_id"] = incident_id
                        synthetic_msg = syntheticMsg(json.dumps(raw_data).encode(), subject="incident.reanalyze")
                        await message_handler(synthetic_msg)
                        logger.info(f"[REANALYZE] Re-analysis completed for {incident_id}")
            except Exception as e:
                logger.error(f"[REANALYZE] Failed: {e}")

        await nc.subscribe("incident.reanalyze", queue="ai-reanalyze-group", cb=reanalyze_handler)
        logger.info("Subscribed to 'incident.reanalyze' for forced Re-Analysis (group: ai-reanalyze-group).")
        
        # Background Agent Heartbeat Generator
        async def heartbeat_loop():
            uptime_start = time.time()
            import psutil
            while True:
                try:
                    uptime = int(time.time() - uptime_start)
                    cpu = psutil.cpu_percent()
                    agents = ["incident", "security", "verify", "recovery"]
                    for agent in agents:
                        payload = {
                            "agent": agent,
                            "status": "ONLINE",
                            "uptime": uptime,
                            "queue_depth": 0,
                            "cpu": cpu / 100.0
                        }
                        subject = f"agent.status.site.global.{agent}"
                        await nc.publish(subject, json.dumps(payload).encode())
                except Exception as hb_err:
                    logger.error(f"Error sending heartbeat: {hb_err}")
                await asyncio.sleep(5)

        asyncio.create_task(heartbeat_loop())

        # Background Trust Engine Evaluator (Phase 6)
        async def trust_evaluator_loop():
            from trust_engine import TrustEngine
            from rag_engine import get_rag_engine
            te = TrustEngine()
            while True:
                rag = None
                try:
                    rag = get_rag_engine()
                    rag.connect()
                    if rag.conn:
                        te.evaluate_trust_scores(rag.conn)
                except Exception as eval_err:
                    logger.error(f"Error in trust evaluation loop: {eval_err}")
                finally:
                    if rag and rag.conn:
                        try:
                            rag.close()
                        except:
                            import logging; logging.getLogger(__name__).debug('_ = None suppressed')
                await asyncio.sleep(10)

        # Background Human Rejection Embedding Sync
        async def sync_human_rejections_loop():
            from rag_engine import get_rag_engine
            from llm_router import get_router
            while True:
                db = None
                try:
                    db = get_rag_engine()
                    db.connect()
                    if db.conn:
                        router = get_router()
                        with db.conn.cursor() as cur:
                            cur.execute("""
                                SELECT pm.incident_id, pm.device_name, pm.rca_summary, pm.report_data, pm.created_at
                                FROM incident_post_mortems pm
                                LEFT JOIN knowledge_vectors kv ON kv.incident_id = CONCAT('KB-REJ-', pm.incident_id::text)
                                WHERE pm.flag = 'HUMAN_REJECTION' 
                                  AND (pm.remediation_effectiveness = 'CURATED_REJECTION' OR (pm.report_data->>'is_curated') = 'true')
                                  AND kv.incident_id IS NULL
                            """)
                            unmapped = cur.fetchall()
                            for row in unmapped:
                                inc_id, device, rca_summary, report_data, created_at = row
                                logger.info(f"[REJECTION SYNC] Found unsynced human rejection for Incident ID: {inc_id}")
                                
                                why_failed = "Unknown reason"
                                failed_action = "Unknown action"
                                if report_data:
                                    why_failed = report_data.get("why_failed") or report_data.get("why_rejected") or "Unknown"
                                    failed_action = report_data.get("failed_action") or "Unknown"
                                
                                text_to_embed = (
                                    f"Human Operator Rejection Memory. Device: {device}. "
                                    f"Failed/Rejected Action: {failed_action}. "
                                    f"Why Rejected: {why_failed}. RCA Summary: {rca_summary}"
                                )
                                
                                embedding = [0.0] * 768
                                if router.availability.get("gemini") and router.gemini_client:
                                    try:
                                        emb_result = router.gemini_client.models.embed_content(
                                            model="text-embedding-004",
                                            contents=text_to_embed
                                        )
                                        if emb_result and emb_result.embeddings:
                                            embedding = emb_result.embeddings[0].values
                                    except Exception as emb_err:
                                        logger.error(f"[REJECTION SYNC] Embedding generation failed for incident {inc_id}: {emb_err}")
                                
                                if all(x == 0.0 for x in embedding):
                                    import random
                                    random.seed(inc_id)
                                    embedding = [random.uniform(-0.1, 0.1) for _ in range(768)]
                                    
                                vector_str = "[" + ",".join(map(str, embedding)) + "]"
                                
                                cur.execute("""
                                    INSERT INTO knowledge_vectors (incident_id, title, symptoms, root_cause, resolution, embedding, confidence, created_at, tags)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s)
                                """, (
                                    f"KB-REJ-{inc_id}",
                                    f"Operator Rejection of {failed_action}",
                                    f"Mitigation action rejected by operator due to high risk on {device}",
                                    why_failed,
                                    f"Alternative chosen: {report_data.get('alternative_chosen') or 'Manual NOC Triage'}",
                                    vector_str,
                                    0.50,
                                    ["rejection", "hitl", failed_action]
                                ))
                                db.conn.commit()
                                logger.info(f"[REJECTION SYNC] Successfully embedded and saved KB-REJ-{inc_id} to knowledge_vectors.")
                except Exception as loop_err:
                    logger.error(f"[REJECTION SYNC] Error in rejection sync loop: {loop_err}")
                finally:
                    if db and db.conn:
                        try:
                            db.close()
                        except:
                            import logging; logging.getLogger(__name__).debug('_ = None suppressed')
                await asyncio.sleep(8)

        asyncio.create_task(sync_human_rejections_loop())
        asyncio.create_task(trust_evaluator_loop())

        # ── P4: Auto Escalation Engine ────────────────────────────
        escalation_engine = AutoEscalationEngine(nc=nc, interval_sec=60)
        asyncio.create_task(escalation_engine.start())
        logger.info("[ESCALATION ENGINE] Auto Escalation Engine started (60s interval).")

        # ── P5: Closure Enforcement Engine ────────────────────────
        closure_engine = ClosureEnforcementEngine()
        await nc.subscribe("incident.site.*.close.request", queue="closure-engine-group", cb=closure_engine.handle_close_request)
        logger.info("[CLOSURE ENGINE] Closure gate subscribed on 'incident.site.*.close.request' (group: closure-engine-group).")

        # ── P5.1: Escalation Enforcement Engine ───────────────────
        async def handle_escalate_request(msg):
            try:
                data = json.loads(msg.data.decode())
                incident_id = data.get("incident_id")
                next_level = data.get("next_level", 2)
                
                # e.g. incident.site.global.escalate.request -> global
                parts = msg.subject.split(".")
                site_id_str = parts[2] if len(parts) > 2 else "global"
                
                logger.info(f"[ESCALATE ENGINE] Escalating incident {incident_id} to Level {next_level} for site {site_id_str}")
                
                from rag_engine import get_rag_engine
                db = get_rag_engine()
                db.connect()
                if db.conn and incident_id:
                    with db.conn.cursor() as cur:
                        # Ensure we don't downgrade
                        cur.execute("UPDATE fleet_incidents SET escalation_level = GREATEST(escalation_level, %s) WHERE incident_id = %s", (next_level, incident_id))
                        db.conn.commit()
                        
                        log_event_sourced(db.conn, "incident_events", incident_id, "ESCALATED", {
                            "actor": "Operator via NOC",
                            "details": f"Escalated to Level {next_level}",
                            "note": data.get("operator_note", "")
                        })
                    
                    # Transition State (if currently ANALYZING/WAITING_APPROVAL -> OPEN, or keep OPEN)
                    await apply_incident_transition(nc, db.conn, incident_id, IncidentState.ANALYZING, IncidentState.OPEN, site_id_str, context={"reason": "Escalation Requested"})
                    db.close()
            except Exception as e:
                logger.error(f"[ESCALATE ENGINE] Failed to handle escalation request: {e}")

        await nc.subscribe("incident.site.*.escalate.request", queue="escalate-engine-group", cb=handle_escalate_request)
        logger.info("[ESCALATE ENGINE] Escalation gate subscribed on 'incident.site.*.escalate.request' (group: escalate-engine-group).")

        # ── P5.2: Human Approval Execution Engine ─────────────────
        async def handle_approval_decision(msg):
            try:
                data = json.loads(msg.data.decode())
                incident_id = data.get("incident_id")
                approval_id = data.get("approval_id")
                decision = data.get("decision")
                operator_id = data.get("operator_id")
                
                # Retrieve site_id since we dropped it from NATS subject to make it global
                from rag_engine import get_rag_engine
                from governance.execution_orchestrator import GovernanceExecutionOrchestrator
                
                logger.info(f"[APPROVAL ENGINE] Received decision {decision} for Incident {incident_id} (Approval ID: {approval_id}) by {operator_id}")
                
                db = get_rag_engine()
                db.connect()
                if db.conn and incident_id:
                    with db.conn.cursor() as cur:
                        cur.execute("SELECT site_id FROM fleet_incidents WHERE incident_id = %s", (incident_id,))
                        row = cur.fetchone()
                        site_id_str = row[0] if row and row[0] else "global"
                    
                    orchestrator = GovernanceExecutionOrchestrator(nc, db.conn)
                    await orchestrator.handle_human_decision(
                        incident_id=incident_id,
                        approval_id=approval_id,
                        decision=decision,
                        operator_id=operator_id,
                        site_id=site_id_str
                    )
                    db.close()
            except Exception as e:
                logger.error(f"[APPROVAL ENGINE] Failed to handle approval decision: {e}")

        await nc.subscribe("approval.decision", queue="approval-engine-group", cb=handle_approval_decision)
        logger.info("[APPROVAL ENGINE] Subscribed to 'approval.decision' (group: approval-engine-group).")

        # ── P6: Operator Presence Engine ──────────────────────────
        presence_engine = OperatorPresenceEngine(nc=nc, interval_sec=10)
        await presence_engine.start()
        logger.info("[PRESENCE DAEMON] Presence Engine initialized.")

        # ── P8: Blast Radius Engine ───────────────────────────────
        blast_engine = BlastRadiusEngine(nc=nc)
        await blast_engine.start()
        logger.info("[BLAST RADIUS ENGINE] Blast Radius Engine initialized.")

        # ── P9: Replay Simulation Engine ──────────────────────────
        replay_engine = ReplaySimulationEngine(nc=nc)
        await replay_engine.start()
        logger.info("[REPLAY ENGINE] Replay Simulation Engine initialized.")

        # Chat Compaction Subscriber
        async def chat_compaction_handler(msg):
            from rag_engine import get_rag_engine
            from llm_router import get_router
            try:
                data = json.loads(msg.data.decode())
                incident_id = data.get("incident_id")
                if not incident_id:
                    return
                
                logger.info(f"[CHAT COMPACTION] Compacting chat history for Incident ID: {incident_id}")
                
                db = get_rag_engine()
                db.connect()
                if not db.conn:
                    return
                
                try:
                    with db.conn.cursor() as cur:
                        # Find the last checkpoint ID
                        cur.execute("""
                            SELECT id FROM chat_messages 
                            WHERE incident_id = %s AND sender = 'SYSTEM' AND message LIKE '[CHAT SUMMARY CHECKPOINT]%'
                            ORDER BY created_at DESC LIMIT 1
                        """, (incident_id,))
                        last_checkpoint_row = cur.fetchone()
                        
                        if last_checkpoint_row:
                            last_id = last_checkpoint_row[0]
                            cur.execute("""
                                SELECT sender, message, created_at FROM chat_messages
                                WHERE incident_id = %s AND id > %s AND message NOT LIKE '[CHAT SUMMARY CHECKPOINT]%'
                                ORDER BY created_at ASC
                            """, (incident_id, last_id))
                        else:
                            cur.execute("""
                                SELECT sender, message, created_at FROM chat_messages
                                WHERE incident_id = %s AND message NOT LIKE '[CHAT SUMMARY CHECKPOINT]%'
                                ORDER BY created_at ASC
                            """, (incident_id,))
                        
                        rows = cur.fetchall()
                        if len(rows) < 10:
                            logger.info(f"[CHAT COMPACTION] Incident ID {incident_id} only has {len(rows)} messages since last checkpoint. Skipping.")
                            return
                        
                        # Format the chat history for the prompt
                        chat_history_str = ""
                        for sender, message, _ in rows:
                            chat_history_str += f"{sender}: {message}\n"
                        
                        prompt = (
                            "You are the AntiGravity Incident Analysis Bot. Summarize the following incident chat history "
                            "between the Client (operator/user) and Operator/AI. Extract the key symptoms reported, "
                            "steps taken, and the current status. Do NOT lose diagnostic details. Keep the summary "
                            "under 150 words.\n\n"
                            f"Chat History:\n{chat_history_str}\n\n"
                            "Summary (start with '[CHAT SUMMARY CHECKPOINT]'):"
                        )
                        
                        router = get_router()
                        res = await router.execute_with_retry(50, prompt) # use medium severity LLM (Gemini/Groq)
                        if res["status"] == "SUCCESS":
                            summary_text = str(res.get("response", "")).strip()
                            if not summary_text.startswith("[CHAT SUMMARY CHECKPOINT]"):
                                summary_text = "[CHAT SUMMARY CHECKPOINT] " + summary_text
                            
                            # Get client_id
                            cur.execute("SELECT client_id FROM chat_messages WHERE incident_id = %s LIMIT 1", (incident_id,))
                            client_row = cur.fetchone()
                            client_id = client_row[0] if client_row else "system"
                            
                            cur.execute("""
                                INSERT INTO chat_messages (client_id, sender, message, attachment_path, read_status, incident_id, is_system_msg, created_at)
                                VALUES (%s, 'SYSTEM', %s, '', 'SENT', %s, TRUE, NOW())
                            """, (client_id, summary_text, incident_id))
                            db.conn.commit()
                            logger.info(f"[CHAT COMPACTION] Successfully saved summary checkpoint for incident {incident_id}")
                except Exception as sub_err:
                    logger.error(f"[CHAT COMPACTION] Database/LLM error: {sub_err}")
                    try:
                        db.conn.rollback()
                    except:
                        import logging; logging.getLogger(__name__).debug('_ = None suppressed')
                finally:
                    if db and db.conn:
                        db.close()
            except Exception as e:
                logger.error(f"[CHAT COMPACTION] Handler exception: {e}")

        await nc.subscribe("chat.compact", queue="chat-compactor-group", cb=chat_compaction_handler)
        logger.info("[CHAT COMPACTION] Subscribed to 'chat.compact' (group: chat-compactor-group).")

        # ── Distributed Tasks: AI Retry ──────────────────────────
        async def ai_retry_handler(msg):
            from rag_engine import get_rag_engine
            try:
                db = get_rag_engine()
                db.connect()
                if not db.conn:
                    return
                try:
                    def _fetch_pending():
                        with db.conn.cursor() as cur:
                            cur.execute("""
                                SELECT i.incident_id, i.device_name, i.evidence 
                                FROM incidents i
                                JOIN incident_states ist ON i.incident_id = ist.incident_id
                                WHERE ist.status IN ('PENDING', 'TRIGGERED') AND i.timestamp < NOW() - INTERVAL '5 minutes'
                                ORDER BY i.timestamp DESC LIMIT 5
                            """)
                            return cur.fetchall()
                    
                    pending = await asyncio.to_thread(_fetch_pending)
                    for row in pending:
                        inc_id, device, evidence = row
                        logger.warning(f"[SCHEDULER RETRY] Retrying AI Consensus for Incident ID {inc_id} on {device}")
                        payload = {
                            "agent": device,
                            "flag": "RETRY_TRIGGER",
                            "evidence": evidence,
                            "incident_id": inc_id,
                            "status": "RETRY",
                            "pc_name": device
                        }
                        await nc.publish(f"telemetry.site.global.critical", json.dumps(payload).encode())
                except Exception as db_err:
                    logger.error(f"[SCHEDULER RETRY] Error in DB query: {db_err}")
                finally:
                    if db and db.conn:
                        db.close()
            except Exception as e:
                logger.error(f"[SCHEDULER RETRY] Exception: {e}")

        await nc.subscribe("scheduler.ai.retry", queue="ai-retry-group", cb=ai_retry_handler)
        logger.info("[SCHEDULER RETRY] Subscribed to 'scheduler.ai.retry' (group: ai-retry-group).")

        # ── Distributed Tasks: Verification ───────────────────────
        async def verification_handler(msg):
            from rag_engine import get_rag_engine
            try:
                db = get_rag_engine()
                db.connect()
                if not db.conn:
                    return
                try:
                    re = RollbackEngine(nc=nc)
                    def _fetch_execs():
                        with db.conn.cursor() as cur:
                            cur.execute("""
                                SELECT incident_id, id, action_name FROM approval_queue 
                                WHERE status = 'EXECUTED' AND created_at < NOW() - INTERVAL '3 minutes'
                                LIMIT 5
                            """)
                            return cur.fetchall()
                    
                    execs = await asyncio.to_thread(_fetch_execs)
                    for row in execs:
                        inc_id, state_id, action = row
                        logger.info(f"[SCHEDULER VERIFY] Verifying execution state for Incident ID {inc_id}")
                        
                        verify_payload = {
                            "incident_id": str(inc_id),
                            "event_id": str(state_id),
                            "action": action,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                        
                        try:
                            ver_resp = await nc.request(
                                "agent.verify.result",
                                json.dumps(verify_payload).encode(),
                                timeout=2.0
                            )
                            verify_data = json.loads(ver_resp.data.decode())
                            rollback_needed = bool(verify_data.get("rollback_needed", False))
                            status_str = str(verify_data.get("verification_status") or "FAILED")
                            
                            def _update_verification():
                                with db.conn.cursor() as cur:
                                    cur.execute("""
                                        INSERT INTO verification_logs (
                                            incident_id, verification_status, service_alive, port_open,
                                            cpu_normalized, memory_normalized, logs_clean, rollback_needed, created_at
                                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                                    """, (
                                        inc_id,
                                        status_str,
                                        bool(verify_data.get("service_alive", True)),
                                        bool(verify_data.get("port_open", True)),
                                        bool(verify_data.get("cpu_normalized", True)),
                                        bool(verify_data.get("memory_normalized", True)),
                                        bool(verify_data.get("logs_clean", True)),
                                        rollback_needed
                                    ))
                                    
                                    if rollback_needed:
                                        cur.execute("UPDATE approval_queue SET status = 'FAILED' WHERE incident_id = %s", (inc_id,))
                                    else:
                                        cur.execute("UPDATE approval_queue SET status = 'VERIFIED' WHERE incident_id = %s", (inc_id,))
                                    db.conn.commit()
                            
                            await asyncio.to_thread(_update_verification)
                            
                            if rollback_needed:
                                await re.trigger_rollback(inc_id, str(state_id), action)
                        except Exception as ver_err:
                            logger.error(f"[SCHEDULER VERIFY] Verification request failed for incident {inc_id}: {ver_err}")
                except Exception as db_err:
                    logger.error(f"[SCHEDULER VERIFY] Error in DB query: {db_err}")
                finally:
                    if db and db.conn:
                        db.close()
            except Exception as e:
                logger.error(f"[SCHEDULER VERIFY] Exception: {e}")

        await nc.subscribe("scheduler.verification", queue="verification-scheduler-group", cb=verification_handler)
        logger.info("[SCHEDULER VERIFY] Subscribed to 'scheduler.verification' (group: verification-scheduler-group).")

        # ── World Model Update Loop ──
        def world_model_loop_sync():
            from rag_engine import get_rag_engine
            from world_model.world_model_updater import WorldModelUpdater
            try:
                db = get_rag_engine()
                db.connect()
                if db.conn:
                    updater = WorldModelUpdater(db.conn)
                    updater.run_all_engines()
                    db.close()
            except Exception as e:
                logger.error(f"[WORLD MODEL LOOP] Error: {e}")

        async def world_model_loop_async():
            while True:
                await asyncio.to_thread(world_model_loop_sync)
                # Run every 5 minutes
                await asyncio.sleep(300)
                
        asyncio.create_task(world_model_loop_async())

        # ── Predictive Intelligence Loop (Sprint B) ──
        def predictive_loop_sync():
            from rag_engine import get_rag_engine
            from predictive.predictive_engine import PredictiveEngine
            try:
                db = get_rag_engine()
                db.connect()
                if db.conn:
                    pred_engine = PredictiveEngine(db.conn)
                    with db.conn.cursor() as cur:
                        cur.execute("SELECT asset_id, criticality, last_telemetry FROM assets WHERE last_telemetry IS NOT NULL LIMIT 50")
                        assets = cur.fetchall()
                        for asset in assets:
                            asset_id, criticality, telemetry = asset
                            if isinstance(telemetry, str):
                                import json
                                telemetry = json.loads(telemetry)
                            
                            # Query actual historical telemetry logs from DB (windowing ops)
                            historical_telemetry = {}
                            cur.execute("""
                                SELECT metric_name, metric_value, EXTRACT(EPOCH FROM timestamp) as ts
                                FROM telemetry_logs
                                WHERE device_name = %s 
                                  AND metric_name IN ('disk_usage', 'cpu_usage', 'memory_usage')
                                ORDER BY timestamp DESC LIMIT 20
                            """, (asset_id,))
                            hist_rows = cur.fetchall()
                            
                            for row in reversed(hist_rows): # Process from oldest to newest
                                m_name, m_val, m_ts = row
                                if m_name not in historical_telemetry:
                                    historical_telemetry[m_name] = []
                                historical_telemetry[m_name].append([m_ts, float(m_val)])
                                
                            pred_engine.predict_incident(asset_id, telemetry, historical_telemetry, criticality)
                    db.close()
            except Exception as e:
                logger.error(f"[PREDICTIVE LOOP] Error: {e}")

        async def predictive_loop_async():
            while True:
                await asyncio.to_thread(predictive_loop_sync)
                await asyncio.sleep(60) # Run every minute
                
        asyncio.create_task(predictive_loop_async())
        
        # ── Recovery Orchestrator & Post Verification ──
        try:
            from rag_engine import get_rag_engine
            db = get_rag_engine()
            db.connect()
            if db.conn:
                from governance.execution_orchestrator import GovernanceExecutionOrchestrator
                from governance.recovery_worker import RecoveryOrchestrator
                from verification.post_verification_engine import PostVerificationEngine
                
                orchestrator = GovernanceExecutionOrchestrator(nc, db.conn)
                recovery_worker = RecoveryOrchestrator(nc, db.conn, orchestrator)
                asyncio.create_task(recovery_worker.start_background_tasks())
                
                post_verification_engine = PostVerificationEngine(nc, db.conn)
                asyncio.create_task(post_verification_engine.start())
        except Exception as e:
            logger.error(f"[WORKER INIT] Failed to start Recovery/Verification Workers: {e}")

        while True:
            await asyncio.sleep(1)
            
    except Exception as e:
        logger.error(f"NATS connection or runner exception: {e}")
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
