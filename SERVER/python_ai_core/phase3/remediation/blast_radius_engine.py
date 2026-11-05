"""
Phase 3.6: Blast Radius & Risk Engine (phase3/remediation/blast_radius_engine.py)

Enforces Invariant #25 (Blast Radius Bound) and Invariant #27 (Least-Impact Remediation).
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger("BLAST_RADIUS_ENGINE")


class BlastRadiusEngine:
    @staticmethod
    def evaluate_blast_radius(blast_radius: Dict[str, Any], risk_score: float, max_allowed_risk: float = 0.80) -> Dict[str, Any]:
        """
        Validates blast radius and risk score against policy thresholds.
        """
        violations = []
        max_affected = blast_radius.get("max_affected_nodes", 1)
        allowed_nodes = blast_radius.get("allowed_node_threshold", 5)

        if max_affected > allowed_nodes:
            violations.append(f"Affected nodes count ({max_affected}) exceeds allowed policy threshold ({allowed_nodes})")

        if risk_score > max_allowed_risk:
            violations.append(f"Risk score ({risk_score}) exceeds maximum allowed risk threshold ({max_allowed_risk})")

        is_safe = (len(violations) == 0)
        return {
            "is_safe": is_safe,
            "risk_score": risk_score,
            "max_affected_nodes": max_affected,
            "violations": violations
        }
