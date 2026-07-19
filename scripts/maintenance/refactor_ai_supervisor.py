import re

with open("SERVER/python_ai_core/ai_supervisor.py", "r") as f:
    lines = f.readlines()

# Find the start and end of the block
start_idx = -1
end_idx = -1

for i, line in enumerate(lines):
    if "# ── Phase 2 Item 4: Verification using ActionVerifier ─────────────" in line:
        start_idx = i
    if "# Acknowledge NATS message" in line and start_idx != -1:
        end_idx = i
        break

if start_idx != -1 and end_idx != -1:
    extracted_block = "".join(lines[start_idx:end_idx])
    
    # We will replace the block with an asyncio.create_task call
    new_call = """
                    import asyncio
                    asyncio.create_task(
                        run_background_verification(
                            nc=nc,
                            incident_id=incident_id,
                            validated_action_name=validated_action.recommended_action,
                            pc_name=data.get("pc_name", "UNKNOWN"),
                            exec_id=exec_id,
                            site_id_str=site_id_str,
                            event_id=event_id
                        )
                    )
"""
    # Insert the background function definition above the message_handler
    # Let's find where message_handler is defined
    handler_idx = -1
    for i, line in enumerate(lines):
        if "async def message_handler(msg):" in line:
            handler_idx = i
            break
            
    background_func = """
async def run_background_verification(nc, incident_id, validated_action_name, pc_name, exec_id, site_id_str, event_id):
    import json
    import time
    from datetime import datetime, timezone
    from schemas import VerificationSchema
    from rag_engine import get_rag_engine
    from verification.action_verifier import ActionVerifier
    from verification.rollback_engine import RollbackEngine
    from cognition.evidence_reasoning_graph import EvidenceReasoningGraph
    from utils.event_sourcing import log_event_sourced
    import logging
    logger = logging.getLogger("SUPERVISOR_BG")

    rag = get_rag_engine()
    rag.connect()
    
    _rollback_engine = RollbackEngine(rag.conn, nc)
    _verifier = ActionVerifier(rag.conn, _rollback_engine, shadow_mode=False)
    _erg = EvidenceReasoningGraph(rag.conn)
    
    logger.info(f"[VERIFY BG] Starting ActionVerifier for incident {incident_id}")
    verify_start_time = time.time()
    
    expected_outcome = {
        "status": "ONLINE"
    }
    
    try:
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
                    cur.execute(\"\"\"
                        INSERT INTO verification_logs (
                            incident_id, verification_status, service_alive, port_open,
                            cpu_normalized, memory_normalized, logs_clean, rollback_needed, response_latency_ms, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()) RETURNING id
                    \"\"\", (
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
                        cur.execute(\"\"\"
                            INSERT INTO rollback_logs (
                                incident_id, original_action, rollback_command,
                                trigger_reason, rollback_result, created_at
                            ) VALUES (%s, %s, %s, %s, %s, NOW()) RETURNING id
                        \"\"\", (
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

            rollback_engine = RollbackEngine(nc)
            rollback_dispatch_time = time.time()
            _inc_id_for_rollback = incident_id if incident_id is not None else 0
            success = await rollback_engine.trigger_rollback(_inc_id_for_rollback, event_id, validated_action_name)
            rollback_rtt_ms = int((time.time() - rollback_dispatch_time) * 1000)
            
            if rollback_id and rag and rag.conn:
                try:
                    rollback_status = "EXECUTED" if success else "FAILED"
                    with rag.conn.cursor() as cur:
                        cur.execute(\"\"\"
                            UPDATE rollback_logs
                            SET rollback_result = %s, execution_rtt_ms = %s, created_at = NOW()
                            WHERE id = %s
                        \"\"\", (rollback_status, rollback_rtt_ms, rollback_id))
                        rag.conn.commit()
                        logger.info(f"[DB BG] Updated rollback log {rollback_id} to status: {rollback_status}")
                        
                        log_event_sourced(rag.conn, "rollback_events", rollback_id, "COMPLETED" if success else "FAILED", {
                            "incident_id": incident_id,
                            "execution_rtt_ms": rollback_rtt_ms
                        })
                except Exception as db_err:
                    logger.error(f"[DB BG] Failed to update rollback log: {db_err}")

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
                    
                    cur.execute(\"\"\"
                        INSERT INTO incident_post_mortems (
                            incident_id, device_name, flag, mttr_seconds, blast_radius,
                            rca_summary, remediation_effectiveness, prevention_steps, report_data, created_at
                        ) VALUES (%s, %s, 'SYSTEM_GENERATED', 0, 'MEDIUM', %s, 'FAILED', ARRAY[%s, %s], %s::jsonb, NOW())
                    \"\"\", (
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
                    _ = None

        if rag and rag.conn and pc_name:
            try:
                from trust_engine import TrustEngine
                te = TrustEngine()
                if validated_verify.rollback_needed:
                    te.record_agent_event(rag.conn, pc_name, "ROLLBACK")
                elif validated_verify.verification_status == "SUCCESS":
                    te.record_agent_event(rag.conn, pc_name, "SUCCESS")
                    
                    try:
                        with rag.conn.cursor() as cur:
                            cur.execute("UPDATE fleet_incidents SET status = 'RESOLVED', resolved_at = NOW() WHERE incident_id = %s", (incident_id,))
                            
                            cur.execute(\"\"\"
                                INSERT INTO incident_post_mortems (
                                    incident_id, device_name, flag, mttr_seconds, blast_radius,
                                    rca_summary, remediation_effectiveness, prevention_steps, report_data, created_at
                                ) VALUES (%s, %s, 'SYSTEM_GENERATED', 0, 'LOW', %s, 'SUCCESS', ARRAY[%s], %s::jsonb, NOW())
                            \"\"\", (
                                incident_id,
                                pc_name,
                                f"Auto-Mitigation '{validated_action_name}' successfully resolved the incident.",
                                f"Added '{validated_action_name}' to Golden Knowledge.",
                                json.dumps({"verified_score": verify_result.get("score", 100), "source": "AUTO_RESOLUTION"})
                            ))
                            
                            cur.execute(\"\"\"
                                INSERT INTO incident_feedback (
                                    incident_id, rca_summary, recommended_action, effectiveness_score, user_feedback, created_at
                                ) VALUES (%s, %s, %s, %s, %s, NOW())
                            \"\"\", (
                                incident_id,
                                f"Auto-Mitigation '{validated_action_name}' successfully resolved the incident.",
                                validated_action_name,
                                verify_result.get("score", 100),
                                "SYSTEM_AUTO_LEARN"
                            ))
                        rag.conn.commit()
                        logger.info(f"[AUTO-RESOLUTION BG] Incident {incident_id} successfully marked as RESOLVED and pushed to Knowledge Queue.")
                    except Exception as resolve_err:
                        logger.error(f"[AUTO-RESOLUTION BG] Failed to resolve incident: {resolve_err}")
                        try:
                            rag.conn.rollback()
                        except:
                            _ = None
            except Exception as te_err:
                logger.error(f"Failed to record trust event or resolve: {te_err}")

    except Exception as e:
        logger.error(f"[VERIFY BG] Unexpected error: {e}")
    finally:
        if rag and rag.conn:
            rag.conn.close()

"""
    
    # Update the lines
    new_lines = lines[:handler_idx] + [background_func] + lines[handler_idx:start_idx] + [new_call] + lines[end_idx:]
    with open("SERVER/python_ai_core/ai_supervisor.py", "w") as fw:
        fw.writelines(new_lines)
    print("REFACTOR SUCCESS")
else:
    print("FAILED TO FIND BLOCK")
