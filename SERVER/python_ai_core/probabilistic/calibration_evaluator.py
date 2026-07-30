"""
PROBABILISTIC CONFIDENCE CALIBRATION EVALUATOR
Calculates Brier Score, Expected Calibration Error (ECE), and Reliability Diagram Data Points
to guarantee that AI confidence scores (e.g. 85%) empirically match true production accuracy (85%).
"""

import math
import logging
from typing import Dict, List, Any, Tuple

logger = logging.getLogger("CALIBRATION_EVALUATOR")

class ConfidenceCalibrationEvaluator:
    """
    Evaluator Kalibrasi Probabilitas Terpisah untuk AIOps Enterprise.
    Menghitung Brier Score dan Expected Calibration Error (ECE) dari riwayat prediksi vs realita (RLHF).
    """

    def __init__(self, num_bins: int = 10):
        self.num_bins = num_bins

    def calculate_brier_score(self, predictions: List[float], actual_outcomes: List[int]) -> float:
        """
        Menhitung Brier Score:
        BS = (1/N) * Σ (p_i - y_i)^2
        Makin mendekati 0.00 = Kalibrasi makin sempurna! (BS <= 0.05 = Excellent)
        """
        if not predictions or len(predictions) != len(actual_outcomes):
            return 1.0

        n = len(predictions)
        squared_errors = [(p - y) ** 2 for p, y in zip(predictions, actual_outcomes)]
        brier_score = sum(squared_errors) / float(n)
        return round(brier_score, 4)

    def calculate_expected_calibration_error(
        self,
        predictions: List[float],
        actual_outcomes: List[int]
    ) -> Tuple[float, List[Dict[str, Any]]]:
        """
        Menhitung Expected Calibration Error (ECE):
        ECE = Σ (|B_b| / N) * | acc(B_b) - conf(B_b) |
        
        Juga mengembalikan Reliability Diagram Data Points per bin.
        """
        if not predictions or len(predictions) != len(actual_outcomes):
            return 1.0, []

        n = len(predictions)
        bin_boundaries = [i / float(self.num_bins) for i in range(self.num_bins + 1)]
        reliability_diagram_bins = []
        total_ece = 0.0

        for b in range(self.num_bins):
            bin_lower = bin_boundaries[b]
            bin_upper = bin_boundaries[b + 1]

            # Kumpulkan sampel dalam bin [lower, upper)
            bin_preds = []
            bin_actuals = []

            for p, y in zip(predictions, actual_outcomes):
                if b == self.num_bins - 1:
                    in_bin = bin_lower <= p <= bin_upper
                else:
                    in_bin = bin_lower <= p < bin_upper

                if in_bin:
                    bin_preds.append(p)
                    bin_actuals.append(y)

            bin_size = len(bin_preds)
            if bin_size > 0:
                avg_confidence = sum(bin_preds) / float(bin_size)
                avg_accuracy = sum(bin_actuals) / float(bin_size)
                calibration_gap = abs(avg_accuracy - avg_confidence)
                total_ece += (bin_size / float(n)) * calibration_gap
            else:
                avg_confidence = (bin_lower + bin_upper) / 2.0
                avg_accuracy = 0.0
                calibration_gap = 0.0

            reliability_diagram_bins.append({
                "bin_index": b + 1,
                "confidence_range": f"[{bin_lower:.1f} - {bin_upper:.1f}]",
                "sample_count": bin_size,
                "average_confidence": round(avg_confidence, 4),
                "average_accuracy": round(avg_accuracy, 4),
                "calibration_gap": round(calibration_gap, 4)
            })

        ece_score = round(total_ece, 4)
        logger.info(f"[CALIBRATION EVALUATOR] ECE = {ece_score:.4f} ({ece_score*100:.2f}%) across {n} samples.")
        return ece_score, reliability_diagram_bins


# Self-Test Demo Calibration Evaluator
if __name__ == "__main__":
    evaluator = ConfidenceCalibrationEvaluator(num_bins=5)

    print("=== CONFIDENCE CALIBRATION EVALUATOR DEMO (ECE & BRIER SCORE) ===")
    
    # Dataset Prediksi AI vs Keputusan Operator Manusia (1=Approve/Correct, 0=Reject/Wrong)
    test_preds   = [0.85, 0.92, 0.78, 0.65, 0.95, 0.45, 0.88, 0.72, 0.90, 0.82]
    test_actuals = [1,    1,    1,    0,    1,    0,    1,    1,    1,    0   ]

    bs = evaluator.calculate_brier_score(test_preds, test_actuals)
    ece, diagram_bins = evaluator.calculate_expected_calibration_error(test_preds, test_actuals)

    print(f"📊 Brier Score: {bs} (Target <= 0.15)")
    print(f"📊 Expected Calibration Error (ECE): {ece} ({ece*100:.2f}%)\n")
    print(f"{'Bin':<5} | {'Range':<15} | {'Samples':<8} | {'Avg Confidence':<15} | {'Avg Accuracy':<15} | {'Gap':<8}")
    print("-" * 75)
    for b in diagram_bins:
        print(f"{b['bin_index']:<5} | {b['confidence_range']:<15} | {b['sample_count']:<8} | {b['average_confidence']*100:<14.1f}% | {b['average_accuracy']*100:<14.1f}% | {b['calibration_gap']:<8}")
