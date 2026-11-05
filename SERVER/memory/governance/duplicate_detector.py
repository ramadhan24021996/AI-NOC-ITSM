"""
SERVER.memory.governance.duplicate_detector
============================================
Component: Knowledge Duplicate Detector

Calculates similarity percentage between a candidate SOP and existing SOPs.
Warns operator if similarity > 85% ("92% match with SOP Oracle RAC Recovery").
"""
import re
import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Set

logger = logging.getLogger("memory.governance.duplicate")


@dataclass
class DuplicateCheckResult:
    is_duplicate: bool
    similarity_pct: int
    matching_sop_title: str = ""
    recommendation: str = ""


class KnowledgeDuplicateDetector:
    """
    Detects duplicate or highly similar SOP documents.
    """

    def check_duplicate(
        self, candidate_text: str, existing_documents: List[Dict[str, str]]
    ) -> DuplicateCheckResult:
        if not candidate_text or not existing_documents:
            return DuplicateCheckResult(is_duplicate=False, similarity_pct=0)

        cand_words = self._tokenize(candidate_text)
        if not cand_words:
            return DuplicateCheckResult(is_duplicate=False, similarity_pct=0)

        max_sim = 0.0
        best_match_title = ""

        for doc in existing_documents:
            doc_text = doc.get("content") or doc.get("text") or ""
            doc_title = doc.get("title") or doc.get("filename") or "Existing SOP"

            doc_words = self._tokenize(doc_text)
            if not doc_words:
                continue

            # Jaccard similarity between word sets
            intersection = cand_words.intersection(doc_words)
            union = cand_words.union(doc_words)
            sim = len(intersection) / len(union) if union else 0.0

            if sim > max_sim:
                max_sim = sim
                best_match_title = doc_title

        sim_pct = int(max_sim * 100)
        is_dup = sim_pct >= 85

        rec = ""
        if is_dup:
            rec = f"SOP ini {sim_pct}% mirip dengan '{best_match_title}'. Disarankan melakukan update/merge daripada membuat SOP baru."
            logger.info(f"[KnowledgeDuplicateDetector] {rec}")

        return DuplicateCheckResult(
            is_duplicate=is_dup,
            similarity_pct=sim_pct,
            matching_sop_title=best_match_title,
            recommendation=rec,
        )

    def _tokenize(self, text: str) -> Set[str]:
        words = re.findall(r"\b[a-z0-9_-]{3,}\b", text.lower())
        stopwords = {"and", "the", "for", "with", "percakapan", "context", "operator", "jarvis", "session"}
        return set(w for w in words if w not in stopwords)
