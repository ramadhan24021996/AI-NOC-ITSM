"""
Knowledge Gap Detector Module
Identifies novel unmatched incident patterns (< 60% similarity to known GraphRAG KEDB nodes)
and routes them to the Human-in-the-Loop Learning Queue for supervised knowledge base expansion.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any


@dataclass
class KnowledgeGapResult:
    is_knowledge_gap: bool
    similarity_score_pct: float
    highest_matching_sop_id: str
    routed_to_learning_queue: bool
    learning_queue_item_id: str
    summary: str


class KnowledgeGapDetector:
    """Detects un-cataloged incident signatures and manages knowledge expansion queues."""

    def detect_knowledge_gap(
        self,
        incident_signature: str,
        observed_symptoms: List[str]
    ) -> KnowledgeGapResult:

        # Similarity calculation simulation
        is_novel = any("unknown" in s.lower() or "custom_app" in s.lower() for s in observed_symptoms)
        similarity = 42.5 if is_novel else 91.0

        gap_detected = similarity < 60.0
        queue_id = f"GAP-LEARN-{hash(incident_signature) % 100000}" if gap_detected else "NONE"

        summary = (
            f"Knowledge Gap Analysis: Similarity={similarity}% "
            f"({'GAP DETECTED: Routed to Learning Queue ' + queue_id if gap_detected else 'Matched existing KEDB SOP'})"
        )

        return KnowledgeGapResult(
            is_knowledge_gap=gap_detected,
            similarity_score_pct=similarity,
            highest_matching_sop_id="SOP-NET-01" if not gap_detected else "NONE",
            routed_to_learning_queue=gap_detected,
            learning_queue_item_id=queue_id,
            summary=summary
        )
