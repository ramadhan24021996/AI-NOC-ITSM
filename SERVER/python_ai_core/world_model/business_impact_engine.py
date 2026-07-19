import psycopg2
import logging
from datetime import datetime

logger = logging.getLogger("BUSINESS_IMPACT_ENGINE")

class BusinessImpactEngine:
    def __init__(self, db_conn):
        self.db = db_conn

    def calculate_criticality(self):
        """Calculates Asset Criticality (LOW, MEDIUM, HIGH, CRITICAL, BUSINESS CRITICAL)"""
        if not self.db:
            return
        
        try:
            with self.db.cursor() as cur:
                # Get all assets and their impacts
                cur.execute("""
                    SELECT a.asset_id, a.device_type, b.mission_critical, b.revenue_impact_per_hour, 
                           b.affected_users, b.compliance_requirement
                    FROM assets a
                    LEFT JOIN asset_business_impacts b ON a.asset_id = b.asset_id
                """)
                assets = cur.fetchall()
                
                for asset in assets:
                    asset_id, device_type, mission_critical, revenue, users, compliance = asset
                    
                    score = 0
                    if mission_critical:
                        score += 50
                    if revenue and revenue > 1000:
                        score += 30
                    elif revenue and revenue > 0:
                        score += 10
                    if users and users > 100:
                        score += 20
                    elif users and users > 10:
                        score += 5
                    if compliance:
                        score += 10
                        
                    # Base type modifiers
                    if device_type in ['Server', 'Router', 'Switch', 'Firewall', 'Database']:
                        score += 30
                    
                    if score >= 80:
                        criticality = 'BUSINESS CRITICAL'
                    elif score >= 60:
                        criticality = 'CRITICAL'
                    elif score >= 40:
                        criticality = 'HIGH'
                    elif score >= 20:
                        criticality = 'MEDIUM'
                    else:
                        criticality = 'LOW'
                        
                    cur.execute("UPDATE assets SET criticality = %s, updated_at = NOW() WHERE asset_id = %s", (criticality, asset_id))
            self.db.commit()
            logger.info("[BUSINESS IMPACT] Criticality Engine calculation complete.")
        except Exception as e:
            logger.error(f"[BUSINESS IMPACT] Failed to calculate criticality: {e}")
            self.db.rollback()
