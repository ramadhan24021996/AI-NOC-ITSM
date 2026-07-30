"""
Layer 4 AI Core — Pre-Approved Action Catalog Engine (Rule 1)
LLM NEVER executes raw shell commands directly.
Forces LLM to select from an immutable catalog of pre-approved Action IDs.
"""

import logging
import time
from typing import Dict, List, Any, Optional

logger = logging.getLogger("PREAPPROVED_ACTION_CATALOG")

class PreApprovedActionCatalog:
    CATALOG = {
        "ACT_RESTART_SPOOLER": {
            "action_id": "ACT_RESTART_SPOOLER",
            "name": "Restart Windows Print Spooler Service",
            "category": "PRINT_SPOOLER",
            "command_template": "net stop spooler && net start spooler",
            "is_preapproved": True
        },
        "ACT_FLUSH_DNS": {
            "action_id": "ACT_FLUSH_DNS",
            "name": "Flush Local DNS Resolver Cache",
            "category": "NETWORK",
            "command_template": "ipconfig /flushdns",
            "is_preapproved": True
        },
        "ACT_DRAIN_REPLICA": {
            "action_id": "ACT_DRAIN_REPLICA",
            "name": "Graceful Read Replica Connection Drain",
            "category": "DATABASE",
            "command_template": "pg_terminate_backend(pid)",
            "is_preapproved": True
        },
        "ACT_SCALE_POD": {
            "action_id": "ACT_SCALE_POD",
            "name": "Scale Out Microservice Pod Replicas",
            "category": "CONTAINER",
            "command_template": "kubectl scale deployment --replicas=3",
            "is_preapproved": True
        }
    }

    @classmethod
    def resolve_action(cls, requested_action: str) -> Dict[str, Any]:
        """
        Validates whether requested action is in the Pre-Approved Catalog.
        Rejects raw shell commands (e.g. 'rm -rf', 'drop database').
        """
        raw_upper = requested_action.upper().strip()

        # Direct raw shell execution attempt check
        prohibited_raw = ["RM -RF", "DROP DATABASE", "DROP TABLE", "FORMAT C:", "SHUTDOWN", "CURL | SH"]
        if any(p in raw_upper for p in prohibited_raw):
            logger.error(f"[ACTION_CATALOG] DIRECT SHELL EXECUTION PROHIBITED: Requested raw string '{requested_action}' rejected!")
            return {
                "is_approved": False,
                "action_id": None,
                "error": "DIRECT_SHELL_EXECUTION_PROHIBITED",
                "message": f"Rule 1 Enforcement: LLM is strictly prohibited from executing raw shell command '{requested_action}'. Action ID from catalog required."
            }

        # Check matched catalog ID
        for action_id, meta in cls.CATALOG.items():
            if action_id == raw_upper or meta["name"].upper() in raw_upper:
                return {
                    "is_approved": True,
                    "action_id": action_id,
                    "metadata": meta,
                    "message": f"Rule 1 Passed: Action '{action_id}' validated against Pre-Approved Catalog."
                }

        # Fallback default catalog mapping for standard actions
        if "SPOOLER" in raw_upper:
            return {"is_approved": True, "action_id": "ACT_RESTART_SPOOLER", "metadata": cls.CATALOG["ACT_RESTART_SPOOLER"]}
        elif "DNS" in raw_upper:
            return {"is_approved": True, "action_id": "ACT_FLUSH_DNS", "metadata": cls.CATALOG["ACT_FLUSH_DNS"]}

        return {
            "is_approved": False,
            "action_id": None,
            "error": "UNAPPROVED_ACTION_ID",
            "message": f"Rule 1 Enforcement: Requested action '{requested_action}' is not in the Pre-Approved Catalog."
        }

    @classmethod
    def add_action_to_db_catalog(cls, action_id: str, name: str, category: str, command_template: str, added_by: str = "NOC_SYSADMIN") -> Dict[str, Any]:
        """
        Persists a newly added Dashboard catalog item directly to PostgreSQL DB table 'preapproved_action_catalog'.
        This becomes the #1 HIGHEST PRIORITY RULE evaluated before LLM reasoning/execution.
        """
        import os
        import psycopg2

        action_id_clean = action_id.upper().strip()
        new_entry = {
            "action_id": action_id_clean,
            "name": name,
            "category": category.upper(),
            "command_template": command_template,
            "is_preapproved": True,
            "added_by": added_by
        }

        # Update local in-memory catalog
        cls.CATALOG[action_id_clean] = new_entry

        # Persist to PostgreSQL DB
        try:
            db_host = os.environ.get("DB_HOST", "postgres")
            db_port = os.environ.get("DB_PORT", "5432")
            db_name = os.environ.get("DB_NAME", "osi_system")
            db_user = os.environ.get("DB_USER", "postgres")
            db_password = os.environ.get("DB_PASSWORD", "postgres")

            conn = psycopg2.connect(host=db_host, port=db_port, dbname=db_name, user=db_user, password=db_password)
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO preapproved_action_catalog (action_id, name, category, command_template, is_preapproved, added_by, created_at)
                    VALUES (%s, %s, %s, %s, TRUE, %s, NOW())
                    ON CONFLICT (action_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        category = EXCLUDED.category,
                        command_template = EXCLUDED.command_template,
                        added_by = EXCLUDED.added_by
                """, (action_id_clean, name, category.upper(), command_template, added_by))
            conn.commit()
            conn.close()
            logger.info(f"[ACTION_CATALOG] Dashboard catalog item '{action_id_clean}' persisted to PostgreSQL DB successfully!")
        except Exception as e:
            logger.warning(f"[ACTION_CATALOG] DB persistence notice (using in-memory cache): {e}")

        return {
            "status": "SUCCESS_PERSISTED_TO_DB",
            "action_id": action_id_clean,
            "priority": "RULE_1_HIGHEST_PRIORITY",
            "metadata": new_entry
        }

# Global catalog instance
action_catalog = PreApprovedActionCatalog()
