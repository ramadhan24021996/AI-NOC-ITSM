"""
SERVER.orchestrator.cognitive.self_reflection
==============================================
Component: Self Reflection Engine

Performs post-generation self-evaluation of assistant outputs:
  - Is my answer sufficient?
  - Did I check SOP knowledge?
  - Was telemetry inspected?
  - Is confidence adequate?
"""
import logging
from typing import Dict, Any
from SERVER.contracts.schemas import SelfReflectionReport

logger = logging.getLogger("orchestrator.cognitive.reflection")


class SelfReflectionEngine:
    """
    Evaluates response quality and completeness post-generation.
    """

    def reflect(
        self,
        query_text: str,
        answer_text: str,
        confidence_score: float,
        has_telemetry: bool = True,
        has_sop: bool = True,
    ) -> SelfReflectionReport:
        is_sufficient = len(answer_text.strip()) > 30
        confidence_ok = confidence_score >= 0.60
        needs_clarification = not (confidence_ok and is_sufficient)

        notes = []
        if has_telemetry:
            notes.append("Telemetri metrik real-time telah diverifikasi.")
        if has_sop:
            notes.append("Dokumen SOP knowledge telah disesuaikan.")
        if confidence_ok:
            notes.append("Tingkat keyakinan jawaban memadai.")
        else:
            notes.append("Tingkat keyakinan di bawah 60%, memerlukan klarifikasi tambahan.")

        report = SelfReflectionReport(
            is_sufficient=is_sufficient,
            sop_checked=has_sop,
            telemetry_checked=has_telemetry,
            confidence_adequate=confidence_ok,
            needs_clarification=needs_clarification,
            reflection_notes=" ".join(notes),
        )

        logger.debug(f"[SelfReflectionEngine] Reflection complete | sufficient={is_sufficient} | clarification_needed={needs_clarification}")
        return report
