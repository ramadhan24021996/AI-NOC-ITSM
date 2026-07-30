import logging
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
import json
import os
import asyncio
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from reranker import get_reranker

try:
    from google import genai  # type: ignore # pyright: ignore[reportMissingImports]
except Exception:
    genai = None

logger = logging.getLogger("RAG_ENGINE")

# ─────────────────────────────────────────────────────────────────────────────
# CONNECTION POOL FIX:
# - max_conn dikurangi dari 20 → 5 (mencegah pool exhaustion antar service)
# - Ditambahkan keepalives agar koneksi idle tidak "zombie"
# - Ditambahkan pool_timeout agar getconn() tidak block selamanya
# - Ditambahkan reconnect logic otomatis jika pool closed/exhausted
# ─────────────────────────────────────────────────────────────────────────────

_POOL_LOCK = threading.Lock()
_POOL_MIN  = 2
_POOL_MAX  = 10         # max per service — pg max_connections 100 with 5 services = safe headroom
_POOL_TIMEOUT = 15      # detik — getconn() akan raise exception setelah 15 detik
_POOL_MAX_AGE  = 1800   # seconds — recycle pool every 30 minutes to prevent stale connections

class RAGEngine:
    _pool = None
    _pool_init_time = None

    def __init__(self):
        self.db_host = os.getenv("DB_HOST", "127.0.0.1")
        self.db_port = os.getenv("DB_PORT", "5432")
        self.db_name = os.getenv("DB_NAME", "osi_system")
        self.user    = os.getenv("DB_USER", "postgres")
        self.password = os.getenv("DB_PASSWORD", "postgres")
        self.conn = None
        self._init_pool()

    def _build_dsn_kwargs(self):
        return dict(
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            user=self.user,
            password=self.password,
            # TCP keepalives — koneksi idle tidak zombie setelah 60 detik
            keepalives=1,
            keepalives_idle=60,
            keepalives_interval=10,
            keepalives_count=5,
            # Connection timeout
            connect_timeout=10,
        )

    def _init_pool(self):
        """Inisialisasi pool hanya sekali (singleton). Thread-safe. Auto-recycles every 30min."""
        with _POOL_LOCK:
            # Auto-recycle pool if too old (stale connection prevention)
            pool_age = time.time() - (RAGEngine._pool_init_time or 0)
            if RAGEngine._pool and not RAGEngine._pool.closed and pool_age > _POOL_MAX_AGE:
                logger.info(f"[RAG POOL] Recycling pool after {int(pool_age)}s (max_age={_POOL_MAX_AGE}s)")
                try:
                    RAGEngine._pool.closeall()
                except Exception:
                    pass
                RAGEngine._pool = None

            if RAGEngine._pool is None or RAGEngine._pool.closed:
                try:
                    RAGEngine._pool = ThreadedConnectionPool(
                        _POOL_MIN, _POOL_MAX,
                        **self._build_dsn_kwargs()
                    )
                    RAGEngine._pool_init_time = time.time()
                    logger.info(f"[RAG POOL] Initialized (min={_POOL_MIN}, max={_POOL_MAX}) → DB {self.db_name}@{self.db_host}")
                except Exception as e:
                    logger.error(f"[RAG POOL] Failed to initialize pool: {e}")
                    RAGEngine._pool = None

    def _get_fresh_conn(self):
        """Ambil koneksi baru langsung (bypass pool) — digunakan saat pool exhausted."""
        try:
            conn = psycopg2.connect(**self._build_dsn_kwargs())
            conn.autocommit = False
            return conn
        except Exception as e:
            logger.error(f"[RAG POOL] Direct connection also failed: {e}")
            return None

    def connect(self):
        """Borrow a connection from the pool. Auto-reconnect jika pool exhausted."""
        # Pastikan pool sudah ada
        if RAGEngine._pool is None or RAGEngine._pool.closed:
            self._init_pool()

        if RAGEngine._pool and not RAGEngine._pool.closed:
            try:
                self.conn = RAGEngine._pool.getconn()
                # Validasi koneksi: cek apakah masih hidup
                if self.conn:
                    try:
                        self.conn.isolation_level  # trigger connection check
                        if self.conn.closed:
                            raise Exception("Connection already closed")
                    except Exception:
                        # Koneksi zombie — kembalikan dan minta yang baru
                        try:
                            RAGEngine._pool.putconn(self.conn, close=True)
                        except Exception:
                            pass
                        self.conn = RAGEngine._pool.getconn()
            except Exception as e:
                logger.warning(f"[RAG POOL] Pool get failed ({e}), using direct connection fallback.")
                self.conn = self._get_fresh_conn()
        else:
            logger.warning("[RAG POOL] Pool not available, using direct connection.")
            self.conn = self._get_fresh_conn()

    def close(self):
        """Return the connection to the pool. WAJIB dipanggil setelah selesai."""
        if self.conn:
            if RAGEngine._pool and not RAGEngine._pool.closed:
                try:
                    # Reset any open transaction sebelum dikembalikan
                    if not self.conn.closed:
                        try:
                            self.conn.rollback()
                        except Exception:
                            pass
                    RAGEngine._pool.putconn(self.conn)
                    logger.debug("[RAG POOL] Connection returned to pool.")
                except Exception as e:
                    logger.warning(f"[RAG POOL] Failed to return conn to pool ({e}), closing directly.")
                    try:
                        self.conn.close()
                    except Exception:
                        pass
            else:
                try:
                    self.conn.close()
                except Exception:
                    pass
            self.conn = None

    def __enter__(self):
        """Context manager: auto-connect."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager: auto-return connection to pool."""
        self.close()
        return False  # biarkan exception propagate



    def query_similar_incidents(self, embedding_vector: list, limit=10):
        """
        1. Vector Search: Queries the knowledge_vectors table for semantic similarity using pgvector.
        Uses <=> operator for Cosine Distance. Returns Top-10 candidates.
        """
        if not self.conn:
            self.connect()
        if not self.conn:
            logger.warning("DB not connected. RAG skipping.")
            return []
            
        try:
            if not embedding_vector:
                logger.warning("RAG query received empty/None embedding_vector.")
                return []
            vector_str = "[" + ",".join(map(str, embedding_vector)) + "]"
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT incident_id, title, symptoms, root_cause, resolution, (1 - (embedding <=> %s::vector)) as similarity_score
                    FROM knowledge_vectors
                    WHERE embedding IS NOT NULL
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                """, (vector_str, vector_str, limit))
                
                results = cur.fetchall()
                parsed_results = []
                try:
                    from probabilistic.probabilistic_engine import ProbabilityCalibrator
                    calibrator = ProbabilityCalibrator()
                except Exception:
                    calibrator = None

                for row in results:
                    r_dict = dict(row)
                    sim = float(r_dict.get("similarity_score", 0.0) or 0.0)
                    if calibrator:
                        prob = calibrator.calibrate_cosine_similarity(sim)
                    else:
                        prob = round(sim, 4)
                    r_dict["calibrated_probability"] = prob
                    r_dict["calibrated_probability_percent"] = f"{round(prob * 100, 2)}%"
                    parsed_results.append(r_dict)

                return parsed_results
                
        except Exception as e:
            logger.error(f"RAG Vector query failed: {e}")
            try:
                self.conn.rollback()
            except Exception:
                pass
            return []

    def query_bm25_search(self, query_text: str, limit=10):
        """
        2. BM25 Search: Queries PostgreSQL Full-Text Search for literal keywords and error codes.
        Returns Top-10 candidates based on ts_rank_cd.
        """
        if not self.conn:
            self.connect()
        if not self.conn or not query_text.strip():
            return []

        try:
            cleaned_query = query_text.replace("'", " ").replace('"', ' ')
            terms = [t for t in cleaned_query.split() if len(t) > 2][:8]
            fts_query = " | ".join(terms) if terms else cleaned_query

            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT incident_id, title, symptoms, root_cause, resolution,
                           ts_rank_cd(
                               to_tsvector('english', coalesce(title, '') || ' ' || coalesce(symptoms, '') || ' ' || coalesce(root_cause, '') || ' ' || coalesce(resolution, '')),
                               plainto_tsquery('english', %s)
                           ) as bm25_score
                    FROM knowledge_vectors
                    WHERE to_tsvector('english', coalesce(title, '') || ' ' || coalesce(symptoms, '') || ' ' || coalesce(root_cause, '') || ' ' || coalesce(resolution, '')) @@ plainto_tsquery('english', %s)
                       OR title ILIKE %s OR symptoms ILIKE %s OR resolution ILIKE %s
                    ORDER BY bm25_score DESC
                    LIMIT %s
                """, (fts_query, fts_query, f"%{fts_query[:30]}%", f"%{fts_query[:30]}%", f"%{fts_query[:30]}%", limit))

                results = cur.fetchall()
                return [dict(row) for row in results]
        except Exception as e:
            logger.warning(f"RAG BM25 query fallback: {e}")
            try:
                self.conn.rollback()
            except Exception:
                pass
            return []

    def reciprocal_rank_fusion(self, vector_results: list, bm25_results: list, k: int = 60) -> list:
        """
        3. Reciprocal Rank Fusion (RRF): Combines Vector Top-10 and BM25 Top-10 using:
        RRF_Score = 1 / (k + rank_vector) + 1 / (k + rank_bm25)
        """
        doc_map = {}

        # Process Vector ranks
        for rank, doc in enumerate(vector_results):
            doc_id = str(doc.get("incident_id"))
            if doc_id not in doc_map:
                doc_map[doc_id] = dict(doc)
                doc_map[doc_id]["rrf_score"] = 0.0
            doc_map[doc_id]["rrf_score"] += 1.0 / (k + (rank + 1))
            doc_map[doc_id]["vector_rank"] = rank + 1

        # Process BM25 ranks
        for rank, doc in enumerate(bm25_results):
            doc_id = str(doc.get("incident_id"))
            if doc_id not in doc_map:
                doc_map[doc_id] = dict(doc)
                doc_map[doc_id]["rrf_score"] = 0.0
            doc_map[doc_id]["rrf_score"] += 1.0 / (k + (rank + 1))
            doc_map[doc_id]["bm25_rank"] = rank + 1

        fusion_list = list(doc_map.values())
        fusion_list.sort(key=lambda x: x["rrf_score"], reverse=True)
        return fusion_list

    def query_hybrid_search(self, query_text: str, embedding_vector: list, limit=3) -> list:
        """
        RAG 2.0 Hybrid Search Pipeline with Smart Redis Caching (5-minute TTL):
          1. Redis Cache Check ('cache:rag:search:<hash>')
          2. Vector Top-10 (pgvector cosine similarity)
          3. BM25 Top-10 (PostgreSQL Full-Text Search literal keywords)
          4. Reciprocal Rank Fusion (RRF)
          5. Cross-Encoder Reranker (Top-3 output)
        """
        from core.cache_manager import get_cache_manager
        cache_mgr = get_cache_manager()
        cached_results = cache_mgr.get_rag_cache(query_text)
        if cached_results:
            logger.info("[RAG 2.0] Returning cached hybrid reranked search results (TTL 5m active)")
            return cached_results[:limit]

        vec_top10 = self.query_similar_incidents(embedding_vector, limit=10)
        bm25_top10 = self.query_bm25_search(query_text, limit=10)

        # Handle empty cases gracefully
        if not vec_top10 and not bm25_top10:
            return [{"status": "DEGRADED", "source": "rag_engine_2.0", "error": "no_matching_vectors"}]

        rrf_candidates = self.reciprocal_rank_fusion(vec_top10, bm25_top10)
        
        # Step 5: Kirim candidate ke Cross-Encoder Reranker
        reranker = get_reranker()
        top3_reranked = reranker.rerank(query_text, rrf_candidates, top_k=limit)
        
        # Cache results in Redis with 5-minute TTL (300s)
        cache_mgr.set_rag_cache(query_text, top3_reranked, ttl=300)

        logger.info("[RAG 2.0] Hybrid Search complete. Vector: %d | BM25: %d | RRF: %d -> Reranked Top-%d (Cached 5m)",
                    len(vec_top10), len(bm25_top10), len(rrf_candidates), len(top3_reranked))
        return top3_reranked

    def evaluate_rag3_canary_decision(self, reranked_sops: list, fleet_count: int = 20) -> dict:
        """
        RAG 3.0 Canary A/B Rollout Decision Evaluator:
        If top 2 candidate SOPs have score delta <= 0.15, tags decision with rollout_mode: 'CANARY_5_PERCENT'.
        """
        from governance.prompt_canary_deployer import PromptCanaryDeployer
        deployer = PromptCanaryDeployer()
        return deployer.evaluate_playbook_canary_rollout(reranked_sops, fleet_size=fleet_count, delta_threshold=0.15)

    # ─────────────────────────────────────────────────────────────────────────
    # LOCAL EMBEDDING FALLBACK
    # Digunakan saat Gemini API tidak tersedia/tidak valid.
    # Menghasilkan pseudo-embedding deterministik dari TF-IDF term weighting
    # sehingga BM25 + RRF masih bisa berjalan tanpa vector similarity.
    # ─────────────────────────────────────────────────────────────────────────
    def _local_embedding_fallback(self, text: str, dim: int = 768) -> list:
        """
        Menghasilkan pseudo-embedding dari teks menggunakan hash + term weighting.
        Tidak seakurat Gemini text-embedding-004, tapi cukup untuk RRF fallback.
        """
        import hashlib, math
        tokens = [w.lower() for w in text.replace('_', ' ').split() if len(w) > 1]
        vec = [0.0] * dim
        for i, token in enumerate(tokens):
            h = int(hashlib.sha256(token.encode()).hexdigest(), 16)
            # IDF-like weight: lebih pendek token = lebih spesifik
            weight = 1.0 / math.log(max(2, len(token)))
            vec[h % dim] += weight * (1.0 / (i + 1))  # positional decay
        # L2-normalize
        norm = math.sqrt(sum(x*x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def _is_gemini_key_valid(self) -> bool:
        """Periksa apakah Gemini API key diisi dengan nilai nyata (bukan placeholder)."""
        key = os.getenv("GEMINI_API_KEY", "")
        return bool(key) and "your_gemini_api_key" not in key and len(key) > 20

    async def embed_and_query_async(self, incident_text: str, limit=3):
        """
        Asynchronous RAG 2.0 Hybrid Search.
        Fallback ke local embedding + BM25 jika Gemini API tidak tersedia.
        """
        from core.cache_manager import get_cache_manager
        cache_mgr = get_cache_manager()
        cached_emb = cache_mgr.get_embedding_cache(incident_text)

        real_embedding = None
        metadata = {"status": "none"}

        if cached_emb:
            real_embedding = cached_emb
            metadata["status"] = "cache_hit"
        elif self._is_gemini_key_valid() and genai is not None:
            # ── Jalur Utama: Gemini API ──────────────────────────────────────
            try:
                api_key = os.getenv("GEMINI_API_KEY", "")
                client = genai.Client(api_key=api_key)
                emb_result = None
                for model_name in ["gemini-embedding-001", "text-embedding-004", "embedding-001"]:
                    try:
                        emb_result = await asyncio.to_thread(
                            client.models.embed_content,
                            model=model_name,
                            contents=incident_text
                        )
                        if emb_result and emb_result.embeddings:
                            break
                    except Exception as model_err:
                        logger.debug(f"[RAG] Model {model_name} failed: {model_err}")
                        emb_result = None

                if emb_result and emb_result.embeddings:
                    import math
                    emb_vals = list(emb_result.embeddings[0].values)
                    if len(emb_vals) > 768:
                        sub = emb_vals[:768]
                        norm = math.sqrt(sum(x*x for x in sub)) or 1.0
                        real_embedding = [x / norm for x in sub]
                    else:
                        real_embedding = emb_vals

                    metadata["status"] = "gemini"
                    cache_mgr.set_embedding_cache(incident_text, real_embedding)
                else:
                    raise ValueError("No embeddings returned from any model candidate")
            except Exception as e:
                logger.warning(f"[RAG] Gemini embedding failed ({e}), switching to local fallback.")
                real_embedding = self._local_embedding_fallback(incident_text)
                metadata["status"] = "local_fallback"
        else:
            # ── Jalur Fallback: Local TF-IDF Pseudo-Embedding ───────────────
            logger.info("[RAG] Gemini API key tidak valid — menggunakan local embedding fallback (BM25 mode).")
            real_embedding = self._local_embedding_fallback(incident_text)
            metadata["status"] = "local_fallback"

        results = await asyncio.to_thread(self.query_hybrid_search, incident_text, real_embedding, limit)
        return {"embedding_vector": real_embedding, "metadata": metadata, "results": results}

    def embed_and_query(self, incident_text: str, limit=3):
        """
        Synchronous RAG 2.0 Hybrid Search.
        Fallback ke local embedding + BM25 jika Gemini API tidak tersedia.
        """
        from core.cache_manager import get_cache_manager
        cache_mgr = get_cache_manager()
        cached_emb = cache_mgr.get_embedding_cache(incident_text)

        real_embedding = None
        metadata = {"status": "none"}

        if cached_emb:
            real_embedding = cached_emb
            metadata["status"] = "cache_hit"
        elif self._is_gemini_key_valid() and genai is not None:
            # ── Jalur Utama: Gemini API ──────────────────────────────────────
            try:
                api_key = os.getenv("GEMINI_API_KEY", "")
                client = genai.Client(api_key=api_key)
                emb_result = None
                for model_name in ["gemini-embedding-001", "text-embedding-004", "embedding-001"]:
                    try:
                        emb_result = client.models.embed_content(
                            model=model_name,
                            contents=incident_text
                        )
                        if emb_result and emb_result.embeddings:
                            break
                    except Exception as model_err:
                        logger.debug(f"[RAG] Model {model_name} failed: {model_err}")
                        emb_result = None

                if emb_result and emb_result.embeddings:
                    import math
                    emb_vals = list(emb_result.embeddings[0].values)
                    if len(emb_vals) > 768:
                        sub = emb_vals[:768]
                        norm = math.sqrt(sum(x*x for x in sub)) or 1.0
                        real_embedding = [x / norm for x in sub]
                    else:
                        real_embedding = emb_vals

                    metadata["status"] = "gemini"
                    cache_mgr.set_embedding_cache(incident_text, real_embedding)
                else:
                    raise ValueError("No embeddings returned from any model candidate")
            except Exception as e:
                logger.warning(f"[RAG] Gemini embedding failed ({e}), switching to local fallback.")
                real_embedding = self._local_embedding_fallback(incident_text)
                metadata["status"] = "local_fallback"
        else:
            # ── Jalur Fallback: Local TF-IDF Pseudo-Embedding ───────────────
            logger.info("[RAG] Gemini API key tidak valid — menggunakan local embedding fallback (BM25 mode).")
            real_embedding = self._local_embedding_fallback(incident_text)
            metadata["status"] = "local_fallback"

        results = self.query_hybrid_search(incident_text, real_embedding, limit=limit)
        return {"embedding_vector": real_embedding, "metadata": metadata, "results": results}

    def ingest_incremental_resolution(self, issue: str, root_cause: str, solution: str, success_rate: float = 1.0) -> Dict[str, Any]:
        """
        Adaptive RAG Incremental Learning (Feature 3):
        Ingests successful incident resolutions {issue, root_cause, solution} into knowledge store
        with a weight proportional to success_rate (e.g. 1.0 - 2.0).
        """
        title = f"Resolution Snippet: {issue[:50]}"
        content = f"Issue: {issue}\nRoot Cause: {root_cause}\nVerified Solution: {solution}\nHistorical Success Rate: {success_rate * 100:.1f}%"
        weight = round(1.0 + float(success_rate), 2) # Weight scale: 1.0 (baseline) to 2.0 (100% success)

        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO validated_knowledge_base (title, category, content, initial_weight, is_approved, created_at)
                    VALUES (%s, 'INCREMENTAL_RESOLUTION', %s, %s, TRUE, NOW())
                    ON CONFLICT DO NOTHING
                """, (title, content, weight))
            conn.commit()
            logger.info(f"[RAG] Incremental knowledge snippet ingested successfully (Weight: {weight}).")
            return {"status": "INGESTED_SUCCESSFULLY", "title": title, "weight": weight}
        except Exception as e:
            conn.rollback()
            logger.error(f"[RAG] Failed to ingest incremental resolution snippet: {e}")
            return {"status": "ERROR", "reason": str(e)}
        finally:
            self._release_connection(conn)


def get_rag_engine():
    return RAGEngine()

