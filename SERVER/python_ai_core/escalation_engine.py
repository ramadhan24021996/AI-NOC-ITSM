"""
P4: Auto Escalation Engine
OSI Incident Ops Hardening v3.0

Rules:
  - > 15 min no ACK   → Level 1: Telegram notify
  - > 30 min no response → Level 2: Reassign to available operator
  - > 60 min unresolved  → Level 3: Dashboard alert + AI escalation
  - SLA breach           → Level 3: Force CRITICAL + Telegram + AI

Runs as asyncio background task inside ai_supervisor.py
"""
import asyncio
import json
import logging
import os
import psycopg2
from datetime import datetime, timezone
from presence_daemon import OperatorPresenceEngine

logger = logging.getLogger("ESCALATION_ENGINE")

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


class AutoEscalationEngine:
    """
    Scans open incidents on a periodic basis and fires escalation
    actions based on age, ACK status, and SLA breach.
    """

    def __init__(self, nc=None, interval_sec: int = 60):
        self.nc = nc
        self.interval_sec = interval_sec

    # ──────────────────────────────────────────────────────────
    # MAIN LOOP
    # ──────────────────────────────────────────────────────────
    async def start(self):
        logger.info("[ESCALATION ENGINE] Started — scanning every %ds", self.interval_sec)
        while True:
            try:
                await self._scan()
            except Exception as e:
                logger.error("[ESCALATION ENGINE] Scan error: %s", e)
            await asyncio.sleep(self.interval_sec)

    # ──────────────────────────────────────────────────────────
    # SCAN
    # ──────────────────────────────────────────────────────────
    async def _scan(self):
        conn = None
        try:
            conn = get_db()
            with conn.cursor() as cur:
                # Fetch non-resolved, not-yet-maximally-escalated incidents
                # Use LIMIT to process batches and avoid O(74k) blocking loop
                cur.execute("""
                    SELECT
                        fi.incident_id,
                        fi.site_id,
                        fi.pc_name,
                        fi.severity,
                        fi.status,
                        fi.owner_id,
                        fi.escalation_level,
                        fi.created_at,
                        fi.acked_at,
                        fi.sla_deadline,
                        EXTRACT(EPOCH FROM (NOW() - fi.created_at))::INTEGER AS age_sec
                    FROM fleet_incidents fi
                    WHERE fi.status NOT IN ('RESOLVED','CLOSED','DLQ','FAILED')
                      AND fi.escalation_level < 3
                    ORDER BY fi.escalation_level ASC, fi.created_at ASC
                    LIMIT 200
                """)
                incidents = cur.fetchall()

            escalated_count = 0
            for row in incidents:
                (inc_id, site_id, pc_name, severity, status, owner_id,
                 esc_level, created_at, acked_at, sla_deadline, age_sec) = row
                fired = await self._evaluate_incident(
                    conn, inc_id, site_id, pc_name, severity, status,
                    owner_id, esc_level, created_at, acked_at, sla_deadline, age_sec
                )
                if fired:
                    conn.commit()
                    escalated_count += 1

            if escalated_count > 0:
                logger.info("[ESCALATION ENGINE] Scan complete: %d incidents escalated this cycle", escalated_count)
        except Exception as e:
            logger.error("[ESCALATION ENGINE] Scan error: %s", e)
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    import logging; logging.getLogger(__name__).debug('_ = None suppressed')
        finally:
            if conn:
                conn.close()

    # ──────────────────────────────────────────────────────────
    # EVALUATE SINGLE INCIDENT
    # ──────────────────────────────────────────────────────────
    async def _evaluate_incident(
        self, conn, inc_id, site_id, pc_name, severity, status,
        owner_id, esc_level, created_at, acked_at, sla_deadline, age_sec
    ):
        fired = False

        # ── RULE 1: No ACK within 15 minutes ──────────────────
        if acked_at is None and age_sec >= 900 and esc_level < 1:
            await self._escalate(
                conn, inc_id, site_id, pc_name, severity, status, owner_id,
                new_level=1,
                action="NOTIFY_TELEGRAM",
                reason=f"No ACK after {age_sec // 60} min (threshold: 15 min)"
            )
            fired = True

        # ── RULE 2: No response within 30 minutes ─────────────
        if acked_at is None and age_sec >= 1800 and esc_level < 2:
            best_op = self._find_available_operator(conn, site_id, severity, exclude=owner_id)
            await self._escalate(
                conn, inc_id, site_id, pc_name, severity, status, owner_id,
                new_level=2,
                action="REASSIGN",
                reason=f"No response after {age_sec // 60} min (threshold: 30 min)",
                new_owner=best_op
            )
            fired = True

        # ── RULE 3: Unresolved after 60 minutes ───────────────
        if age_sec >= 3600 and esc_level < 3:
            await self._escalate(
                conn, inc_id, site_id, pc_name, severity, status, owner_id,
                new_level=3,
                action="ALERT_DASHBOARD",
                reason=f"Unresolved after {age_sec // 60} min (threshold: 60 min)"
            )
            fired = True

        # ── RULE 4: SLA Breach ────────────────────────────────
        if sla_deadline:
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            if sla_deadline < now_utc and severity not in ('CRITICAL',) and esc_level < 3:
                await self._escalate(
                    conn, inc_id, site_id, pc_name, severity, status, owner_id,
                    new_level=3,
                    action="FORCE_CRITICAL",
                    reason=f"SLA breached: deadline was {sla_deadline}"
                )
                fired = True

        if fired:
            logger.info(
                "[ESCALATION ENGINE] Incident #%d escalated | age=%ds | level=%d | site=%s",
                inc_id, age_sec, esc_level + 1, site_id
            )
        return fired

    # ──────────────────────────────────────────────────────────
    # ESCALATION ACTION
    # ──────────────────────────────────────────────────────────
    async def _escalate(
        self, conn, inc_id, site_id, pc_name, severity, status,
        old_owner, new_level, action, reason, new_owner=None
    ):
        try:
            with conn.cursor() as cur:
                # 1. Update incident escalation level
                cur.execute("""
                    UPDATE fleet_incidents
                    SET escalation_level = %s,
                        last_escalated_at = NOW(),
                        escalation_reason = %s,
                        owner_id = COALESCE(%s, owner_id),
                        severity = CASE WHEN %s = 'FORCE_CRITICAL' THEN 'CRITICAL' ELSE severity END
                    WHERE incident_id = %s
                """, (new_level, reason, new_owner, action, inc_id))

                # 2. Log to escalation_log
                cur.execute("""
                    INSERT INTO escalation_log
                        (incident_id, escalation_level, action_taken, previous_owner, new_owner, triggered_at)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                """, (inc_id, new_level, action, old_owner, new_owner))

                # 3. Log to incident_events (event sourcing)
                payload = {
                    "escalation_level": new_level,
                    "action": action,
                    "reason": reason,
                    "new_owner": new_owner,
                    "site_id": site_id,
                    "pc_name": pc_name
                }
                cur.execute("""
                    INSERT INTO incident_events
                        (incident_id, event_type, payload, created_at)
                    VALUES (%s, 'ESCALATED', %s, NOW())
                """, (str(inc_id), json.dumps(payload)))

            # 4. Publish to NATS for real-time dashboard update
            if self.nc:
                nats_payload = {
                    "incident_id": inc_id,
                    "site_id": site_id or "global",
                    "pc_name": pc_name,
                    "severity": severity,
                    "escalation_level": new_level,
                    "action": action,
                    "reason": reason,
                    "new_owner": new_owner,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                site_id_str = "global"
                if site_id:
                    s = str(site_id).lower().strip()
                    s = s.replace(" ", "_").replace(".", "_")
                    site_id_str = s

                await self.nc.publish(
                    f"incident.site.{site_id_str}.escalation",
                    json.dumps(nats_payload).encode()
                )

                # Telegram notification for level 1+
                if new_level >= 1:
                    # Level 3: sertakan ringkasan investigasi AI (HandoffPackager)
                    if new_level >= 3:
                        try:
                            from escalation.handoff_packager import HandoffPackager
                            packager = HandoffPackager(db_conn=conn)
                            package  = packager.build(inc_id)
                            telegram_body = packager.to_telegram_message(package)
                        except Exception as hp_err:
                            logger.warning("[ESCALATION] HandoffPackager failed: %s", hp_err)
                            telegram_body = (
                                f"🚨 *ESKALASI L3 AI → NOC ENGINEER*\n"
                                f"Incident #{inc_id} | {pc_name or 'Unknown'} @ {site_id or 'Global'}\n"
                                f"Severity: {severity}\nReason: {reason}"
                            )
                    else:
                        telegram_body = (
                            f"⚠️ ESCALATION L{new_level}\n"
                            f"Incident #{inc_id} | {pc_name or 'Unknown'} @ {site_id or 'Global'}\n"
                            f"Severity: {severity}\nReason: {reason}"
                        )

                    telegram_msg = {
                        "type": "ESCALATION_ALERT",
                        "incident_id": inc_id,
                        "level": new_level,
                        "message": telegram_body,
                    }
                    await self.nc.publish("telegram.alert", json.dumps(telegram_msg).encode())

        except Exception as e:
            logger.error("[ESCALATION ENGINE] Failed to escalate incident #%d: %s", inc_id, e)
            raise

    # ──────────────────────────────────────────────────────────
    # FIND AVAILABLE OPERATOR
    # ──────────────────────────────────────────────────────────
    def _find_available_operator(self, conn, site_id: str, severity: str, exclude: str = None) -> str | None:
        """
        Find the best available operator for reassignment using OperatorPresenceEngine
        """
        try:
            engine = OperatorPresenceEngine()
            routed_op = engine.route_incident(site_id=site_id, category=severity, conn=conn)
            if routed_op:
                logger.info("[ESCALATION ENGINE] Auto-assign via PresenceEngine → operator=%s", routed_op)
                return routed_op
        except Exception as e:
            logger.warning("[ESCALATION ENGINE] Operator presence routing failed: %s", e)
        return None
