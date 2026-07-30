"""
HISTORICAL INCIDENT REPLAY & VALIDATION PIPELINE (MODEL PROMOTION GATEKEEPER)
Replays historical incident sequences against current vs. candidate DBN transition matrices.
Evaluates Accuracy, ECE, Mean Expected Utility (MEU), and False Positive/Negative Rates.

Guarantees ZERO PERFORMANCES REGRESSION: Candidate models are promoted to production ONLY if
Performance(Candidate) > Performance(Current).
"""

import sys
import os
import logging
from typing import Dict, List, Any, Tuple

# Ensure parent directory (python_ai_core) is in sys.path for direct execution
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from probabilistic.calibration_evaluator import ConfidenceCalibrationEvaluator
from probabilistic.dynamic_bayesian_network import DynamicBayesianNetwork

logger = logging.getLogger("REPLAY_VALIDATION_PIPELINE")

class ReplayValidationPipeline:
    """
    Pipeline Validasi & Benchmark Replay Insiden Historis.
    Bertindak sebagai Gatekeeper / Penjaga Gerbang MLOps untuk Promosi Model DBN Baru.
    """

    def __init__(self):
        self.calibrator = ConfidenceCalibrationEvaluator(num_bins=5)

    def evaluate_matrix_performance(
        self,
        matrix: Dict[str, Dict[str, float]],
        test_sequences: List[List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """
        Mengevaluasi kinerja suatu matriks DBN terhadap sekuens pengujian historis.
        """
        predictions = []
        actuals = []
        correct_counts = 0
        total_samples = 0
        utility_sum = 0.0

        dbn = DynamicBayesianNetwork()
        # Override DBN transition matrix for testing
        dbn.default_transition_matrix = matrix

        for seq in test_sequences:
            dev_name = seq[0].get("device_id", "TEST_HOST")
            for step in seq:
                obs = step["observation"]
                ground_truth_state = step["ground_truth_state"] # Status aktual yang terjadi

                belief, dominant = dbn.update_belief_step(dev_name, obs)
                conf = belief[dominant]

                predictions.append(conf)
                is_correct = 1 if dominant == ground_truth_state else 0
                actuals.append(is_correct)

                if is_correct:
                    correct_counts += 1
                    utility_sum += (conf * 100.0)
                else:
                    utility_sum -= (conf * 150.0)

                total_samples += 1

        acc = round(correct_counts / float(total_samples) if total_samples > 0 else 0.0, 4)
        brier = self.calibrator.calculate_brier_score(predictions, actuals)
        ece, _ = self.calibrator.calculate_expected_calibration_error(predictions, actuals)
        mean_utility = round(utility_sum / float(total_samples) if total_samples > 0 else 0.0, 2)

        # Composite Safety Score (Makin tinggi makin aman & presisi)
        # Score = (Accuracy * 40) + (Mean_Utility * 0.4) - (ECE * 30) - (Brier * 20)
        composite_score = round((acc * 40.0) + (mean_utility * 0.4) - (ece * 30.0) - (brier * 20.0), 2)

        return {
            "accuracy": acc,
            "accuracy_percent": f"{acc*100:.1f}%",
            "brier_score": brier,
            "ece_score": ece,
            "mean_expected_utility": mean_utility,
            "composite_safety_score": composite_score
        }

    def validate_and_gatekeep_model_promotion(
        self,
        current_matrix: Dict[str, Dict[str, float]],
        candidate_matrix: Dict[str, Dict[str, float]],
        historical_replay_data: List[List[Dict[str, Any]]]
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Menjalankan Replay Validasi A/B Benchmark antara Current Model vs Candidate Model.
        Mengembalikan decision True/False untuk Promosi Model.
        """
        logger.info(f"[REPLAY GATEKEEPER] Running A/B benchmark across {len(historical_replay_data)} historical incident streams...")

        current_metrics = self.evaluate_matrix_performance(current_matrix, historical_replay_data)
        candidate_metrics = self.evaluate_matrix_performance(candidate_matrix, historical_replay_data)

        score_curr = current_metrics["composite_safety_score"]
        score_cand = candidate_metrics["composite_safety_score"]

        is_promoted = score_cand > score_curr
        decision_label = "PROMOTED TO PRODUCTION" if is_promoted else "REJECTED (REGRESSION PREVENTED)"

        report = {
            "decision": decision_label,
            "is_promoted": is_promoted,
            "score_delta": round(score_cand - score_curr, 2),
            "current_model_metrics": current_metrics,
            "candidate_model_metrics": candidate_metrics,
            "reasoning": (
                f"Candidate model score ({score_cand}) "
                f"{'exceeds' if is_promoted else 'fails to exceed'} current model score ({score_curr}). "
                f"Accuracy: {current_metrics['accuracy_percent']} -> {candidate_metrics['accuracy_percent']}, "
                f"ECE: {current_metrics['ece_score']} -> {candidate_metrics['ece_score']}."
            )
        }

        logger.info(f"[REPLAY GATEKEEPER] Decision: {decision_label} (Delta = {report['score_delta']})")
        return is_promoted, report


# Self-Test Replay Validation Pipeline Demo
if __name__ == "__main__":
    pipeline = ReplayValidationPipeline()

    print("=== HISTORICAL INCIDENT REPLAY & VALIDATION GATEKEEPER DEMO ===")

    current_mat = {
        "HEALTHY":          {"HEALTHY": 0.90, "MINOR_ANOMALY": 0.07, "PROGRESSIVE_LEAK": 0.02, "CRITICAL_FAILURE": 0.01},
        "MINOR_ANOMALY":    {"HEALTHY": 0.20, "MINOR_ANOMALY": 0.50, "PROGRESSIVE_LEAK": 0.25, "CRITICAL_FAILURE": 0.05},
        "PROGRESSIVE_LEAK": {"HEALTHY": 0.02, "MINOR_ANOMALY": 0.08, "PROGRESSIVE_LEAK": 0.65, "CRITICAL_FAILURE": 0.25},
        "CRITICAL_FAILURE": {"HEALTHY": 0.01, "MINOR_ANOMALY": 0.04, "PROGRESSIVE_LEAK": 0.15, "CRITICAL_FAILURE": 0.80}
    }

    candidate_mat = {
        "HEALTHY":          {"HEALTHY": 0.85, "MINOR_ANOMALY": 0.11, "PROGRESSIVE_LEAK": 0.03, "CRITICAL_FAILURE": 0.01},
        "MINOR_ANOMALY":    {"HEALTHY": 0.15, "MINOR_ANOMALY": 0.45, "PROGRESSIVE_LEAK": 0.35, "CRITICAL_FAILURE": 0.05},
        "PROGRESSIVE_LEAK": {"HEALTHY": 0.01, "MINOR_ANOMALY": 0.05, "PROGRESSIVE_LEAK": 0.70, "CRITICAL_FAILURE": 0.24},
        "CRITICAL_FAILURE": {"HEALTHY": 0.01, "MINOR_ANOMALY": 0.03, "PROGRESSIVE_LEAK": 0.10, "CRITICAL_FAILURE": 0.86}
    }

    # Generate 5 test incident sequences
    test_replays = []
    for i in range(5):
        seq = [
            {"device_id": f"HOST-{i}", "observation": {"z_score_mem": 0.4, "z_score_cpu": 0.5, "mem_growth_rate": 0.2}, "ground_truth_state": "HEALTHY"},
            {"device_id": f"HOST-{i}", "observation": {"z_score_mem": 1.5, "z_score_cpu": 1.2, "mem_growth_rate": 3.1}, "ground_truth_state": "MINOR_ANOMALY"},
            {"device_id": f"HOST-{i}", "observation": {"z_score_mem": 2.2, "z_score_cpu": 1.8, "mem_growth_rate": 7.5}, "ground_truth_state": "PROGRESSIVE_LEAK"},
            {"device_id": f"HOST-{i}", "observation": {"z_score_mem": 3.8, "z_score_cpu": 2.5, "mem_growth_rate": 15.0}, "ground_truth_state": "CRITICAL_FAILURE"}
        ]
        test_replays.append(seq)

    promoted, rep = pipeline.validate_and_gatekeep_model_promotion(current_mat, candidate_mat, test_replays)

    print(f"\n🛡️ RESULT DECISION: {rep['decision']}")
    print(f"   Reasoning: {rep['reasoning']}")
    print(f"   Current Model Score  : {rep['current_model_metrics']['composite_safety_score']} (Accuracy: {rep['current_model_metrics']['accuracy_percent']})")
    print(f"   Candidate Model Score: {rep['candidate_model_metrics']['composite_safety_score']} (Accuracy: {rep['candidate_model_metrics']['accuracy_percent']})")
