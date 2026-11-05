"""
Feature Extractor Module
Extracts time-series statistical anomaly features from multi-modal metric payloads.
"""

from typing import Dict, List, Any
import math


class FeatureExtractor:
    @staticmethod
    def extract_features(values: List[float]) -> Dict[str, float]:
        if not values:
            return {"mean": 0.0, "std_dev": 0.0, "max": 0.0, "min": 0.0, "spike_index": 0.0}

        n = len(values)
        mean_val = sum(values) / n
        variance = sum((x - mean_val) ** 2 for x in values) / n if n > 1 else 0.0
        std_dev = math.sqrt(variance)

        max_val = max(values)
        min_val = min(values)
        spike_index = round((max_val - mean_val) / (std_dev + 1e-6), 2)

        return {
            "mean": round(mean_val, 2),
            "std_dev": round(std_dev, 2),
            "max": round(max_val, 2),
            "min": round(min_val, 2),
            "spike_index": spike_index
        }
