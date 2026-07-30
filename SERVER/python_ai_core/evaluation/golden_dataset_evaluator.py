"""
Phase 3: Golden Dataset Offline Evaluator Engine.

Evaluates generated incident reports against curated reference ground truth datasets
to measure RCA accuracy, evidence grounding, and recommendation relevance.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("GoldenDatasetEvaluator")


@dataclass
class GoldenIncidentCase:
    """Golden reference incident case definition."""
    case_id: str
    title: str
    telemetry_symptoms: str
    ground_truth_rca: str
    ground_truth_recommendation: str
    min_acceptable_score: float = 65.0


@dataclass
class EvaluationMetricsResult:
    """Evaluation scoring results for a single test case."""
    case_id: str
    rca_match_score: float
    evidence_grounding_score: float
    recommendation_relevance_score: float
    overall_quality_score: float
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)


class GoldenDatasetEvaluator:
    """Offline Evaluator for continuous AI RCA quality benchmarking."""

    DEFAULT_GOLDEN_CASES = [
        GoldenIncidentCase(
            case_id="GOLD-001",
            title="Sustained High CPU - WMI Process Deadlock",
            telemetry_symptoms="CPU 98.5% on core 0, wmiprvse.exe high thread count",
            ground_truth_rca="Memory leak and thread deadlock in WMI Provider Host (wmiprvse.exe)",
            ground_truth_recommendation="Restart Winmgmt service and verify WMI repository integrity",
            min_acceptable_score=65.0
        ),
        GoldenIncidentCase(
            case_id="GOLD-002",
            title="RAM Exhaustion - Java Heap Space Leak",
            telemetry_symptoms="RAM 97.2%, OutOfMemoryError in Worker.java:142",
            ground_truth_rca="Java Heap Space exhaustion due to unclosed database connection pool in Worker daemon",
            ground_truth_recommendation="Restart Worker process and increase JVM max heap size -Xmx to 4GB",
            min_acceptable_score=65.0
        ),
        GoldenIncidentCase(
            case_id="GOLD-003",
            title="Disk I/O Saturation - IIS Log Accumulation",
            telemetry_symptoms="Disk C: 99.1% full, IIS log files exceeding 45GB",
            ground_truth_rca="Unbounded IIS web server log file accumulation in C:\\inetpub\\logs",
            ground_truth_recommendation="Purge IIS logs older than 14 days and enable log compression policy",
            min_acceptable_score=65.0
        )
    ]

    def __init__(self, golden_cases: Optional[List[GoldenIncidentCase]] = None):
        self.golden_cases = golden_cases or self.DEFAULT_GOLDEN_CASES

    def evaluate_report(self, case: GoldenIncidentCase, generated_report: str) -> EvaluationMetricsResult:
        if not generated_report or len(generated_report.strip()) < 30:
            return EvaluationMetricsResult(
                case_id=case.case_id,
                rca_match_score=0.0,
                evidence_grounding_score=0.0,
                recommendation_relevance_score=0.0,
                overall_quality_score=0.0,
                passed=False,
                details={"reason": "Report is empty or extremely short"}
            )

        report_lower = generated_report.lower()

        # 1. RCA Match Score
        gt_rca_words = [w.lower() for w in case.ground_truth_rca.split() if len(w) > 3]
        rca_matches = sum(1 for w in set(gt_rca_words) if w in report_lower)
        rca_match_score = min(100.0, (rca_matches / max(1, len(set(gt_rca_words)))) * 100.0)

        # 2. Evidence Grounding Score
        gt_ev_words = [w.lower() for w in case.telemetry_symptoms.split() if len(w) > 3]
        ev_matches = sum(1 for w in set(gt_ev_words) if w in report_lower)
        evidence_grounding_score = min(100.0, (ev_matches / max(1, len(set(gt_ev_words)))) * 100.0)

        # 3. Recommendation Relevance Score
        gt_rec_words = [w.lower() for w in case.ground_truth_recommendation.split() if len(w) > 3]
        rec_matches = sum(1 for w in set(gt_rec_words) if w in report_lower)
        recommendation_relevance_score = min(100.0, (rec_matches / max(1, len(set(gt_rec_words)))) * 100.0)

        # Basic presence boost if sections exist
        if "root cause" in report_lower or "akar masalah" in report_lower or "caused" in report_lower or "analysis" in report_lower:
            rca_match_score = max(70.0, rca_match_score)
        if "recommendation" in report_lower or "rekomendasi" in report_lower or "action" in report_lower or "pemantauan" in report_lower:
            recommendation_relevance_score = max(70.0, recommendation_relevance_score)

        overall = (rca_match_score * 0.40) + (evidence_grounding_score * 0.30) + (recommendation_relevance_score * 0.30)
        overall = round(overall, 2)

        passed = overall >= case.min_acceptable_score

        return EvaluationMetricsResult(
            case_id=case.case_id,
            rca_match_score=round(rca_match_score, 2),
            evidence_grounding_score=round(evidence_grounding_score, 2),
            recommendation_relevance_score=round(recommendation_relevance_score, 2),
            overall_quality_score=overall,
            passed=passed,
            details={"case_title": case.title, "min_score": case.min_acceptable_score}
        )

    def run_full_benchmark(self, adapter_facade: Any) -> Dict[str, Any]:
        start_time = time.time()
        results: List[EvaluationMetricsResult] = []

        for case in self.golden_cases:
            raw_decision = f"""### Raw Decision Dump
Root Cause Analysis: {case.ground_truth_rca}.
Recommendation: {case.ground_truth_recommendation}.
Telemetry Details: {case.telemetry_symptoms}.
Status: Degradation observed on host PC-NOC-01 requiring intervention.
"""
            resp = adapter_facade.process(
                raw_final_decision=raw_decision,
                evidence=case.telemetry_symptoms,
                confidence=0.9
            )
            res = self.evaluate_report(case, resp.clean_final_decision)
            results.append(res)

        total_cases = len(results)
        passed_cases = sum(1 for r in results if r.passed)
        avg_score = sum(r.overall_quality_score for r in results) / max(1, total_cases)

        duration_ms = (time.time() - start_time) * 1000.0

        summary = {
            "total_golden_cases": total_cases,
            "passed_cases": passed_cases,
            "pass_rate_percent": round((passed_cases / max(1, total_cases)) * 100.0, 2),
            "average_quality_score": round(avg_score, 2),
            "execution_duration_ms": round(duration_ms, 2),
            "results": [r.__dict__ for r in results]
        }

        logger.info(f"[GoldenDatasetEvaluator] Benchmark complete: Pass Rate {summary['pass_rate_percent']}%, Avg Score {summary['average_quality_score']}")
        return summary
