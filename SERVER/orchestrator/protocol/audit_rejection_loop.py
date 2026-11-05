"""
SERVER.orchestrator.protocol.audit_rejection_loop
==================================================
Component: Audit Rejection Loop Manager

Rejects contract outputs back to AI NOC when Jarvis audit fails or missing evidence is detected:
"Review gagal. Evidence PostgreSQL Log belum tersedia. Jalankan pengumpulan log sebelum rekomendasi dipublikasikan."
"""
import logging
from typing import List, Dict, Any
from SERVER.contracts.schemas import AINOCReviewContract, AuditRejectionFeedback

logger = logging.getLogger("orchestrator.protocol.rejection")


class AuditRejectionLoopManager:
    """
    Manages audit rejection loops back to AI NOC for evidence remediation.
    """

    def process_audit_result(
        self, contract: AINOCReviewContract, is_audit_pass: bool
    ) -> AuditRejectionFeedback:
        if is_audit_pass and len(contract.missing_evidence) == 0:
            return AuditRejectionFeedback(
                is_rejected=False,
                rejection_reason="",
                required_remediation=[],
            )

        missing_str = ", ".join(contract.missing_evidence) if contract.missing_evidence else "Informasi Pendukung SOP"
        reason = f"Review gagal. Evidence {missing_str} belum tersedia. Jalankan pengumpulan log/bukti sebelum rekomendasi dipublikasikan."
        remediation = [f"Jalankan pengumpul bukti untuk {m}" for m in contract.missing_evidence] or ["Jalankan simulasi ulang Sandbox"]

        feedback = AuditRejectionFeedback(
            is_rejected=True,
            rejection_reason=reason,
            required_remediation=remediation,
        )

        logger.warning(f"[AuditRejectionLoopManager] Contract {contract.incident_id} REJECTED: {reason}")
        return feedback
