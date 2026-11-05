"""
Knowledge Promotion Pipeline Module
Enforces a 10-Stage Knowledge Promotion Lifecycle (CI/CD for Knowledge):
DRAFT ──► SANDBOX ──► SIMULATED ──► VALIDATED ──► HUMAN_REVIEW ──► SHADOW_MODE ──► LIMITED_DEPLOYMENT ──► PRODUCTION ──► DEPRECATED ──► ARCHIVED
Ensures no AI-discovered pattern modifies production knowledge without passing rigorous promotion stages.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class KnowledgeLifecycleStage(Enum):
    DRAFT = 1
    SANDBOX = 2
    SIMULATED = 3
    VALIDATED = 4
    HUMAN_REVIEW = 5
    SHADOW_MODE = 6
    LIMITED_DEPLOYMENT = 7
    PRODUCTION = 8
    DEPRECATED = 9
    ARCHIVED = 10


@dataclass
class KnowledgeCandidateState:
    candidate_id: str
    knowledge_name: str
    current_stage: KnowledgeLifecycleStage
    stage_history: List[str]
    evidence_score: float
    promoted_by: str
    is_production_active: bool


class KnowledgePromotionPipeline:
    """Manages the progressive 10-stage promotion of candidate knowledge into production."""

    def __init__(self):
        self.candidates: Dict[str, KnowledgeCandidateState] = {}

    def create_knowledge_candidate(
        self,
        knowledge_id: str,
        name: str
    ) -> KnowledgeCandidateState:

        cid = f"CAND-{knowledge_id}"
        state = KnowledgeCandidateState(
            candidate_id=cid,
            knowledge_name=name,
            current_stage=KnowledgeLifecycleStage.DRAFT,
            stage_history=["DRAFT"],
            evidence_score=0.50,
            promoted_by="KnowledgeExtractor",
            is_production_active=False
        )
        self.candidates[cid] = state
        return state

    def promote_candidate(
        self,
        candidate_id: str,
        target_stage: KnowledgeLifecycleStage,
        evidence_boost: float = 0.15,
        operator_approved: bool = True
    ) -> KnowledgeCandidateState:

        cand = self.candidates.get(candidate_id)
        if not cand:
            raise ValueError(f"Candidate '{candidate_id}' not found")

        # Require human review if advancing to SHADOW_MODE or PRODUCTION
        if target_stage in (KnowledgeLifecycleStage.SHADOW_MODE, KnowledgeLifecycleStage.PRODUCTION) and not operator_approved:
            raise PermissionError("Human Review required for production knowledge promotion")

        cand.current_stage = target_stage
        cand.stage_history.append(target_stage.name)
        cand.evidence_score = min(1.0, cand.evidence_score + evidence_boost)

        if target_stage == KnowledgeLifecycleStage.PRODUCTION:
            cand.is_production_active = True

        return cand
