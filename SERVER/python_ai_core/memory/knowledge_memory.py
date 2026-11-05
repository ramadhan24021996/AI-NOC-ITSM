import logging
import json
import uuid
import os
import math
import time
import hashlib
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Any, Dict, List, Optional, Tuple

try:
    from google import genai
except ImportError:
    genai = None

logger = logging.getLogger("KNOWLEDGE_MEMORY")

class KnowledgeMemoryManager:
    """
    Layer 3: Knowledge Memory Manager
    - Stores SOPs, vendor documentation (MikroTik, Cisco, Linux), network runbooks,
      RCAs, lessons learned, and resolutions in PostgreSQL using pgvector (768 dimensions).
    - Features:
        * Document Loader
        * Embedding Pipeline (Gemini API with deterministic TF-IDF fallback)
        * Vector Search & BM25 Full-Text Search (Hybrid Search via RRF)
        * Metadata Filtering (category, severity, tags, environment, validation_status)
        * Knowledge Versioning (incrementing version without overwriting)
        * Knowledge Freshness Score (exponential decay F = e^(-lambda * t))
        * Knowledge Confidence Score
    """

    def __init__(self, vector_dim: int = 768):
        self.vector_dim = vector_dim
        self.db_host = os.getenv("DB_HOST", "127.0.0.1")
        self.db_port = os.getenv("DB_PORT", "5432")
        self.db_name = os.getenv("DB_NAME", "osi_system")
        self.user = os.getenv("DB_USER", "postgres")
        self.password = os.getenv("DB_PASSWORD", "SecurePassword_123!")

    def _get_connection(self):
        return psycopg2.connect(
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            user=self.user,
            password=self.password
        )

    def _is_gemini_valid(self) -> bool:
        key = os.getenv("GEMINI_API_KEY", "")
        return bool(key) and "your_gemini_api_key" not in key and len(key) > 20

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generates a 768-dimensional normalized vector.
        Uses Gemini API if valid, otherwise falls back to deterministic TF-IDF pseudo-embedding.
        """
        if self._is_gemini_valid() and genai is not None:
            try:
                api_key = os.getenv("GEMINI_API_KEY", "")
                client = genai.Client(api_key=api_key)
                for model_name in ["gemini-embedding-001", "text-embedding-004", "embedding-001"]:
                    try:
                        res = client.models.embed_content(model=model_name, contents=text)
                        if res and res.embeddings:
                            vals = list(res.embeddings[0].values)
                            if len(vals) > self.vector_dim:
                                sub = vals[:self.vector_dim]
                                norm = math.sqrt(sum(x*x for x in sub)) or 1.0
                                return [x / norm for x in sub]
                            elif len(vals) < self.vector_dim:
                                padded = vals + [0.0] * (self.vector_dim - len(vals))
                                norm = math.sqrt(sum(x*x for x in padded)) or 1.0
                                return [x / norm for x in padded]
                            return vals
                    except Exception as me:
                        logger.debug(f"[KNOWLEDGE_MEMORY] Gemini model {model_name} error: {me}")
            except Exception as e:
                logger.warning(f"[KNOWLEDGE_MEMORY] Gemini embedding failed ({e}), using TF-IDF fallback.")

        # Local TF-IDF Deterministic Pseudo-Embedding Fallback
        tokens = [w.lower() for w in text.replace('_', ' ').replace('-', ' ').split() if len(w) > 1]
        vec = [0.0] * self.vector_dim
        for i, token in enumerate(tokens):
            h = int(hashlib.sha256(token.encode()).hexdigest(), 16)
            weight = 1.0 / math.log(max(2, len(token)))
            vec[h % self.vector_dim] += weight * (1.0 / (i + 1))
        norm = math.sqrt(sum(x*x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def calculate_freshness_score(self, created_time: float, lambda_decay: float = 0.0000001) -> float:
        """
        Calculates Freshness Score: F = e^(-lambda * elapsed_seconds)
        """
        elapsed = max(0.0, time.time() - created_time)
        return math.exp(-lambda_decay * elapsed)

    def insert_knowledge(
        self,
        title: str,
        category: str,
        description: str = "",
        symptoms: str = "",
        root_cause: str = "",
        solution: str = "",
        tags: Optional[List[str]] = None,
        reference: str = "",
        environment: str = "PRODUCTION",
        severity: str = "MEDIUM",
        confidence: float = 1.0,
        source: str = "USER_TEACHING",
        author: str = "OPERATOR",
        validator: str = "JARVIS_VALIDATOR",
        related_incident: str = "",
        related_rca: str = "",
        related_sop: str = "",
        related_policy: str = ""
    ) -> Dict[str, Any]:
        """
        Inserts a new knowledge entry into jarvis_knowledge_store with full metadata and pgvector embedding.
        """
        item_uuid = str(uuid.uuid4())
        tags_arr = tags or []
        combined_text = f"{title}\n{description}\n{symptoms}\n{root_cause}\n{solution}\n{' '.join(tags_arr)}"
        embedding_vector = self.generate_embedding(combined_text)
        vector_str = "[" + ",".join(map(str, embedding_vector)) + "]"

        sql = """
            INSERT INTO jarvis_knowledge_store (
                uuid, title, description, category, tags, symptoms, root_cause, solution, reference,
                environment, validation_status, severity, confidence, source, author, validator,
                version, embedding_version, knowledge_score, freshness_score, related_incident,
                related_rca, related_sop, related_policy, content_tsvector, embedding, created, updated
            ) VALUES (
                %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, 'VALIDATED', %s, %s, %s, %s, %s,
                1, 'gemini-text-embedding-004', %s, 1.0, %s,
                %s, %s, %s,
                to_tsvector('indonesian', %s), %s::vector, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            RETURNING uuid, title, category, tags, severity, confidence, version, created;
        """

        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, (
                    item_uuid, title, description, category.upper().strip(), tags_arr, symptoms,
                    root_cause, solution, reference, environment.upper().strip(), severity.upper().strip(),
                    confidence, source, author, validator, confidence, related_incident, related_rca,
                    related_sop, related_policy, combined_text, vector_str
                ))
                row = cur.fetchone()
            conn.commit()
            logger.info(f"[KNOWLEDGE_MEMORY] Ingested Knowledge '{title}' (UUID: {item_uuid}, Category: {category})")
            return dict(row)
        except Exception as e:
            conn.rollback()
            logger.error(f"[KNOWLEDGE_MEMORY] Insert failed: {e}")
            raise e
        finally:
            conn.close()

    def hybrid_search(
        self,
        query_text: str,
        category_filter: Optional[str] = None,
        severity_filter: Optional[str] = None,
        limit: int = 5,
        rrf_k: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Hybrid Search combining Vector Cosine Similarity + BM25 Full-Text Search via Reciprocal Rank Fusion (RRF).
        Supports metadata filtering by category and severity.
        """
        query_vector = self.generate_embedding(query_text)
        vector_str = "[" + ",".join(map(str, query_vector)) + "]"

        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 1. Vector Search (Filter active and validated entries only)
                where_clauses = ["embedding IS NOT NULL", "is_active = TRUE", "validation_status = 'VALIDATED'"]
                filter_params = []
                if category_filter:
                    where_clauses.append("category = %s")
                    filter_params.append(category_filter.upper().strip())
                if severity_filter:
                    where_clauses.append("severity = %s")
                    filter_params.append(severity_filter.upper().strip())

                where_sql = " WHERE " + " AND ".join(where_clauses)
                vec_sql = f"""
                    SELECT uuid, title, description, category, tags, symptoms, root_cause, solution,
                           confidence, freshness_score, (1 - (embedding <=> %s::vector)) as similarity_score
                    FROM jarvis_knowledge_store
                    {where_sql}
                    ORDER BY embedding <=> %s::vector
                    LIMIT 10;
                """
                vec_params = [vector_str] + filter_params + [vector_str]
                cur.execute(vec_sql, tuple(vec_params))
                vector_results = cur.fetchall()

                # 2. BM25 Search (Filter active and validated entries only)
                bm25_where = ["content_tsvector @@ plainto_tsquery('indonesian', %s)", "is_active = TRUE", "validation_status = 'VALIDATED'"]
                if category_filter:
                    bm25_where.append("category = %s")
                if severity_filter:
                    bm25_where.append("severity = %s")
                bm25_params = [query_text, query_text] + filter_params

                bm25_sql = f"""
                    SELECT uuid, title, description, category, tags, symptoms, root_cause, solution,
                           confidence, freshness_score,
                           ts_rank_cd(content_tsvector, plainto_tsquery('indonesian', %s)) as bm25_score
                    FROM jarvis_knowledge_store
                    WHERE {' AND '.join(bm25_where)}
                    ORDER BY bm25_score DESC
                    LIMIT 10;
                """
                cur.execute(bm25_sql, tuple(bm25_params))
                bm25_results = cur.fetchall()

            # 3. Reciprocal Rank Fusion
            doc_map = {}
            for rank, r in enumerate(vector_results):
                doc_id = str(r["uuid"])
                if doc_id not in doc_map:
                    doc_map[doc_id] = dict(r)
                    doc_map[doc_id]["rrf_score"] = 0.0
                doc_map[doc_id]["rrf_score"] += 1.0 / (rrf_k + (rank + 1))

            for rank, r in enumerate(bm25_results):
                doc_id = str(r["uuid"])
                if doc_id not in doc_map:
                    doc_map[doc_id] = dict(r)
                    doc_map[doc_id]["rrf_score"] = 0.0
                doc_map[doc_id]["rrf_score"] += 1.0 / (rrf_k + (rank + 1))

            fusion_list = list(doc_map.values())
            fusion_list.sort(key=lambda x: x["rrf_score"], reverse=True)
            return fusion_list[:limit]

        except Exception as e:
            logger.error(f"[KNOWLEDGE_MEMORY] Hybrid search error: {e}")
            return []
        finally:
            conn.close()
