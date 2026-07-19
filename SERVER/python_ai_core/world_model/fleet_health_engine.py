import logging
from datetime import datetime

logger = logging.getLogger("FLEET_HEALTH_ENGINE")

class FleetHealthEngine:
    def __init__(self, db_conn):
        self.db = db_conn

    def update_health_scores(self):
        """Calculates Fleet Health Score (0-100) per asset based on telemetry, historical incidents, and trust."""
        if not self.db:
            return
        
        try:
            with self.db.cursor() as cur:
                cur.execute("SELECT asset_id, hostname, last_telemetry, trust_score FROM assets")
                assets = cur.fetchall()
                
                for asset in assets:
                    asset_id, hostname, telemetry, trust = asset
                    score = 100.0
                    
                    # 1. Trust impact
                    if trust is not None:
                        # Trust defaults to 100, impacts health if it drops
                        trust_impact = (100.0 - float(trust)) * 0.5
                        score -= trust_impact
                        
                    # 2. Historical Incident Impact
                    cur.execute("SELECT COUNT(*), SUM(mttr_seconds) FROM incident_post_mortems WHERE device_name = %s", (hostname,))
                    inc_row = cur.fetchone()
                    if inc_row and inc_row[0] > 0:
                        inc_count = inc_row[0]
                        # Minus 2 points per incident
                        score -= (inc_count * 2)
                        
                    # 3. Telemetry Impact
                    if telemetry and isinstance(telemetry, dict):
                        # Assuming telemetry contains CPU, RAM, Disk
                        cpu = float(telemetry.get('cpu_usage', 0))
                        ram = float(telemetry.get('ram_usage', 0))
                        if cpu > 90:
                            score -= 10
                        elif cpu > 80:
                            score -= 5
                        if ram > 90:
                            score -= 10
                            
                        # If application errors or watchdog alerts present
                        if telemetry.get('application_crashes') or telemetry.get('web_errors'):
                            score -= 15
                            
                        # Restart counts
                        restart_count = int(telemetry.get('restart_count', 0))
                        if restart_count > 0:
                            score -= (restart_count * 5)
                            
                    # Floor score at 0
                    score = max(0.0, min(100.0, score))
                    
                    cur.execute("UPDATE assets SET health_score = %s, updated_at = NOW() WHERE asset_id = %s", (score, asset_id))
                    
            self.db.commit()
            logger.info("[FLEET HEALTH] Health Score calculation complete.")
        except Exception as e:
            logger.error(f"[FLEET HEALTH] Failed to update health scores: {e}")
            self.db.rollback()
