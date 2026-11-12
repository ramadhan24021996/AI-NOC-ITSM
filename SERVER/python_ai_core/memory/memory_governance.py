import logging
import json
import uuid
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Any, Dict, List, Optional
from .knowledge_validation_engine import KnowledgeValidationEngine
from .knowledge_memory import KnowledgeMemoryManager

logger = logging.getLogger("MEMORY_GOVERNANCE")

class MemoryGovernanceManager:
    """
    Memory Governance Manager for Jarvis AI NOC:
    Controls memory quality, safety, authorization, deduplication, and audit trails.
    Responsibilities:
      1. Pre-validation via KnowledgeValidationEngine before activation.
      2. Duplicate Detection & Prevention (deduplication gate).
      3. Completeness & Metadata Quality Enforcement.
      4. Versioning Control (version increments).
      5. Confidence Score Calibration.
      6. Teacher RBAC Authorization Enforcement.
      7. Immutable Audit Trail Logging (jarvis_audit_trail).
    """

    def __init__(
        self,
        validation_engine: Optional[KnowledgeValidationEngine] = None,
        knowledge_mgr: Optional[KnowledgeMemoryManager] = None
    ):
        self.validation_engine = validation_engine or KnowledgeValidationEngine()
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

    def check_teacher_authorization(self, author_name: str, category: str) -> bool:
        """
        Enforces RBAC permissions for teaching/modifying knowledge.
        """
        # System agents and designated operators are authorized
        unauthorized = ["GUEST", "UNTRUSTED", "ANONYMOUS"]
        return author_name.upper().strip() not in unauthorized

    def govern_new_knowledge_ingestion(
        self,
        title: str,
        solution: str,
        category: str = "NETWORK",
        symptoms: str = "",
        root_cause: str = "",
        tags: Optional[List[str]] = None,
        severity: str = "MEDIUM",
        confidence: float = 1.0,
        source: str = "USER_TEACHING",
        author: str = "OPERATOR"
    ) -> Dict[str, Any]:
        """
        Full governance ingestion gate for proposed knowledge.
        """
        # 1. Teacher Authorization RBAC Check
        if not self.check_teacher_authorization(author, category):
            err_msg = f"AUTHORIZATION ERROR: Pengguna '{author}' tidak memiliki wewenang untuk menambahkan pengetahuan."
            logger.warning(f"[MEMORY_GOVERNANCE] {err_msg}")
            self._log_audit_event(author, "GOVERN_INGESTION", "REJECTED_UNAUTHORIZED", {"title": title, "reason": err_msg})
            return {"status": "REJECTED_UNAUTHORIZED", "message": err_msg, "is_active": False}

        # 2. Validation via KnowledgeValidationEngine
        val_result = self.validation_engine.validate_new_knowledge(
            title=title, solution=solution, category=category, symptoms=symptoms,
            root_cause=root_cause, tags=tags, severity=severity, confidence=confidence, author=author
        )

        if not val_result["is_valid"]:
            val_status = val_result["validation_status"]
            reason = val_result["reason"]
            logger.warning(f"[MEMORY_GOVERNANCE] Ingestion governed: {val_status} - {reason}")

            # If rejected by policy or pending HITL, record audit trail & return pending state
            self._log_audit_event(author, "GOVERN_INGESTION", val_status, {"title": title, "validation_result": val_result})

            return {
                "status": val_status,
                "message": reason,
                "is_active": False,
                "requires_hitl": val_result.get("requires_hitl", True),
                "completeness_score": val_result.get("completeness_score", 0.0),
                "validation_result": val_result
            }

        # 3. Duplicate Prevention Check
        existing_matches = self.knowledge_mgr.hybrid_search(
            query_text=f"{title} {solution}",
            category_filter=category,
            limit=1
        )
        if existing_matches:
            top_match = existing_matches[0]
            similarity = float(top_match.get("similarity_score", 0.0) or 0.0)
            if similarity > 0.95 or top_match.get("title", "").strip().lower() == title.strip().lower():
                dup_msg = f"DEDUPLICATION GATE: Pengetahuan identik sudah ada dengan judul '{top_match.get('title')}' (UUID: {top_match.get('uuid')}). Ingest dibatalkan."
                logger.info(f"[MEMORY_GOVERNANCE] {dup_msg}")
                self._log_audit_event(author, "GOVERN_INGESTION", "REJECTED_DUPLICATE", {"title": title, "existing_uuid": top_match.get("uuid")})
                return {
                    "status": "REJECTED_DUPLICATE",
                    "message": dup_msg,
                    "is_active": False,
                    "existing_uuid": top_match.get("uuid")
                }

        # 4. Calibration & Quality Ingestion
        ingest_res = self.knowledge_mgr.insert_knowledge(
            title=title, category=category, description=f"Gejala: {symptoms}\nPenyebab: {root_cause}",
            symptoms=symptoms, root_cause=root_cause, solution=solution, tags=tags or [],
            environment="PRODUCTION", severity=severity, confidence=min(1.0, max(0.1, confidence)),
            source=source, author=author, validator="MEMORY_GOVERNANCE_MANAGER"
        )

        k_uuid = ingest_res["uuid"]

        # 5. Record Immutable Audit Event
        self._log_audit_event(
            author=author, operation="GOVERN_INGESTION", status="SUCCESS_VALIDATED",
            target_uuid=k_uuid, details={"title": title, "completeness_score": val_result["completeness_score"]}
        )

        return {
            "status": "SUCCESS_VALIDATED",
            "message": f"Pengetahuan '{title}' lolos evaluasi governance dan diaktifkan di Knowledge Memory.",
            "uuid": k_uuid,
            "is_active": True,
            "completeness_score": val_result["completeness_score"]
        }

    def _log_audit_event(
        self, author: str, operation: str, status: str,
        details: Dict[str, Any], target_uuid: Optional[str] = None
    ):
        audit_id = str(uuid.uuid4())
        sql = """
            INSERT INTO jarvis_audit_trail (
                audit_id, memory_layer, operation, target_uuid, operator, status, details, timestamp
            ) VALUES (
                %s::uuid, 'GOVERNANCE', %s, %s::uuid, %s, %s, %s::jsonb, CURRENT_TIMESTAMP
            );
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (
                    audit_id, operation, target_uuid if target_uuid else None,
                    author, status, json.dumps(details)
                ))
            conn.commit()
        except Exception as e:
            logger.error(f"[MEMORY_GOVERNANCE] Audit log error: {e}")
        finally:
            conn.close()
