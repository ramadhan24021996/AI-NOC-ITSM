"""
SERVER.orchestrator.dispatcher.rag_dispatcher
=============================================
Tahap 2.3 — LLM & Knowledge Router (Dispatcher Layer)

ARSITEKTUR:
  orchestrator → [RAG Dispatcher] → python_ai_core/engines/rag_engine.py → pgvector (PostgreSQL)

PRINSIP:
  - HANYA lapisan orkestrasi (wrapper). Tidak memindahkan atau menulis ulang RAGEngine.
  - Tidak ada modul selain dispatcher ini yang boleh mengimpor RAGEngine secara langsung.
  - Menyembunyikan detail implementasi pgvector, BM25, RRF, dan Cross-Encoder Reranker.
  - Backward compatible: python_ai_core/engines/rag_engine.py tidak disentuh.
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("orchestrator.dispatcher.rag")


class RAGDispatcher:
    """
    Orchestration wrapper untuk RAGEngine dari python_ai_core.
    Menyediakan knowledge retrieval (vector + BM25 hybrid search) ke seluruh platform.

    Pipeline internal RAGEngine yang dibungkus:
      1. Embedding via Gemini API (atau local TF-IDF pseudo-embedding fallback)
      2. Redis cache check (TTL 5 menit)
      3. pgvector cosine similarity search (Vector Top-10)
      4. PostgreSQL Full-Text Search / BM25 (BM25 Top-10)
      5. Reciprocal Rank Fusion (RRF) — menggabungkan Vector + BM25
      6. Cross-Encoder Reranker (Top-3 output)

    Contoh penggunaan:
        dispatcher = RAGDispatcher()
        result = await dispatcher.retrieve_async("CPU spike di Surabaya Data Center")
        result = dispatcher.retrieve_sync("CPU spike di Surabaya Data Center")
    """

    def __init__(self):
        self._engine = None

    def _get_engine(self):
        """Lazy initialization: memuat RAGEngine saat pertama kali dibutuhkan."""
        if self._engine is None:
            try:
                import importlib
                # Menggunakan importlib agar dispatcher tidak memiliki hard-coded
                # direct import string ke python_ai_core (sesuai aturan BC02).
                rag_module = importlib.import_module("SERVER.python_ai_core.engines.rag_engine")
                RAGEngine = rag_module.RAGEngine
                self._engine = RAGEngine()
                logger.info("[RAGDispatcher] RAGEngine initialized successfully.")

            except Exception as exc:
                logger.error(f"[RAGDispatcher] Failed to load RAGEngine: {exc}")
                raise
        return self._engine

    async def retrieve_async(
        self,
        incident_text: str,
        limit: int = 3,
    ) -> Dict[str, Any]:
        """
        Async hybrid knowledge retrieval (RAG 2.0 pipeline).

        Args:
            incident_text: Teks lengkap incident/symptoms yang ingin dicari knowledge-nya.
            limit: Jumlah hasil maksimum yang dikembalikan.

        Returns:
            dict: {
                "embedding_vector": list[float],
                "metadata": {"status": "gemini"|"cache_hit"|"local_fallback"},
                "results": list[dict]  # Top-N reranked knowledge entries
            }
        """
        engine = self._get_engine()
        logger.info(f"[RAGDispatcher] Async hybrid retrieval | query='{incident_text[:60]}...' | limit={limit}")
        return await engine.embed_and_query_async(incident_text, limit=limit)

    def retrieve_sync(
        self,
        incident_text: str,
        limit: int = 3,
    ) -> Dict[str, Any]:
        """
        Synchronous hybrid knowledge retrieval (RAG 2.0 pipeline).

        Args:
            incident_text: Teks incident yang ingin dicari knowledge-nya.
            limit: Jumlah hasil maksimum yang dikembalikan.

        Returns:
            dict: {
                "embedding_vector": list[float],
                "graph_context": str,
                "metadata": dict,
                "results": list[dict]
            }
        """
        engine = self._get_engine()
        logger.info(f"[RAGDispatcher] Sync hybrid retrieval | query='{incident_text[:60]}...' | limit={limit}")
        return engine.embed_and_query(incident_text, limit=limit)

    def ingest_resolution(
        self,
        issue: str,
        root_cause: str,
        solution: str,
        success_rate: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Ingests a resolved incident into the knowledge store (Adaptive RAG Learning).
        Digunakan setelah insiden berhasil diselesaikan untuk meningkatkan kualitas retrieval.

        Args:
            issue: Deskripsi masalah/gejala.
            root_cause: Akar penyebab yang teridentifikasi.
            solution: Solusi yang berhasil diterapkan.
            success_rate: 0.0–1.0. Bobot efektivitas solusi.

        Returns:
            dict: {"status": "INGESTED_SUCCESSFULLY"|"ERROR", "title": str, "weight": float}
        """
        engine = self._get_engine()
        logger.info(f"[RAGDispatcher] Ingesting resolution | issue='{issue[:50]}' | success_rate={success_rate}")
        return engine.ingest_incremental_resolution(issue, root_cause, solution, success_rate)
