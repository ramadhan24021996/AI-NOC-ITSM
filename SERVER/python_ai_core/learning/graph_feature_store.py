"""
Enterprise Graph Feature Store
Separates Incident Features, Topology Features, Telemetry Features, Graph Features, and Embedding Features for retraining.
"""

import logging
import time
from typing import Dict, List, Any

logger = logging.getLogger("GRAPH_FEATURE_STORE")

class GraphFeatureStore:
    """
    Enterprise Feature Store
    Decouples raw telemetry, topology graphs, and AI embeddings into structured feature sets.
    """

    def __init__(self):
        self.features: Dict[str, Dict[str, Any]] = {}

    def store_feature_record(
        self,
        incident_id: str,
        incident_features: Dict[str, Any],
        topology_features: Dict[str, Any],
        telemetry_features: Dict[str, Any],
        embedding_features: List[float]
    ):
        """Stores structured feature vector record for incident."""
        record = {
            "incident_id": incident_id,
            "incident_features": incident_features,
            "topology_features": topology_features,
            "telemetry_features": telemetry_features,
            "embedding_features": embedding_features,
            "stored_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        self.features[incident_id] = record
        logger.info("[FEATURE STORE] Stored feature record for incident: %s", incident_id)

    def get_feature_record(self, incident_id: str) -> Dict[str, Any]:
        """Retrieves stored feature record for retraining."""
        return self.features.get(incident_id, {})
