"""
Layer 4 AI Core — Symptom Clustering & Novelty Detection Engine (L4_SymptomClusterEngine)
Uses Cosine Density Distance & Feature Clustering to detect novel anomaly patterns (NOVEL_UNSEEN_ANOMALY).
Prevents forcing outdated or irrelevant SOPs onto unprecedented incident scenarios.
"""

import math
import logging
import json
import time
from typing import Dict, List, Any, Optional

logger = logging.getLogger("SYMPTOM_CLUSTER_ENGINE")

class SymptomClusterEngine:
    def __init__(self):
        # Baseline known symptom centroids in normalized feature space
        self.known_centroids = {
            "SPOOLER_DEADLOCK_CLUSTER": [0.90, 0.20, 0.10, 0.05],
            "DATABASE_SLOW_QUERY_CLUSTER": [0.85, 0.95, 0.40, 0.10],
            "MEMORY_LEAK_CLUSTER": [0.30, 0.98, 0.20, 0.05],
            "NETWORK_SOCKET_EXHAUSTION": [0.40, 0.30, 0.95, 0.15],
            "DISK_IO_SATURATION": [0.70, 0.40, 0.30, 0.90]
        }

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1)) or 1e-9
        norm2 = math.sqrt(sum(b * b for b in vec2)) or 1e-9
        return dot / (norm1 * norm2)

    def analyze_symptom_novelty(self, telemetry_vector: List[float], primary_symptom: str) -> Dict[str, Any]:
        """
        Calculates Novelty Score N = 1 - max(CosineSimilarity(v, Centroids))
        If N > 0.40 -> Flagged as NOVEL_UNSEEN_ANOMALY.
        """
        if len(telemetry_vector) < 4:
            telemetry_vector = (telemetry_vector + [0.1, 0.1, 0.1, 0.1])[:4]

        best_cluster = "UNKNOWN_CLUSTER"
        max_sim = 0.0

        for cluster_name, centroid in self.known_centroids.items():
            sim = self._cosine_similarity(telemetry_vector, centroid)
            if sim > max_sim:
                max_sim = sim
                best_cluster = cluster_name

        novelty_score = round(1.0 - max_sim, 4)
        is_novel = novelty_score > 0.40

        result = {
            "primary_symptom": primary_symptom,
            "matched_cluster": best_cluster if not is_novel else "NOVEL_UNSEEN_ANOMALY_CLUSTER",
            "cluster_similarity": round(max_sim, 4),
            "novelty_score": novelty_score,
            "is_novel_anomaly": is_novel,
            "recommendation_strategy": "EXPLORATORY_SAFE_DIAGNOSIS" if is_novel else "STANDARD_TAXONOMY_MATCH",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }

        if is_novel:
            logger.warning(f"[SYMPTOM_CLUSTER] NOVEL UNSEEN ANOMALY DETECTED for '{primary_symptom}' (Novelty Score: {novelty_score:.4f}). Standard SOP override restricted.")
        else:
            logger.info(f"[SYMPTOM_CLUSTER] Matched symptom '{primary_symptom}' to cluster '{best_cluster}' (Sim: {max_sim * 100:.1f}%).")

        return result

# Global instance
symptom_cluster_engine = SymptomClusterEngine()
