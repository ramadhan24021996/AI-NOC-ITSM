"""
SERVER.orchestrator.dispatcher.embedding_dispatcher
===================================================
Tahap 2.3 — LLM & Knowledge Router (Dispatcher Layer)

ARSITEKTUR:
  orchestrator → [Embedding Dispatcher] → Gemini Embedding API | Local TF-IDF Fallback

PRINSIP:
  - HANYA lapisan orkestrasi. Tidak memindahkan atau menulis ulang core embedding logic.
  - Menyembunyikan detail provider embedding (Gemini API vs local pseudo-embedding).
  - Mendukung caching embedding via Redis (5 menit TTL) melalui RAGEngine.
  - Backward compatible: tidak ada perubahan pada python_ai_core.
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("orchestrator.dispatcher.embedding")


class EmbeddingDispatcher:
    """
    Orchestration wrapper untuk embedding pipeline.
    Menghasilkan vector embedding dari teks untuk keperluan:
      1. RAG similarity search (pgvector)
      2. Semantic cache key generation
      3. Knowledge vector ingestion

    Pipeline:
      1. Cek Redis embedding cache (key: 'cache:emb:<hash_of_text>')
      2. Jika cache miss: panggil Gemini text-embedding-004 (atau gemini-embedding-001)
      3. Jika Gemini tidak tersedia: fallback ke local TF-IDF pseudo-embedding (deterministik)

    Contoh penggunaan:
        dispatcher = EmbeddingDispatcher()
        vector = dispatcher.embed("CPU 98% sustained - PEKALONGAN-PC-01")
        # Returns: list[float] panjang 768
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
                logger.info("[EmbeddingDispatcher] RAGEngine (embedding pipeline) initialized.")
            except Exception as exc:
                logger.error(f"[EmbeddingDispatcher] Failed to load embedding pipeline: {exc}")
                raise
        return self._engine

    def embed(self, text: str) -> List[float]:
        """
        Synchronous embedding. Mengembalikan vector float[768].

        Kasus penggunaan: context builder, batch processing, non-async pipeline.

        Args:
            text: Teks yang akan di-embed.

        Returns:
            list[float]: Vector embedding panjang 768.
        """
        engine = self._get_engine()
        logger.info(f"[EmbeddingDispatcher] Embedding text (sync) | len={len(text)}")
        # Gunakan local embedding yang sudah ada di RAGEngine (deterministik, tanpa DB call)
        return engine._local_embedding_fallback(text, dim=768)

    async def embed_async(self, text: str) -> Dict[str, Any]:
        """
        Asynchronous embedding dengan Gemini API (fallback ke local jika tidak tersedia).

        Args:
            text: Teks yang akan di-embed.

        Returns:
            dict: {
                "embedding_vector": list[float],
                "metadata": {"status": "gemini"|"cache_hit"|"local_fallback"},
                "results": []  # Kosong, hanya embedding (tanpa hybrid search)
            }
        """
        engine = self._get_engine()
        logger.info(f"[EmbeddingDispatcher] Embedding text (async) | len={len(text)}")
        # Memanfaatkan embed_and_query_async tapi kembalikan hanya embedding-nya
        result = await engine.embed_and_query_async(text, limit=0)
        return {
            "embedding_vector": result.get("embedding_vector", []),
            "metadata": result.get("metadata", {}),
        }

    def is_gemini_available(self) -> bool:
        """Cek apakah Gemini embedding API tersedia dan key valid."""
        engine = self._get_engine()
        return engine._is_gemini_key_valid()
