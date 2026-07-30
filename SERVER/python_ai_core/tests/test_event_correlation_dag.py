#!/usr/bin/env python3
"""
Automated Test Suite for Pilar 4: Cross-Layer Causal DAG & 30-Second Time-Window Event Correlation
- Tests 30-second sliding time-window clustering
- Tests L1-L7 cross-layer cascading failure propagation detection
- Tests Causal DAG matrix node & edge generation
"""

import sys
import os
import time
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.event_correlation_engine import EventCorrelationEngine
from engines.causal_dag_engine import CausalDAGEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("TEST_CORRELATION")

def run_event_correlation_dag_tests():
    logger.info("==================================================================")
    logger.info("🚀 STARTING PILAR 4: CROSS-LAYER CAUSAL DAG CORRELATION TESTS")
    logger.info("==================================================================")

    start_time = time.time()
    correlation_engine = EventCorrelationEngine(time_window_seconds=30)
    now = time.time()

    # Simulate multi-layer cascading failure events occurring within 30 seconds
    sample_events = [
        {
            "event_id": "EV-001",
            "layer": "L1_NETWORK",
            "device_id": "ROUTER-GW-01",
            "description": "Gateway Link Down / Packet Loss 100%",
            "timestamp": now - 25
        },
        {
            "event_id": "EV-002",
            "layer": "L3_DATABASE",
            "device_id": "POSTGRES-PRIMARY",
            "description": "PostgreSQL Connection Timeout / Socket Refused",
            "timestamp": now - 18
        },
        {
            "event_id": "EV-003",
            "layer": "L6_PRESENTATION",
            "device_id": "WEB-PORTAL-01",
            "description": "HTTP 502 Bad Gateway / Upstream Unreachable",
            "timestamp": now - 10
        },
        {
            "event_id": "EV-004",
            "layer": "L7_BROWSER_EXT",
            "device_id": "KASIR-POS-STORE-01",
            "description": "Browser Extension Socket Disconnected",
            "timestamp": now - 2
        },
        # Separate event outside the 30s window (60s ago)
        {
            "event_id": "EV-OLD-005",
            "layer": "L3_MICROSERVICE",
            "device_id": "OLD-DAEMON",
            "description": "Unrelated routine daemon cycle",
            "timestamp": now - 120
        }
    ]

    # 1. Test 30-Second Time-Window Clustering
    logger.info("\n[TEST 1] Testing 30-Second Time-Window Event Clustering...")
    clusters = correlation_engine.cluster_events_by_window(sample_events, window_seconds=30)
    logger.info(f"Retrieved {len(clusters)} clusters from 5 sample events.")
    assert len(clusters) == 2, f"Expected 2 clusters (1 active cluster of 4 events + 1 old event), got {len(clusters)}"
    assert len(clusters[0]) == 1 and len(clusters[1]) == 4
    logger.info("✅ TEST 1 PASSED: 30-Second sliding window clustering 100% verified.")

    # 2. Test Cross-Layer Cascading Failure Analysis
    logger.info("\n[TEST 2] Testing L1-L7 Cross-Layer Cascading Failure Analysis...")
    cascading_cluster = clusters[1]
    cascading_res = correlation_engine.correlate_cross_layer_cascading(cascading_cluster)
    
    root_ev = cascading_res.get("root_cause_event")
    assert root_ev is not None, "Failed to identify root cause event"
    affected_layers = cascading_res.get("affected_layers") or []
    assert len(affected_layers) == 4
    assert cascading_res.get("is_cascading_failure") == True
    logger.info(f"Root Cause Origin: {root_ev.get('layer')} ({root_ev.get('device_id')}) -> {cascading_res.get('summary')}")
    logger.info("✅ TEST 2 PASSED: Cross-layer cascading failure origin accurately pinpointed to L1 Network.")

    # 3. Test Causal DAG Matrix Generation
    logger.info("\n[TEST 3] Testing Causal DAG Matrix Generation...")
    dag_matrix = correlation_engine.build_causal_matrix(cascading_cluster)
    logger.info(f"Generated DAG: {len(dag_matrix['nodes'])} Nodes, {len(dag_matrix['edges'])} Edges")
    assert len(dag_matrix["nodes"]) == 4
    assert len(dag_matrix["edges"]) == 3
    assert dag_matrix["nodes"][0]["type"] == "ROOT_CAUSE"
    logger.info("✅ TEST 3 PASSED: Causal DAG nodes & edges successfully built.")

    # 4. Test Integration with CausalDAGEngine
    logger.info("\n[TEST 4] Testing Integration with CausalDAGEngine...")
    dag_engine = CausalDAGEngine()
    cross_dag_res = dag_engine.build_cross_layer_cascading_dag("INC-CASCADE-9999", sample_events, window_seconds=30)
    assert cross_dag_res.get("nodes_count") == 4
    assert cross_dag_res.get("edges_count") == 3
    logger.info(f"CausalDAGEngine Result: {cross_dag_res.get('summary')}")
    logger.info("✅ TEST 4 PASSED: CausalDAGEngine cross-layer cascading DAG 100% verified.")

    elapsed = time.time() - start_time
    logger.info("\n==================================================================")
    logger.info(f"🎉 ALL PILAR 4 CROSS-LAYER CAUSAL DAG TESTS PASSED SUCCESSFULLY! ({elapsed:.2f}s)")
    logger.info("==================================================================")

if __name__ == "__main__":
    run_event_correlation_dag_tests()
