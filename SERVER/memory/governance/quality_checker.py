"""
SERVER.memory.governance.quality_checker
=========================================
Component: Knowledge Quality Checker

Evaluates 4 quality metrics for Markdown staging candidates:
  - completeness (0-100)
  - consistency (0-100)
  - evidence (0-100)
  - readability (0-100)
Computes overall_score.
HARD GATE: overall_score < 80 blocks approval until edited.
"""
import re
import logging
from dataclasses import dataclass

logger = logging.getLogger("memory.governance.quality")


@dataclass
class QualityScorecard:
    completeness: int = 90
    consistency: int = 90
    evidence: int = 90
    readability: int = 90
    overall_score: int = 90
    is_approvable: bool = True
    rejection_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "completeness": self.completeness,
            "consistency": self.consistency,
            "evidence": self.evidence,
            "readability": self.readability,
            "overall_score": self.overall_score,
            "is_approvable": self.is_approvable,
            "rejection_reason": self.rejection_reason,
        }


class KnowledgeQualityChecker:
    """
    Quality gate checker ensuring only high-quality SOPs (overall >= 80) can be approved.
    """

    def evaluate(self, transcript_md: str, cognitive_metadata: dict) -> QualityScorecard:
        text = (transcript_md or "").strip()
        length = len(text)

        # 1. Completeness check (0-100)
        has_conversation = "## Percakapan" in text or "User" in text or "Operator" in text
        has_context = "## Context" in text or "Intent" in text or "Goal" in text

        if length < 50:
            completeness = 20
        elif length < 150:
            completeness = 50
        elif length < 300:
            completeness = 70
        else:
            completeness = 85

        if has_conversation and has_context:
            completeness += 15
        completeness = min(100, completeness)

        # 2. Consistency check (0-100)
        has_conflict = cognitive_metadata.get("conflict_resolution", {}).get("has_conflict", False)
        consistency = 60 if has_conflict else 95

        # 3. Evidence check (0-100)
        confidence = cognitive_metadata.get("confidence", cognitive_metadata.get("ai_confidence", 0.90))
        try:
            conf_val = float(confidence)
        except (ValueError, TypeError):
            conf_val = 0.90
        evidence = int(conf_val * 100)

        # 4. Readability check (0-100)
        has_headers = "#" in text
        has_bullet_points = "-" in text or "*" in text
        readability = 30 if length < 50 else 70
        if has_headers:
            readability += 15
        if has_bullet_points:
            readability += 15
        readability = min(100, readability)

        # Compute overall score
        overall = int((completeness + consistency + evidence + readability) / 4.0)

        # HARD GATE: overall_score < 80 blocks approval
        is_approvable = overall >= 80
        reason = ""
        if not is_approvable:
            reason = f"Quality score {overall} is below minimum threshold (80). Please edit and improve SOP detail."
            logger.warning(f"[KnowledgeQualityChecker] BLOCKED: {reason}")

        scorecard = QualityScorecard(
            completeness=completeness,
            consistency=consistency,
            evidence=evidence,
            readability=readability,
            overall_score=overall,
            is_approvable=is_approvable,
            rejection_reason=reason,
        )

        logger.debug(f"[KnowledgeQualityChecker] Scorecard evaluated | overall={overall} | approvable={is_approvable}")
        return scorecard
