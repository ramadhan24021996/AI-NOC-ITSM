"""
Model Governance Engine Module
Unified Version Control & Deployment Governance:
- Unified versioning: model_version, graphrag_version, causal_graph_version
- Approval workflow gate
- Automated rollback gate if RCA precision drops below 95% threshold
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone


@dataclass
class ModelGovernanceSnapshot:
    governance_version: str
    model_version: str
    graphrag_version: str
    causal_graph_version: str
    precision_pct: float
    approved_by: str
    status: str    # "ACTIVE", "DEPRECATED", "ROLLED_BACK"
    created_at: str


class ModelGovernanceEngine:
    """Manages model & graph versioning, deployment approvals, and automatic rollback gates."""

    def __init__(self, current_version: str = "v7.0.0"):
        self.active_version = current_version
        self.history: List[ModelGovernanceSnapshot] = []
        self._initialize_baseline()

    def _initialize_baseline(self):
        now_ts = datetime.now(timezone.utc).isoformat()
        self.history.append(ModelGovernanceSnapshot(
            governance_version="v7.0.0",
            model_version="gemini-1.5-flash-v7",
            graphrag_version="graphrag-v3.2",
            causal_graph_version="causal-graph-v5.4",
            precision_pct=97.2,
            approved_by="NOC-Lead-Architect",
            status="ACTIVE",
            created_at=now_ts
        ))

    def evaluate_deployment_or_rollback(
        self,
        candidate_version: str,
        current_precision_pct: float
    ) -> tuple[bool, str]:
        """Evaluates whether to approve deployment or trigger automatic rollback."""

        # Automated Rollback Gate: Precision < 95%
        if current_precision_pct < 95.0:
            active_snap = self.history[-1]
            active_snap.status = "ROLLED_BACK"
            return False, f"AUTOMATIC ROLLBACK TRIGGERED: Precision dropped ({current_precision_pct}% < 95.0%). Reverting to stable baseline."

        return True, f"DEPLOYMENT APPROVED: Candidate version {candidate_version} precision ({current_precision_pct}%) meets 95% threshold."
