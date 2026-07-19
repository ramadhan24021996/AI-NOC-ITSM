import os
import psycopg2
from typing import Dict, Any, List

class AgentRegistry:
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

    def register_agent(self, agent_id: str, capabilities: List[str], version: str):
        conn = self._get_conn()
        if not conn: return
        try:
            with conn.cursor() as cur:
                # Update fleet_devices or a dedicated agents table
                cur.execute("""
                    INSERT INTO fleet_devices (device_name, device_type, os_version, last_seen)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (device_name) DO UPDATE SET 
                        last_seen = NOW(),
                        os_version = EXCLUDED.os_version
                """, (agent_id, ",".join(capabilities), version))
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            conn.close()

    def discover_service(self, service_type: str) -> str:
        # Find the most recently seen agent with this capability
        conn = self._get_conn()
        if not conn: 
            raise Exception("AgentRegistry Database connection failed")
            
        agent = None
        try:
            with conn.cursor() as cur:
                search = f"%{service_type}%"
                cur.execute("""
                    SELECT device_name FROM fleet_devices 
                    WHERE device_type ILIKE %s 
                      AND last_seen > NOW() - INTERVAL '5 minutes'
                    ORDER BY last_seen DESC LIMIT 1
                """, (search,))
                row = cur.fetchone()
                if row:
                    agent = row[0]
        except Exception as e:
            raise Exception(f"Agent discovery failed: {str(e)}")
        finally:
            conn.close()
            
        if not agent:
            raise Exception(f"No active agent found for service type: {service_type}")
            
        return agent
