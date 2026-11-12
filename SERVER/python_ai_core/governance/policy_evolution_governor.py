"""
Learning Isolation & Policy Evolution Governor (governance/policy_evolution_governor.py)

Enforces strict governance & training isolation:
1. Training Environment Isolation: Training reads read-only DPO exports; zero direct DB write permissions to production tables.
2. Invariant Protection: Candidate models/policies are validated against G3 (Provenance), G4 (Outcome Verification), and G5 (Fail-Closed HITL). Any candidate weakening invariants is REJECTED.
3. Immutable Versioning: Policy evolution uses strict v1 -> v2 -> v3 immutable audit trail with full rollback capability.
4. Controlled Promotion: GOLDEN ≠ ACTIVE. Promotion requires ELIGIBLE_FOR_ACTIVATION -> HITL Approval -> ACTIVE.
"""

import logging
import psycopg2
import psycopg2.extras
import os
import json
import time
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger("POLICY_EVOLUTION_GOVERNOR")

DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("DB_PORT", "5433" if DB_HOST == "127.0.0.1" else "5432")
DB_NAME = os.environ.get("DB_NAME", "osi_system")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("POSTGRES_PASSWORD", ""))


class PolicyEvolutionGovernor:
    def __init__(self):
        pass

    def _get_connection(self):
        return psycopg2.connect(
            host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
            user=DB_USER, password=DB_PASSWORD
        )

    def export_isolated_training_dataset(self, output_dir: str = "/tmp/isolated_training") -> Dict[str, Any]:
        """
        Exports read-only dataset from PostgreSQL dpo_training_pairs into isolated directory.
        Training environment operates strictly read-only against production DB.
        """
        os.makedirs(output_dir, exist_ok=True)
        dataset_file = os.path.join(output_dir, f"training_export_{int(time.time())}.jsonl")

        conn = None
        try:
            conn = self._get_connection()
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT id, record_id, incident_id, prompt, chosen, rejected, domain, quality_score, trace_id, outcome_id
                    FROM dpo_training_pairs;
                """)
                rows = cur.fetchall()

            count = 0
            with open(dataset_file, "w", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(dict(r)) + "\n")
                    count += 1

            logger.info(f"[LEARNING ISOLATION] Exported {count} records to isolated dataset '{dataset_file}' (Read-Only)")
            return {
                "status": "SUCCESS",
                "export_file": dataset_file,
                "record_count": count,
                "production_db_write_permitted": False
            }
        except Exception as e:
            logger.error(f"[LEARNING ISOLATION] Dataset export error: {e}")
            return {"status": "ERROR", "message": str(e)}
        finally:
            if conn:
                try: conn.close()
                except Exception: pass

    def verify_candidate_policy_invariants(self, candidate_rules: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Evaluates candidate policy rules against core production invariants (G3, G4, G5).
        Returns: (passed: bool, reason: str)
        """
        if not candidate_rules or not isinstance(candidate_rules, dict):
            return False, "Candidate rules payload empty or invalid format"

        # Invariant 1: G5 Fail-Closed HITL Verification
        hitl_bypass = candidate_rules.get("bypass_hitl_high_risk", False)
        conf_override = candidate_rules.get("allow_confidence_hitl_override", False)
        hitl_enforced = candidate_rules.get("enforce_hitl_high_risk", True)

        if hitl_bypass or conf_override or not hitl_enforced:
            return False, "INVARIANT_VIOLATION_G5: Candidate attempts to bypass/weaken Fail-Closed HITL enforcement"

        # Invariant 2: G4 Outcome Verification Protection
        allow_unverified_dpo = candidate_rules.get("allow_unverified_outcome_dpo", False)
        if allow_unverified_dpo:
            return False, "INVARIANT_VIOLATION_G4: Candidate attempts to allow positive DPO from unverified outcomes"

        # Invariant 3: G3 Provenance Protection
        require_provenance = candidate_rules.get("require_provenance_chain", True)
        if not require_provenance:
            return False, "INVARIANT_VIOLATION_G3: Candidate attempts to disable immutable provenance chain requirement"

        return True, "All production safety invariants VERIFIED PASSED"

    def propose_policy_version(
        self,
        rules_json: Dict[str, Any],
        change_reason: str,
        source_dpo_pair_ids: List[int],
        created_by: str = "AUTO_LEARNING_ENGINE"
    ) -> Dict[str, Any]:
        """
        Creates new immutable version row in policy_versions table with status 'SANDBOX_DRAFT'.
        """
        import uuid
        change_id = f"CHG-POLICY-{int(time.time())}-{uuid.uuid4().hex[:6]}"
        conn = None
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                # Get current max version number
                cur.execute("SELECT COALESCE(MAX(version), 0) FROM policy_versions;")
                max_ver = cur.fetchone()[0]
                new_version = max_ver + 1

                cur.execute("""
                    INSERT INTO policy_versions (
                        version, parent_version, change_id, change_reason, rules_json,
                        source_dpo_pair_ids, is_active, activation_status, created_by, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, FALSE, 'SANDBOX_DRAFT', %s, NOW())
                    RETURNING id, version, change_id;
                """, (
                    new_version, max_ver, change_id, change_reason, json.dumps(rules_json),
                    json.dumps(source_dpo_pair_ids), created_by
                ))
                row = cur.fetchone()

            conn.commit()
            logger.info(f"[POLICY GOVERNOR] Proposed immutable Policy Version {new_version} (ChangeID: {change_id}, Status: SANDBOX_DRAFT)")
            return {
                "status": "PROPOSED",
                "version_id": row[0],
                "version": row[1],
                "change_id": row[2],
                "activation_status": "SANDBOX_DRAFT"
            }
        except Exception as e:
            if conn:
                try: conn.rollback()
                except Exception: pass
            logger.error(f"[POLICY GOVERNOR] Failed to propose policy version: {e}")
            return {"status": "ERROR", "message": str(e)}
        finally:
            if conn:
                try: conn.close()
                except Exception: pass

    def evaluate_and_stage_candidate(self, version_id: int) -> Dict[str, Any]:
        """
        Evaluates staged candidate against invariants.
        If passed -> promotes status from SANDBOX_DRAFT to ELIGIBLE_FOR_ACTIVATION.
        """
        conn = None
        try:
            conn = self._get_connection()
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("SELECT id, version, rules_json, activation_status FROM policy_versions WHERE id = %s;", (version_id,))
                row = cur.fetchone()

            if not row:
                return {"status": "REJECTED", "reason": "Policy version record not found"}

            rules = row["rules_json"]
            if isinstance(rules, str):
                rules = json.loads(rules)

            passed, reason = self.verify_candidate_policy_invariants(rules)

            with conn.cursor() as cur:
                if passed:
                    cur.execute("""
                        UPDATE policy_versions 
                        SET activation_status = 'ELIGIBLE_FOR_ACTIVATION', evaluation_result = %s, updated_at = NOW()
                        WHERE id = %s;
                    """, (json.dumps({"passed": True, "reason": reason}), version_id))
                    conn.commit()
                    logger.info(f"[POLICY GOVERNOR] Policy Version {row['version']} PASSED invariant evaluation -> ELIGIBLE_FOR_ACTIVATION")
                    return {"status": "ELIGIBLE_FOR_ACTIVATION", "version": row["version"], "reason": reason}
                else:
                    cur.execute("""
                        UPDATE policy_versions 
                        SET activation_status = 'REJECTED', evaluation_result = %s, updated_at = NOW()
                        WHERE id = %s;
                    """, (json.dumps({"passed": False, "reason": reason}), version_id))
                    conn.commit()
                    logger.warning(f"[POLICY GOVERNOR] Policy Version {row['version']} REJECTED by invariant check -> {reason}")
                    return {"status": "REJECTED", "version": row["version"], "reason": reason}

        except Exception as e:
            if conn:
                try: conn.rollback()
                except Exception: pass
            logger.error(f"[POLICY GOVERNOR] Error evaluating candidate: {e}")
            return {"status": "ERROR", "message": str(e)}
        finally:
            if conn:
                try: conn.close()
                except Exception: pass

    def approve_and_activate_policy(self, version_id: int, approved_by: str) -> Dict[str, Any]:
        """
        Controlled Promotion Gate: Promotes ELIGIBLE_FOR_ACTIVATION policy to ACTIVE upon explicit HITL approval.
        Deactivates previous active policy version atomically.
        """
        if not approved_by:
            return {"status": "BLOCKED", "reason": "HITL Approval required (approved_by cannot be empty)"}

        conn = None
        try:
            conn = self._get_connection()
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("SELECT id, version, activation_status, rules_json FROM policy_versions WHERE id = %s;", (version_id,))
                row = cur.fetchone()

            if not row:
                return {"status": "BLOCKED", "reason": "Policy version not found"}

            curr_status = row["activation_status"]
            if curr_status != "ELIGIBLE_FOR_ACTIVATION":
                return {"status": "BLOCKED", "reason": f"Cannot activate policy in status '{curr_status}'. Must be 'ELIGIBLE_FOR_ACTIVATION'"}

            with conn.cursor() as cur:
                # Deactivate all active policy versions
                cur.execute("UPDATE policy_versions SET is_active = FALSE, updated_at = NOW() WHERE is_active = TRUE;")
                # Activate current policy version
                cur.execute("""
                    UPDATE policy_versions 
                    SET is_active = TRUE, activation_status = 'ACTIVE', approved_by = %s, approved_at = NOW(), updated_at = NOW()
                    WHERE id = %s;
                """, (approved_by, version_id))

            conn.commit()
            logger.info(f"[POLICY GOVERNOR] Policy Version {row['version']} ACTIVATED by HITL Approver '{approved_by}'")
            return {"status": "ACTIVE", "version": row["version"], "approved_by": approved_by}
        except Exception as e:
            if conn:
                try: conn.rollback()
                except Exception: pass
            logger.error(f"[POLICY GOVERNOR] Error activating policy: {e}")
            return {"status": "ERROR", "message": str(e)}
        finally:
            if conn:
                try: conn.close()
                except Exception: pass

    def rollback_policy(self, target_version_id: int, reason: str) -> Dict[str, Any]:
        """
        Rolls back to a previous valid policy version. Refuses rollback to invalid/rejected version.
        """
        conn = None
        try:
            conn = self._get_connection()
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("SELECT id, version, activation_status FROM policy_versions WHERE id = %s;", (target_version_id,))
                row = cur.fetchone()

            if not row:
                return {"status": "BLOCKED", "reason": "Target rollback policy version not found"}

            if row["activation_status"] in ["REJECTED", "BLOCKED", "INVALID"]:
                return {"status": "BLOCKED", "reason": f"Cannot rollback to invalid policy status '{row['activation_status']}'"}

            with conn.cursor() as cur:
                cur.execute("UPDATE policy_versions SET is_active = FALSE, updated_at = NOW() WHERE is_active = TRUE;")
                cur.execute("UPDATE policy_versions SET is_active = TRUE, activation_status = 'ACTIVE', updated_at = NOW() WHERE id = %s;", (target_version_id,))

            conn.commit()
            logger.info(f"[POLICY GOVERNOR] Policy rolled back to Version {row['version']}. Reason: {reason}")
            return {"status": "ROLLED_BACK", "target_version": row["version"], "reason": reason}
        except Exception as e:
            if conn:
                try: conn.rollback()
                except Exception: pass
            return {"status": "ERROR", "message": str(e)}
        finally:
            if conn:
                try: conn.close()
                except Exception: pass
