"""
Enterprise Autonomous AI OS — Phase 6: Step 6.4
Evolution Engine

AI menganalisis laporan audit arsitektur dan mengusulkan
"Evolution Proposals" untuk peningkatan sistem.

Proposals wajib disetujui operator via Dashboard (Human-in-the-Loop)
sebelum diterapkan. Tidak ada auto-apply ke production.

Proposal disimpan ke approval_queue dengan type = 'EVOLUTION'.
"""

import json
import logging
import os
import uuid
from typing import Dict, List, Optional

logger = logging.getLogger("EVOLUTION_ENGINE")


class EvolutionEngine:
    """
    Analyzes system_audits and meta_cognition_logs to generate
    structured Evolution Proposals for Human review.
    """

    def __init__(self, db_conn=None):
        self._conn = db_conn

    def analyze_and_propose(self) -> List[Dict]:
        """
        Full evolution analysis cycle.
        Returns list of proposals submitted to approval_queue.
        """
        proposals = []

        # 1. Analyze recent arch audits
        audit_proposals = self._proposals_from_audits()
        proposals.extend(audit_proposals)

        # 2. Analyze meta-cognition trends
        cognition_proposals = self._proposals_from_cognition()
        proposals.extend(cognition_proposals)
        
        # 3. Process human Ground Truth Feedback
        feedback_proposals = self._process_human_feedback()
        proposals.extend(feedback_proposals)

        # 4. Submit all to approval_queue
        for proposal in proposals:
            self._submit_proposal(proposal)

        logger.info("[EVOLUTION_ENGINE] Generated %d evolution proposals.", len(proposals))
        return proposals

    def _proposals_from_audits(self) -> List[Dict]:
        """Extract proposals from recent architecture audit findings."""
        proposals = []
        if not self._conn:
            return proposals
        try:
            with self._conn.cursor() as cur:
                cur.execute("""
                    SELECT audit_data FROM system_audits
                    WHERE audit_type IN ('ARCH_AUDITOR', 'CURIOSITY_ENGINE')
                      AND created_at > NOW() - INTERVAL '24 hours'
                    ORDER BY created_at DESC
                    LIMIT 5
                """)
                rows = cur.fetchall()
                for row in rows:
                    data = row[0] if isinstance(row[0], dict) else json.loads(row[0])
                    checks = data.get("checks", [])
                    for check in checks:
                        if check.get("severity") in ("HIGH", "MEDIUM"):
                            for finding in check.get("findings", []):
                                proposals.append({
                                    "proposal_id":   str(uuid.uuid4())[:8],
                                    "type":          "ARCHITECTURE_FIX",
                                    "title":         f"[{check['type']}] {finding[:80]}",
                                    "description":   finding,
                                    "severity":      check["severity"],
                                    "auto_generated": True,
                                })
        except Exception as e:
            logger.error("[EVOLUTION_ENGINE] Audit analysis error: %s", e)
        return proposals

    def _proposals_from_cognition(self) -> List[Dict]:
        """Extract proposals from meta-cognition trends."""
        proposals = []
        if not self._conn:
            return proposals
        try:
            with self._conn.cursor() as cur:
                # High hallucination rate
                cur.execute("""
                    SELECT
                        COUNT(*) FILTER (WHERE bias_detected = TRUE) * 100.0
                        / NULLIF(COUNT(*), 0) as hallucination_rate,
                        AVG(efficiency_score) as avg_efficiency
                    FROM meta_cognition_logs
                    WHERE evaluated_at > NOW() - INTERVAL '7 days'
                """)
                row = cur.fetchone()
                if row and row[0]:
                    hallucination_rate = float(row[0] or 0)
                    avg_efficiency     = float(row[1] or 1.0)

                    if hallucination_rate > 20.0:
                        proposals.append({
                            "proposal_id":   str(uuid.uuid4())[:8],
                            "type":          "KNOWLEDGE_ENRICHMENT",
                            "title":         f"Hallucination rate {hallucination_rate:.1f}% detected",
                            "description":   (
                                f"AI hallucination rate in last 7 days: {hallucination_rate:.1f}%. "
                                "Recommend running Curiosity Engine to enrich knowledge base "
                                "on frequently failed topics."
                            ),
                            "severity":      "HIGH",
                            "auto_generated": True,
                        })

                    if avg_efficiency < 0.6:
                        proposals.append({
                            "proposal_id":   str(uuid.uuid4())[:8],
                            "type":          "PERFORMANCE_TUNING",
                            "title":         f"Average AI efficiency {avg_efficiency:.2f} below threshold",
                            "description":   (
                                f"Average cognitive efficiency: {avg_efficiency:.2f} (threshold: 0.6). "
                                "Consider enabling prompt caching and reducing planning cycle depth."
                            ),
                            "severity":      "MEDIUM",
                            "auto_generated": True,
                        })
        except Exception as e:
            logger.error("[EVOLUTION_ENGINE] Cognition analysis error: %s", e)
        return proposals

    def _process_human_feedback(self) -> List[Dict]:
        """Extract proposals from Human Ground Truth Feedback."""
        proposals = []
        if not self._conn:
            return proposals
        try:
            with self._conn.cursor() as cur:
                # Find pending feedback
                cur.execute("""
                    SELECT feedback_id, incident_id, ai_root_cause, human_root_cause, score
                    FROM incident_feedback
                    WHERE feedback_state = 'PENDING'
                """)
                rows = cur.fetchall()
                for row in rows:
                    fid, iid, ai_rc, human_rc, score = row
                    
                    # Generate a Golden Policy proposal based on feedback
                    proposals.append({
                        "proposal_id":   str(uuid.uuid4())[:8],
                        "type":          "GOLDEN_POLICY_UPDATE",
                        "title":         f"Learn from Incident #{iid} Feedback (Score: {score})",
                        "description":   f"AI guessed: '{ai_rc}'. Operator corrected: '{human_rc}'. Need to encode this into RAG.",
                        "severity":      "HIGH",
                        "auto_generated": True,
                        "metadata": {
                            "feedback_id": fid,
                            "incident_id": iid,
                            "human_rc": human_rc
                        }
                    })
                    
                    # Mark as processed so we don't read it again
                    cur.execute("UPDATE incident_feedback SET feedback_state = 'PROCESSED' WHERE feedback_id = %s", (fid,))
                
                self._conn.commit()
        except Exception as e:
            logger.error("[EVOLUTION_ENGINE] Feedback processing error: %s", e)
            try:
                self._conn.rollback()
            except Exception:
                import logging; logging.getLogger(__name__).debug('_ = None suppressed')
        return proposals

    def _submit_proposal(self, proposal: Dict) -> bool:
        """Submit evolution proposal to approval_queue for human review."""
        if not self._conn:
            return False
        try:
            with self._conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO approval_queue
                        (incident_id, action_name, risk_level, status, created_at)
                    VALUES (0, %s, %s, 'PENDING', NOW())
                """, (
                    json.dumps(proposal),
                    proposal.get("severity", "LOW"),
                ))
            self._conn.commit()
            logger.info("[EVOLUTION_ENGINE] Proposal submitted: %s", proposal.get("title", "")[:60])
            return True
        except Exception as e:
            logger.warning("[EVOLUTION_ENGINE] Failed to submit proposal: %s", e)
            try:
                self._conn.rollback()
            except Exception:
                import logging; logging.getLogger(__name__).debug('_ = None suppressed')
            return False

    def get_pending_proposals(self) -> List[Dict]:
        """Return all pending evolution proposals."""
        if not self._conn:
            return list()
        try:
            with self._conn.cursor() as cur:
                cur.execute("""
                    SELECT id, action_name, risk_level, status, created_at
                    FROM approval_queue
                    WHERE incident_id = 0
                      AND status = 'PENDING'
                    ORDER BY created_at DESC
                    LIMIT 20
                """)
                rows = cur.fetchall()
                result = []
                for r in rows:
                    try:
                        action_data = json.loads(r[1]) if isinstance(r[1], str) else r[1]
                    except Exception:
                        action_data = {"raw": str(r[1])}
                    result.append({
                        "id": r[0], "proposal": action_data,
                        "risk": r[2], "severity": r[2],
                        "status": r[3], "created_at": str(r[4])
                    })
                return result
        except Exception as e:
            logger.error("[EVOLUTION_ENGINE] get_pending_proposals error: %s", e)
            return list()
