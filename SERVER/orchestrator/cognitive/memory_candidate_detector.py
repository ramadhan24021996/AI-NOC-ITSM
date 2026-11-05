"""
SERVER.orchestrator.cognitive.memory_candidate_detector
========================================================
Component: Memory Candidate Detector

Detects operator statements containing operational rules or facts:
Example: "Mulai hari ini backup dilakukan pukul 23.00."
Returns MemoryCandidateResult.
"""
import re
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any

logger = logging.getLogger("orchestrator.cognitive.memory_candidate")


@dataclass
class MemoryCandidateResult:
    is_candidate: bool
    fact_text: str = ""
    candidate_type: str = "OPERATIONAL_RULE"
    confidence: float = 0.91


class MemoryCandidateDetector:
    """
    Extracts memory candidate facts from user statements.
    """

    def detect(self, query_text: str) -> MemoryCandidateResult:
        query_lower = query_text.lower()

        # Detection patterns for operational rules / facts
        patterns = [
            r"\b(mulai hari ini|mulai besok|setiap hari|catat|ingat)\b",
            r"\b(backup|maintenance|jadwal|schedule)\s+(dilakukan|berjalan|diatur)\b",
            r"\b(server|node|ip)\s+([a-z0-9.-]+)\s+(adalah|dipindah|diubah|diganti)\b",
        ]

        is_candidate = any(re.search(p, query_lower) for p in patterns)
        if is_candidate:
            logger.info(f"[MemoryCandidateDetector] Memory candidate detected: {query_text[:60]}")
            return MemoryCandidateResult(
                is_candidate=True,
                fact_text=query_text,
                candidate_type="OPERATIONAL_RULE",
                confidence=0.91,
            )

        return MemoryCandidateResult(is_candidate=False)
