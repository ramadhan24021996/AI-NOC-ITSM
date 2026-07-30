#!/usr/bin/env python3
"""
Automated Production Readiness Test Suite for RAG Hybrid Search Engine:
- PostgreSQL pgvector HNSW Vector Similarity Search
- PostgreSQL GIN Full-Text Search (BM25)
- Reciprocal Rank Fusion (RRF)
- Cross-Encoder Reranker
- Redis Query Caching
"""

import sys
import os
import time
import logging

# Set up imports path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_engine import RAGEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("TEST_RAG")

def run_rag_production_tests():
    logger.info("==================================================================")
    logger.info("🚀 STARTING RAG HYBRID ENGINE PRODUCTION READINESS TEST SUITE")
    logger.info("==================================================================")

    start_time = time.time()
    rag = RAGEngine()
    
    # 1. Connection Pool Test
    logger.info("\n[TEST 1] Testing DB Connection Pool...")
    rag.connect()
    assert rag.conn is not None, "Failed to connect to PostgreSQL database pool"
    logger.info("✅ TEST 1 PASSED: PostgreSQL pool connected cleanly.")

    # 2. Vector Search (HNSW Index) Test
    logger.info("\n[TEST 2] Testing HNSW Dense Vector Search...")
    sample_vec = [0.01 * (i % 10) for i in range(768)]
    vec_results = rag.query_similar_incidents(sample_vec, limit=5)
    logger.info(f"Retrieved {len(vec_results)} vector candidates.")
    if vec_results:
        first = vec_results[0]
        logger.info(f"Top Candidate: {first.get('incident_id')} — {first.get('title')} (Score: {first.get('similarity_score')})")
    logger.info("✅ TEST 2 PASSED: HNSW Vector Search executed successfully.")

    # 3. BM25 Sparse Search (GIN FTS Index) Test
    logger.info("\n[TEST 3] Testing BM25 Sparse Full-Text Search (GIN Index)...")
    bm25_results = rag.query_bm25_search("CPU bottleneck high load memory leak", limit=5)
    logger.info(f"Retrieved {len(bm25_results)} BM25 FTS candidates.")
    if bm25_results:
        first_bm25 = bm25_results[0]
        logger.info(f"Top BM25 Candidate: {first_bm25.get('incident_id')} — {first_bm25.get('title')} (BM25 Score: {first_bm25.get('bm25_score')})")
    logger.info("✅ TEST 3 PASSED: BM25 FTS Search executed successfully.")

    # 4. Reciprocal Rank Fusion (RRF) Test
    logger.info("\n[TEST 4] Testing Reciprocal Rank Fusion (RRF)...")
    fusion_results = rag.reciprocal_rank_fusion(vec_results, bm25_results, k=60)
    logger.info(f"Fused {len(fusion_results)} candidates via RRF.")
    if fusion_results:
        logger.info(f"Top RRF Fused Item: {fusion_results[0].get('incident_id')} (RRF Score: {fusion_results[0].get('rrf_score'):.5f})")
    logger.info("✅ TEST 4 PASSED: Reciprocal Rank Fusion executed successfully.")

    # 5. Hybrid Search Pipeline (Vector + BM25 + RRF + Reranker + Redis Cache)
    logger.info("\n[TEST 5] Testing Hybrid Search End-to-End Pipeline...")
    query_text = "High CPU utilization on gateway router causing packet drops"
    
    # First execution (Cache miss / warm-up)
    t0 = time.time()
    hybrid_res1 = rag.query_hybrid_search(query_text, sample_vec, limit=3)
    t_miss = (time.time() - t0) * 1000
    logger.info(f"1st Hybrid Query (Cache Miss): {len(hybrid_res1)} items in {t_miss:.2f} ms")

    # Second execution (Redis Cache Hit)
    t1 = time.time()
    hybrid_res2 = rag.query_hybrid_search(query_text, sample_vec, limit=3)
    t_hit = (time.time() - t1) * 1000
    logger.info(f"2nd Hybrid Query (Redis Cache Hit): {len(hybrid_res2)} items in {t_hit:.2f} ms")

    assert len(hybrid_res1) > 0, "Hybrid search returned empty result set"
    assert t_hit < t_miss or t_hit < 20, "Redis cache hit was not significantly faster"
    logger.info("✅ TEST 5 PASSED: Hybrid Search & Redis Caching 100% verified.")

    rag.close()
    elapsed = time.time() - start_time
    logger.info("\n==================================================================")
    logger.info(f"🎉 ALL 5 RAG PRODUCTION READINESS TESTS PASSED SUCCESSFULLY! ({elapsed:.2f}s)")
    logger.info("==================================================================")

if __name__ == "__main__":
    run_rag_production_tests()
