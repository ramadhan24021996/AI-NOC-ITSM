"""
supervisor/handlers/approval_handler.py
----------------------------------------
HITL Approval, Escalation, Background Verification, & Chat Compaction Handlers.
Dipecah dari ai_supervisor.py.
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timezone

from state_machine import IncidentState
from supervisor.pipeline_logger import log_event_sourced
from supervisor.core import set_runtime_state

logger = logging.getLogger("AI_SUPERVISOR.approval_handler")


async def apply_incident_transition(nc, conn, incident_id: int, from_state: str, to_state: str, site_id: str = "global", actor: str = "system", context: dict | None = None) -> bool:
    """Helper to apply incident state transition via IncidentEventBus."""
    try:
        from services.state_observer import incident_event_bus
    except ImportError:
        from python_ai_core.services.state_observer import incident_event_bus
    return await incident_event_bus.apply_transition(nc, conn, incident_id, from_state, to_state, site_id, actor, context or {})


async def handle_escalate_request(nc, msg):
    """Handles auto/manual escalation requests."""
    try:
        data = json.loads(msg.data.decode())
        incident_id = data.get("incident_id")
        next_level = data.get("next_level", 2)
        
        parts = msg.subject.split(".")
        site_id_str = parts[2] if len(parts) > 2 else "global"
        
        logger.info(f"[ESCALATE ENGINE] Escalating incident {incident_id} to Level {next_level} for site {site_id_str}")
        
        from engines.rag_engine import get_rag_engine
        db = get_rag_engine()
        db.connect()
        if db.conn and incident_id:
            with db.conn.cursor() as cur:
                cur.execute("UPDATE fleet_incidents SET escalation_level = GREATEST(escalation_level, %s) WHERE incident_id = %s", (next_level, incident_id))
                db.conn.commit()
                
                log_event_sourced(db.conn, "incident_events", incident_id, "ESCALATED", {
                    "actor": "Operator via NOC",
                    "details": f"Escalated to Level {next_level}",
                    "note": data.get("operator_note", "")
                })
            
            await apply_incident_transition(nc, db.conn, incident_id, IncidentState.ANALYZING, IncidentState.OPEN, site_id_str, context={"reason": "Escalation Requested"})
            db.close()
    except Exception as e:
        logger.error(f"[ESCALATE ENGINE] Failed to handle escalation request: {e}")


async def handle_approval_decision(nc, msg):
    """Handles HITL human approval decision."""
    try:
        data = json.loads(msg.data.decode())
        incident_id = data.get("incident_id")
        approval_id = data.get("approval_id")
        decision = data.get("decision")
        operator_id = data.get("operator_id")
        
        from engines.rag_engine import get_rag_engine
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


async def run_background_verification(nc, incident_id, validated_action_name, pc_name, exec_id, site_id_str, event_id, incident_details=None):
    """Runs background verification after remediation action execution."""
    from engines.rag_engine import get_rag_engine
    from verification.action_verifier import ActionVerifier
    from verification.rollback_engine import RollbackEngine
    from cognition.evidence_reasoning_graph import ReasoningRecorder
    bg_logger = logging.getLogger("SUPERVISOR_BG")

    rag = get_rag_engine()
    rag.connect()

    _rollback_engine = RollbackEngine(rag.conn, nc)
    _verifier = ActionVerifier(rag.conn, _rollback_engine, shadow_mode=False)
    _erg = ReasoningRecorder(rag.conn)

    bg_logger.info(f"[VERIFY BG] Starting ActionVerifier for incident {incident_id}")
    verify_start_time = time.time()
    
    if incident_details is None:
        incident_details = {}
        
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
    
    bg_logger.info(f"[VERIFY BG] Computed Dynamic Success Criteria: {expected_outcome}")

    try:
        await apply_incident_transition(nc, rag.conn, incident_id, IncidentState.EXECUTING, IncidentState.VERIFYING, site_id_str, context={"action": validated_action_name})
        
        verification_result = await _verifier.verify_execution(
            incident_id=str(incident_id),
            execution_id=str(exec_id),
            action_name=validated_action_name,
            pc_name=pc_name,
            expected_outcome=expected_outcome,
            timeout_seconds=30
        )

        verification_result_dict = verification_result if isinstance(verification_result, dict) else {}
        bg_logger.info(f"[VERIFY BG] ActionVerifier returned: {verification_result_dict}")

        is_verified = bool(
            verification_result_dict.get("success", False)
            or verification_result_dict.get("status") == "SUCCESS"
        )

        if is_verified:
            bg_logger.info(f"[VERIFY BG] Verification SUCCESS for Incident {incident_id}")
            await apply_incident_transition(nc, rag.conn, incident_id, IncidentState.VERIFYING, IncidentState.RESOLVED, site_id_str, context={"resolution": "Verified Successful (Dual-Evidence Rule #6)"})
        else:
            failure_reason = verification_result_dict.get("failure_reason", "Verification failed")
            bg_logger.warning(f"[VERIFY BG] Verification FAILED for Incident {incident_id}: {failure_reason}")
            await apply_incident_transition(nc, rag.conn, incident_id, IncidentState.VERIFYING, IncidentState.RECOVERING, site_id_str, context={"reason": failure_reason})
            
            bg_logger.info(f"[VERIFY BG] Triggering RollbackEngine for Incident {incident_id}")
            rollback_success = await _rollback_engine.trigger_rollback(
                incident_id=str(incident_id),
                execution_id=str(exec_id),
                action_name=validated_action_name
            )
            
            if rollback_success:
                bg_logger.info(f"[VERIFY BG] Rollback executed successfully for Incident {incident_id}")
                await apply_incident_transition(nc, rag.conn, incident_id, IncidentState.RECOVERING, IncidentState.OPEN, site_id_str, context={"reason": "Rollback Executed - Needs Human Triage"})
            else:
                bg_logger.error(f"[VERIFY BG] Rollback FAILED for Incident {incident_id}")
                await apply_incident_transition(nc, rag.conn, incident_id, IncidentState.RECOVERING, IncidentState.DEGRADED, site_id_str, context={"reason": "Rollback Failed - Escalated to Critical"})

        # RLIF Autonomy Calibration Feedback Loop (Level 5 Adaptive Learning)
        try:
            from governance.rlif_autonomy_calibrator import get_rlif_calibrator
            calibrator = get_rlif_calibrator()
            calib_res = calibrator.record_execution_outcome(
                action_id=validated_action_name,
                asset_class=pc_name,
                success=is_verified,
                incident_id=str(incident_id),
                details=verification_result_dict
            )
            bg_logger.info(f"[VERIFY BG] RLIF Autonomy Calibrated: {calib_res.get('transition')} -> Tier: {calib_res.get('new_tier')}")
        except Exception as _rlif_err:
            bg_logger.warning(f"[VERIFY BG] RLIF Autonomy Calibrator update skipped: {_rlif_err}")

        _erg.record_verification_step(
            incident_id=str(incident_id),
            action_name=validated_action_name,
            passed=is_verified,
            duration_ms=int((time.time() - verify_start_time) * 1000),
            details=verification_result_dict
        )
    except Exception as e:
        bg_logger.error(f"[VERIFY BG] Exception in background verification: {e}")
    finally:
        if rag and rag.conn:
            try:
                rag.close()
            except Exception:
                pass


async def chat_compaction_handler(nc, msg):
    """Summarizes chat message history for long-running incident conversations."""
    from engines.rag_engine import get_rag_engine
    from engines.llm_router import get_router
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
                
                chat_history_str = ""
                for sender, message, _ in rows:
                    chat_history_str += f"{sender}: {message}\n"
                
                prompt = (
                    "You are the Sovereign AI NOC Incident Analysis Copilot. Summarize the following incident chat history "
                    "between the Client (operator/user) and Operator/AI. Extract the key symptoms reported, "
                    "steps taken, and the current status. Do NOT lose diagnostic details. Keep the summary "
                    "under 150 words.\n\n"
                    f"Chat History:\n{chat_history_str}\n\n"
                    "Summary (start with '[CHAT SUMMARY CHECKPOINT]'):"
                )
                
                router = get_router()
                res = await router.execute_with_retry(50, prompt)
                if res["status"] == "SUCCESS":
                    summary_text = str(res.get("response", "")).strip()
                    if not summary_text.startswith("[CHAT SUMMARY CHECKPOINT]"):
                        summary_text = "[CHAT SUMMARY CHECKPOINT] " + summary_text
                    
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
            except Exception:
                pass
        finally:
            if db and db.conn:
                db.close()
    except Exception as e:
        logger.error(f"[CHAT COMPACTION] Handler exception: {e}")


async def verification_handler(nc, msg):
    """NATS subscriber for verification scheduler tasks."""
    from engines.rag_engine import get_rag_engine
    from verification.rollback_engine import RollbackEngine
    try:
        db = get_rag_engine()
        db.connect()
        if not db.conn:
            return
        try:
            re = RollbackEngine(db.conn, nc)
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
                                inc_id, status_str,
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
