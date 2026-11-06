import logging
import json
import uuid
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Any, Dict, List, Optional

logger = logging.getLogger("POLICY_MEMORY")

class PolicyMemoryManager:
    """
    Layer 5: Policy Memory Manager
    - Stores and manages permanent governance policies in PostgreSQL (jarvis_policy_rules).
    - Enforces rules such as:
        * No router reboot without approval (NO_UNAPPROVED_ROUTER_REBOOT)
        * No production service shutdown without approval (NO_UNAPPROVED_PROD_SHUTDOWN)
        * HIGH risk commands require HITL (HIGH_COMMAND_HITL)
        * CRITICAL risk commands require Approval (CRITICAL_COMMAND_APPROVAL)
        * Mandatory Audit Log & Mandatory Rollback Plan
    - Integrates with PolicyEngine and RAG Engine.
    """

    def __init__(self):
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

    def evaluate_command_against_policies(self, command_str: str, risk_level: str) -> Dict[str, Any]:
        """
        Evaluates a proposed command and risk level against stored permanent policy rules.
        """
        cmd_lower = command_str.lower().strip()
        risk_upper = risk_level.upper().strip()

        sql = """
            SELECT uuid, policy_code, title, description, rule_effect, target_command_pattern,
                   target_risk_level, requires_approval, requires_hitl, requires_rollback_plan, requires_audit_logging
            FROM jarvis_policy_rules;
        """

        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql)
                policies = cur.fetchall()

            triggered_policies = []
            final_effect = "ALLOW"
            requires_approval = False
            requires_hitl = False
            requires_rollback_plan = False
            requires_audit_logging = True

            for p in policies:
                pattern = p["target_command_pattern"].lower()
                patterns = [pt.strip() for pt in pattern.split("|")]
                pattern_matched = any(pt in cmd_lower for pt in patterns)
                risk_matched = (p["target_risk_level"].upper() == risk_upper)

                if pattern_matched or risk_matched:
                    triggered_policies.append(dict(p))
                    if p["requires_approval"]:
                        requires_approval = True
                    if p["requires_hitl"]:
                        requires_hitl = True
                    if p["requires_rollback_plan"]:
                        requires_rollback_plan = True
                    if p["requires_audit_logging"]:
                        requires_audit_logging = True

                    if p["rule_effect"] == "DENY":
                        final_effect = "DENY"
                    elif p["rule_effect"] == "REQUIRE_APPROVAL" and final_effect != "DENY":
                        final_effect = "REQUIRE_APPROVAL"
                    elif p["rule_effect"] == "FORCE_HITL" and final_effect not in ["DENY", "REQUIRE_APPROVAL"]:
                        final_effect = "FORCE_HITL"

            return {
                "final_effect": final_effect,
                "requires_approval": requires_approval,
                "requires_hitl": requires_hitl,
                "requires_rollback_plan": requires_rollback_plan,
                "requires_audit_logging": requires_audit_logging,
                "triggered_policies": triggered_policies
            }

        except Exception as e:
            logger.error(f"[POLICY_MEMORY] Policy evaluation error: {e}")
            return {
                "final_effect": "FORCE_HITL",
                "requires_approval": True,
                "requires_hitl": True,
                "requires_rollback_plan": True,
                "requires_audit_logging": True,
                "triggered_policies": []
            }
        finally:
            conn.close()

    def get_all_policies(self) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM jarvis_policy_rules ORDER BY created ASC;"
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql)
                rows = cur.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[POLICY_MEMORY] Error getting policies: {e}")
            return []
        finally:
            conn.close()
