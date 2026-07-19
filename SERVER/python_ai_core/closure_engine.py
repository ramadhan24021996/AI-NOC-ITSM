"""
P5/P13: Closure Enforcement Engine — Strict Quorum v3.1
OSI Incident Ops Hardening

Strict Quorum Rules (ALL must _ = None):
  1. At least 1 piece of evidence (fleet_evidence OR ai_evidence_logs)
  2. Operator-provided resolution_summary (min 10 chars)
  3. Named resolution actor (not 'system')
  4. Postmortem mandatory if incident duration > 60 minutes
  5. [P13 NEW] verification_logs must confirm remediation success:
       rollback_needed = FALSE AND service_alive = TRUE
       for the incident's device within the last 30 minutes.
  6. AI reflection record (ai_reflection_logs) — soft check, warning only.

  resolution_proof        → screenshot/log path
  resolution_actor        → operator_id (L3 or ADMIN for force-close)
  resolution_duration_sec → computed automatically
"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional, Tuple

import psycopg2

from core.knowledge_edge_manager import get_edge_manager

logger = logging.getLogger("CLOSURE_ENGINE")

DB_HOST     = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT     = os.getenv("DB_PORT", "5432")
DB_NAME     = os.getenv("DB_NAME", "osi_system")
DB_USER     = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

def get_db():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, database=DB_NAME,
        user=DB_USER, password=DB_PASSWORD
    )


class ClosureEnforcementEngine:
    """
    Gate that validates all closure prerequisites before allowing
    an incident to transition to RESOLVED or CLOSED state.

    Usage:
        engine = ClosureEnforcementEngine()
        ok, reason = engine.validate_closure(incident_id, actor, summary, proof)
        if ok:
            engine.commit_closure(incident_id, actor, summary, proof, conn)
    """

    # ──────────────────────────────────────────────────────────
    # VALIDATE
    # ──────────────────────────────────────────────────────────
    def validate_closure(
        self,
        incident_id: int,
        actor: str,
        resolution_summary: str,
        resolution_proof: Optional[str] = None,
        conn=None
    ) -> Tuple[bool, str]:
        """
        Returns (can_close: bool, reason: str)
        """
        close_conn = False
        if conn is None:
            conn = get_db()
            close_conn = True

        try:
            with conn.cursor() as cur:
                # ── Check 1: Evidence exists ──────────────────
                cur.execute("""
                    SELECT 
                        (SELECT COUNT(*) FROM fleet_evidence WHERE incident_id = %s) +
                        (SELECT COUNT(*) FROM ai_evidence_logs WHERE incident_id = %s)
                    AS total_evidence
                """, (incident_id, incident_id))
                evidence_count = cur.fetchone()[0]
                if evidence_count == 0:
                    return False, "CLOSURE_BLOCKED: No evidence attached. Attach logs, screenshot, or AI evidence before closing."

                # ── Check 2: Resolution summary not empty ─────
                if not resolution_summary or len(resolution_summary.strip()) < 10:
                    return False, "CLOSURE_BLOCKED: resolution_summary required (minimum 10 characters)."

                # ── Check 3: Actor (operator) exists ──────────
                if not actor or actor == "system":
                    return False, "CLOSURE_BLOCKED: Closure must be performed by a named operator (not 'system')."

                # ── Check 4: Duration & postmortem gate ───────
                cur.execute("""
                    SELECT 
                        EXTRACT(EPOCH FROM (NOW() - created_at))::INTEGER AS age_sec,
                        (SELECT COUNT(*) FROM incident_post_mortems WHERE incident_id = %s) AS has_postmortem
                    FROM fleet_incidents 
                    WHERE incident_id = %s
                """, (incident_id, incident_id))
                row = cur.fetchone()
                if row is None:
                    return False, f"CLOSURE_BLOCKED: Incident #{incident_id} not found."

                age_sec, has_postmortem = row
                if age_sec > 3600 and has_postmortem == 0:
                    return False, (
                        f"CLOSURE_BLOCKED: Incident open for {age_sec // 60} minutes. "
                        "Postmortem required for incidents lasting > 60 minutes. "
                        "Submit postmortem via API before closing."
                    )

                # ── Check 5: [P13] Verification quorum — remediation confirmed ─
                cur.execute("""
                    SELECT COUNT(*) FROM fleet_incidents WHERE incident_id = %s
                """, (incident_id,))
                fi_row = cur.fetchone()
                if fi_row and fi_row[0] > 0:
                    cur.execute("""
                        SELECT pc_name FROM fleet_incidents WHERE incident_id = %s
                    """, (incident_id,))
                    fi_name_row = cur.fetchone()
                    device_name = fi_name_row[0] if fi_name_row else None

                    if device_name:
                        cur.execute("""
                            SELECT COUNT(*) FROM verification_logs
                            WHERE host_name = %s
                              AND rollback_needed = FALSE
                              AND service_alive   = TRUE
                              AND verified_at     > NOW() - INTERVAL '30 minutes'
                        """, (device_name,))
                        verif_count = cur.fetchone()[0]
                        if verif_count == 0:
                            return False, (
                                f"CLOSURE_BLOCKED: No successful verification record found for device '{device_name}' "
                                "in the last 30 minutes. Run agent verification before closing. "
                                "(verification_logs must show rollback_needed=FALSE and service_alive=TRUE)"
                            )

                # ── Check 6: AI reflection exists (soft warning) ───────────────
                cur.execute("""
                    SELECT COUNT(*) FROM ai_reflection_logs WHERE incident_id = %s
                """, (incident_id,))
                reflection_count = cur.fetchone()[0]
                if reflection_count == 0:
                    logger.warning(
                        "[CLOSURE ENGINE] Incident #%d closing without AI reflection — proceeding with warning.",
                        incident_id
                    )
                    # Not a hard block — warning only (AI may not have run if HITL-only path)

                return True, "OK"

        except Exception as e:
            logger.error("[CLOSURE ENGINE] Validation error for incident #%d: %s", incident_id, e)
            return False, f"CLOSURE_BLOCKED: Internal validation error: {e}"
        finally:
            if close_conn:
                conn.close()

    # ──────────────────────────────────────────────────────────
    # COMMIT CLOSURE
    # ──────────────────────────────────────────────────────────
    async def commit_closure(
        self,
        incident_id: int,
        actor: str,
        resolution_summary: str,
        resolution_proof: Optional[str] = None,
        conn=None,
        emergency_skip: bool = False,
        skip_reason: Optional[str] = None,
        nc=None
    ) -> Tuple[bool, str]:
        """
        After validation passes, commit the closure record and
        update fleet_incidents.status to 'RESOLVED'.
        """
        close_conn = False
        if conn is None:
            conn = get_db()
            close_conn = True

        try:
            with conn.cursor() as cur:
                # Get duration
                cur.execute("""
                    SELECT EXTRACT(EPOCH FROM (NOW() - created_at))::INTEGER
                    FROM fleet_incidents WHERE incident_id = %s
                """, (incident_id,))
                row = cur.fetchone()
                duration_sec = int(row[0]) if row else 0

                # Get AI reflection id if any
                cur.execute("""
                    SELECT reflection_id FROM ai_reflection_logs 
                    WHERE incident_id = %s ORDER BY created_at DESC LIMIT 1
                """, (incident_id,))
                refl_row = cur.fetchone()
                ai_reflection_id = refl_row[0] if refl_row else None

                # Get postmortem id if any  
                cur.execute("""
                    SELECT post_mortem_id FROM incident_post_mortems
                    WHERE incident_id = %s LIMIT 1
                """, (incident_id,))
                pm_row = cur.fetchone()
                postmortem_id = pm_row[0] if pm_row else None
                postmortem_required = (duration_sec > 3600)

                # Insert closure record
                cur.execute("""
                    INSERT INTO incident_closure
                        (incident_id, resolution_summary, resolution_actor, resolution_proof,
                         resolution_duration_sec, ai_reflection_id, postmortem_required,
                         postmortem_id, enforcement_passed, skip_reason, closed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (incident_id) DO UPDATE SET
                        resolution_summary = EXCLUDED.resolution_summary,
                        resolution_actor   = EXCLUDED.resolution_actor,
                        resolution_proof   = EXCLUDED.resolution_proof,
                        resolution_duration_sec = EXCLUDED.resolution_duration_sec,
                        enforcement_passed = EXCLUDED.enforcement_passed,
                        closed_at          = NOW()
                """, (
                    incident_id, resolution_summary, actor, resolution_proof,
                    duration_sec, ai_reflection_id, postmortem_required,
                    postmortem_id, not emergency_skip, skip_reason
                ))

                # Get current status
                cur.execute("SELECT status FROM fleet_incidents WHERE incident_id = %s", (incident_id,))
                status_row = cur.fetchone()
                current_status = status_row[0] if status_row else "OPEN"

                # Event sourcing
                payload = {
                    "actor": actor,
                    "resolution_summary": resolution_summary,
                    "duration_sec": duration_sec,
                    "ai_reflection_id": ai_reflection_id,
                    "postmortem_id": postmortem_id,
                    "emergency_skip": emergency_skip
                }
                cur.execute("""
                    INSERT INTO incident_events
                        (incident_id, event_type, payload, created_at)
                    VALUES (%s, 'RESOLVED', %s, NOW())
                """, (str(incident_id), json.dumps(payload)))

            conn.commit()
            
            # Delegate status update and telemetry to Event Bus
            from state_observer import incident_event_bus
            from state_machine import IncidentState
            await incident_event_bus.apply_transition(
                nc=nc,
                conn=conn,
                incident_id=incident_id,
                from_state=current_status,
                to_state=IncidentState.RESOLVED,
                actor=actor,
                context={"resolution_summary": resolution_summary, "duration_sec": duration_sec}
            )
            logger.info(
                "[CLOSURE ENGINE] Incident #%d RESOLVED by %s in %ds",
                incident_id, actor, duration_sec
            )

            # P15: Reinforce knowledge graph edges for this resolved incident
            try:
                edge_manager = get_edge_manager()
                edges_affected = edge_manager.reinforce_edges(
                    resolved_incident_id=str(incident_id),
                    relationship_hint="SAME_RESOLUTION"
                )
                logger.info(
                    "[CLOSURE ENGINE] Knowledge graph reinforced: %d edges updated for incident #%d",
                    edges_affected, incident_id
                )
            except Exception as edge_err:
                # Edge reinforcement is non-critical — do not block closure on failure
                logger.warning("[CLOSURE ENGINE] Edge reinforcement failed (non-critical): %s", edge_err)

            return True, f"Incident #{incident_id} resolved. Duration: {duration_sec // 60} min."

        except Exception as e:
            logger.error("[CLOSURE ENGINE] Commit error for incident #%d: %s", incident_id, e)
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    import logging; logging.getLogger(__name__).debug('_ = None suppressed')
            return False, f"DB_ERROR: {e}"
        finally:
            if close_conn and conn:
                conn.close()

    # ──────────────────────────────────────────────────────────
    # NATS HANDLER — listen for closure requests
    # ──────────────────────────────────────────────────────────
    async def handle_close_request(self, msg):
        """
        NATS subject: incident.close.request
        Payload: {incident_id, actor, resolution_summary, resolution_proof?, emergency_skip?}
        Reply: {success, reason}
        """
        try:
            data = json.loads(msg.data.decode())
            incident_id = int(data.get("incident_id", 0))
            actor = data.get("actor", "")
            summary = data.get("resolution_summary", "")
            proof = data.get("resolution_proof")
            emergency = bool(data.get("emergency_skip", False))
            skip_reason = data.get("skip_reason")

            if emergency:
                # Emergency bypass — still log it
                ok, reason = await self.commit_closure(
                    incident_id, actor, summary, proof,
                    emergency_skip=True, skip_reason=skip_reason, nc=msg._client
                )
            else:
                # Normal path: validate first
                ok, reason = self.validate_closure(incident_id, actor, summary, proof)
                if ok:
                    ok, reason = await self.commit_closure(incident_id, actor, summary, proof, nc=msg._client)

            response = {"success": ok, "reason": reason, "incident_id": incident_id}
            await msg.respond(json.dumps(response).encode())

        except Exception as e:
            logger.error("[CLOSURE ENGINE] NATS handler error: %s", e)
            err = {"success": False, "reason": str(e)}
            if msg.reply:
                await msg.respond(json.dumps(err).encode())
