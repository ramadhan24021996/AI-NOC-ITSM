"""
supervisor/pipeline_logger.py
------------------------------
AI Supervisor Pipeline Logging & Event Sourcing.
Dipecah dari ai_supervisor.py untuk memisahkan logika persistensi DB audit.
"""
import logging
import json
import uuid
from datetime import datetime, timezone

logger = logging.getLogger("AI_SUPERVISOR.pipeline_logger")

# Try loading AI Runtime state
try:
    from runtime.ai_runtime_state import AIRuntimeState
    _ai_runtime = AIRuntimeState("ai_supervisor")
except Exception:
    _ai_runtime = None


def log_ai_pipeline(
    conn, incident_id, event_id, reasoning_dag, rag_vectors,
    raw_prompt, llm_response, confidence_score, action_executed,
    first_hypothesis, second_hypothesis, final_decision, models_used,
    elapsed_ms, cognitive_trace: dict | None = None
):
    """
    Writes standard pipeline log + cognitive traces
    (reasoning_trace, planning_trace, policy_trace, memory_trace) to ai_audit_trail.
    """
    if not conn:
        return
    try:
        with conn.cursor() as cur:
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

            cur.execute("""
                INSERT INTO ai_audit_trail (
                    incident_id, event_id, reasoning_dag, rag_vectors_retrieved,
                    raw_prompt, llm_response, confidence_score, action_executed,
                    reasoning_trace, planning_trace, policy_trace, memory_trace,
                    worker_state, execution_time_ms, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                incident_id, event_id, json.dumps(reasoning_dag),
                json.dumps(rag_vectors), raw_prompt, llm_response,
                confidence_score, action_executed, reasoning_trace,
                planning_trace, policy_trace, memory_trace, worker_state,
                int(elapsed_ms), datetime.now(timezone.utc)
            ))

            span_id = uuid.uuid4().hex[:8]
            cur.execute("""
                INSERT INTO ai_reflection_logs (
                    incident_id, timestamp, stage_version, first_hypothesis, second_hypothesis, 
                    final_decision, confidence_score, ai_models_used, decision_time_ms,
                    trace_id, span_id, parent_span
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                incident_id, datetime.now(timezone.utc), "v7_hitl",
                first_hypothesis, second_hypothesis, final_decision,
                confidence_score, models_used, int(elapsed_ms),
                event_id, span_id, "ai-supervisor"
            ))
            conn.commit()
            logger.info("[AI OS] Pipeline log + cognitive trace saved. worker_state=%s elapsed_ms=%d", worker_state, int(elapsed_ms))
    except Exception as e:
        logger.error(f"Failed to log AI pipeline to DB: {e}")
        try:
            conn.rollback()
        except Exception:
            pass


def log_event_sourced(conn, table_name, entity_id, event_type, payload):
    """
    Event sourcing persistence router for incident, approval, verification,
    rollback, and security events.
    """
    if not conn:
        return
    try:
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
        except Exception:
            pass
