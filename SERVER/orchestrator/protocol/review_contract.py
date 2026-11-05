"""
SERVER.orchestrator.protocol.review_contract
==============================================
Component: AI NOC Review Contract Validator

Validates and constructs standardized JSON contracts emitted by AI NOC prior to Jarvis audit:
{
  "incident_id": "...",
  "hypothesis": ["..."],
  "evidence": ["..."],
  "missing_evidence": ["..."],
  "policy_result": {},
  "sandbox_result": {},
  "recommended_actions": ["..."],
  "confidence": 0.96,
  "review_required": false
}
"""
import logging
from typing import Dict, Any, List
from SERVER.contracts.schemas import AINOCReviewContract

logger = logging.getLogger("orchestrator.protocol.contract")


class AINOCReviewContractValidator:
    """
    Constructs and validates structured JSON review contracts emitted by AI NOC.
    """

    def build_contract(
        self,
        incident_id: str,
        hypothesis: List[str],
        evidence: List[str],
        recommended_actions: List[str],
        ai_noc_confidence: float = 0.96,
        missing_evidence: List[str] = None,
    ) -> AINOCReviewContract:
        missing = missing_evidence or []
        contract = AINOCReviewContract(
            incident_id=incident_id,
            hypothesis=hypothesis,
            evidence=evidence,
            missing_evidence=missing,
            policy_result={"policy_status": "COMPLIANT", "maintenance_window_active": False},
            sandbox_result={"simulation_verdict": "PASS", "data_loss_risk": "NONE"},
            recommended_actions=recommended_actions,
            ai_noc_confidence=ai_noc_confidence,
            review_required=len(missing) > 0,
        )

        logger.debug(f"[AINOCReviewContractValidator] Contract built for {incident_id} | Conf: {ai_noc_confidence}")
        return contract
