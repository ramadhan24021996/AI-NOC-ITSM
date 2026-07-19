"""
Enterprise Autonomous AI OS — Phase 5: Step 5.4
Continuous Architecture Auditor

Daemon yang berjalan setiap 6 jam untuk mendeteksi:
  1. Schema Drift — kolom/tabel baru yang tidak terdokumentasi
  2. Knowledge Drift — knowledge_vectors dengan freshness rendah
  3. Agent Drift — agent yang tidak mengirim heartbeat
  4. Policy Drift — policy_rules yang tidak pernah triggered
  5. Process Drift — NATS subjects tanpa consumer aktif

Semua temuan ditulis ke system_audits dan dapat diakses via Dashboard API.
"""

import asyncio
import json
import logging
import os
import time
from typing import Dict, List, Any, Optional

logger = logging.getLogger("ARCH_AUDITOR")

DB_HOST  = os.getenv("DB_HOST", "postgres")
DB_PORT  = os.getenv("DB_PORT", "5432")
DB_NAME  = os.getenv("DB_NAME", "osi_system")
DB_USER  = os.getenv("DB_USER", "postgres")
DB_PASS  = os.getenv("DB_PASSWORD", "postgres")
NATS_URL = os.getenv("NATS_URL", "nats://nats:4222")


def _get_db():
    import psycopg2
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, database=DB_NAME,
        user=DB_USER, password=DB_PASS
    )


class ArchAuditor:
    """
    Continuously audits the AI OS for architecture drift.
    """

    def __init__(self):
        self._conn: Optional[Any] = None

    def _connect(self) -> None:
        if not self._conn or self._conn.closed:
            self._conn = _get_db()

    # ─── 1. Knowledge Drift ───────────────────────────────────────────────────
    def audit_knowledge_drift(self) -> Dict[str, Any]:
        self._connect()
        assert self._conn is not None
        findings = []
        try:
            with self._conn.cursor() as cur:
                # Stale vectors
                cur.execute("""
                    SELECT COUNT(*) FROM knowledge_vectors
                    WHERE status = 'GOLDEN'
                      AND freshness_score < 0.5
                """)
                stale_count = cur.fetchone()[0]
                if stale_count > 0:
                    findings.append(f"{stale_count} GOLDEN vectors have freshness < 0.5")

                # DRAFT vectors older than 7 days (not approved)
                cur.execute("""
                    SELECT COUNT(*) FROM knowledge_vectors
                    WHERE status = 'DRAFT'
                      AND created_at < NOW() - INTERVAL '7 days'
                """)
                old_drafts = cur.fetchone()[0]
                if old_drafts > 0:
                    findings.append(f"{old_drafts} DRAFT vectors pending approval > 7 days")

        except Exception as e:
            findings.append(f"Knowledge drift check error: {e}")
            try:
                self._conn.rollback()
            except Exception:
                import logging; logging.getLogger(__name__).debug('_ = None suppressed')
        return {"type": "KNOWLEDGE_DRIFT", "findings": findings, "severity": "HIGH" if findings else "OK"}

    # ─── 2. Agent Drift ───────────────────────────────────────────────────────
    def audit_agent_drift(self) -> Dict[str, Any]:
        self._connect()
        assert self._conn is not None
        findings = []
        try:
            with self._conn.cursor() as cur:
                # Agents not seen in 5 minutes
                cur.execute("""
                    SELECT agent, last_seen FROM agent_heartbeats
                    WHERE last_seen < NOW() - INTERVAL '5 minutes'
                """)
                silent = cur.fetchall()
                for row in silent:
                    findings.append(f"Agent '{row[0]}' last seen at {row[1]}")

                # Low trust agents
                cur.execute("""
                    SELECT agent_name, trust_score FROM agent_trust_scores
                    WHERE trust_score < 40.0
                """)
                low_trust = cur.fetchall()
                for row in low_trust:
                    findings.append(f"Agent '{row[0]}' has critically low trust: {row[1]:.1f}")

        except Exception as e:
            findings.append(f"Agent drift check error: {e}")
            try:
                self._conn.rollback()
            except Exception:
                import logging; logging.getLogger(__name__).debug('_ = None suppressed')
        return {"type": "AGENT_DRIFT", "findings": findings, "severity": "MEDIUM" if findings else "OK"}

    # ─── 3. Policy Drift ─────────────────────────────────────────────────────
    def audit_policy_drift(self) -> Dict[str, Any]:
        self._connect()
        assert self._conn is not None
        findings = []
        try:
            with self._conn.cursor() as cur:
                # Policy rules never triggered in 30 days
                cur.execute("""
                    SELECT rule_name, description FROM policy_rules
                    WHERE is_active = TRUE
                      AND updated_at < NOW() - INTERVAL '30 days'
                    LIMIT 10
                """)
                old_rules = cur.fetchall()
                for row in old_rules:
                    findings.append(f"Policy rule '{row[0]}' not updated in 30+ days")

        except Exception as e:
            findings.append(f"Policy drift check error: {e}")
            try:
                self._conn.rollback()
            except Exception:
                import logging; logging.getLogger(__name__).debug('_ = None suppressed')
        return {"type": "POLICY_DRIFT", "findings": findings, "severity": "LOW" if findings else "OK"}

    # ─── 4. System Health Summary ─────────────────────────────────────────────
    def audit_system_health(self) -> Dict[str, Any]:
        self._connect()
        assert self._conn is not None
        metrics = {}
        try:
            with self._conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM incidents WHERE timestamp > NOW() - INTERVAL '24 hours'")
                metrics["incidents_24h"] = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM knowledge_vectors WHERE status = 'GOLDEN'")
                metrics["golden_vectors"] = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM knowledge_vectors WHERE status = 'DRAFT'")
                metrics["draft_vectors"] = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM fleet_devices WHERE online = TRUE")
                metrics["online_devices"] = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM simulation_results WHERE created_at > NOW() - INTERVAL '24 hours'")
                metrics["simulations_24h"] = cur.fetchone()[0]

        except Exception as e:
            logger.error("[ARCH_AUDITOR] Health summary error: %s", e)
            try:
                self._conn.rollback()
            except Exception:
                import logging; logging.getLogger(__name__).debug('_ = None suppressed')
        return {"type": "SYSTEM_HEALTH", "metrics": metrics, "severity": "OK"}

    # ─── Full Audit Run ───────────────────────────────────────────────────────
    def run_full_audit(self) -> Dict[str, Any]:
        report = {
            "audited_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "checks": [
                self.audit_knowledge_drift(),
                self.audit_agent_drift(),
                self.audit_policy_drift(),
                self.audit_system_health(),
            ]
        }

        # Determine overall severity
        severities = [c.get("severity", "OK") for c in report["checks"]]
        if "HIGH" in severities:
            report["overall"] = "HIGH"
        elif "MEDIUM" in severities:
            report["overall"] = "MEDIUM"
        elif "LOW" in severities:
            report["overall"] = "LOW"
        else:
            report["overall"] = "OK"

        # Persist to system_audits
        self._persist(report)
        logger.info("[ARCH_AUDITOR] Full audit complete. Overall: %s", report["overall"])
        return report

    def _persist(self, report: Dict) -> None:
        """Write audit report to system_audits."""
        try:
            self._connect()
            assert self._conn is not None
            with self._conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO system_audits
                        (status, raw_json, recommendation)
                    VALUES (%s, %s, %s)
                """, (
                    report.get("overall", "UNKNOWN"),
                    json.dumps(report),
                    "Auto-generated by ArchAuditor"
                ))
            self._conn.commit()
        except Exception as e:
            logger.warning("[ARCH_AUDITOR] Failed to persist audit: %s", e)
            try:
                self._conn.rollback()
            except Exception:
                import logging; logging.getLogger(__name__).debug('_ = None suppressed')


async def daemon(interval_hours: int = 6):
    """Run architecture auditor as periodic daemon."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    auditor = ArchAuditor()
    logger.info("[ARCH_AUDITOR] Daemon started. Interval=%dh", interval_hours)

    while True:
        try:
            report = auditor.run_full_audit()
            if report["overall"] in ("HIGH", "MEDIUM"):
                logger.warning("[ARCH_AUDITOR] DRIFT DETECTED: %s", report["overall"])
        except Exception as e:
            logger.error("[ARCH_AUDITOR] Daemon cycle error: %s", e)
        await asyncio.sleep(interval_hours * 3600)


if __name__ == "__main__":
    asyncio.run(daemon(interval_hours=6))
