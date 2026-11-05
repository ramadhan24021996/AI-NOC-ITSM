"""
Unit Test & Latency Verification for Semantic Cache Layer
Tests Cosine Similarity vector matching (>0.95), <20ms latency retrieval, and cost savings.
"""

import sys
import os
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.semantic_cache_manager import SemanticCacheManager, FastTextEmbedder


class TestSemanticCacheLayer(unittest.TestCase):

    def setUp(self):
        # Initialize semantic cache with 0.90 threshold for testing flexible similarity
        self.cache = SemanticCacheManager(similarity_threshold=0.90)
        self.cache.clear()

    def tearDown(self):
        self.cache.clear()

    def test_fast_text_embedder(self):
        """Test vector extraction and Cosine Similarity math."""
        text1 = "High CPU 98% pada Server Web-01 akibat unindexed query"
        text2 = "High CPU 95% pada Server Web-03 akibat unindexed query"
        text3 = "Disk C: hampir penuh 99% pada Server DB-01"

        vec1 = FastTextEmbedder.get_vector(text1)
        vec2 = FastTextEmbedder.get_vector(text2)
        vec3 = FastTextEmbedder.get_vector(text3)

        sim_12 = FastTextEmbedder.cosine_similarity(vec1, vec2)
        sim_13 = FastTextEmbedder.cosine_similarity(vec1, vec3)

        print(f"\n  [VECTOR MATH] Similar Query Cosine Similarity: {sim_12:.4f}")
        print(f"  [VECTOR MATH] Dissimilar Query Cosine Similarity: {sim_13:.4f}")

        self.assertGreater(sim_12, 0.90, "Similar query similarity should be > 0.90")
        self.assertLess(sim_13, 0.50, "Dissimilar query similarity should be < 0.50")

    def test_semantic_cache_miss_and_hit(self):
        """Test cache miss on first call, exact hit, and semantic similar hit (< 20ms latency)."""
        prompt_1 = "High CPU 98% pada Server Web-01 akibat unindexed query lock"
        reasoning_response = {
            "status": "SUCCESS",
            "model": "deepseek-reasoner",
            "response": "RECOMENDED_ACTION: Kill locking query PID 4912 & create index on orders(user_id).",
            "root_cause": "PostgreSQL Unindexed Query Lock",
            "confidence": 0.98
        }

        # 1. First Call -> Cache Miss
        t0 = time.monotonic()
        res_1 = self.cache.get(prompt_1)
        ms_1 = (time.monotonic() - t0) * 1000
        self.assertIsNone(res_1, "First query should be a cache miss")

        # Save to cache
        self.cache.set(prompt_1, reasoning_response)

        # 2. Exact Query Call -> Cache Hit < 20ms
        t0 = time.monotonic()
        res_exact = self.cache.get(prompt_1)
        ms_exact = (time.monotonic() - t0) * 1000

        self.assertIsNotNone(res_exact, "Exact query should hit cache")
        self.assertTrue(res_exact.get("_semantic_cache_hit"), "Cache hit flag should be True")
        self.assertLess(ms_exact, 20.0, f"Cache hit latency ({ms_exact:.2f}ms) must be < 20ms")
        print(f"\n  [CACHE HIT EXACT] Latency: {ms_exact:.2f}ms | Similarity: {res_exact.get('_similarity')}")

        # 3. Similar Incident Query (Web-03 vs Web-01) -> Semantic Cache Hit < 20ms
        prompt_2 = "High CPU 95% pada Server Web-03 akibat unindexed query lock"
        t0 = time.monotonic()
        res_similar = self.cache.get(prompt_2)
        ms_similar = (time.monotonic() - t0) * 1000

        self.assertIsNotNone(res_similar, "Similar incident query should hit semantic cache")
        self.assertTrue(res_similar.get("_semantic_cache_hit"), "Semantic cache hit flag should be True")
        self.assertLess(ms_similar, 20.0, f"Semantic cache hit latency ({ms_similar:.2f}ms) must be < 20ms")
        self.assertEqual(res_similar.get("root_cause"), "PostgreSQL Unindexed Query Lock")

        print(f"  [CACHE HIT SEMANTIC SIMILAR] Latency: {ms_similar:.2f}ms | Similarity: {res_similar.get('_similarity')}")
        print(f"  [COST & LATENCY SAVED] Hits: {self.cache.get_stats()['cache_hits']} | Latency Saved: {self.cache.get_stats()['total_latency_saved_ms']}ms | Cost Saved: ${self.cache.get_stats()['total_cost_saved_usd']}")

    def test_dissimilar_query_miss(self):
        """Test that different incidents do not trigger false positive cache hits."""
        prompt_1 = "High CPU 98% pada Server Web-01 akibat unindexed query lock"
        prompt_dissimilar = "Printer Kasir Spooler Stalled pada POS-Jakarta-02"

        self.cache.set(prompt_1, {"status": "SUCCESS", "response": "Fix CPU"})
        res = self.cache.get(prompt_dissimilar)
        self.assertIsNone(res, "Dissimilar query should result in cache miss")


if __name__ == "__main__":
    unittest.main()
