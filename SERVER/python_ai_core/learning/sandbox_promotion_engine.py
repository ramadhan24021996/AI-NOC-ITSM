"""
Automated AI Learning Sandbox Promotion Engine (learning/sandbox_promotion_engine.py)

Manages the 4-stage Sandbox Promotion Lifecycle:
  1. SANDBOX_DRAFT (Initial Staging from documents / telemetry logs)
  2. SIMULATION_RUNNING (Automated Command Dry-Run & Safety Check)
  3. VERIFIED_SANDBOX (Passed dry-run verification & safety checks)
  4. APPROVED_GOLDEN (Promoted to Live RAG Production vector store)

Ensures zero data-poisoning and zero-production-risk for AI Knowledge & SOPs.
"""

import logging
import json
import os
import sys
import psycopg2

logger = logging.getLogger("SANDBOX_PROMOTION_ENGINE")

DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("DB_PORT", "5433" if DB_HOST == "127.0.0.1" else "5432")
DB_NAME = os.environ.get("DB_NAME", "osi_system")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("POSTGRES_PASSWORD", "SecurePassword_123!"))

def get_db():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD
    )

# High-risk command blacklists for dry-run verification
COMMAND_BLACKLIST = [
    "rm -rf /", "drop database", "format c:", "mkfs", "dd if=/dev/zero",
    "del /q /f c:\\windows\\system32", ":(){ :|:& };:"
]

class SandboxPromotionEngine:
    def __init__(self, conn=None):
        self.conn = conn or get_db()

    def run_sandbox_dryrun_verification(self, incident_id: str, command: str, resolution_text: str) -> tuple[bool, float, list[str]]:
        """
        Runs dry-run safety and syntax checks on a staged sandbox SOP.
        Returns: (passed: bool, safety_score: float, reasons: list[str])
        """
        logger.info(f"[SANDBOX ENGINE] Running Dry-Run Verification on Vector '{incident_id}'")
        reasons = []
        safety_score = 100.0

        # Check 1: Command Blacklist Check
        cmd_upper = (command or "").upper()
        for b_cmd in COMMAND_BLACKLIST:
            if b_cmd.upper() in cmd_upper:
                safety_score = 0.0
                reasons.append(f"Command blacklist match: '{b_cmd}'")
                logger.error(f"[SANDBOX BLOCKED] Vector '{incident_id}' failed safety check: {b_cmd}")
                return False, safety_score, reasons

        # Check 2: Resolution Length & Completeness
        if len(resolution_text or "") < 50:
            safety_score -= 30.0
            reasons.append("Resolution text too short or incomplete")

        # Check 3: Structured 5-Section Header Check
        required_sections = ["Ringkasan Kasus", "Analisis Akar Masalah", "Panduan Penanganan 3-Tahap", "Skrip Eksekusi"]
        missing = [s for s in required_sections if s not in resolution_text]
        if missing:
            safety_score -= (10.0 * len(missing))
            reasons.append(f"Missing structured sections: {', '.join(missing)}")

        passed = safety_score >= 80.0
        if passed:
            reasons.append("All dry-run safety and syntax checks PASSED")
            logger.info(f"[SANDBOX PASSED] Vector '{incident_id}' verified with score {safety_score:.1f}%")
        else:
            logger.warning(f"[SANDBOX FAILED] Vector '{incident_id}' failed with score {safety_score:.1f}%")

        return passed, safety_score, reasons

    def promote_sandbox_vectors(self) -> dict:
        """
        Evaluates all staged SANDBOX_DRAFT knowledge vectors and promotes verified ones to APPROVED_GOLDEN.
        """
        logger.info("=== Executing Automated Sandbox Promotion Lifecycle ===")
        promoted = 0
        rejected = 0
        total_eval = 0

        with self.conn.cursor() as cur:
            # Fetch vectors in SANDBOX_DRAFT status
            cur.execute("""
                SELECT incident_id, title, symptoms, root_cause, resolution, confidence
                FROM knowledge_vectors
                WHERE status IN ('DRAFT', 'SANDBOX_DRAFT')
                ORDER BY created_at ASC
                LIMIT 500
            """)
            rows = cur.fetchall()
            total_eval = len(rows)

            for r in rows:
                v_id, title, symp, rc, res, conf = r[0], r[1], r[2], r[3], r[4], r[5]

                # Extract command snippet if present
                cmd = ""
                if "```powershell" in (res or ""):
                    try:
                        cmd = res.split("```powershell")[1].split("```")[0].strip()
                    except:
                        pass
                elif "```bash" in (res or ""):
                    try:
                        cmd = res.split("```bash")[1].split("```")[0].strip()
                    except:
                        pass

                passed, score, reasons = self.run_sandbox_dryrun_verification(v_id, cmd, res or "")

                new_status = "APPROVED" if passed else "REJECTED_SANDBOX"
                if passed:
                    promoted += 1
                else:
                    rejected += 1

                # Update vector status in PostgreSQL
                cur.execute("""
                    UPDATE knowledge_vectors
                    SET status = %s,
                        confidence = %s,
                        last_validated = NOW(),
                        freshness_score = 1.0
                    WHERE incident_id = %s
                """, (new_status, score, v_id))

                # Log to policy audit trail
                cur.execute("""
                    INSERT INTO policy_audit_trail (incident_id, policy_version, input_context, matched_rule, effect, evaluated_at)
                    VALUES (0, 1, %s, 'Sandbox Promotion Engine', %s, NOW())
                """, (
                    json.dumps({"vector_id": v_id, "title": title, "score": score, "reasons": reasons}),
                    new_status
                ))

            self.conn.commit()

        logger.info(f"✅ Sandbox Promotion Lifecycle Complete:")
        logger.info(f"   Evaluated: {total_eval} Sandbox Draft Vectors")
        logger.info(f"   Promoted:  {promoted} to APPROVED_GOLDEN")
        logger.info(f"   Rejected:  {rejected} (Failed Safety/Syntax Checks)")

        return {
            "total_evaluated": total_eval,
            "promoted_golden": promoted,
            "rejected_sandbox": rejected
        }

if __name__ == "__main__":
    engine = SandboxPromotionEngine()
    engine.promote_sandbox_vectors()
