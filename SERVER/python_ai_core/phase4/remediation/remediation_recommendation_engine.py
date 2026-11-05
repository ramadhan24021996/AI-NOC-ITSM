"""
Phase 4.1 Remediation Recommendation Engine (phase4/remediation/remediation_recommendation_engine.py)

Ranks remediation candidates deterministically following Hard Safety Gates.
Enforces:
- INVARIANT #29 (Safety Precedes Optimization)
- INVARIANT #30 (Recommendation is NOT Authorization)
- Explicit candidate lifecycle separation
- Deterministic tie-breaker hierarchy: Score > Risk > Blast > Lexicographical ACTION_ID
- First-class NO_SAFE_REMEDIATION disposition when zero candidates pass safety
"""

import dataclasses
import logging
from typing import Dict, Any, List, Optional, Tuple
from phase3.remediation.remediation_contract import RemediationContract
from phase4.remediation.remediation_action_registry import ActionRegistry, ActionContract
from phase4.remediation.candidate_normalizer import CandidateNormalizer
from phase4.remediation.remediation_scoring_policy import RemediationScoringPolicy
from phase4.remediation.remediation_hard_safety_gate import RemediationHardSafetyGate
from phase4.remediation.remediation_score_calculator import RemediationScoreCalculator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("REMEDIATION_RECOMMENDATION_ENGINE")


@dataclasses.dataclass
class CandidateEvaluationResult:
    candidate_id: str
    action_id: str
    candidate_status: str  # REGISTERED vs UNREGISTERED_DENIED
    safety_status: str     # PASS_SAFETY vs ELIMINATED
    scoring_status: str    # SCORED vs SKIPPED
    ranking_status: str    # RECOMMENDED vs RANKED_ALTERNATIVE vs ELIMINATED
    authorization_status: str  # AWAITING_HITL vs DENIED
    score: float = 0.0
    risk_score: float = 0.0
    blast_radius_nodes: int = 1
    violations: List[str] = dataclasses.field(default_factory=list)
    contract: Optional[RemediationContract] = None


class RemediationRecommendationEngine:
    def __init__(self, policy: Optional[RemediationScoringPolicy] = None):
        self.registry = ActionRegistry()
        self.normalizer = CandidateNormalizer(self.registry)
        self.policy = policy or RemediationScoringPolicy()
        self.safety_gate = RemediationHardSafetyGate(self.policy)
        self.score_calc = RemediationScoreCalculator(self.policy)

    def rank_remediation_candidates(
        self,
        incident_id: str,
        trace_id: str,
        proposals: List[Dict[str, Any]],
        cause_status: str = "CONFIRMED"
    ) -> Dict[str, Any]:
        """
        Ranks candidate remediation proposals following exact pipeline:
        Candidate Normalization -> Action Registry Lookup -> Hard Safety Gate -> Deterministic Scoring -> Deterministic Tie-Breaker Ranking.
        """
        logger.info(f"=== [RECOMMENDATION ENGINE] Ranking {len(proposals)} candidates for Incident '{incident_id}' ===")
        evaluations: List[CandidateEvaluationResult] = []

        for idx, prop in enumerate(proposals, start=1):
            cand_id = f"R{idx}"
            # 1. Candidate Normalization & Action Registry Lookup
            is_reg, action_contract, norm_msg = self.normalizer.normalize_and_resolve_candidate(prop)

            if not is_reg or not action_contract:
                res = CandidateEvaluationResult(
                    candidate_id=cand_id,
                    action_id=prop.get("action_id", "UNREGISTERED"),
                    candidate_status="UNREGISTERED_DENIED",
                    safety_status="ELIMINATED",
                    scoring_status="SKIPPED",
                    ranking_status="ELIMINATED",
                    authorization_status="DENIED",
                    violations=[f"Normalizer failure: {norm_msg}"]
                )
                evaluations.append(res)
                continue

            # Build RemediationContract for safety evaluation
            rem_contract = prop.get("contract")
            if not rem_contract:
                rem_contract = RemediationContract(
                    contract_id=f"REM-{cand_id}",
                    incident_id=incident_id,
                    trace_id=trace_id,
                    confirmed_cause_id=prop.get("cause_id", "CAUSE-1"),
                    cause_status=cause_status,
                    objective=f"Execute {action_contract.name}",
                    target_scope=prop.get("target_scope", "srv-prod-db-01"),
                    preconditions=prop.get("preconditions", [{"name": "pre", "check_value": True, "expected_value": True}]),
                    action_definition={"action_type": action_contract.execution_type, "action_id": action_contract.action_id},
                    constraints=["NO_PROD_DOWNTIME"],
                    risk_score=prop.get("risk_score", action_contract.default_risk),
                    blast_radius=prop.get("blast_radius", {"max_affected_nodes": action_contract.default_blast_radius}),
                    reversibility=action_contract.rollback_supported,
                    rollback_contract=prop.get("rollback_contract"),
                    postconditions=prop.get("postconditions", [{"metric_name": "cpu", "target_value": 15.0}]),
                    verification_policy={"policy": "G4_VERIFICATION"}
                )

            # 2. Hard Safety Gate Evaluation (INVARIANT #29)
            pass_safety, safety_status, violations = self.safety_gate.evaluate_safety_gate(rem_contract, action_registered=True)

            if not pass_safety:
                res = CandidateEvaluationResult(
                    candidate_id=cand_id,
                    action_id=action_contract.action_id,
                    candidate_status="REGISTERED",
                    safety_status="ELIMINATED",
                    scoring_status="SKIPPED",
                    ranking_status="ELIMINATED",
                    authorization_status="DENIED",
                    risk_score=rem_contract.risk_score,
                    blast_radius_nodes=rem_contract.blast_radius.get("max_affected_nodes", 1),
                    violations=violations,
                    contract=rem_contract
                )
                evaluations.append(res)
                continue

            # 3. Deterministic Score Calculation (Only for PASS_SAFETY candidates)
            score = self.score_calc.calculate_score(
                rem_contract,
                causal_fit=prop.get("causal_fit", 0.90),
                evidence_support=prop.get("evidence_support", 0.85),
                historical_success=prop.get("historical_success", 0.90),
                counterfactual_delta=prop.get("counterfactual_delta", 0.80)
            )

            res = CandidateEvaluationResult(
                candidate_id=cand_id,
                action_id=action_contract.action_id,
                candidate_status="REGISTERED",
                safety_status="PASS_SAFETY",
                scoring_status="SCORED",
                ranking_status="RANKED_ALTERNATIVE",
                authorization_status="AWAITING_HITL",
                score=score,
                risk_score=rem_contract.risk_score,
                blast_radius_nodes=rem_contract.blast_radius.get("max_affected_nodes", 1),
                contract=rem_contract
            )
            evaluations.append(res)

        # Filter candidates that passed safety
        eligible_candidates = [e for e in evaluations if e.safety_status == "PASS_SAFETY"]

        # If zero candidates passed safety -> NO_SAFE_REMEDIATION disposition
        if not eligible_candidates:
            logger.warning(f"[NO SAFE REMEDIATION] 0/{len(proposals)} candidates passed Hard Safety Gate for Incident '{incident_id}'.")
            return {
                "status": "NO_SAFE_REMEDIATION",
                "disposition": "NO_SAFE_REMEDIATION",
                "recommended_option": None,
                "evaluations": [dataclasses.asdict(e) for e in evaluations],
                "action_required": "MANUAL_INVESTIGATION_REQUIRED"
            }

        # 4. Deterministic Tie-Breaker Ranking Hierarchy:
        # 1) Highest Score -> 2) Lowest Risk Score -> 3) Smallest Blast Radius -> 4) Lexicographical ACTION_ID
        sorted_candidates = sorted(
            eligible_candidates,
            key=lambda e: (-e.score, e.risk_score, e.blast_radius_nodes, e.action_id)
        )

        top_cand = sorted_candidates[0]
        top_cand.ranking_status = "RECOMMENDED"

        logger.info(f"🏆 [RECOMMENDED OPTION] Winner: Candidate '{top_cand.candidate_id}' ({top_cand.action_id}) Score: {top_cand.score} (Risk: {top_cand.risk_score})")

        return {
            "status": "CONFIRMED_REMEDIATION_READY",
            "disposition": "CONFIRMED_REMEDIATION_READY",
            "recommended_option": dataclasses.asdict(top_cand),
            "ranked_options": [dataclasses.asdict(e) for e in sorted_candidates],
            "all_evaluations": [dataclasses.asdict(e) for e in evaluations],
            "authorization_status": "AWAITING_HITL"
        }
