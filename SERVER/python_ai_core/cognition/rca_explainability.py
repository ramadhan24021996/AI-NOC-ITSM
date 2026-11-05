"""
Enterprise RCA Explainability Engine
Generates structured, human-auditable RCA explainability responses containing
Dependency Chain, Topology Chain, Failure Chain, Evidence, Matching Incidents,
Graph Path, Confidence, Probability, Reasoning, Suggested Fix, and Preventive Actions.
"""

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("RCA_EXPLAINABILITY")

class RCAExplainabilityEngine:
    """
    Enterprise RCA Explainability Engine
    Transforms complex graph traversals and probability scores into comprehensive, auditable RCA reports.
    """

    def generate_explainability_report(
        self,
        incident_id: str,
        symptom_node_id: str,
        rca_candidates: List[Dict[str, Any]],
        blast_radius: Dict[str, Any],
        evidence_list: Optional[List[Dict[str, Any]]] = None,
        matching_incidents: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Builds a complete, auditable explainability payload."""

        top_candidate = rca_candidates[0] if rca_candidates else {
            "node_id": symptom_node_id,
            "score": 0.5,
            "confidence": 0.5,
            "reason": "Direct symptom anomaly"
        }

        root_cause_id = top_candidate.get("node_id", symptom_node_id)
        score = top_candidate.get("score", 0.5)
        confidence = top_candidate.get("confidence", 0.5)
        reason = top_candidate.get("reason", "Graph traversal identified path anomaly")
        path = top_candidate.get("path", [symptom_node_id, root_cause_id])

        ev_list = evidence_list or top_candidate.get("evidence", [])
        match_inc = matching_incidents or []

        # Construct Chains
        dependency_chain = " ➔ ".join(path)
        topology_chain = f"Client Device ({symptom_node_id}) ➔ Access Network ➔ Gateway ➔ Infrastructure ({root_cause_id})"
        failure_chain = f"Root Anomaly ({root_cause_id}) ➔ Service Degradation ➔ Symptom ({symptom_node_id})"

        # Generate Actionable Recommendations
        suggested_fix = f"Perform diagnostics and restart/clear configuration on `{root_cause_id}`."
        preventive_action = f"Configure redundant fallback path and increase metric alert sensitivity for `{root_cause_id}`."

        return {
            "incident_id": incident_id,
            "symptom_node": symptom_node_id,
            "root_cause_node": root_cause_id,
            "dependency_chain": dependency_chain,
            "topology_chain": topology_chain,
            "failure_chain": failure_chain,
            "evidence": ev_list,
            "historical_evidence": [m.get("title", "") for m in match_inc[:3]],
            "matching_incidents": match_inc[:3],
            "graph_path": path,
            "similarity_score": round(score, 4),
            "confidence_score": round(confidence, 4),
            "probability_percent": f"{round(confidence * 100, 2)}%",
            "reasoning": reason,
            "affected_components": blast_radius.get("affected_devices", []),
            "suggested_fix": suggested_fix,
            "preventive_action": preventive_action,
            "learning_feedback_status": "READY_FOR_OPERATOR_FEEDBACK"
        }
