import logging
import json
import uuid
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Any, Dict, Optional
from .knowledge_memory import KnowledgeMemoryManager

logger = logging.getLogger("EXPERIENCE_MEMORY")

class ExperienceMemoryManager:
    """
    Layer 4: Experience Memory Manager
    - Automates closed-loop experience learning from resolved incidents:
        Incident -> RCA Created -> Recovery Succeeded -> Verification Succeeded
        -> Generate Lesson Learned & Executive Summary -> Generate Embedding
        -> Ingest into Knowledge Memory (Category: LESSON_LEARNED) -> Instantly available for RAG.
    - NEVER fine-tunes LLM weights directly.
    """

    def __init__(self, knowledge_mgr: Optional[KnowledgeMemoryManager] = None):
        self.knowledge_mgr = knowledge_mgr or KnowledgeMemoryManager()
        self.db_host = os.getenv("DB_HOST", "127.0.0.1")
        self.db_port = os.getenv("DB_PORT", "5432")
        self.db_name = os.getenv("DB_NAME", "osi_system")
        self.user = os.getenv("DB_USER", "postgres")
        self.password = os.getenv("DB_PASSWORD", "")

    def _get_connection(self):
        try:
            from shared.db_pool import get_db_connection
            return get_db_connection()
        except Exception:
            return psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.user,
                password=self.password
            )

    def process_incident_learning(
        self,
        incident_id: int,
        device_name: str,
        rca_id: str,
        root_cause: str,
        recovery_action: str,
        verification_status: str = "SUCCESS",
        author: str = "EXPERIENCE_ENGINE"
    ) -> Dict[str, Any]:
        """
        Executes the closed-loop learning pipeline upon successful incident resolution and verification.
        """
        if verification_status.upper() != "SUCCESS":
            logger.warning(f"[EXPERIENCE_MEMORY] Verification status '{verification_status}' is not SUCCESS. Skipping learning ingestion.")
            return {"status": "SKIPPED", "reason": "Verification status not SUCCESS"}

        # 1. Generate Lesson Learned & Executive Summary
        lesson_title = f"Lesson Learned: Insiden #{incident_id} pada {device_name}"
        executive_summary = (
            f"Insiden #{incident_id} pada perangkat {device_name} disebabkan oleh: {root_cause}. "
            f"Tindakan pemulihan yang berhasil dieksekusi: {recovery_action}. Verifikasi akhir: PASS."
        )
        symptoms = f"Anomali telemetri terdeteksi pada node {device_name}"
        solution = f"Eksekusi langkah mitigasi: {recovery_action}. Jalankan verifikasi kesehatan sistem."

        # 2. Ingest into Knowledge Store via KnowledgeMemoryManager (Category: LESSON_LEARNED)
        k_res = self.knowledge_mgr.insert_knowledge(
            title=lesson_title,
            category="LESSON_LEARNED",
            description=executive_summary,
            symptoms=symptoms,
            root_cause=root_cause,
            solution=solution,
            tags=[device_name, "closed_loop", "incident_resolution", "rca_learning"],
            environment="PRODUCTION",
            severity="HIGH",
            confidence=0.98,
            source="CLOSED_LOOP_LEARNING",
            author=author,
            validator="VERIFICATION_ENGINE",
            related_incident=str(incident_id),
            related_rca=rca_id
        )

        k_uuid = k_res.get("uuid")

        # 3. Record in jarvis_experience_lessons table
        exp_uuid = str(uuid.uuid4())
        sql = """
            INSERT INTO jarvis_experience_lessons (
                uuid, incident_id, device_name, rca_id, recovery_action, verification_status,
                lesson_learned, executive_summary, knowledge_uuid, confidence, source, author, timestamp
            ) VALUES (
                %s::uuid, %s, %s, %s, %s, %s,
                %s, %s, %s::uuid, 0.98, 'CLOSED_LOOP_LEARNING', %s, CURRENT_TIMESTAMP
            )
            RETURNING uuid, incident_id, device_name, verification_status, timestamp;
        """

        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, (
                    exp_uuid, incident_id, device_name, rca_id, recovery_action,
                    verification_status, executive_summary, executive_summary, k_uuid, author
                ))
                row = cur.fetchone()
            conn.commit()
            logger.info(f"[EXPERIENCE_MEMORY] Closed-loop learning completed for Incident #{incident_id}. Lesson UUID: {exp_uuid}")
            return {
                "status": "LEARNING_COMPLETED",
                "experience_uuid": exp_uuid,
                "knowledge_uuid": k_uuid,
                "title": lesson_title,
                "summary": executive_summary
            }
        except Exception as e:
            conn.rollback()
            logger.error(f"[EXPERIENCE_MEMORY] Failed to record experience lesson: {e}")
            raise e
        finally:
            conn.close()
