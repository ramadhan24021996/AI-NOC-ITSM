import os
import json
import psycopg2
from typing import Dict, Any

class LessonEngine:
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

    def self_evaluate(self, incident_id: str, outcome_data: Dict[str, Any]) -> Dict[str, Any]:
        return {"incident_id": incident_id, "evaluated_outcome": outcome_data.get("status", "unknown")}

    def generate_lesson_learned(self, incident_id: str) -> Dict[str, Any]:
        lesson = {"incident_id": incident_id, "lesson": "No lesson found"}
        conn = self._get_conn()
        if not conn: return lesson
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT title, root_cause, resolution FROM incidents WHERE id = %s", (incident_id,))
                row = cur.fetchone()
                if row:
                    lesson = {
                        "incident_id": incident_id,
                        "title": row[0],
                        "root_cause": row[1],
                        "resolution": row[2]
                    }
        except Exception:
            import logging; logging.getLogger(__name__).debug('_ = None suppressed')
        finally:
            conn.close()
        return lesson
        
    def generate_automatic_documentation(self, incident_id: str, format: str = "json") -> str:
        lesson = self.generate_lesson_learned(incident_id)
        if format == "json":
            return json.dumps(lesson)
        return f"Incident {incident_id}: {lesson.get('title', '')} - {lesson.get('root_cause', '')}"