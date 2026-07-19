import json
import logging
from datetime import datetime

logger = logging.getLogger("TIMELINE_BUILDER")

class TimelineBuilder:
    def __init__(self, db_conn=None):
        self.db_conn = db_conn

    def build_timeline(self, pc_name: str, duration_minutes: int = 15) -> list:
        timeline = []
        if not self.db_conn:
            timeline.append({
                "timestamp": datetime.utcnow().isoformat(),
                "event": "Telemetry stream initialized",
                "source": "AGENT"
            })
            return timeline

        try:
            with self.db_conn.cursor() as cur:
                # Query recent incidents
                cur.execute("""
                    SELECT created_at, description, severity 
                    FROM fleet_incidents 
                    WHERE pc_name = %s AND created_at >= NOW() - INTERVAL '%s minutes'
                    ORDER BY created_at ASC
                """, (pc_name, duration_minutes))
                for row in cur.fetchall():
                    timeline.append({
                        "timestamp": row[0].isoformat(),
                        "event": f"Incident Alert: {row[1]}",
                        "source": f"INGESTOR ({row[2]})"
                    })
                
                # Query recent audit log actions
                cur.execute("""
                    SELECT created_at, action_executed, confidence_score 
                    FROM ai_audit_trail 
                    WHERE created_at >= NOW() - INTERVAL '%s minutes'
                    ORDER BY created_at ASC
                """, (duration_minutes,))
                for row in cur.fetchall():
                    timeline.append({
                        "timestamp": row[0].isoformat(),
                        "event": f"AI Evaluated Action: {row[1]} (Confidence: {row[2]}%)",
                        "source": "AI_SUPERVISOR"
                    })
        except Exception as e:
            logger.error(f"Error querying timeline data: {e}")
        
        timeline.sort(key=lambda x: x["timestamp"])
        return timeline
