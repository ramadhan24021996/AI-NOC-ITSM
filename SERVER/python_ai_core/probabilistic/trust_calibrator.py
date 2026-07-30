"""
Layer 4 AI Core — Model Trust Calibration Engine (L4_TrustCalibrator)
Tracks (Predicted_Confidence, Actual_Outcome) and computes Expected Calibration Error (ECE) real-time.
Triggers calibration alerts to SRA if ECE > 0.15 (AI Overconfident / Underconfident).
"""

import math
import logging
import json
import time
from typing import Dict, List, Any, Tuple

logger = logging.getLogger("TRUST_CALIBRATOR")

class TrustCalibratorEngine:
    def __init__(self, num_bins: int = 10, ece_threshold: float = 0.15):
        self.num_bins = num_bins
        self.ece_threshold = ece_threshold
        self.history: List[Tuple[float, bool]] = [] # (confidence, is_correct)

    def record_prediction_outcome(self, confidence: float, is_correct: bool):
        """Records a (confidence, outcome) pair to history."""
        self.history.append((max(0.0, min(1.0, float(confidence))), bool(is_correct)))
        if len(self.history) > 1000:
            self.history = self.history[-1000:] # Keep last 1000 records

    def compute_expected_calibration_error(self) -> Dict[str, Any]:
        """
        Calculates Expected Calibration Error (ECE):
        ECE = sum( (|Bin_b| / N) * |acc(Bin_b) - conf(Bin_b)| )
        If ECE > 0.15 -> Alerts SRA & recommends Platt Scaling recalibration.
        """
        if len(self.history) < 5:
            return {"ece_score": 0.0, "total_samples": len(self.history), "status": "INSUFFICIENT_SAMPLES"}

        bin_boundaries = [i / self.num_bins for i in range(self.num_bins + 1)]
        total_samples = len(self.history)
        ece = 0.0

        bin_details = []
        for i in range(self.num_bins):
            bin_lower = bin_boundaries[i]
            bin_upper = bin_boundaries[i + 1]

            bin_samples = [item for item in self.history if bin_lower <= item[0] < bin_upper or (i == self.num_bins - 1 and item[0] == bin_upper)]
            bin_size = len(bin_samples)

            if bin_size > 0:
                avg_confidence = sum(item[0] for item in bin_samples) / bin_size
                avg_accuracy = sum(1.0 for item in bin_samples if item[1]) / bin_size
                bin_error = abs(avg_accuracy - avg_confidence)
                ece += (bin_size / total_samples) * bin_error

                bin_details.append({
                    "bin_range": f"{bin_lower:.1f}-{bin_upper:.1f}",
                    "size": bin_size,
                    "avg_confidence": round(avg_confidence, 4),
                    "avg_accuracy": round(avg_accuracy, 4),
                    "error": round(bin_error, 4)
                })

        ece_score = round(float(ece), 4)
        is_breached = ece_score > self.ece_threshold

        result = {
            "ece_score": ece_score,
            "threshold": self.ece_threshold,
            "total_samples": total_samples,
            "is_calibration_breached": is_breached,
            "status": "HIGH_CALIBRATION_ERROR_ECE_BREACH" if is_breached else "WELL_CALIBRATED",
            "recommendation": "Recalibrate Platt Scaling & Adjust Entropy Threshold" if is_breached else "Model confidence remains well-calibrated",
            "bin_details": bin_details,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }

        if is_breached:
            logger.warning(f"[TRUST_CALIBRATOR] ECE CALIBRATION BREACH DETECTED! ECE = {ece_score:.4f} > {self.ece_threshold}. Recalibration required!")
        else:
            logger.info(f"[TRUST_CALIBRATOR] ECE = {ece_score:.4f} (Well-Calibrated across {total_samples} samples).")

        return result

# Global instance
trust_calibrator_engine = TrustCalibratorEngine()
