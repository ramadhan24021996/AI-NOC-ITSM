"""
SERVER.orchestrator.cognitive.explanation_engine
===============================================
Component: Explanation Engine

Provides step-by-step decision justification audit trails for Dashboard UI:
"Mengapa AI mengambil keputusan ini?"
Telemetry -> Knowledge -> Historical Incident -> Reasoning -> Recommendation
"""
import logging
from typing import Dict, Any, List
from SERVER.contracts.schemas import ExplanationTrail

logger = logging.getLogger("orchestrator.cognitive.explanation")


class ExplanationEngine:
    """
    Generates structured decision justification trails.
    """

    def generate_trail(
        self,
        intent: str,
        primary_evidence: str,
        confidence_score: float,
        strategy: str,
    ) -> ExplanationTrail:
        steps = [
            f"1. Telemetry & Metrik: Diverifikasi dari sinyal {primary_evidence}.",
            "2. Knowledge & SOP: Pencarian RAG dokumen pendukung.",
            f"3. Reasoning Engine: Intent terdeteksi sebagai '{intent}' dengan strategi '{strategy}'.",
            f"4. Confidence Score: Dihitung skor keyakinan akhir sebesar {int(confidence_score * 100)}%.",
            "5. Recommendation: Rekomendasi tindakan disusun sesuai standar ITIL/NOC.",
        ]

        summary = (
            f"Keputusan diambil berdasarkan bukti {primary_evidence} dengan keyakinan {int(confidence_score * 100)}% "
            f"menggunakan strategi {strategy}."
        )

        trail = ExplanationTrail(
            reasoning_steps=steps,
            audit_summary=summary,
        )

        logger.debug(f"[ExplanationEngine] Generated explanation trail with {len(steps)} steps")
        return trail
