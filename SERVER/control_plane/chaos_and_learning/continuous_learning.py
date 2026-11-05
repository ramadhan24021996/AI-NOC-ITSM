"""
SERVER.control_plane.chaos_and_learning - Continuous Learning Pipeline
Continuous Learning Pipeline producing Candidate Models.
STRICT INVARIANT: Candidate Models MUST pass offline evaluation & manual approval BEFORE production deployment!
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

@dataclass
class CandidateModelArtifact:
    model_id: str
    version: str
    training_data_size: int
    offline_eval_score: float
    is_offline_evaluated: bool = False
    is_human_approved: bool = False
    status: str = "candidate"  # "candidate" -> "evaluated" -> "approved" -> "deployed"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class ContinuousLearningPipeline:
    """Continuous Learning Pipeline with mandatory evaluation & approval gates."""
    def __init__(self):
        self._candidate_artifacts: Dict[str, CandidateModelArtifact] = {}

    def train_candidate_model(self, model_id: str, data_size: int) -> CandidateModelArtifact:
        """Trains a new candidate model artifact. Status starts as 'candidate'."""
        artifact = CandidateModelArtifact(
            model_id=model_id,
            version=f"v{len(self._candidate_artifacts)+1}.0-candidate",
            training_data_size=data_size,
            offline_eval_score=0.0,
            status="candidate",
        )
        self._candidate_artifacts[model_id] = artifact
        return artifact

    def run_offline_evaluation(self, model_id: str, eval_score: float) -> CandidateModelArtifact:
        """Runs offline benchmark evaluation on candidate model artifact."""
        artifact = self._candidate_artifacts.get(model_id)
        if not artifact:
            raise KeyError(f"Candidate model {model_id} not found.")

        artifact.offline_eval_score = eval_score
        artifact.is_offline_evaluated = True
        artifact.status = "evaluated"
        return artifact

    def approve_for_production(self, model_id: str, approver_id: str) -> CandidateModelArtifact:
        """Manually approves an evaluated candidate model for production deployment."""
        artifact = self._candidate_artifacts.get(model_id)
        if not artifact:
            raise KeyError(f"Candidate model {model_id} not found.")

        if not artifact.is_offline_evaluated:
            raise ValueError(f"Cannot approve un-evaluated candidate model {model_id}.")

        artifact.is_human_approved = True
        artifact.status = "approved"
        return artifact
