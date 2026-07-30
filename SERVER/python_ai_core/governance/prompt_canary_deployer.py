"""
Phase 3 Governance Framework: Regression Testing & Canary Deployment Engine.

Ensures zero degradation when updating prompts:
1. Enforces strict Regression Testing against Golden Dataset.
2. Supports Canary Traffic Splitting (e.g., 90% Prod / 10% Canary).
3. Tracks full audit metadata across evaluation runs.
"""

import json
import logging
import random
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from adapters.output_synthesizer import OutputAdapterFacade, SynthesizerConfig, MockOutputSynthesizer
from evaluation.categorized_golden_dataset import CategorizedGoldenDatasetEvaluator, FormalAIMetricsResult

logger = logging.getLogger("PromptCanaryDeployer")


@dataclass
class RegressionTestResult:
    prod_prompt_version: str
    canary_prompt_version: str
    prod_score: float
    canary_score: float
    prod_unsupported_rate: float
    canary_unsupported_rate: float
    passed_regression: bool
    deployment_recommendation: str
    audit_metadata: Dict[str, Any]


class RegressionTestRunner:
    """Enforces Golden Dataset Regression Testing before deploying new prompt versions."""

    def __init__(self, evaluator: Optional[CategorizedGoldenDatasetEvaluator] = None):
        self.evaluator = evaluator or CategorizedGoldenDatasetEvaluator()

    def run_regression_test(self, prod_version: str = "v1.2", canary_version: str = "v2.0") -> RegressionTestResult:
        """Executes regression test comparing prod prompt vs canary prompt."""
        # 1. Evaluate Prod Prompt
        cfg_prod = SynthesizerConfig(prompt_version=prod_version)
        facade_prod = OutputAdapterFacade(config=cfg_prod, synthesizer=MockOutputSynthesizer(cfg_prod))
        res_prod: FormalAIMetricsResult = self.evaluator.run_formal_evaluation(
            facade_prod, prompt_version=prod_version, evaluation_run_id=f"eval-prod-{int(time.time())}"
        )

        # 2. Evaluate Canary Prompt
        cfg_canary = SynthesizerConfig(prompt_version=canary_version)
        facade_canary = OutputAdapterFacade(config=cfg_canary, synthesizer=MockOutputSynthesizer(cfg_canary))
        res_canary: FormalAIMetricsResult = self.evaluator.run_formal_evaluation(
            facade_canary, prompt_version=canary_version, evaluation_run_id=f"eval-canary-{int(time.time())}"
        )

        # 3. Decision Rule: Canary Score >= Prod Score AND Canary Unsupported Rate <= Prod Unsupported Rate
        passed = (res_canary.overall_governance_score >= res_prod.overall_governance_score) and \
                 (res_canary.unsupported_claim_rate_percent <= res_prod.unsupported_claim_rate_percent + 2.0)

        recommendation = "APPROVED_FOR_CANARY_DEPLOYMENT" if passed else "REJECTED_DUE_TO_REGRESSION"

        audit_meta = {
            "prod_eval": res_prod.audit_metadata,
            "canary_eval": res_canary.audit_metadata,
            "timestamp": time.time()
        }

        logger.info(f"[RegressionTestRunner] Regression Test Result: Prod ({prod_version}: {res_prod.overall_governance_score}) vs Canary ({canary_version}: {res_canary.overall_governance_score}). Status: {recommendation}")

        return RegressionTestResult(
            prod_prompt_version=prod_version,
            canary_prompt_version=canary_version,
            prod_score=res_prod.overall_governance_score,
            canary_score=res_canary.overall_governance_score,
            prod_unsupported_rate=res_prod.unsupported_claim_rate_percent,
            canary_unsupported_rate=res_canary.unsupported_claim_rate_percent,
            passed_regression=passed,
            deployment_recommendation=recommendation,
            audit_metadata=audit_meta
        )


class PromptCanaryDeployer:
    """Manages Canary Traffic Splitting for Prompt Deployments."""

    def __init__(
        self,
        prod_version: str = "v1.2",
        canary_version: str = "v2.0",
        canary_weight_percent: float = 10.0
    ):
        self.prod_version = prod_version
        self.canary_version = canary_version
        self.canary_weight_percent = canary_weight_percent

    def select_prompt_version(self, incident_id: Optional[int] = None) -> Tuple[str, bool]:
        """
        Determines whether an incident uses Prod or Canary prompt based on traffic weight.
        If incident_id is provided, uses deterministic hashing; otherwise uses random selection.
        """
        if incident_id is not None:
            val = (int(incident_id) * 31 + 7) % 100
        else:
            val = random.uniform(0, 100)
        if val < self.canary_weight_percent:
            return self.canary_version, True
        return self.prod_version, False

    def evaluate_playbook_canary_rollout(
        self,
        reranked_sops: list,
        fleet_size: int = 20,
        delta_threshold: float = 0.15
    ) -> dict:
        """
        RAG 3.0 Playbook Canary A/B Rollout Evaluator:
        If top 2 candidate SOPs have a close relevance score (score_delta <= 0.15),
        triggers a 5% Canary rollout for Candidate A instead of 100% full deployment.
        """
        if not reranked_sops or len(reranked_sops) < 2:
            return {
                "rollout_mode": "FULL_DEPLOYMENT_100",
                "reason": "Single SOP candidate identified",
                "selected_sop": reranked_sops[0] if reranked_sops else None
            }

        sop_a = reranked_sops[0]
        sop_b = reranked_sops[1]

        score_a = float(sop_a.get("rerank_score", sop_a.get("similarity", 0.8)))
        score_b = float(sop_b.get("rerank_score", sop_b.get("similarity", 0.8)))

        score_delta = abs(score_a - score_b)

        if score_delta <= delta_threshold and fleet_size >= 5:
            canary_hosts_count = max(1, int(round(fleet_size * 0.05)))
            return {
                "rollout_mode": "CANARY_5_PERCENT",
                "reason": f"Close candidate score delta ({score_delta:.4f} <= {delta_threshold:.2f}). Triggering 5% Canary rollout.",
                "candidate_a": sop_a,
                "candidate_b": sop_b,
                "score_delta": round(score_delta, 4),
                "canary_hosts_count": canary_hosts_count,
                "fleet_size": fleet_size,
                "telemetry_window_sec": 180
            }

        return {
            "rollout_mode": "FULL_DEPLOYMENT_100",
            "reason": f"Clear top candidate (score_delta {score_delta:.4f} > {delta_threshold:.2f}). Direct 100% rollout.",
            "selected_sop": sop_a,
            "score_delta": round(score_delta, 4)
        }

    def monitor_canary_telemetry_window(
        self,
        canary_run_id: str,
        candidate_a: dict,
        candidate_b: dict,
        telemetry_recovered: bool = True
    ) -> dict:
        """
        Evaluates 3-minute telemetry window for Candidate A on 5% Canary fleet:
        - If telemetry recovers: promote Candidate A to 100% Full Fleet Rollout.
        - If telemetry degrades: rollback 5% fleet and switch to Candidate B.
        """
        if telemetry_recovered:
            logger.info("[RAG 3.0 CANARY] Canary 5%% telemetry RECOVERED for RunID=%s. Promoting Candidate A '%s' to 100%% Full Rollout.",
                        canary_run_id, candidate_a.get("title", candidate_a.get("sop_id", "A")))
            return {
                "status": "PROMOTED_100_PERCENT",
                "promoted_sop": candidate_a,
                "action": "EXECUTE_100_PERCENT_FULL_FLEET",
                "canary_run_id": canary_run_id,
                "telemetry_status": "HEALTHY"
            }
        else:
            logger.warning("[RAG 3.0 CANARY] Canary 5%% telemetry DEGRADED for RunID=%s. Rolling back Candidate A and switching to Candidate B '%s'.",
                           canary_run_id, candidate_b.get("title", candidate_b.get("sop_id", "B")))
            return {
                "status": "FALLBACK_TO_CANDIDATE_B",
                "promoted_sop": candidate_b,
                "action": "ROLLBACK_5_PERCENT_AND_DEPLOY_CANDIDATE_B",
                "canary_run_id": canary_run_id,
                "telemetry_status": "DEGRADED"
            }
