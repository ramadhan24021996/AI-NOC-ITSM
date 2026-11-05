"""
SERVER.orchestrator.cognitive.knowledge_gap_detector
=====================================================
Component: Knowledge Gap Detector

Identifies missing SOPs or knowledge in RAG documents and triggers learning prompts:
"Saya belum memiliki SOP Oracle RAC. Apakah Anda ingin mengajarkan SOP baru?"
"""
import re
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

logger = logging.getLogger("orchestrator.cognitive.knowledge_gap")


@dataclass
class KnowledgeGapResult:
    has_gap: bool
    missing_topic: str = ""
    suggested_prompt: Optional[str] = None
    missing_sop_count: int = 0


class KnowledgeGapDetector:
    """
    Detects knowledge gaps when RAG results are empty or low score.
    """

    def detect(
        self, query_text: str, rag_chunks: List[Dict[str, Any]]
    ) -> KnowledgeGapResult:
        query_lower = query_text.lower()

        is_empty = len(rag_chunks) == 0
        has_low_score = False
        if not is_empty:
            scores: List[float] = []
            for c in rag_chunks:
                s = c.get("score") if c.get("score") is not None else c.get("relevance", 1.0)
                try:
                    scores.append(float(s) if s is not None else 1.0)
                except (ValueError, TypeError):
                    scores.append(1.0)
            avg_score = sum(scores) / len(scores) if scores else 0.0
            has_low_score = avg_score < 0.45

        if is_empty or has_low_score:
            # Extract topic name from query
            topic = "SOP"
            tech_match = re.search(r"\b(oracle rac|kubernetes|bgp|redis|postgresql|nginx|docker|netdata)\b", query_lower)
            if tech_match:
                topic = f"SOP {tech_match.group(1).title()}"
            else:
                topic = "SOP Operasional"

            prompt = f"Saya belum memiliki {topic}. Apakah Anda ingin mengajarkan SOP baru ini?"
            logger.info(f"[KnowledgeGapDetector] Gap detected | topic={topic}")
            return KnowledgeGapResult(
                has_gap=True,
                missing_topic=topic,
                suggested_prompt=prompt,
                missing_sop_count=1,
            )

        return KnowledgeGapResult(has_gap=False, missing_sop_count=0)
