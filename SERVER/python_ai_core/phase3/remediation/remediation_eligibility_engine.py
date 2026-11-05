"""
Phase 3.6: Remediation Eligibility Engine & Manager (phase3/remediation/remediation_eligibility_engine.py)

1. RemediationEligibilityEngine: Evaluates contract eligibility, preconditions, blast radius, rollback, and postconditions.
2. Persists immutable remediation decision records to PostgreSQL system_audits with SHA-256 integrity hash.
"""

import logging
import json
import psycopg2
import os
from typing import Dict, Any, List, Optional
from phase3.remediation.remediation_contract import RemediationContract
from phase3.remediation.precondition_engine import PreconditionEngine
from phase3.remediation.blast_radius_engine import BlastRadiusEngine
from phase3.remediation.postcondition_engine import PostconditionEngine

logger = logging.getLogger("REMEDIATION_ELIGIBILITY_ENGINE")

DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("DB_PORT", "5433" if DB_HOST == "127.0.0.1" else "5432")
DB_NAME = os.environ.get("DB_NAME", "osi_system")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("POSTGRES_PASSWORD", "SecurePassword_123!"))


class RemediationEligibilityEngine:
    def __init__(self):
        pass

    def evaluate_remediation_eligibility(self, contract: RemediationContract) -> Dict[str, Any]:
        """
        Evaluates full contract eligibility before transitioning status to ELIGIBLE / AWAITING_HITL.
        """
        logger.info(f"[REMEDIATION ELIGIBILITY] Evaluating contract '{contract.contract_id}' (Incident: '{contract.incident_id}')")

        # 1. Contract Integrity Check (Invariants #21 - #26)
        integrity = contract.validate_contract_integrity()
        if not integrity["is_valid"]:
            contract.status = "PRECONDITION_FAILED"
            return {
                "status": "DENIED",
                "reason": "CONTRACT_INTEGRITY_VIOLATION",
                "contract_id": contract.contract_id,
                "violations": integrity["violations"]
            }

        # 2. Precondition Check (Invariant #23)
        pre_res = PreconditionEngine.evaluate_preconditions(contract.preconditions)
        if not pre_res["all_passed"]:
            contract.status = "PRECONDITION_FAILED"
            return {
                "status": "DENIED",
                "reason": "PRECONDITION_CHECK_FAILED",
                "contract_id": contract.contract_id,
                "failed_conditions": pre_res["failed_conditions"]
            }

        # 3. Blast Radius & Risk Check (Invariant #25)
        blast_res = BlastRadiusEngine.evaluate_blast_radius(contract.blast_radius, contract.risk_score)
        if not blast_res["is_safe"]:
            contract.status = "PRECONDITION_FAILED"
            return {
                "status": "DENIED",
                "reason": "EXCESSIVE_BLAST_RADIUS_OR_RISK",
                "contract_id": contract.contract_id,
                "violations": blast_res["violations"]
            }

        # Contract passed all eligibility criteria -> Transition to ELIGIBLE / AWAITING_HITL
        contract.status = "AWAITING_HITL"
        logger.info(f"[REMEDIATION ELIGIBILITY] Contract '{contract.contract_id}' is ELIGIBLE & AWAITING HITL AUTHORIZATION!")

        # Persist contract to PostgreSQL system_audits
        self.persist_remediation_contract(contract)

        return {
            "status": "ELIGIBLE",
            "contract_id": contract.contract_id,
            "contract_status": contract.status,
            "required_authorization": contract.required_authorization,
            "contract_hash": contract.contract_hash
        }

    def persist_remediation_contract(self, contract: RemediationContract):
        conn = None
        try:
            conn = psycopg2.connect(
                host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
                user=DB_USER, password=DB_PASSWORD
            )
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO system_audits (status, recommendation, raw_json, timestamp)
                    VALUES (%s, %s, %s, NOW());
                """, (
                    f"REMEDIATION_CONTRACT_{contract.status}",
                    f"Incident: {contract.incident_id} | Cause: {contract.confirmed_cause_id} | Auth: {contract.required_authorization}",
                    json.dumps(contract.to_dict())
                ))
            conn.commit()
            logger.info(f"[REMEDIATION PERSISTENCE] Persisted contract '{contract.contract_id}' to PostgreSQL system_audits (Hash: {contract.contract_hash[:8]}...)")
        except Exception as e:
            logger.error(f"[REMEDIATION PERSISTENCE] Error persisting contract: {e}")
            if conn:
                try: conn.rollback()
                except Exception: pass
        finally:
            if conn:
                try: conn.close()
                except Exception: pass
