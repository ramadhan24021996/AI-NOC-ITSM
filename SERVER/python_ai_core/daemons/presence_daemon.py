"""
P6: Operator Presence Engine & Auto-Routing
OSI Incident Ops Hardening v3.0

Features:
  - Heartbeat listener on NATS subject `operator.presence.heartbeat`
  - Periodic presence checker (heartbeat > 90s -> OFFLINE, load >= capacity -> BUSY)
  - availability_score formula computation
  - Auto-routing helper: routes incident to best operator
  - Audit hooks for presence state changes (OPERATOR_ONLINE, OPERATOR_OFFLINE, OPERATOR_ASSIGNED)
"""
import asyncio
import json
import logging
import os
import psycopg2
from datetime import datetime, timezone
from audit_logger import write_audit_log, get_db

logger = logging.getLogger("PRESENCE_DAEMON")

class OperatorPresenceEngine:
    def __init__(self, nc=None, interval_sec: int = 10):
        self.nc = nc
        self.interval_sec = interval_sec

    # ──────────────────────────────────────────────────────────
    # START DAEMON
    # ──────────────────────────────────────────────────────────
    async def start(self):
        logger.info("[PRESENCE DAEMON] Starting Operator Presence Engine...")
        if self.nc:
            await self.nc.subscribe("operator.presence.heartbeat", queue="presence-daemon-group", cb=self.handle_heartbeat)
            logger.info("[PRESENCE DAEMON] Subscribed to NATS 'operator.presence.heartbeat'")
        
        # Start periodic evaluation loop
        asyncio.create_task(self.presence_check_loop())

    # ──────────────────────────────────────────────────────────
    # HANDLE HEARTBEAT
    # ──────────────────────────────────────────────────────────
    async def handle_heartbeat(self, msg):
        """
        NATS payload:
        {
          "operator_id": "op_123",
          "status": "ONLINE",      // ONLINE, AWAY, BUSY
          "current_site": "jakarta",
          "current_shift": "night"
        }
        """
        conn = None
        try:
            data = json.loads(msg.data.decode())
            op_id = data.get("operator_id")
            status = data.get("status", "ONLINE")
            current_site = data.get("current_site", "global")
            current_shift = data.get("current_shift")

            if not op_id:
                return

            conn = get_db()
            with conn.cursor() as cur:
                # 1. Fetch current presence status if exists
                cur.execute("SELECT status FROM operator_presence WHERE operator_id = %s", (op_id,))
                row = cur.fetchone()
                old_status = row[0] if row else "OFFLINE"

                # 2. Update presence details
                cur.execute("""
                    INSERT INTO operator_presence
                        (operator_id, status, heartbeat_at, last_seen, current_site, current_shift)
                    VALUES (%s, %s, NOW(), NOW(), %s, %s)
                    ON CONFLICT (operator_id) DO UPDATE SET
                        status = CASE WHEN operator_presence.status = 'BUSY' THEN 'BUSY' ELSE EXCLUDED.status END,
                        heartbeat_at = NOW(),
                        last_seen = NOW(),
                        current_site = EXCLUDED.current_site,
                        current_shift = EXCLUDED.current_shift
                """, (op_id, status, current_site, current_shift))

                # 3. Log audit if operator goes online
                if old_status == "OFFLINE" and status in ("ONLINE", "AWAY"):
                    write_audit_log(
                        action_type="OPERATOR_ONLINE",
                        actor=op_id,
                        target="operator_presence",
                        payload={"status": status, "site": current_site, "shift": current_shift},
                        conn=conn
                    )

            conn.commit()

            # Publish presence update via NATS
            if self.nc:
                update_event = {
                    "operator_id": op_id,
                    "status": status,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                await self.nc.publish("operator.presence.update", json.dumps(update_event).encode())

        except Exception as e:
            logger.error("[PRESENCE DAEMON] Heartbeat processing failed: %s", e)
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

    # ──────────────────────────────────────────────────────────
    # PERIODIC PRESENCE CHECK LOOP
    # ──────────────────────────────────────────────────────────
    async def presence_check_loop(self):
        while True:
            try:
                await self.evaluate_presence()
            except Exception as e:
                logger.error("[PRESENCE DAEMON] Evaluation loop failed: %s", e)
            await asyncio.sleep(self.interval_sec)

    async def evaluate_presence(self):
        conn = None
        try:
            conn = get_db()
            with conn.cursor() as cur:
                # 1. Fetch current shift/limits
                cur.execute("""
                    SELECT 
                        opr.operator_id, 
                        opr.status, 
                        opr.heartbeat_at,
                        op.max_workload,
                        (SELECT COUNT(*) FROM fleet_incidents WHERE owner_id = opr.operator_id AND status NOT IN ('RESOLVED','CLOSED')) AS current_load,
                        op.specialization
                    FROM operator_presence opr
                    LEFT JOIN operator_profiles op ON op.operator_id = opr.operator_id
                """)
                operators = cur.fetchall()

                for row in operators:
                    op_id, status, heartbeat_at, max_workload, current_load, spec = row
                    max_workload = max_workload or 5
                    current_load = current_load or 0
                    spec = spec or []

                    new_status = status
                    
                    # Heartbeat check: if > 90 seconds, mark OFFLINE
                    if heartbeat_at:
                        now_dt = datetime.now(heartbeat_at.tzinfo) if heartbeat_at.tzinfo else datetime.now()
                        age_sec = (now_dt - heartbeat_at).total_seconds()
                        if age_sec > 90 and status != "OFFLINE":
                            new_status = "OFFLINE"
                            write_audit_log(
                                action_type="OPERATOR_OFFLINE",
                                actor=op_id,
                                target="operator_presence",
                                payload={"reason": "Heartbeat timeout (>90s)", "last_seen_sec": age_sec},
                                conn=conn
                            )
                    
                    # Capacity check: if current_load >= max_capacity, mark BUSY
                    if new_status in ("ONLINE", "AWAY") and current_load >= max_workload:
                        new_status = "BUSY"

                    # Calculate availability_score
                    # availability_score = (weight_online * status) + (weight_capacity * remaining_capacity)
                    weight_online = 0.6
                    weight_capacity = 0.4
                    
                    status_factor = 1.0 if new_status == "ONLINE" else 0.5 if new_status == "AWAY" else 0.0
                    capacity_factor = max(0.0, (max_workload - current_load) / max_workload)
                    availability_score = (weight_online * status_factor) + (weight_capacity * capacity_factor)

                    # Update database presence
                    cur.execute("""
                        UPDATE operator_presence
                        SET status = %s,
                            current_load = %s,
                            max_capacity = %s,
                            availability_score = %s
                        WHERE operator_id = %s
                    """, (new_status, current_load, max_workload, availability_score, op_id))

                    # Publish status update if changed
                    if new_status != status and self.nc:
                        update_event = {
                            "operator_id": op_id,
                            "status": new_status,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                        await self.nc.publish("operator.presence.update", json.dumps(update_event).encode())

            conn.commit()
        except Exception as e:
            logger.error("[PRESENCE DAEMON] Failed to evaluate presence: %s", e)
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

    # ──────────────────────────────────────────────────────────
    # AUTO-ROUTING ENGINE
    # ──────────────────────────────────────────────────────────
    def route_incident(self, site_id: str, category: str, conn=None) -> str or None:
        """
        Routes an incident to the best matching operator:
          1. status IN ('ONLINE', 'AWAY')
          2. site access match
          3. Rank by availability_score (which factors load and status)
        """
        close_conn = False
        if conn is None:
            conn = get_db()
            close_conn = True

        try:
            with conn.cursor() as cur:
                # Find matching operator
                cur.execute("""
                    SELECT opr.operator_id, op.specialization, opr.availability_score
                    FROM operator_presence opr
                    JOIN operator_profiles op ON op.operator_id = opr.operator_id
                    WHERE opr.status IN ('ONLINE', 'AWAY')
                      AND (%s IS NULL OR %s = ANY(op.site_access) OR cardinality(op.site_access) = 0)
                    ORDER BY opr.availability_score DESC
                """, (site_id, site_id))
                rows = cur.fetchall()

                if not rows:
                    return None

                # Rank by specialization match
                best_op = None
                best_score = -1.0
                for row in rows:
                    op_id, spec, avail_score = row
                    spec = spec or []
                    match_score = 1.0 if category.upper() in [s.upper() for s in spec] else 0.0
                    
                    # Final weighted score with specialization
                    final_score = (0.8 * avail_score) + (0.2 * match_score)
                    if final_score > best_score:
                        best_score = final_score
                        best_op = op_id

                return best_op
        except Exception as e:
            logger.error("[PRESENCE DAEMON] Incident routing error: %s", e)
            return None
        finally:
            if close_conn:
                conn.close()
