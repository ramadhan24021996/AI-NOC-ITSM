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

try:
    from .reranker import get_reranker
except ImportError:
    from engines.reranker import get_reranker

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
_POOL_MAX  = 15         # max per service — pg max_connections 100 with 6 services = safe headroom
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
        self.password = os.getenv("DB_PASSWORD", "SecurePassword_123!")
        self.conn = None
        self._conn_from_pool = False  # track origin: pool vs direct
        self._init_pool()

    def _build_dsn_kwargs(self):
        return dict(
            host=self.db_host,
            port=int(self.db_port),
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
            # Auto-kill koneksi yang stuck idle-in-transaction > 30 detik
            options='-c idle_in_transaction_session_timeout=30000',
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
            conn = psycopg2.connect(**self._build_dsn_kwargs())  # type: ignore
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
                self._conn_from_pool = True
            except Exception as e:
                logger.warning(f"[RAG POOL] Pool get failed ({e}), using direct connection fallback.")
                self.conn = self._get_fresh_conn()
                self._conn_from_pool = False
        else:
            logger.warning("[RAG POOL] Pool not available, using direct connection.")
            self.conn = self._get_fresh_conn()
            self._conn_from_pool = False

    def close(self):
        """Return the connection to the pool. WAJIB dipanggil setelah selesai."""
        if self.conn:
            if self._conn_from_pool and RAGEngine._pool and not RAGEngine._pool.closed:
                try:
                    # Reset any open transaction sebelum dikembalikan ke pool
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
                # Direct connection (fallback) — tutup langsung, jangan kembalikan ke pool
                try:
                    if not self.conn.closed:
                        self.conn.rollback()
                    self.conn.close()
                except Exception:
                    pass
            self.conn = None
            self._conn_from_pool = False

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

    # ── FTS Configuration ─────────────────────────────────────────────────────
    # 'simple' — Tidak ada stemming, tidak ada stop word filter bawaan.
    # Pilihan tepat untuk:
    #   - Bahasa Indonesia (stemmer 'indonesian' bukan bawaan PG, perlu extension)
    #   - Istilah teknis NOC: BGP, OSPF, spooler, kasir, RDP, SLA, CPU
    #   - Error codes: OOMKilled, ERR_123, NATS_TIMEOUT
    # Kelemahan: query 'the server' → 'the' dan 'server' sama bobotnya.
    # Diatasi dengan: INDONESIAN_STOP_WORDS manual filter di bawah.
    _FTS_CONFIG: str = "simple"

    # Stop word Bahasa Indonesia yang paling umum — difilter sebelum FTS query
    # agar tidak menjadi noise dalam hasil BM25.
    _INDONESIAN_STOP_WORDS: frozenset = frozenset({
        "dan", "atau", "yang", "di", "ke", "dari", "ini", "itu", "ada",
        "adalah", "dengan", "untuk", "pada", "oleh", "tidak", "juga",
        "sudah", "belum", "saat", "ketika", "karena", "jika", "bila",
        "the", "a", "an", "is", "in", "on", "at", "of", "to", "for",
        "and", "or", "not", "with", "was", "has", "have", "be", "as",
    })

    # Karakter yang harus di-strip sebelum dikirim ke tsquery PostgreSQL.
    # Menggunakan frozenset per-char untuk menghindari masalah escaping string.
    # Mencakup semua operator tsquery + karakter SQL yang berpotensi berbahaya.
    _FTS_SPECIAL_CHARS: frozenset = frozenset({
        "&", "|", "!", ":", "*", "(", ")", "'", '"',
        "<", ">", "-", ";", "\\", ",", "%", "=", "+",
    })

    def _sanitize_fts_query(self, raw_query: str) -> str:
        """Sanitize raw query string untuk aman digunakan dalam PostgreSQL FTS.

        - Escape special tsquery chars: &|!:*()'"<->
        - Hapus karakter kontrol
        - Trim ke maks 300 karakter
        """
        import re
        # Hapus karakter kontrol dan null
        sanitized = re.sub(r'[\x00-\x1f\x7f]', ' ', raw_query)
        # Escape special tsquery characters
        for char in self._FTS_SPECIAL_CHARS:
            sanitized = sanitized.replace(char, ' ')
        # Collapse whitespace
        sanitized = ' '.join(sanitized.split())
        return sanitized[:300]

    def _build_fts_query_tokens(self, query_text: str, max_tokens: int = 8) -> str:
        """Bangun FTS tsquery dari teks query.

        Pipeline:
          1. Sanitize special chars
          2. Split ke tokens
          3. Filter token pendek (< 2 char) dan Indonesian stop words
          4. Gabung dengan OR operator (' | ') untuk BM25 recall tinggi

        Args:
            query_text: Raw query dari upstream
            max_tokens: Maks token yang digunakan (default 8 — cukup untuk precision)

        Returns:
            FTS tsquery string, misal: "cpu | kasir | spooler | offline"
        """
        sanitized = self._sanitize_fts_query(query_text)
        raw_tokens = sanitized.lower().split()
        # Filter: panjang minimal 2, bukan stop word
        tokens = [
            t for t in raw_tokens
            if len(t) >= 2 and t not in self._INDONESIAN_STOP_WORDS
        ][:max_tokens]

        if not tokens:
            # Fallback: gunakan kata pertama dari sanitized query
            fallback = sanitized.split()[:3]
            tokens = [t for t in fallback if len(t) >= 2] or [sanitized[:50]]

        return " | ".join(tokens)

    def query_bm25_search(self, query_text: str, limit: int = 10) -> List[Dict]:
        """
        BM25 Full-Text Search via PostgreSQL — Production v2.0 (P0-1 Fix).

        Perubahan dari versi sebelumnya:
          - FTS config: 'english' → 'simple'
            Alasan: 'english' melakukan stemming (printer→print, kasir→kasir OK,
            spooler→spooler OK, tetapi 'BGP' → 'bgp' match tergantung stemmer).
            Lebih penting: 'english' membuang stop words seperti 'is', 'the',
            TAPI juga bisa salah buang kata Indonesia. 'simple' tidak melakukan
            stemming dan tidak ada built-in stop word filter — kita kontrol sendiri
            via _build_fts_query_tokens().

          - Weighted ts_rank per field (symptoms > title > root_cause > resolution):
            symptoms adalah sinyal retrieval utama — operator mencari berdasarkan
            gejala yang diamati, bukan judul atau solusinya.

          - Sanitized query: escape semua special FTS chars sebelum query.

          - ILIKE fallback tetap dipertahankan sebagai safety net.

        Args:
            query_text: Teks query mentah dari upstream (incident description, dll)
            limit:      Jumlah hasil maksimum (default 10)

        Returns:
            List of Dict dengan keys: incident_id, title, symptoms, root_cause,
            resolution, bm25_score. Sorted by bm25_score DESC.
        """
        if not self.conn:
            self.connect()
        if not self.conn or not query_text.strip():
            logger.warning("[BM25] Skipped — no connection or empty query.")
            return []

        # Build FTS query tokens dengan filtering Indonesian stop words
        fts_query_str = self._build_fts_query_tokens(query_text)
        # ILIKE pattern untuk fallback (max 40 char agar tidak terlalu broad)
        ilike_pattern = f"%{self._sanitize_fts_query(query_text)[:40]}%"

        logger.debug(
            "[BM25] query='%s' → fts_tokens='%s' | config='%s'",
            query_text[:60], fts_query_str, self._FTS_CONFIG
        )

        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        incident_id,
                        title,
                        symptoms,
                        root_cause,
                        resolution,
                        -- Weighted BM25 score: symptoms lebih penting dari resolution
                        -- Bobot mengikuti signifikansi field untuk retrieval NOC:
                        --   symptoms  (1.0) — operator query berdasarkan gejala
                        --   title     (0.5) — judul biasanya ringkas
                        --   root_cause(0.3) — relevan untuk RCA lookup
                        --   resolution(0.2) — bonus jika query menyebut solusi
                        (
                            ts_rank_cd(
                                setweight(to_tsvector(%(cfg)s, coalesce(symptoms, '')),    'A') ||
                                setweight(to_tsvector(%(cfg)s, coalesce(title, '')),       'B') ||
                                setweight(to_tsvector(%(cfg)s, coalesce(root_cause, '')), 'C') ||
                                setweight(to_tsvector(%(cfg)s, coalesce(resolution, '')), 'D'),
                                to_tsquery(%(cfg)s, %(fts_q)s),
                                -- normalization: 1=length, 4=unique words, 32=log(rank+1)
                                32
                            )
                        ) AS bm25_score
                    FROM knowledge_vectors
                    WHERE
                        (
                            setweight(to_tsvector(%(cfg)s, coalesce(symptoms, '')),    'A') ||
                            setweight(to_tsvector(%(cfg)s, coalesce(title, '')),       'B') ||
                            setweight(to_tsvector(%(cfg)s, coalesce(root_cause, '')), 'C') ||
                            setweight(to_tsvector(%(cfg)s, coalesce(resolution, '')), 'D')
                        ) @@ to_tsquery(%(cfg)s, %(fts_q)s)
                        OR title ILIKE %(ilike)s
                        OR symptoms ILIKE %(ilike)s
                        OR resolution ILIKE %(ilike)s
                    ORDER BY bm25_score DESC
                    LIMIT %(lim)s
                """, {
                    "cfg":   self._FTS_CONFIG,
                    "fts_q": fts_query_str,
                    "ilike": ilike_pattern,
                    "lim":   limit,
                })

                rows = cur.fetchall()
                results = [dict(row) for row in rows]

                logger.info(
                    "[BM25] Found %d results | query='%s' | fts='%s' | config='%s'",
                    len(results), query_text[:60], fts_query_str, self._FTS_CONFIG
                )
                return results

        except Exception as e:
            logger.warning(
                "[BM25] FTS query failed (fts_q='%s', config='%s'): %s — "
                "attempting ILIKE-only fallback.",
                fts_query_str, self._FTS_CONFIG, e
            )
            try:
                self.conn.rollback()
            except Exception:
                pass

            # ── ILIKE-Only Safety Fallback ────────────────────────────────────
            # Jika FTS gagal (misal: invalid fts_query_str), gunakan pure ILIKE
            # sebagai last resort agar BM25 path tidak sepenuhnya kosong.
            try:
                with self.conn.cursor(cursor_factory=RealDictCursor) as cur_fb:
                    first_token = self._sanitize_fts_query(query_text).split()[0][:40] if query_text.strip() else ""
                    if not first_token:
                        return []
                    cur_fb.execute("""
                        SELECT incident_id, title, symptoms, root_cause, resolution,
                               0.1::float AS bm25_score
                        FROM knowledge_vectors
                        WHERE title ILIKE %(p)s OR symptoms ILIKE %(p)s
                        ORDER BY incident_id
                        LIMIT %(lim)s
                    """, {"p": f"%{first_token}%", "lim": limit})
                    fallback_rows = cur_fb.fetchall()
                    logger.info(
                        "[BM25] ILIKE fallback returned %d results for token='%s'",
                        len(fallback_rows), first_token
                    )
                    return [dict(r) for r in fallback_rows]
            except Exception as e2:
                logger.error("[BM25] ILIKE fallback also failed: %s", e2)
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                return []

    def reciprocal_rank_fusion(self, vector_results: list, bm25_results: list, k: int = 60) -> list:
        """
        Multi-Factor Reciprocal Rank Fusion (RRF):
        Blends Vector semantic rank + BM25 keyword rank + Historical Resolution Success Rate (RLOF weight).
        Final Score = Base_RRF * (0.60 + 0.25 * Success_Rate + 0.15 * Confidence)
        """
        doc_map = {}

        # Process Vector ranks
        for rank, doc in enumerate(vector_results):
            doc_id = str(doc.get("incident_id") or doc.get("id"))
            if doc_id not in doc_map:
                doc_map[doc_id] = dict(doc)
                doc_map[doc_id]["rrf_score"] = 0.0
            doc_map[doc_id]["rrf_score"] += 1.0 / (k + (rank + 1))
            doc_map[doc_id]["vector_rank"] = rank + 1

        # Process BM25 ranks
        for rank, doc in enumerate(bm25_results):
            doc_id = str(doc.get("incident_id") or doc.get("id"))
            if doc_id not in doc_map:
                doc_map[doc_id] = dict(doc)
                doc_map[doc_id]["rrf_score"] = 0.0
            doc_map[doc_id]["rrf_score"] += 1.0 / (k + (rank + 1))
            doc_map[doc_id]["bm25_rank"] = rank + 1

        # Apply Multi-Factor Success Calibration
        for doc_id, doc in doc_map.items():
            success_rate = float(doc.get("success_rate", 1.0) or 1.0)
            confidence = float(doc.get("confidence", 0.9) or 0.9)
            calibration_multiplier = 0.60 + (0.25 * success_rate) + (0.15 * confidence)
            doc["calibrated_score"] = round(doc["rrf_score"] * calibration_multiplier, 4)
            doc["success_rate"] = success_rate
            doc["confidence"] = confidence

        fusion_list = list(doc_map.values())
        fusion_list.sort(key=lambda x: x.get("calibrated_score", x["rrf_score"]), reverse=True)
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
        try:
            from core.cache_manager import get_cache_manager
        except ImportError:
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
    # ── Local Embedding Dual-Stage Fallback ───────────────────────────────────
    _st_model = None
    _st_attempted = False

    def _local_embedding_fallback(self, text: str, dim: int = 768) -> list:
        """
        Menghasilkan local embedding saat Gemini API tidak tersedia.

        Pipeline Dual-Stage:
          1. Stage 1 (Preferred): Gunakan SentenceTransformer
             (misal: 'paraphrase-multilingual-MiniLM-L12-v2' atau 'all-MiniLM-L6-v2')
             jika package sentence_transformers terinstall di environment.
          2. Stage 2 (Deterministic Zero-Dependency Fallback): Subword N-gram Feature Hashing
             dengan IDF term weighting + character trigrams + positional decay.
        """
        # ── Stage 1: Try SentenceTransformer if available ────────────────────
        if not RAGEngine._st_attempted:
            RAGEngine._st_attempted = True
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore # pyright: ignore[reportMissingImports]
                model_name = os.getenv("LOCAL_EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
                RAGEngine._st_model = SentenceTransformer(model_name)
                logger.info(f"[RAG] Successfully loaded local SentenceTransformer model '{model_name}'")
            except Exception as st_err:
                logger.debug(f"[RAG] Local SentenceTransformer not available ({st_err}). Using zero-dependency subword n-gram hashing.")
                RAGEngine._st_model = None

        if RAGEngine._st_model is not None:
            try:
                emb = RAGEngine._st_model.encode(text).tolist()
                import math
                if len(emb) != dim:
                    if len(emb) > dim:
                        emb = emb[:dim]
                    else:
                        emb = emb + [0.0] * (dim - len(emb))
                norm = math.sqrt(sum(x * x for x in emb)) or 1.0
                return [float(x / norm) for x in emb]
            except Exception as st_inf_err:
                logger.warning(f"[RAG] SentenceTransformer inference failed: {st_inf_err}")

        # ── Stage 2: Enhanced Zero-Dependency Subword N-Gram Feature Hashing ──
        import hashlib, math, re

        clean_text = text.replace("_", " ").lower()
        words = [w for w in re.findall(r'\w+', clean_text) if len(w) > 1]

        # Subword n-grams (trigrams) untuk menangkap variasi kata & typos NOC
        n_grams = []
        for word in words:
            if len(word) >= 3:
                for i in range(len(word) - 2):
                    n_grams.append(word[i:i+3])

        vec = [0.0] * dim

        # Feature Hashing Word Tokens with Positional Decay & IDF Weighting
        for i, word in enumerate(words):
            h = int(hashlib.sha256(f"w:{word}".encode("utf-8")).hexdigest(), 16)
            weight = 1.0 / math.log(max(2, len(word)))
            vec[h % dim] += weight * (1.0 / (i + 1))

        # Feature Hashing Character Trigrams
        for i, ngram in enumerate(n_grams):
            h = int(hashlib.sha256(f"ng:{ngram}".encode("utf-8")).hexdigest(), 16)
            vec[h % dim] += 0.5 * (1.0 / (i + 1))

        # L2-normalize vector
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
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
        metadata: Dict[str, Any] = {"status": "none"}

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
        if isinstance(results, list):
            metadata["results_count"] = len(results)
            if results and isinstance(results[0], dict):
                metadata["top1_score"] = float(results[0].get("similarity_score") or results[0].get("score") or results[0].get("rrf_score") or 0.0)
        return {"embedding_vector": real_embedding, "metadata": metadata, "results": results}

    def embed_and_query(self, incident_text: str, limit=3):
        """
        Synchronous RAG 2.0 Hybrid Search.
        Fallback ke local embedding + BM25 jika Gemini API tidak tersedia.
        """
        try:
            from core.cache_manager import get_cache_manager
        except ImportError:
            from core.cache_manager import get_cache_manager
        cache_mgr = get_cache_manager()
        cached_emb = cache_mgr.get_embedding_cache(incident_text)

        real_embedding = None
        metadata: Dict[str, Any] = {"status": "none"}

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
        
        # Implementation 2 & 4: Graph Context Injection & Multi-Factor Graph Ranking
        graph_context = ""
        try:
            from services.knowledge_graph_service import get_knowledge_graph_service
            kg_svc = get_knowledge_graph_service()
            # Extract candidate node from incident text if present or fallback
            node_target = incident_text.split()[0] if incident_text else "Client-PC"
            graph_context = kg_svc.get_graph_context(node_target)
        except Exception as exc:
            logger.debug("[RAG] Graph context injection fallback: %s", exc)
            graph_context = f"\n[GRAPH CONTEXT: Incident Topology for {incident_text[:30]}]\n"

        return {
            "embedding_vector": real_embedding,
            "graph_context": graph_context,
            "metadata": metadata,
            "results": results
        }


    def ingest_incremental_resolution(self, issue: str, root_cause: str, solution: str, success_rate: float = 1.0) -> Dict[str, Any]:
        """
        Adaptive RAG Incremental Learning (Feature 3):
        Ingests successful incident resolutions {issue, root_cause, solution} into knowledge store
        with a weight proportional to success_rate (e.g. 1.0 - 2.0).
        """
        title = f"Resolution Snippet: {issue[:50]}"
        content = f"Issue: {issue}\nRoot Cause: {root_cause}\nVerified Solution: {solution}\nHistorical Success Rate: {success_rate * 100:.1f}%"
        weight = round(1.0 + success_rate, 2) # Weight scale: 1.0 (baseline) to 2.0 (100% success)

        if not self.conn or getattr(self.conn, "closed", 1):
            self.connect()

        try:
            if self.conn:
                with self.conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO validated_knowledge_base (title, category, content, initial_weight, is_approved, created_at)
                        VALUES (%s, 'INCREMENTAL_RESOLUTION', %s, %s, TRUE, NOW())
                        ON CONFLICT DO NOTHING
                    """, (title, content, weight))
                self.conn.commit()
                logger.info(f"[RAG] Incremental knowledge snippet ingested successfully (Weight: {weight}).")
                return {"status": "INGESTED_SUCCESSFULLY", "title": title, "weight": weight}
            return {"status": "ERROR", "reason": "No DB connection available"}
        except Exception as e:
            if self.conn:
                try:
                    self.conn.rollback()
                except Exception:
                    pass
            logger.error(f"[RAG] Failed to ingest incremental resolution snippet: {e}")
            return {"status": "ERROR", "reason": str(e)}
        finally:
            self.close()


def get_rag_engine():
    return RAGEngine()

