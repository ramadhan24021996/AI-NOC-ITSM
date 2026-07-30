"""
P9: Replay Simulation Engine
OSI Incident Ops Hardening v3.0

Features:
  - Timeline reconstruction from incident_events
  - Replay modes: FORENSIC, TRAINING, SIMULATION, AI_REFLECTION
  - Computes root cause, missed signals, operator delay, escalation effectiveness
  - Saves sessions to replay_sessions table
  - Integrates NATS subject incident.replay.<incident_id> and immutable audit logging
"""
import asyncio
import json
import logging
import os
import psycopg2
from datetime import datetime, timezone
from services.audit_logger import write_audit_log, get_db

logger = logging.getLogger("REPLAY_ENGINE")

class ReplaySimulationEngine:
    def __init__(self, nc=None):
        self.nc = nc

    async def start(self):
        logger.info("[REPLAY ENGINE] Starting Replay Simulation Engine...")
        if self.nc:
            # Subscribe to wildcard replay topic with queue group
            await self.nc.subscribe("incident.site.*.replay.*", queue="replay-engine-group", cb=self.handle_replay_request)
            logger.info("[REPLAY ENGINE] Subscribed to NATS 'incident.site.*.replay.*'")

    async def handle_replay_request(self, msg):
        """
        NATS subject: incident.replay.<incident_id>
        Payload:
        {
          "mode": "FORENSIC",  // FORENSIC, TRAINING, SIMULATION, AI_REFLECTION
          "actor": "op_99"
        }
        """
        try:
            subject = msg.subject
            incident_id_str = subject.split(".")[-1]
            incident_id = int(incident_id_str)

            data = json.loads(msg.data.decode())
            mode = data.get("mode", "FORENSIC")
            actor = data.get("actor", "system")

            logger.info("[REPLAY ENGINE] Replay request for Incident #%d (mode: %s, actor: %s)", incident_id, mode, actor)
            
            result = self.execute_replay(incident_id, mode, actor)
            
            if msg.reply:
                await msg.respond(json.dumps(result).encode())

            # Notify thread using sharded site subject
            if self.nc:
                site_id_str = "global"
                try:
                    db_conn = get_db()
                    with db_conn.cursor() as cur:
                        cur.execute("SELECT site_id FROM fleet_incidents WHERE incident_id = %s", (incident_id,))
                        row = cur.fetchone()
                        if row and row[0]:
                            s = str(row[0]).lower().strip()
                            s = s.replace(" ", "_").replace(".", "_")
                            site_id_str = s
                    db_conn.close()
                except Exception as dberr:
                    logger.warning(f"Failed to query site ID for replay notify: {dberr}")

                await self.nc.publish(f"chat.site.{site_id_str}.thread.{incident_id}", json.dumps({
                    "type": "SYSTEM_INCIDENT",
                    "sender_type": "SYSTEM",
                    "incident_id": incident_id,
                    "message": f"🔄 Replay Simulation ({mode}) completed. Lessons learned: {result['lessons_learned']}",
                    "data": result
                }).encode())

            # ── GAP: Rollback Trigger ──
            # Auto-trigger rollback jika replay mendeteksi kegagalan (anomaly_found = True)
            if self.nc and result.get("anomaly_found"):
                logger.info(f"[REPLAY ENGINE] Anomaly detected in incident {incident_id}. Auto-triggering rollback via NATS.")
                rollback_payload = {
                    "incident_id": incident_id,
                    "action": "AUTO_REVERT",
                    "reason": "Anomaly detected during Replay Simulation",
                    "triggered_by": "replay_engine"
                }
                await self.nc.publish("remediation.rollback", json.dumps(rollback_payload).encode())

        except Exception as e:
            logger.error("[REPLAY ENGINE] Replay request handling failed: %s", e)
            if msg.reply:
                await msg.respond(json.dumps({"success": False, "reason": str(e)}).encode())

    def execute_replay(self, incident_id: int, mode: str, actor: str) -> dict:
        conn = get_db()
        try:
            # 1. Audit log: REPLAY_STARTED
            write_audit_log(
                action_type="REPLAY_STARTED",
                actor=actor,
                target=f"incident_{incident_id}",
                payload={"mode": mode},
                conn=conn
            )

            # 2. Fetch all events for the incident
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT event_id, event_type, payload, created_at
                    FROM incident_events
                    WHERE incident_id = %s
                    ORDER BY created_at ASC
                """, (str(incident_id),))
                rows = cur.fetchall()

            timeline = []
            anomaly_found = False
            remediation_path = "Original remediation path followed."
            
            for row in rows:
                ev_id, ev_type, payload_str, created_at = row
                try:
                    payload = json.loads(payload_str)
                except Exception:
                    payload = {"raw": payload_str}
                
                timeline.append({
                    "event_id": ev_id,
                    "type": ev_type,
                    "payload": payload,
                    "timestamp": created_at.isoformat() if created_at else None
                })
                if ev_type == "FAILED" or ev_type == "ROLLBACK":
                    anomaly_found = True

            # 3. Calculate operator delay and escalation effectiveness
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT created_at, acked_at, resolved_at, severity, description
                    FROM fleet_incidents
                    WHERE incident_id = %s
                """, (incident_id,))
                inc_row = cur.fetchone()

            op_delay_sec = 0
            rca_summary = "N/A"
            escalation_eff = "N/A"
            lessons_learned = "All systems functioned normally."

            if inc_row:
                created_at, acked_at, resolved_at, severity, description = inc_row
                rca_summary = f"Root cause related to: {description or 'General alert'}"
                
                if acked_at and created_at:
                    op_delay_sec = int((acked_at - created_at).total_seconds())

                # Escalation effectiveness check
                cur.execute("SELECT COUNT(*) FROM escalation_log WHERE incident_id = %s", (incident_id,))
                esc_row = cur.fetchone()
                esc_count = esc_row[0] if esc_row else 0
                if esc_count > 0:
                    escalation_eff = f"Escalated {esc_count} times. Response delay: {op_delay_sec}s."
                    lessons_learned = "Operator response time needs improvement. Escalation engine fired successfully."
                else:
                    escalation_eff = "No escalations required."
                    lessons_learned = "SLA maintained. Smooth closure path."

            # AI Reflection Generation
            reflection = {
                "root_cause": rca_summary,
                "missed_signals": ["Pre-incident warning metrics were ignored"] if op_delay_sec > 900 else [],
                "operator_delay_seconds": op_delay_sec,
                "escalation_effectiveness": escalation_eff,
                "improved_remediation_path": "Auto-rollback triggered immediately upon verification failure." if anomaly_found else "Remediation path optimized."
            }

            replay_result = {
                "timeline": timeline,
                "reflection": reflection,
                "remediation_path": remediation_path
            }

            # 4. Save session to replay_sessions
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO replay_sessions
                        (incident_id, mode, started_at, completed_at, replay_result, anomaly_found, lessons_learned)
                    VALUES (%s, %s, NOW(), NOW(), %s, %s, %s)
                    RETURNING replay_id
                """, (
                    incident_id,
                    mode,
                    json.dumps(replay_result),
                    anomaly_found,
                    lessons_learned
                ))
                replay_row = cur.fetchone()
                replay_id = replay_row[0] if replay_row else None

                # Audit log: REPLAY_COMPLETED
                write_audit_log(
                    action_type="REPLAY_COMPLETED",
                    actor=actor,
                    target=f"incident_{incident_id}",
                    payload={"replay_id": replay_id, "mode": mode, "timeline_events": len(timeline)},
                    conn=conn
                )

            conn.commit()
            return {
                "success": True,
                "replay_id": replay_id,
                "incident_id": incident_id,
                "mode": mode,
                "timeline_size": len(timeline),
                "lessons_learned": lessons_learned,
                "reflection": reflection,
                "anomaly_found": anomaly_found
            }

        except Exception as e:
            logger.error("[REPLAY ENGINE] Replay execution failed: %s", e)
            conn.rollback()
            raise
        finally:
            conn.close()
