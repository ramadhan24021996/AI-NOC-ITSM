"""
Playbook Eligibility & Classification Pipeline (planning/playbook_eligibility_pipeline.py)

Enforces strict 9-stage promotion lifecycle for AI NOC Knowledge & Playbooks:
KNOWLEDGE_VECTOR → CLASSIFICATION (INFORMATIONAL / DIAGNOSTIC / REMEDIATION)
  ├── INFORMATIONAL ──► RAG ONLY (0 Playbooks)
  ├── DIAGNOSTIC ────► DIAGNOSTIC READ-ONLY CANDIDATE ──► STATIC VALIDATION
  └── REMEDIATION ───► CANDIDATE ──► STATIC ──► SECURITY ──► DRY-RUN ──► SANDBOX_DRAFT ──► VALIDATED ──► HITL_REVIEW ──► GOLDEN ──► ELIGIBLE ──► ACTIVE

Absolute Rules:
1. APPROVED Knowledge ≠ Eligible Playbook (Knowledge approval != execution authorization).
2. GOLDEN ≠ ACTIVE (Requires ELIGIBLE_FOR_ACTIVATION -> Policy -> HITL -> ACTIVE).
3. INFORMATIONAL vectors NEVER produce executable commands.
4. DIAGNOSTIC playbooks are strictly read-only.
5. REMEDIATION candidates must satisfy all 9 eligibility stages before activation.
"""

import logging
import psycopg2
import psycopg2.extras
import os
import json
import re
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger("PLAYBOOK_ELIGIBILITY_PIPELINE")

DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("DB_PORT", "5433" if DB_HOST == "127.0.0.1" else "5432")
DB_NAME = os.environ.get("DB_NAME", "osi_system")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("POSTGRES_PASSWORD", "[REDACTED_DB_PASS]"))

# Security Blacklist for Destructive Commands
COMMAND_BLACKLIST = [
    "rm -rf /", "rm -rf", "rm ", "reset", "kill", "killall", "pkill",
    "systemctl restart", "systemctl stop", "systemctl disable",
    "service stop", "service restart", "reboot", "shutdown", "poweroff",
    "bash -c", "sh -c", "sudo ", "su ", "exec ", "python -c", "perl -e",
    "drop database", "drop table", "truncate table", "delete from", "format c:", "mkfs",
    "dd if=/dev/zero", "del /q /f", "del /s", "shutdown -s", "poweroff",
    "init 0", ":(){ :|:& };:", "chmod -r 777 /",
    "/ip route", "/ip firewall", "/ip address", "/ip nat",
    "kubectl delete", "docker rm", "docker system prune", "docker volume rm",
    "docker network rm", "virsh destroy", "qm destroy", "terraform destroy"
]

# Read-only Diagnostic Command Patterns
DIAGNOSTIC_PATTERNS = [
    r"\bping\b", r"\btraceroute\b", r"\bnslookup\b", r"\bnetstat\b", r"\bdf -h\b",
    r"\bfree -m\b", r"\btop -bn1\b", r"\bps aux\b", r"\bsystemctl status\b",
    r"\bGet-Service\b", r"\bGet-Process\b", r"\bGet-EventLog\b", r"\bTest-NetConnection\b"
]

# Destructive Action Keywords
DESTRUCTIVE_KEYWORDS = [
    "kill", "killall", "pkill", "stop", "restart", "reboot", "delete",
    "remove", "truncate", "format", "clear", "purge", "rm"
]


class PlaybookEligibilityPipeline:
    def __init__(self):
        pass

    def _get_connection(self):
        return psycopg2.connect(
            host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
            user=DB_USER, password=DB_PASSWORD
        )

    def classify_knowledge_vector(self, title: str, symptoms: str, root_cause: str, resolution: str, tags: List[str]) -> str:
        """
        Classifies a Knowledge Vector into:
        - INFORMATIONAL: RAG Search Only (human guidance, SOP reference, hardware check notes)
        - DIAGNOSTIC: Read-only diagnostic command candidate
        - REMEDIATION: Automated remediation command candidate
        """
        res_text = (resolution or "").lower()
        title_text = (title or "").lower()
        symptom_text = (symptoms or "").lower()
        all_text = f"{title_text} {symptom_text} {res_text}"

        # 1. Check if resolution contains explicit CLI / PowerShell / Bash command syntax
        has_cli_syntax = any(kw in res_text for kw in ["systemctl", "get-service", "stop-service", "restart-service", "kill", "top -bn1", "netstat", "powershell", "cmd.exe", "bash"])

        if not has_cli_syntax:
            # Human guidance, general SOP text, hardware checks -> INFORMATIONAL
            return "INFORMATIONAL"

        # 2. Check for Destructive / Remediation Keywords
        has_remediation = any(kw in all_text for kw in DESTRUCTIVE_KEYWORDS)

        # 3. Check for Read-only Diagnostic Patterns
        is_diagnostic = any(re.search(p, all_text) for p in DIAGNOSTIC_PATTERNS)

        if has_remediation:
            return "REMEDIATION"
        elif is_diagnostic:
            return "DIAGNOSTIC"
        else:
            return "INFORMATIONAL"

    def validate_candidate_command(self, command_str: str, classification: str) -> Tuple[bool, str, float]:
        """
        Performs static syntax & security blacklist validation on a command string.
        Returns: (passed: bool, reason: str, risk_score: float)
        """
        if not command_str or len(command_str.strip()) < 3:
            return False, "Empty or invalid command string length", 1.0

        cmd_upper = command_str.upper()

        # Security Check 1: Blacklist Match
        for b_cmd in COMMAND_BLACKLIST:
            if b_cmd.upper() in cmd_upper:
                return False, f"Security Blacklist Match: '{b_cmd}'", 1.0

        # Security Check 2: Diagnostic Read-Only Safety
        if classification == "DIAGNOSTIC":
            for d_kw in DESTRUCTIVE_KEYWORDS:
                if d_kw.upper() in cmd_upper:
                    return False, f"Diagnostic command contains destructive keyword: '{d_kw}'", 0.90

        # Syntax Check 3: Suspicious Unescaped Wildcards or Injection Chars
        if "; rm " in command_str or "&& rm " in command_str or "|| rm " in command_str:
            return False, "Suspicious command chaining injection pattern detected", 1.0

        risk_score = 0.80 if classification == "REMEDIATION" else 0.20
        return True, "Passed static & security validation", risk_score

    def run_batch_eligibility_classification(self) -> Dict[str, Any]:
        """
        Runs empirical batch classification & eligibility validation across all PostgreSQL knowledge_vectors.
        Enforces zero bulk activation: only candidates passing all gates reach ACTIVE.
        """
        conn = None
        try:
            conn = self._get_connection()
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT incident_id, title, symptoms, root_cause, resolution, tags, status, layer
                    FROM knowledge_vectors;
                """)
                vectors = cur.fetchall()

            total_vectors = len(vectors)
            counts = {
                "INFORMATIONAL": 0,
                "DIAGNOSTIC": 0,
                "REMEDIATION": 0,
                "UNCLASSIFIED": 0
            }

            candidates_staged = 0
            blacklisted_count = 0
            active_count = 0

            # Process each vector safely
            with conn.cursor() as cur:
                for v in vectors:
                    v_id = v["incident_id"]
                    title = v["title"] or ""
                    symptoms = v["symptoms"] or ""
                    root_cause = v["root_cause"] or ""
                    resolution = v["resolution"] or ""
                    tags = v["tags"] or []
                    status = v["status"] or "SANDBOX_DRAFT"
                    layer = v["layer"] or 1

                    cls = self.classify_knowledge_vector(title, symptoms, root_cause, resolution, tags)
                    counts[cls] = counts.get(cls, 0) + 1

                    # Rule: INFORMATIONAL vectors NEVER create playbooks
                    if cls == "INFORMATIONAL":
                        continue

                    # Extract candidate command string if available
                    cmd = None
                    if "systemctl" in resolution.lower() or "powershell" in resolution.lower() or "cmd" in resolution.lower():
                        cmd = resolution[:300]

                    if not cmd:
                        continue

                    passed, reason, risk = self.validate_candidate_command(cmd, cls)
                    if not passed:
                        blacklisted_count += 1
                        logger.warning(f"[PLAYBOOK PIPELINE] Vector '{v_id}' rejected by security validation: {reason}")
                        continue

                    # Stage candidate in playbooks table as SANDBOX_DRAFT (NOT ACTIVE!)
                    cur.execute("""
                        INSERT INTO playbooks (
                            name, description, script, target_layer, status, category,
                            created_at, steps, source_vector_id, risk_level, hitl_approved, classification
                        ) VALUES (%s, %s, %s, %s, 'SANDBOX_DRAFT', %s, NOW(), %s, %s, %s, FALSE, %s)
                        ON CONFLICT DO NOTHING;
                    """, (
                        title[:100], f"Symptom: {symptoms[:100]} | RCA: {root_cause[:100]}",
                        cmd, layer, cls, json.dumps({"diagnosis": symptoms[:150], "verification": "Empirical Verification Required"}),
                        v_id, "HIGH" if risk >= 0.50 else "LOW", cls
                    ))
                    candidates_staged += 1

                # Check actual ACTIVE playbooks count in PostgreSQL
                cur.execute("SELECT COUNT(*) FROM playbooks WHERE status = 'ACTIVE';")
                row = cur.fetchone()
                active_count = row[0] if row else 0

            conn.commit()

            logger.info(f"[PLAYBOOK PIPELINE] Classification complete. Total: {total_vectors}, Informational: {counts['INFORMATIONAL']}, Diagnostic: {counts['DIAGNOSTIC']}, Remediation: {counts['REMEDIATION']}, Staged Sandbox Draft: {candidates_staged}, Active: {active_count}")

            return {
                "total_knowledge_vectors": total_vectors,
                "classification": counts,
                "pipeline_metrics": {
                    "candidates_staged_as_sandbox_draft": candidates_staged,
                    "security_blacklisted_rejected": blacklisted_count,
                    "active_playbooks": active_count,
                    "zero_bulk_activation_enforced": True
                }
            }
        except Exception as e:
            if conn:
                try: conn.rollback()
                except Exception: pass
            logger.error(f"[PLAYBOOK PIPELINE] Error in batch classification: {e}")
            return {"status": "ERROR", "message": str(e)}
        finally:
            if conn:
                try: conn.close()
                except Exception: pass
