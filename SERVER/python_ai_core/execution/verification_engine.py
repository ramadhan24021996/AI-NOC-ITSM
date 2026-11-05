import logging
import json
import time
import os
import psycopg2
import psycopg2.extras
from typing import Dict, List, Any, Optional

logger = logging.getLogger("VERIFICATION_ENGINE")

DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("DB_PORT", "5433" if DB_HOST == "127.0.0.1" else "5432")
DB_NAME = os.environ.get("DB_NAME", "osi_system")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("POSTGRES_PASSWORD", "SecurePassword_123!"))


class VerificationEngine:
    """
    Enterprise Empirical Post-Verification Engine.
    Memverifikasi status operasional nyata melalui metrik telemetri,
    penurunan antrean, konektivitas, dan hilangnya error.
    """

    def _get_connection(self):
        return psycopg2.connect(
            host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
            user=DB_USER, password=DB_PASSWORD
        )

    def verify_remediation(
        self,
        action_id: str,
        verification_steps: List[str],
        target_asset: str,
        execution_result: Optional[Dict[str, Any]] = None,
        post_telemetry: Optional[Dict[str, Any]] = None,
        pre_telemetry: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        incident_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Melakukan evaluasi verifikasi independen ganda dan mencatat hasil outcome ke PostgreSQL.
        """
        # [K-09 / Rule #6] Never assume success. Missing execution evidence => fail.
        if not execution_result:
            execution_result = {"success": False, "exit_code": None}
        if not post_telemetry:
            # No post-remediation telemetry => cannot be verified.
            all_passed_override = False
        else:
            all_passed_override = True
        post_telemetry = post_telemetry or {}
        pre_telemetry = pre_telemetry or {}

        step_results = []
        all_passed = True
        failure_reasons = []
        if not all_passed_override:
            all_passed = False
            failure_reasons.append("post_remediation_evidence missing (Rule #6).")

        # Generate canonical outcome_id
        outcome_id = f"OUTCOME-{action_id}-{int(time.time())}"

        # 1. Cek Hasil Eksekusi Dasar (Script / Command)
        exec_success = execution_result.get("success") is True and execution_result.get("exit_code") == 0
        if not exec_success:
            all_passed = False
            failure_reasons.append("Command execution failed with non-zero exit code.")

        # 2. Cek Metrik Telemetri Pasca-Tindakan (INDEPENDENT VERIFICATION)
        # Skenario Spooler & Printer Queue
        if "ACT_RESTART_SPOOLER" in action_id.upper() or "SPOOLER" in action_id.upper():
            spooler_running = post_telemetry.get("spooler_running", False)
            queue_count = post_telemetry.get("print_queue_count", 0)

            if not spooler_running:
                all_passed = False
                failure_reasons.append("Spooler service is still STOPPED post-restart or unverified.")
            if queue_count > 0 and post_telemetry.get("queue_stuck", False):
                all_passed = False
                failure_reasons.append(f"Print queue is still stuck with {queue_count} pending jobs.")

        # Skenario Konektivitas Jaringan & Ping
        if "NET" in action_id.upper() or "PING" in action_id.upper() or "INTERFACE" in action_id.upper():
            ping_ok = post_telemetry.get("ping_success", False)
            if not ping_ok:
                all_passed = False
                failure_reasons.append("Target IP remains UNREACHABLE via ICMP ping check or unverified.")

        # 3. Evaluasi Langkah Verifikasi Tertulis dalam SOP
        for step in verification_steps:
            passed = True
            if "queue_cleared" in step and post_telemetry.get("print_queue_count", 0) > 0:
                passed = False
                failure_reasons.append(f"Step '{step}' failed: Queue not cleared.")

            step_results.append({
                "step": step,
                "passed": passed,
                "output": f"Verification '{step}': {'OK' if passed else 'FAILED'}"
            })

            if not passed:
                all_passed = False

        status_str = "VERIFIED_SUCCESS" if all_passed else "VERIFICATION_FAILED"
        logger.info(f"[VERIFICATION] Action '{action_id}' on asset '{target_asset}': Result={status_str} (OutcomeID={outcome_id})")

        # 4. Persist Outcome Record to PostgreSQL remediation_results
        self._persist_outcome_record(
            outcome_id=outcome_id,
            trace_id=trace_id,
            execution_id=execution_id,
            incident_id=incident_id,
            action_id=action_id,
            target_asset=target_asset,
            outcome_verified=all_passed,
            pre_telemetry=pre_telemetry,
            post_telemetry=post_telemetry,
            recovery_criteria={"steps": step_results, "reasons": failure_reasons}
        )

        # 5. Update Canonical Provenance Tracker if trace_id is present
        if trace_id:
            try:
                from provenance.provenance_tracker import ProvenanceTracker
                ptracker = ProvenanceTracker()
                ptracker.create_provenance_chain(trace_id=trace_id, incident_id=incident_id)
                ptracker.update_stage_id(trace_id=trace_id, stage_name="outcome_id", stage_value=outcome_id)
                if execution_id: ptracker.update_stage_id(trace_id=trace_id, stage_name="execution_id", stage_value=execution_id)
            except Exception as p_err:
                logger.warning(f"[VERIFICATION] Error updating provenance tracker: {p_err}")

        return {
            "outcome_id": outcome_id,
            "trace_id": trace_id,
            "execution_id": execution_id,
            "action_id": action_id,
            "target_asset": target_asset,
            "execution_success": exec_success,
            "all_verified": all_passed,
            "outcome_verified": all_passed,
            "verification_status": status_str,
            "failure_reasons": failure_reasons,
            "step_details": step_results
        }

    def _persist_outcome_record(
        self,
        outcome_id: str,
        trace_id: Optional[str],
        execution_id: Optional[str],
        incident_id: Optional[str],
        action_id: str,
        target_asset: str,
        outcome_verified: bool,
        pre_telemetry: Dict[str, Any],
        post_telemetry: Dict[str, Any],
        recovery_criteria: Dict[str, Any]
    ) -> None:
        conn = None
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                # Check if action_id exists in remediation_registry
                cur.execute("SELECT COUNT(*) FROM remediation_registry WHERE remediation_id = %s;", (action_id,))
                rem_id_val = action_id if cur.fetchone()[0] > 0 else None

                cur.execute("""
                    INSERT INTO remediation_results (
                        outcome_id, trace_id, execution_id, incident_id, remediation_id,
                        service_restored, outcome_verified, pre_telemetry, post_telemetry, recovery_criteria,
                        evidence, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (outcome_id) DO NOTHING;
                """, (
                    outcome_id, trace_id, execution_id, incident_id, rem_id_val,
                    outcome_verified, outcome_verified, json.dumps(pre_telemetry), json.dumps(post_telemetry),
                    json.dumps(recovery_criteria), f"Asset: {target_asset} | Action: {action_id} | Verified: {outcome_verified}"
                ))
            conn.commit()
            logger.info(f"[VERIFICATION] Persisted outcome record '{outcome_id}' to PostgreSQL remediation_results")
        except Exception as e:
            if conn:
                try: conn.rollback()
                except Exception: pass
            logger.error(f"[VERIFICATION] Failed to persist outcome record '{outcome_id}': {e}")
        finally:
            if conn:
                try: conn.close()
                except Exception: pass
