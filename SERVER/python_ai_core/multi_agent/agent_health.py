import os
import psycopg2
from typing import Dict, Any

class AgentHealthMonitor:
    def __init__(self):
        self.db_host = os.environ.get("DB_HOST", "postgres")
        self.db_port = os.environ.get("DB_PORT", "5432")
        self.db_name = os.environ.get("DB_NAME", "osi_system")
        self.db_user = os.environ.get("DB_USER", "postgres")
        self.db_password = os.environ.get("DB_PASSWORD", "postgres")

    def _get_conn(self):
        try:
            return psycopg2.connect(
                host=self.db_host, port=self.db_port, dbname=self.db_name, 
                user=self.db_user, password=self.db_password
            )
        except Exception:
            return None

    def check_health(self, agent_id: str) -> Dict[str, Any]:
        health = {"status": "unhealthy"}
        conn = self._get_conn()
        if not conn: return health
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT EXTRACT(EPOCH FROM (NOW() - last_seen)) 
                    FROM fleet_devices 
                    WHERE device_name = %s
                """, (agent_id,))
                row = cur.fetchone()
                if row and row[0] is not None:
                    if row[0] < 300: # Seen in last 5 minutes
                        health["status"] = "healthy"
                        health["latency"] = row[0]
                    else:
                        health["status"] = "timeout"
        except Exception:
            import logging; logging.getLogger(__name__).debug('_ = None suppressed')
        finally:
            conn.close()
        return health

    def trigger_watchdog(self, agent_id: str):
        # Watchdog logic would send an alert or try to restart agent service remotely
        import logging; logging.getLogger(__name__).debug('_ = None suppressed')
