import os
import json
import logging
import hashlib
from typing import Optional, List
import redis

logger = logging.getLogger("CACHE_MANAGER")

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

class RedisCacheManager:
    """
    Centralized, resilient Redis-based cache manager for Python AI Core.
    Handles semantic LLM query caching, embedding caching, and database preheating.
    """
    def __init__(self):
        self.redis_client = None
        try:
            redis_sentinel_hosts = os.getenv("REDIS_SENTINEL_HOSTS")
            redis_password = os.getenv('REDIS_PASSWORD')
            
            if redis_sentinel_hosts:
                # HA Sentinel Connection
                from redis.sentinel import Sentinel
                # Expecting format: "sentinel1:26379,sentinel2:26379"
                sentinel_nodes = [tuple(node.split(":")) for node in redis_sentinel_hosts.split(",")]
                sentinel_kwargs = {"password": redis_password} if redis_password else {}
                sentinel = Sentinel(sentinel_nodes, socket_timeout=1, sentinel_kwargs=sentinel_kwargs)
                master_name = os.getenv("REDIS_MASTER_NAME", "mymaster")
                self.redis_client = sentinel.master_for(
                    master_name, 
                    password=redis_password,
                    decode_responses=True,
                    socket_timeout=1,
                    protocol=2
                )
                logger.info("[CACHE] Successfully connected to Redis via Sentinel Cluster.")
            else:
                # Standalone Connection
                self.redis_client = redis.Redis(
                    password=redis_password,
                    host=REDIS_HOST, 
                    port=REDIS_PORT, 
                    decode_responses=True, 
                    socket_timeout=1,
                    protocol=2
                )
                logger.info("[CACHE] Successfully connected to Standalone Redis.")

            if self.redis_client:
                self.redis_client.ping()
                logger.info("[CACHE] Successfully connected to Redis.")
        except Exception as exc:
            logger.warning("[CACHE] Redis unavailable: %s — AI Core caching disabled.", exc)
            self.redis_client = None

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()

    def get_llm_cache(self, prompt: str) -> Optional[dict]:
        if not self.redis_client:
            return None
        try:
            key = f"cache:llm:{self._hash(prompt)}"
            data = self.redis_client.get(key)
            if data:
                logger.info("[CACHE HIT] LLM response retrieved from Redis.")
                return json.loads(data)
        except Exception as exc:
            logger.warning("[CACHE ERROR] Failed to read LLM cache: %s", exc)
        return None

    def set_llm_cache(self, prompt: str, response: dict, ttl: int = 3600) -> bool:
        if not self.redis_client or not response:
            return False
        try:
            key = f"cache:llm:{self._hash(prompt)}"
            self.redis_client.setex(key, ttl, json.dumps(response))
            logger.debug("[CACHE SET] Cached LLM response with TTL=%d", ttl)
            return True
        except Exception as exc:
            logger.warning("[CACHE ERROR] Failed to write LLM cache: %s", exc)
        return False

    def get_embedding_cache(self, text: str) -> Optional[List[float]]:
        if not self.redis_client:
            return None
        try:
            key = f"cache:emb:{self._hash(text)}"
            data = self.redis_client.get(key)
            if data:
                logger.info("[CACHE HIT] Embedding retrieved from Redis.")
                return json.loads(data)
        except Exception as exc:
            logger.warning("[CACHE ERROR] Failed to read embedding cache: %s", exc)
        return None

    def set_embedding_cache(self, text: str, embedding: List[float], ttl: int = 86400) -> bool:
        if not self.redis_client or not embedding:
            return False
        try:
            key = f"cache:emb:{self._hash(text)}"
            self.redis_client.setex(key, ttl, json.dumps(embedding))
            logger.debug("[CACHE SET] Cached embedding with TTL=%d", ttl)
            return True
        except Exception as exc:
            logger.warning("[CACHE ERROR] Failed to write embedding cache: %s", exc)
        return False

    def preheat_embeddings(self, conn) -> int:
        """
        Preheats Redis cache with existing knowledge_vectors embeddings from DB.
        """
        if not self.redis_client or not conn:
            return 0
        
        logger.info("[CACHE PREHEAT] Starting knowledge vectors embedding preheat...")
        count = 0
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT title, symptoms, root_cause, resolution, embedding 
                    FROM knowledge_vectors 
                    WHERE embedding IS NOT NULL
                """)
                rows = cur.fetchall()
                for row in rows:
                    title, symptoms, root_cause, resolution, embedding_str = row
                    
                    # Parse embedding array if stored as string/vector type
                    if isinstance(embedding_str, str):
                        try:
                            embedding = json.loads(embedding_str)
                        except:
                            # Strip brackets and split by comma
                            clean_str = embedding_str.strip("[]")
                            embedding = [float(x) for x in clean_str.split(",") if x.strip()]
                    elif isinstance(embedding_str, list):
                        embedding = embedding_str
                    else:
                        continue
                    
                    # Construct matching text patterns used during RAG or lookup
                    texts_to_cache = [
                        f"Title: {title or ''} Symptoms: {symptoms or ''} Description: ",
                        f"Title: {title or ''} Symptoms: {symptoms or ''} Description: {root_cause or ''}",
                        f"Title: {title or ''} Symptoms: {symptoms or ''} Description: {resolution or ''}"
                    ]
                    
                    for text in texts_to_cache:
                        self.set_embedding_cache(text, embedding, ttl=604800) # Cache for 7 days
                        count += 1
                        
            logger.info("[CACHE PREHEAT] Completed. Cached %d embedding variants.", count)
        except Exception as exc:
            logger.error("[CACHE PREHEAT ERROR] Preheat failed: %s", exc)
            try:
                conn.rollback()
            except:
                import logging; logging.getLogger(__name__).debug('_ = None suppressed')
        return count

# Global Singleton instance
_cache_manager = None

def get_cache_manager() -> RedisCacheManager:
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = RedisCacheManager()
    return _cache_manager
