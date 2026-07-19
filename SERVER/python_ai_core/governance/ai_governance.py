import logging
import psycopg2
from typing import Dict, Any, List
import json
import os
import uuid

logger = logging.getLogger("AIGovernanceEngine")

class AIGovernanceEngine:
    def __init__(self, db_conn=None):
        self.conn = db_conn
        if not self.conn:
            self.db_host = os.getenv("DB_HOST", "127.0.0.1")
            self.db_port = os.getenv("DB_PORT", "5432")
            self.db_name = os.getenv("DB_NAME", "osi_system")
            self.user = os.getenv("DB_USER", "postgres")
            self.password = os.getenv("DB_PASSWORD", "postgres")
            self.conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.user,
                password=self.password
            )

    def propose_change(self, asset_type: str, asset_name: str, author: str, change_payload: Dict[str, Any], rollback_payload: Dict[str, Any]) -> str:
        """
        Mendaftarkan perubahan (Prompt, Rule, Bayesian) untuk diaudit dan menunggu approval.
        """
        if not self.conn: return ""
        try:
            version_tag = f"v-{str(uuid.uuid4())[:8]}"
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO ai_governance_audit (
                        asset_type, asset_name, version_tag, author, approval_status, change_payload, rollback_payload
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    asset_type, asset_name, version_tag, author, "PENDING", 
                    json.dumps(change_payload), json.dumps(rollback_payload)
                ))
            self.conn.commit()
            logger.info(f"Proposed change for {asset_name} by {author} (Version: {version_tag})")
            return version_tag
        except Exception as e:
            logger.error(f"Failed to propose change: {e}")
            self.conn.rollback()
            return ""

    def approve_change(self, version_tag: str, approver: str):
        """
        Menyetujui perubahan. Dalam produksi, ini juga akan mentrigger implementasi perubahan
        secara live ke memori atau Redis.
        """
        if not self.conn: return False
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    UPDATE ai_governance_audit 
                    SET approval_status = 'APPROVED' 
                    WHERE version_tag = %s
                """, (version_tag,))
            self.conn.commit()
            logger.info(f"Version {version_tag} APPROVED by {approver}.")
            return True
        except Exception as e:
            logger.error(f"Failed to approve change: {e}")
            self.conn.rollback()
            return False

    def rollback_change(self, version_tag: str):
        """
        Memutar kembali perubahan AI ke rollback_payload.
        """
        if not self.conn: return False
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT rollback_payload FROM ai_governance_audit WHERE version_tag = %s", (version_tag,))
                row = cur.fetchone()
                if row:
                    rb_payload = row[0]
                    # Logic to physically revert the asset (e.g., redis.set, db update)
                    # ...
                    
                    cur.execute("UPDATE ai_governance_audit SET approval_status = 'ROLLED_BACK' WHERE version_tag = %s", (version_tag,))
                    self.conn.commit()
                    logger.warning(f"Version {version_tag} ROLLED BACK.")
                    return True
        except Exception as e:
            logger.error(f"Failed to rollback change: {e}")
            self.conn.rollback()
        return False
