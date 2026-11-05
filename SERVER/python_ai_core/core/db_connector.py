import psycopg2
from psycopg2.extras import RealDictCursor
import logging
import os
import time

logger = logging.getLogger(__name__)


class DatabaseConnector:
    def __init__(self):
        # Using Docker service names
        self.host = os.getenv("DB_HOST", "osi-postgres")
        self.port = os.getenv("DB_PORT", "5432")
        self.dbname = os.getenv("DB_NAME", "osi_system")
        self.user = os.getenv("DB_USER", "postgres")
        self.password = os.getenv("DB_PASSWORD", "SecurePassword_123!")

    def get_connection(self):
        try:
            return psycopg2.connect(
                host=self.host,
                port=self.port,
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                connect_timeout=5
            )
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            return None

    # ── Device Queries ────────────────────────────────────────────────────────

    def query_all_devices(self):
        conn = self.get_connection()
        if not conn:
            return []
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT pc_name, ip, online, os_version, last_seen, "
                    "COALESCE(site_id, 'HQ') as site_id, "
                    "COALESCE(status, CASE WHEN online THEN 'ONLINE' ELSE 'OFFLINE' END) as status "
                    "FROM fleet_devices LIMIT 200"
                )
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error(f"[DB] query_all_devices failed: {e}")
            return []
        finally:
            conn.close()


    def query_device_by_name(self, name_hint: str):
        conn = self.get_connection()
        if not conn:
            return None
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT pc_name, ip, online, os_version, last_seen "
                    "FROM fleet_devices WHERE pc_name ILIKE %s LIMIT 1",
                    (f"%{name_hint}%",)
                )
                return cur.fetchone()
        finally:
            conn.close()

    def query_device_by_ip(self, ip_address: str):
        """Lookup device by IP address."""
        conn = self.get_connection()
        if not conn:
            return None
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT pc_name, ip, online, os_version, last_seen "
                    "FROM fleet_devices WHERE ip = %s LIMIT 1",
                    (ip_address,)
                )
                return cur.fetchone()
        finally:
            conn.close()

    def query_offline_devices(self):
        """Returns all devices currently flagged as OFFLINE."""
        conn = self.get_connection()
        if not conn:
            return []
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT pc_name, ip, os_version, last_seen "
                    "FROM fleet_devices WHERE online = FALSE ORDER BY last_seen ASC LIMIT 20"
                )
                return cur.fetchall()
        finally:
            conn.close()

    # ── Printer Queries ───────────────────────────────────────────────────────

    def query_all_printers(self):
        conn = self.get_connection()
        if not conn:
            return []
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT name, model, ip, status, toner_pct, queue_count, error_msg "
                    "FROM fleet_printers LIMIT 20"
                )
                return cur.fetchall()
        finally:
            conn.close()

    # ── Incident Queries ──────────────────────────────────────────────────────

    def query_active_incidents(self, limit: int = 5):
        conn = self.get_connection()
        if not conn:
            return []
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT incident_id, device_name, flag, evidence, confidence, timestamp, closed_time
                    FROM incidents
                    WHERE closed_time IS NULL
                    ORDER BY timestamp DESC
                    LIMIT %s
                    """,
                    (limit,)
                )
                return cur.fetchall()
        finally:
            conn.close()

    def query_incident_by_id(self, incident_id: int):
        """Fetch a single incident by ID (open or closed)."""
        conn = self.get_connection()
        if not conn:
            return None
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT incident_id, device_name, flag, evidence, confidence, timestamp, closed_time
                    FROM incidents WHERE incident_id = %s
                    """,
                    (incident_id,)
                )
                return cur.fetchone()
        finally:
            conn.close()

    def close_incident(self, incident_id: int) -> bool:
        """Mark an incident as closed by setting closed_time = NOW()."""
        conn = self.get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE incidents SET closed_time = NOW() WHERE incident_id = %s AND closed_time IS NULL",
                    (incident_id,)
                )
                affected = cur.rowcount
                conn.commit()
                if affected > 0:
                    logger.info(f"[DB] Incident {incident_id} closed successfully.")
                    return True
                logger.warning(f"[DB] Incident {incident_id} not found or already closed.")
                return False
        except Exception as e:
            logger.error(f"[DB] Failed to close incident {incident_id}: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def query_recent_alarms(self, limit: int = 10, severity_min: int = 0):
        """
        Fetch recent alarms from ai_approval_logs or incidents flagged as alarms.
        Falls back to recent incidents if alarm table doesn't exist.
        """
        conn = self.get_connection()
        if not conn:
            return []
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Try dedicated alarm table first
                try:
                    cur.execute(
                        """
                        SELECT id, incident_id, risk_level, action_name, approval_status, approval_expiry
                        FROM ai_approval_logs
                        ORDER BY id DESC
                        LIMIT %s
                        """,
                        (limit,)
                    )
                    return cur.fetchall()
                except Exception:
                    # Fallback: use recent incidents as alarms
                    cur.execute(
                        """
                        SELECT incident_id, device_name, flag AS alarm_type, confidence, timestamp
                        FROM incidents
                        ORDER BY timestamp DESC
                        LIMIT %s
                        """,
                        (limit,)
                    )
                    return cur.fetchall()
        finally:
            conn.close()

    def query_network_health_summary(self) -> dict:
        """
        Returns aggregated network health summary:
        total devices, online count, offline count, open incidents.
        """
        conn = self.get_connection()
        if not conn:
            return {"total": 0, "online": 0, "offline": 0, "open_incidents": 0}
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT COUNT(*) AS total, SUM(CASE WHEN online THEN 1 ELSE 0 END) AS online_count FROM fleet_devices")
                row = cur.fetchone()
                total = int(row["total"] or 0)
                online = int(row["online_count"] or 0)

                cur.execute("SELECT COUNT(*) AS cnt FROM incidents WHERE closed_time IS NULL")
                inc_row = cur.fetchone()
                open_inc = int(inc_row["cnt"] or 0)

                return {
                    "total": total,
                    "online": online,
                    "offline": total - online,
                    "open_incidents": open_inc,
                    "health_pct": round((online / total * 100) if total > 0 else 100.0, 1)
                }
        except Exception as e:
            logger.error(f"[DB] query_network_health_summary failed: {e}")
            return {"total": 0, "online": 0, "offline": 0, "open_incidents": 0, "health_pct": 100.0}
        finally:
            conn.close()

    # ── Generic Raw Query ─────────────────────────────────────────────────────

    def raw_query(self, sql: str, params=None) -> list:
        """
        Execute a read-only SQL query and return list of RealDictRow dicts.
        Used by: _workflow_audit_log_query, SLA compliance, and future analytics.
        """
        conn = self.get_connection()
        if not conn:
            return []
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params or [])
                rows = cur.fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[DB] raw_query failed: {e} | SQL: {sql[:80]}")
            return []
        finally:
            conn.close()

