import asyncio
import logging
import json
import psycopg2
import os
from datetime import datetime, timezone

logger = logging.getLogger("TIMELINE_KPI")

class TimelineKPIEngine:
    def __init__(self):
        self.db_params = {
            "host": os.getenv("DB_HOST", "postgres"),
            "port": os.getenv("DB_PORT", "5432"),
            "database": os.getenv("DB_NAME", "osi_system"),
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", "postgres")
        }

    def _get_db(self):
        return psycopg2.connect(**self.db_params)

    def calculate_incident_timelines(self):
        try:
            conn = self._get_db()
            cursor = conn.cursor()
            
            # Fetch active or recently closed incidents
            cursor.execute("SELECT incident_id, timestamp, raw_data FROM incidents WHERE raw_data->>'closed_time' IS NULL")
            incidents = cursor.fetchall()
            
            for incident_id, start_time, raw_data in incidents:
                if not isinstance(raw_data, dict):
                    if isinstance(raw_data, str):
                        try:
                            raw_data = json.loads(raw_data)
                        except:
                            raw_data = {}
                    else:
                        raw_data = {}
                
                def get_first(q, p):
                    cursor.execute(q, p)
                    row = cursor.fetchone()
                    return row[0] if row else None

                # 1. First Evidence Time
                first_ev = get_first("SELECT MIN(timestamp) FROM fleet_evidence WHERE incident_id = %s", (incident_id,))
                if first_ev: raw_data['first_evidence_time'] = first_ev.isoformat()
                
                # 2. Issue Started Time
                raw_data['issue_started_time'] = start_time.isoformat()
                
                # 3. AI Detection Time
                ai_det = get_first("SELECT MIN(timestamp) FROM ai_reflection_logs WHERE incident_id = %s", (incident_id,))
                if ai_det: raw_data['ai_detection_time'] = ai_det.isoformat()
                
                # 4. Correlation Completed Time
                corr_comp = get_first("SELECT MIN(timestamp) FROM ai_reflection_logs WHERE incident_id = %s AND final_decision IS NOT NULL", (incident_id,))
                if corr_comp: raw_data['correlation_completed_time'] = corr_comp.isoformat()
                
                # 5. Root Cause Completed Time
                rca_comp = get_first("SELECT MIN(created_at) FROM decision_graphs WHERE incident_id = %s", (incident_id,))
                if rca_comp: raw_data['root_cause_completed_time'] = rca_comp.isoformat()
                
                # 6. Recommendation Generated Time
                rec_gen = get_first("SELECT MIN(created_at) FROM decision_graphs WHERE incident_id = %s AND consensus_output IS NOT NULL", (incident_id,))
                if rec_gen: raw_data['recommendation_generated_time'] = rec_gen.isoformat()
                
                # 7. Human Approval Time
                hum_appr = get_first("SELECT MIN(approved_at) FROM ai_approval_logs WHERE incident_id = %s AND approval_status = 'APPROVED'", (incident_id,))
                if hum_appr: raw_data['human_approval_time'] = hum_appr.isoformat()
                
                # 8. Execution Time
                exec_time = get_first("SELECT MIN(created_at) FROM incident_events WHERE incident_id = %s::text AND event_type = 'COMMAND_EXECUTION'", (incident_id,))
                if exec_time: raw_data['execution_time'] = exec_time.isoformat()
                
                # 9. Verification Time
                verif_time = get_first("SELECT MIN(created_at) FROM verification_logs WHERE incident_id = %s", (incident_id,))
                if verif_time: raw_data['verification_time'] = verif_time.isoformat()
                
                # 10. Solved Time
                solved_time = get_first("SELECT MIN(resolved_at) FROM incident_states WHERE incident_id = %s AND status IN ('RESOLVED', 'SOLVED VERIFIED')", (incident_id,))
                if solved_time: raw_data['solved_time'] = solved_time.isoformat()
                
                # 11. Closed Time
                closed_time = get_first("SELECT MIN(resolved_at) FROM incident_states WHERE incident_id = %s AND status = 'CLOSED'", (incident_id,))
                if closed_time: raw_data['closed_time'] = closed_time.isoformat()

                
                # Calculate Durations
                def time_diff(t1_iso, t2_iso):
                    if not t1_iso or not t2_iso: return 0
                    
                    # Convert to datetime objects if they are strings
                    if isinstance(t1_iso, str):
                        t1 = datetime.fromisoformat(t1_iso.replace('Z', '+00:00'))
                    else:
                        t1 = t1_iso
                    if isinstance(t2_iso, str):
                        t2 = datetime.fromisoformat(t2_iso.replace('Z', '+00:00'))
                    else:
                        t2 = t2_iso
                    
                    # Convert both to naive UTC datetimes by removing tzinfo or replacing it
                    if t1.tzinfo is not None:
                        t1 = t1.astimezone(timezone.utc).replace(tzinfo=None)
                    if t2.tzinfo is not None:
                        t2 = t2.astimezone(timezone.utc).replace(tzinfo=None)
                        
                    return max(0, int((t2 - t1).total_seconds()))

                # Detection Duration (Issue Started -> AI Detection)
                if raw_data.get('ai_detection_time'):
                    raw_data['detection_duration_sec'] = time_diff(raw_data.get('issue_started_time'), raw_data.get('ai_detection_time'))
                
                # Analysis Duration (AI Detection -> Recommendation Generated)
                if raw_data.get('ai_detection_time') and raw_data.get('recommendation_generated_time'):
                    raw_data['analysis_duration_sec'] = time_diff(raw_data.get('ai_detection_time'), raw_data.get('recommendation_generated_time'))
                
                # Approval Duration (Recommendation Generated -> Human Approval)
                if raw_data.get('recommendation_generated_time') and raw_data.get('human_approval_time'):
                    raw_data['approval_duration_sec'] = time_diff(raw_data.get('recommendation_generated_time'), raw_data.get('human_approval_time'))
                
                # Resolution Duration (Human Approval -> Solved Time)
                if raw_data.get('human_approval_time') and raw_data.get('solved_time'):
                    raw_data['resolution_duration_sec'] = time_diff(raw_data.get('human_approval_time'), raw_data.get('solved_time'))
                
                # Total Incident Duration (Issue Started -> Solved Time)
                if raw_data.get('issue_started_time') and raw_data.get('solved_time'):
                    raw_data['total_incident_duration_sec'] = time_diff(raw_data.get('issue_started_time'), raw_data.get('solved_time'))

                # Sprint L+ Extensions: Multi-dimensional Timelines
                
                # A. Evidence Timeline
                cursor.execute("SELECT timestamp, evidence_type FROM fleet_evidence WHERE incident_id = %s ORDER BY timestamp ASC LIMIT 20", (incident_id,))
                evidence_rows = cursor.fetchall()
                if evidence_rows:
                    raw_data['evidence_timeline'] = [{"time": r[0].isoformat() if r[0] else None, "desc": r[1]} for r in evidence_rows]
                
                # B. Confidence Timeline
                cursor.execute("SELECT timestamp, confidence_score FROM ai_reflection_logs WHERE incident_id = %s ORDER BY timestamp ASC LIMIT 20", (incident_id,))
                conf_rows = cursor.fetchall()
                if conf_rows:
                    raw_data['confidence_timeline'] = [{"time": r[0].isoformat() if r[0] else None, "val": r[1]} for r in conf_rows]
                
                # C. AI Thinking Steps
                thinking_steps = []
                if raw_data.get('ai_detection_time'):
                    thinking_steps.append({"step": "Observation", "time": raw_data['ai_detection_time']})
                if raw_data.get('correlation_completed_time'):
                    thinking_steps.append({"step": "Correlation", "time": raw_data['correlation_completed_time']})
                if raw_data.get('root_cause_completed_time'):
                    thinking_steps.append({"step": "Root Cause", "time": raw_data['root_cause_completed_time']})
                if raw_data.get('recommendation_generated_time'):
                    thinking_steps.append({"step": "Recommendation", "time": raw_data['recommendation_generated_time']})
                if thinking_steps:
                    raw_data['ai_thinking_steps'] = thinking_steps

                # D. Micro-KPIs (Sprint L+)
                if raw_data.get('correlation_completed_time') and raw_data.get('root_cause_completed_time'):
                    raw_data['rca_duration_sec'] = time_diff(raw_data.get('correlation_completed_time'), raw_data.get('root_cause_completed_time'))
                
                if raw_data.get('execution_time') and raw_data.get('verification_time'):
                    raw_data['execution_duration_sec'] = time_diff(raw_data.get('execution_time'), raw_data.get('verification_time'))

                # Update Postgres
                cursor.execute("UPDATE incidents SET raw_data = %s WHERE incident_id = %s", (json.dumps(raw_data), incident_id))
            
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error calculating timelines: {e}")

async def daemon(interval_seconds: int = 5):
    logger.info("Sprint L: Starting Timeline KPI Engine...")
    engine = TimelineKPIEngine()
    while True:
        engine.calculate_incident_timelines()
        await asyncio.sleep(interval_seconds)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(daemon())
