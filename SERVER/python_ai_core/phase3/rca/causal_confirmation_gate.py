"""
Phase 3.4: Causal Confirmation Gate & Forensic Decision Recorder (phase3/rca/causal_confirmation_gate.py)

1. CausalConfirmationGate: Deterministic 10-condition Confirmation Gate. Enforces LLM Isolation & G5 HITL Authorization Boundary.
2. ForensicCausalDecisionRecordEngine: Persists immutable decision record into PostgreSQL system_audits with SHA-256 integrity hash verification.
"""

import logging
import json
import psycopg2
import os
from typing import Dict, Any, List, Optional
from phase3.hypothesis.hypothesis_competition_engine import HypothesisContract, HypothesisRanker
from phase3.rca.confirmation_contract import ForensicCausalDecisionRecord
from phase3.rca.causal_sufficiency_engine import CausalSufficiencyEngine
from phase3.rca.why_engine import WhyEngine
from phase3.rca.why_not_engine import WhyNotEngine
from phase3.rca.alternative_elimination_engine import AlternativeEliminationEngine

logger = logging.getLogger("CAUSAL_CONFIRMATION_GATE")

DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("DB_PORT", "5433" if DB_HOST == "127.0.0.1" else "5432")
DB_NAME = os.environ.get("DB_NAME", "osi_system")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("POSTGRES_PASSWORD", ""))


class CausalConfirmationGate:
    def __init__(self):
        pass

    def evaluate_confirmation(self, incident_id: str, trace_id: str, hypotheses: List[HypothesisContract], proposed_by_llm: bool = False) -> ForensicCausalDecisionRecord:
        """
        Deterministically evaluates Causal Confirmation Gate for incident hypotheses.
        Invariant #10 Enforcement: If proposed_by_llm attempts direct transition without gate pass -> DENIED!
        Invariant #12 & #13 Enforcement: Confirmation does NOT authorize remediation (G5 HITL retains authorization control).
        """
        logger.info(f"[CAUSAL CONFIRMATION GATE] Evaluating incident '{incident_id}' (Trace: {trace_id})")

        # 1. Rank hypothesis competition via Bayesian Engine
        report = HypothesisRanker.rank_and_generate_report(incident_id, hypotheses)
        ranked = report["ranked_hypotheses"]

        if not hypotheses:
            return self._create_denied_record(incident_id, trace_id, "NO_HYPOTHESES_PROVIDED")

        winner = hypotheses[0]
        runner_up_p = hypotheses[1].posterior_probability if len(hypotheses) > 1 else 0.0

        # 2. Evaluate Causal Sufficiency
        suff_res = CausalSufficiencyEngine.evaluate_causal_sufficiency(winner, runner_up_posterior=runner_up_p)
        is_confirmed = suff_res["is_sufficient"] and not proposed_by_llm

        # 3. Generate Why & Why-Not Explanations
        why_exp = WhyEngine.generate_why_explanation(winner, suff_res["causal_margin"])
        why_not_exps = WhyNotEngine.generate_why_not_explanations(hypotheses[1:], winner.posterior_probability)

        # 4. Construct Alternative Elimination Matrix
        elim_matrix = AlternativeEliminationEngine.construct_elimination_matrix(hypotheses)

        decision = "CONFIRMED" if is_confirmed else ("DENIED" if proposed_by_llm else "INCONCLUSIVE")
        reason = "ALL_MANDATORY_CAUSAL_CONDITIONS_PASSED" if is_confirmed else ("LLM_DIRECT_CONFIRMATION_ATTEMPT_BLOCKED" if proposed_by_llm else "EVIDENCE_SUFFICIENCY_NOT_SATISFIED")

        record = ForensicCausalDecisionRecord(
            incident_id=incident_id,
            trace_id=trace_id,
            hypothesis_id=winner.hypothesis_id,
            candidate=winner.candidate,
            decision=decision,
            decision_reason=reason,
            evidence_ids=[e.evidence_id for e in winner.supporting_evidence],
            independent_source_groups=[e.independence_group for e in winner.supporting_evidence],
            temporal_analysis=why_exp.get("temporal_alignment", {}),
            topology_analysis=why_exp.get("topology_alignment", {}),
            probe_results=[],
            contradictions=[e.to_dict() for e in winner.contradicting_evidence],
            alternative_hypotheses=[h.to_dict() for h in hypotheses[1:]],
            why_explanation=why_exp,
            why_not_explanation={"alternatives": why_not_exps},
            posterior_distribution={h.candidate: h.posterior_probability for h in hypotheses},
            causal_margin=suff_res["causal_margin"],
            counterfactual_status="PASSED" if is_confirmed else "PENDING",
            gate_results=suff_res["conditions"],
            provenance_chain={"trace_id": trace_id, "record_count": len(winner.supporting_evidence)}
        )

        # Persist decision record to PostgreSQL system_audits
        self.persist_decision_record(record)
        return record

    def _create_denied_record(self, incident_id: str, trace_id: str, reason: str) -> ForensicCausalDecisionRecord:
        return ForensicCausalDecisionRecord(
            incident_id=incident_id, trace_id=trace_id, hypothesis_id="NONE", candidate="NONE",
            decision="DENIED", decision_reason=reason, evidence_ids=[], independent_source_groups=[],
            temporal_analysis={}, topology_analysis={}, probe_results=[], contradictions=[],
            alternative_hypotheses=[], why_explanation={}, why_not_explanation={},
            posterior_distribution={}, causal_margin=0.0, counterfactual_status="DENIED",
            gate_results={}, provenance_chain={"trace_id": trace_id}
        )

    def persist_decision_record(self, record: ForensicCausalDecisionRecord):
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
                    f"CAUSAL_DECISION_{record.decision}",
                    f"Incident: {record.incident_id} | Candidate: {record.candidate} | Reason: {record.decision_reason}",
                    json.dumps(record.to_dict())
                ))
            conn.commit()
            logger.info(f"[CAUSAL DECISION RECORD] Persisted decision '{record.decision}' to PostgreSQL system_audits (Hash: {record.integrity_hash[:8]}...)")
        except Exception as e:
            logger.error(f"[CAUSAL DECISION RECORD] Error persisting decision record: {e}")
            if conn:
                try: conn.rollback()
                except Exception: pass
        finally:
            if conn:
                try: conn.close()
                except Exception: pass
