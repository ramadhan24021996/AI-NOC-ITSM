import logging
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
import json
import os
import asyncio

logger = logging.getLogger("RAG_ENGINE")

class RAGEngine:
    _pool = None

    def __init__(self):
        self.db_host = os.getenv("DB_HOST", "127.0.0.1")
        self.db_port = os.getenv("DB_PORT", "5432")
        self.db_name = os.getenv("DB_NAME", "osi_system")
        self.user = os.getenv("DB_USER", "postgres")
        self.password = os.getenv("DB_PASSWORD", "postgres")
        self.conn = None
        
        # Initialize singleton connection pool
        if RAGEngine._pool is None:
            try:
                RAGEngine._pool = ThreadedConnectionPool(
                    1, 20,
                    host=self.db_host,
                    port=self.db_port,
                    database=self.db_name,
                    user=self.user,
                    password=self.password
                )
                logger.info("RAG Engine connection pool initialized.")
            except Exception as e:
                logger.error(f"Failed to initialize RAG connection pool: {e}")

    def connect(self):
        """Borrow a connection from the pool"""
        if RAGEngine._pool:
            try:
                self.conn = RAGEngine._pool.getconn()
            except Exception as e:
                logger.error(f"Failed to get connection from pool: {e}")

    def close(self):
        """Return the connection to the pool"""
        if self.conn and RAGEngine._pool:
            RAGEngine._pool.putconn(self.conn)
            self.conn = None

    def query_similar_incidents(self, embedding_vector: list, limit=5):
        """
        Queries the knowledge_vectors table for semantic similarity using pgvector.
        Uses <=> operator for Cosine Distance.
        """
        if not self.conn:
            logger.warning("DB not connected. RAG skipping.")
            return [{"status": "DEGRADED", "source": "rag_engine", "error": "db_not_connected"}]
            
        try:
            vector_str = "[" + ",".join(map(str, embedding_vector)) + "]"
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT incident_id, title, symptoms, root_cause, resolution, (1 - (embedding <=> %s)) as similarity_score
                    FROM knowledge_vectors
                    ORDER BY embedding <=> %s
                    LIMIT %s
                """, (vector_str, vector_str, limit))
                
                results = cur.fetchall()
                return [dict(row) for row in results]
                
        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            self.conn.rollback()
            return [{"status": "DEGRADED", "source": "rag_engine", "error": str(e)}]

    async def embed_and_query_async(self, incident_text: str, limit=5):
        """
        Asynchronous wrapper to prevent blocking the AI Supervisor event loop.
        No dummy fallback. If embedding fails, it raises an exception.
        """
        from google import genai
        from core.cache_manager import get_cache_manager
        
        cache_mgr = get_cache_manager()
        cached_emb = cache_mgr.get_embedding_cache(incident_text)
        
        real_embedding = None
        metadata = {"status": "none"}
        
        if cached_emb:
            real_embedding = cached_emb
            metadata["status"] = "cache_hit"
        else:
            # Execute synchronous network call in a separate thread
            try:
                api_key = os.getenv("GEMINI_API_KEY", "")
                client = genai.Client(api_key=api_key)
                emb_result = await asyncio.to_thread(
                    client.models.embed_content,
                    model="text-embedding-004",
                    contents=incident_text
                )
                if emb_result and emb_result.embeddings:
                    real_embedding = emb_result.embeddings[0].values
                else:
                    raise ValueError("No embeddings returned")
                metadata["status"] = "resolved"
                cache_mgr.set_embedding_cache(incident_text, real_embedding)
            except Exception as e:
                logger.error(f"Embedding generation failed. No dummy vector allowed. Error: {e}")
                # Fail fast instead of returning dummy [0.0] vectors which cause hallucinations
                raise ValueError(f"Failed to generate valid embedding for RAG context: {e}")
                
        # Execute DB query in a separate thread
        results = await asyncio.to_thread(self.query_similar_incidents, real_embedding, limit)
        
        return {
            "embedding_vector": real_embedding,
            "metadata": metadata,
            "results": results
        }

    def embed_and_query(self, incident_text: str, limit=5):
        """Legacy synchronous wrapper."""
        from google import genai
        from core.cache_manager import get_cache_manager
        
        cache_mgr = get_cache_manager()
        cached_emb = cache_mgr.get_embedding_cache(incident_text)
        
        real_embedding = None
        metadata = {"status": "none"}
        
        if cached_emb:
            real_embedding = cached_emb
            metadata["status"] = "cache_hit"
        else:
            try:
                api_key = os.getenv("GEMINI_API_KEY", "")
                client = genai.Client(api_key=api_key)
                emb_result = client.models.embed_content(
                    model="text-embedding-004",
                    contents=incident_text
                )
                if emb_result and emb_result.embeddings:
                    real_embedding = emb_result.embeddings[0].values
                else:
                    raise ValueError("No embeddings returned")
                metadata["status"] = "resolved"
                cache_mgr.set_embedding_cache(incident_text, real_embedding)
            except Exception as e:
                logger.error(f"Embedding generation failed: {e}")
                raise ValueError(f"Failed to generate embedding: {e}")
                
        results = self.query_similar_incidents(real_embedding, limit=limit)
        return {
            "embedding_vector": real_embedding,
            "metadata": metadata,
            "results": results
        }

def get_rag_engine():
    return RAGEngine()
