"""
Phase 3: Prompt A/B Testing Framework.

Compares outputs from different prompt versions (e.g., v1.2 vs v2.0)
across identical incident inputs to evaluate quality improvements and select optimal templates.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from adapters.output_synthesizer import OutputAdapterFacade, SynthesizerConfig, MockOutputSynthesizer
from evaluation.golden_dataset_evaluator import GoldenDatasetEvaluator

logger = logging.getLogger("PromptABTester")


@dataclass
class ABTestResult:
    """Result of an A/B prompt test comparison."""
    prompt_version_a: str
    prompt_version_b: str
    score_a: float
    score_b: float
    winning_version: str
    improvement_percent: float
    details_a: Dict[str, Any]
    details_b: Dict[str, Any]


class PromptABTester:
    """Automated A/B Testing Engine for Prompt Versions."""

    def __init__(self, evaluator: Optional[GoldenDatasetEvaluator] = None):
        self.evaluator = evaluator or GoldenDatasetEvaluator()

    def compare_prompts(self, version_a: str = "v1.2", version_b: str = "v2.0") -> ABTestResult:
        """Executes golden benchmark for Version A vs Version B and compares scores."""
        # 1. Config A
        cfg_a = SynthesizerConfig(prompt_version=version_a)
        facade_a = OutputAdapterFacade(config=cfg_a, synthesizer=MockOutputSynthesizer(cfg_a))
        res_a = self.evaluator.run_full_benchmark(facade_a)

        # 2. Config B
        cfg_b = SynthesizerConfig(prompt_version=version_b)
        facade_b = OutputAdapterFacade(config=cfg_b, synthesizer=MockOutputSynthesizer(cfg_b))
        res_b = self.evaluator.run_full_benchmark(facade_b)

        score_a = res_a.get("average_quality_score", 0.0)
        score_b = res_b.get("average_quality_score", 0.0)

        winning_version = version_a if score_a >= score_b else version_b
        diff = abs(score_b - score_a)
        base = max(0.1, score_a)
        improvement_percent = round((diff / base) * 100.0, 2)

        logger.info(f"[PromptABTester] Comparison Complete: {version_a} ({score_a}) vs {version_b} ({score_b}). Winner: {winning_version}")

        return ABTestResult(
            prompt_version_a=version_a,
            prompt_version_b=version_b,
            score_a=score_a,
            score_b=score_b,
            winning_version=winning_version,
            improvement_percent=improvement_percent,
            details_a=res_a,
            details_b=res_b
        )
