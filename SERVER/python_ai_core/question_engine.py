import logging
import json
from datetime import datetime

logger = logging.getLogger("QUESTION_ENGINE")

class QuestionEngine:
    def __init__(self, conn=None):
        self.conn = conn

    def evaluate_clarification_needs(self, confidence: float, evidence_completeness: float, incident_similarity: float, hypothesis_conflict: float, incident_details: dict = None) -> dict:
        """
        Determines if mandatory operator clarification is triggered based on safety parameters.
        """
        requires_clarification = False
        triggers = []

        if confidence < 85.0 and evidence_completeness < 70.0:
            requires_clarification = True
            triggers.append(f"Low confidence ({confidence:.1f}) and incomplete evidence ({evidence_completeness:.1f}%)")
        if incident_similarity < 60.0:
            requires_clarification = True
            triggers.append(f"Novel incident with low historical similarity ({incident_similarity:.1f}%)")
        if hypothesis_conflict > 40.0:
            requires_clarification = True
            triggers.append(f"High multi-model hypothesis conflict ({hypothesis_conflict:.1f}%)")

        # Generate structural operational questions
        questions = {
            "operational": [
                "was there recent deployment?",
                "was config changed recently?",
                "was patching performed?",
                "any service restart recently?"
            ],
            "impact": [
                "are users affected?",
                "which services affected?",
                "partial or total outage?"
            ],
            "scope": [
                "single host?",
                "multi-host?",
                "site-wide?"
            ],
            "security": [
                "unusual login activity?",
                "failed auth spikes?",
                "suspicious IPs?"
            ]
        }

        # Dynamic relevance tailoring based on incident_details context
        if incident_details:
            desc = (incident_details.get("description") or incident_details.get("symptoms") or "").lower()
            device = (incident_details.get("device_name") or incident_details.get("device") or "").lower()
            
            # Prioritize or add context-specific questions
            if any(k in desc or k in device for k in ["sec", "auth", "login", "hacked", "perm", "port", "user", "ssh", "fw", "firewall"]):
                questions["security"].insert(0, f"Verify authorization logs for device: {device or 'target device'}")
            
            if any(k in desc or k in device for k in ["disk", "db", "postgres", "sql", "storage", "space", "memory", "cpu"]):
                questions["operational"].insert(0, "Is the service experiencing resource starvation (disk/CPU/RAM)?")
                
            if any(k in desc or k in device for k in ["network", "switch", "route", "ping", "dns", "conn", "http"]):
                questions["scope"].insert(0, "Check if routing table or DNS resolving is impaired downstream.")

        return {
            "requires_clarification": requires_clarification,
            "triggers": triggers,
            "questions": questions
        }

    def log_questions(self, incident_id: int, questions_payload: dict, triggers: list):
        """Persists the generated questions to the question_logs table."""
        if not self.conn:
            return None
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO question_logs (incident_id, questions, triggers, created_at)
                    VALUES (%s, %s, %s, NOW()) RETURNING id
                """, (
                    incident_id,
                    json.dumps(questions_payload),
                    json.dumps(triggers)
                ))
                log_id = cur.fetchone()[0]
                self.conn.commit()
                logger.info(f"Logged generated questions with ID {log_id} for incident {incident_id}")
                return log_id
        except Exception as e:
            logger.error(f"Failed to log questions to DB: {e}")
            self.conn.rollback()
            return None

    def save_operator_answer(self, incident_id: int, question_log_id: int, question: str, answer: str, username: str = "operator"):
        """Saves operator answer as runtime_truth and writes to clarification_memory."""
        if not self.conn:
            return
        try:
            with self.conn.cursor() as cur:
                # Save answer
                cur.execute("""
                    INSERT INTO operator_answers (incident_id, question_log_id, question, answer, answered_by, created_at)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                """, (incident_id, question_log_id, question, answer, username))
                
                # Save to clarification memory for training/RAG feedback loop
                cur.execute("""
                    INSERT INTO clarification_memory (incident_id, runtime_key, runtime_val, created_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (incident_id, runtime_key) DO UPDATE SET runtime_val = EXCLUDED.runtime_val
                """, (incident_id, question, answer))
                
                self.conn.commit()
                logger.info(f"Operator answer for '{question}' registered as runtime_truth.")
        except Exception as e:
            logger.error(f"Failed to save operator answer: {e}")
            self.conn.rollback()
