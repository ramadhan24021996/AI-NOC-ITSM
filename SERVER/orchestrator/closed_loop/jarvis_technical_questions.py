"""
SERVER.orchestrator.closed_loop.jarvis_technical_questions
============================================================
Component: Jarvis Technical Question Generator

Generates specific technical audit questions when rejecting an AI NOC contract:
  - Mengapa memilih restart PostgreSQL?
  - Apakah lock table sudah diverifikasi?
  - Apakah checkpoint sedang berjalan?
  - Apakah WAL penuh?
  - Apakah Backup Job masih aktif?
  - Apakah sudah melihat Incident #2025-301?
"""
import logging
from typing import List, Dict, Any
from SERVER.contracts.schemas import JarvisTechnicalQuestionPayload

logger = logging.getLogger("orchestrator.closed_loop.questions")


class JarvisTechnicalQuestionGenerator:
    """
    Generates technical audit questions for AI NOC contract remediation.
    """

    def generate_questions(self, target_action: str = "Restart PostgreSQL Container") -> JarvisTechnicalQuestionPayload:
        questions = [
            f"Mengapa memilih '{target_action}'?",
            "Apakah lock table sudah diverifikasi melalui pg_stat_activity?",
            "Apakah checkpoint sedang berjalan saat insiden puncak?",
            "Apakah WAL disk storage penuh?",
            "Apakah Backup Job cron_backup.sh masih aktif?",
            "Apakah sudah memeriksa riwayat pemulihan pada Incident #2025-301?",
        ]

        payload = JarvisTechnicalQuestionPayload(
            technical_questions=questions,
            context_explanation="Pertanyaan audit teknis dihasilkan oleh Jarvis untuk peninjauan kembali oleh AI NOC Engine.",
        )

        logger.debug(f"[JarvisTechnicalQuestionGenerator] Generated {len(questions)} technical audit questions")
        return payload
