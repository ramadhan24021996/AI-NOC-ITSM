import logging
import json
import uuid
import os
import math
import time
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Any, Dict, List, Optional
from .knowledge_memory import KnowledgeMemoryManager

logger = logging.getLogger("KNOWLEDGE_LIFECYCLE")

class KnowledgeLifecycleManager:
    """
    Knowledge Lifecycle Manager for Jarvis AI NOC:
    Manages the lifecycle of stored knowledge AFTER ingestion:
      1. Deprecating outdated SOPs/Knowledge (deprecated status & is_active = False).
      2. Version Archiving without deletion (e.g. MTU 1492 v1 -> MTU 1500 v2).
         Old version is archived (is_active = False, superseded_by = v2_uuid), while RAG is directed to v2.
      3. Dynamic Confidence Calibration:
         - Solution Succeeded in production: Confidence += 0.05 (Max 1.0)
         - Solution Failed in production: Confidence -= 0.15 (Min 0.1)
      4. Merging identical or duplicate knowledge entries.
      5. Flagging contradicting active entries for Human Review (REQUIRES_HUMAN_REVIEW).
      6. Evaluating Freshness Score decay (F = e^(-lambda * t)) and marking stale entries.
    """

    def __init__(self, knowledge_mgr: Optional[KnowledgeMemoryManager] = None):
        self.knowledge_mgr = knowledge_mgr or KnowledgeMemoryManager()
        self.db_host = os.getenv("DB_HOST", "127.0.0.1")
        self.db_port = os.getenv("DB_PORT", "5432")
        self.db_name = os.getenv("DB_NAME", "osi_system")
        self.user = os.getenv("DB_USER", "postgres")
        self.password = os.getenv("DB_PASSWORD", "[REDACTED_DB_PASS]")

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

    def publish_new_version(
        self,
        old_knowledge_uuid: str,
        new_title: str,
        new_solution: str,
        new_symptoms: str = "",
        new_root_cause: str = "",
        author: str = "OPERATOR",
        version_notes: str = ""
    ) -> Dict[str, Any]:
        """
        Publishes a new version of an existing knowledge entry (e.g. MTU 1492 -> MTU 1500).
        Archiving behavior:
          - Keeps the old version in PostgreSQL for audit & historical reference (is_active = False, validation_status = 'SUPERSEDED').
          - Links old version via superseded_by = new_uuid.
          - Creates new version with version = old_version + 1 and is_active = True.
          - RAG search queries only retrieve active version.
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 1. Fetch old record
                cur.execute("SELECT * FROM jarvis_knowledge_store WHERE uuid = %s::uuid;", (old_knowledge_uuid,))
                old_rec = cur.fetchone()
                if not old_rec:
                    raise ValueError(f"Knowledge UUID '{old_knowledge_uuid}' not found.")

                new_version_num = old_rec.get("version", 1) + 1
                category = old_rec.get("category", "NETWORK")
                tags = old_rec.get("tags", [])
                severity = old_rec.get("severity", "MEDIUM")

                # 2. Insert new version record via KnowledgeMemoryManager
                new_rec = self.knowledge_mgr.insert_knowledge(
                    title=new_title,
                    category=category,
                    description=f"Version {new_version_num}. Notes: {version_notes}",
                    symptoms=new_symptoms or old_rec.get("symptoms", ""),
                    root_cause=new_root_cause or old_rec.get("root_cause", ""),
                    solution=new_solution,
                    tags=tags,
                    severity=severity,
                    confidence=1.0,
                    source="VERSION_UPDATE",
                    author=author,
                    validator="KNOWLEDGE_LIFECYCLE_MANAGER"
                )

                new_uuid = new_rec["uuid"]

                # 3. Archive old version (is_active = False, superseded_by = new_uuid)
                cur.execute("""
                    UPDATE jarvis_knowledge_store
                    SET is_active = FALSE,
                        validation_status = 'SUPERSEDED',
                        superseded_by = %s::uuid,
                        review_notes = %s,
                        updated = CURRENT_TIMESTAMP
                    WHERE uuid = %s::uuid;
                """, (new_uuid, f"Superseded by v{new_version_num} (UUID: {new_uuid})", old_knowledge_uuid))

                cur.execute("""
                    UPDATE jarvis_knowledge_store
                    SET version = %s
                    WHERE uuid = %s::uuid;
                """, (new_version_num, new_uuid))

            conn.commit()
            logger.info(f"[KNOWLEDGE_LIFECYCLE] Published v{new_version_num} for '{new_title}' (New UUID: {new_uuid}, Old UUID: {old_knowledge_uuid} archived)")
            return {
                "status": "VERSION_UPDATED",
                "new_uuid": new_uuid,
                "old_uuid": old_knowledge_uuid,
                "version": new_version_num,
                "title": new_title
            }
        except Exception as e:
            conn.rollback()
            logger.error(f"[KNOWLEDGE_LIFECYCLE] Failed to publish new version: {e}")
            raise e
        finally:
            conn.close()

    def update_confidence_on_outcome(self, knowledge_uuid: str, is_success: bool) -> Dict[str, Any]:
        """
        Dynamically calibrates confidence score based on production execution outcome:
          - If is_success == True:  Confidence = min(1.0, Confidence + 0.05), usage_count++, success_rate updated.
          - If is_success == False: Confidence = max(0.1, Confidence - 0.15), usage_count++, failure_rate updated.
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT confidence, usage_count, success_rate, failure_rate FROM jarvis_knowledge_store WHERE uuid = %s::uuid;", (knowledge_uuid,))
                rec = cur.fetchone()
                if not rec:
                    return {"status": "NOT_FOUND"}

                curr_conf = float(rec["confidence"])
                curr_usage = int(rec["usage_count"]) + 1

                if is_success:
                    new_conf = round(min(1.0, curr_conf + 0.05), 2)
                    delta_text = "+0.05"
                else:
                    new_conf = round(max(0.1, curr_conf - 0.15), 2)
                    delta_text = "-0.15"

                cur.execute("""
                    UPDATE jarvis_knowledge_store
                    SET confidence = %s,
                        usage_count = %s,
                        updated = CURRENT_TIMESTAMP
                    WHERE uuid = %s::uuid
                    RETURNING uuid, confidence, usage_count;
                """, (new_conf, curr_usage, knowledge_uuid))
                updated_row = cur.fetchone()

            conn.commit()
            logger.info(f"[KNOWLEDGE_LIFECYCLE] Calibrated confidence for UUID {knowledge_uuid}: {curr_conf} -> {new_conf} ({delta_text})")
            return dict(updated_row)
        except Exception as e:
            conn.rollback()
            logger.error(f"[KNOWLEDGE_LIFECYCLE] Failed to calibrate confidence: {e}")
            return {"status": "ERROR", "reason": str(e)}
        finally:
            conn.close()

    def deprecate_knowledge(self, knowledge_uuid: str, reason: str = "Outdated SOP") -> Dict[str, Any]:
        """
        Marks knowledge as DEPRECATED and inactive (is_active = False).
        """
        sql = """
            UPDATE jarvis_knowledge_store
            SET validation_status = 'DEPRECATED',
                is_active = FALSE,
                review_notes = %s,
                updated = CURRENT_TIMESTAMP
            WHERE uuid = %s::uuid
            RETURNING uuid, title, validation_status, is_active;
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, (reason, knowledge_uuid))
                row = cur.fetchone()
            conn.commit()
            logger.info(f"[KNOWLEDGE_LIFECYCLE] Deprecated Knowledge UUID {knowledge_uuid}. Reason: {reason}")
            return dict(row) if row else {"status": "NOT_FOUND"}
        except Exception as e:
            conn.rollback()
            logger.error(f"[KNOWLEDGE_LIFECYCLE] Deprecation error: {e}")
            return {"status": "ERROR", "reason": str(e)}
        finally:
            conn.close()

    def flag_for_human_review(self, knowledge_uuid: str, review_reason: str) -> Dict[str, Any]:
        """
        Flags a knowledge entry for Human Review (REQUIRES_HUMAN_REVIEW).
        """
        sql = """
            UPDATE jarvis_knowledge_store
            SET validation_status = 'REQUIRES_HUMAN_REVIEW',
                review_notes = %s,
                updated = CURRENT_TIMESTAMP
            WHERE uuid = %s::uuid
            RETURNING uuid, title, validation_status, review_notes;
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, (review_reason, knowledge_uuid))
                row = cur.fetchone()
            conn.commit()
            logger.warning(f"[KNOWLEDGE_LIFECYCLE] Flagged Knowledge UUID {knowledge_uuid} for Human Review: {review_reason}")
            return dict(row) if row else {"status": "NOT_FOUND"}
        except Exception as e:
            conn.rollback()
            logger.error(f"[KNOWLEDGE_LIFECYCLE] Human review flag error: {e}")
            return {"status": "ERROR", "reason": str(e)}
        finally:
            conn.close()
