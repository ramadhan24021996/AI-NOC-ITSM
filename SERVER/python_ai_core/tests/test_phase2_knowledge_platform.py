"""
Phase 2 Knowledge Platform Verification Suite
Validates 14-Source Knowledge Aggregation, KEDB/SOP Integration, CMDB Drift Detection, and Telemetry/Log Ingestion.
"""

import unittest
import time
import os
import sys

# Ensure python_ai_core path resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cognition.knowledge_graph import DynamicKnowledgeGraph, GraphNode, GraphEdge, _DB_OFFLINE_CACHE_TS
import cognition.knowledge_graph as kg_mod
kg_mod._DB_OFFLINE_CACHE_TS = time.time()
kg_mod.HAS_REDIS = False

from engines.multi_source_knowledge_aggregator import MultiSourceKnowledgeAggregator
from services.kedb_runbook_service import KEDBRunbookService
from services.cmdb_baseline_service import CMDBBaselineService
from engines.telemetry_log_index_engine import TelemetryLogIndexEngine

class TestPhase2KnowledgePlatform(unittest.TestCase):

    def setUp(self):
        self.aggregator = MultiSourceKnowledgeAggregator()
        self.kedb = KEDBRunbookService()
        self.cmdb = CMDBBaselineService()
        self.telemetry = TelemetryLogIndexEngine()

    def test_01_kedb_and_runbook_search(self):
        matches = self.kedb.search_kedb("HTTP 504 Gateway Timeout")
        self.assertTrue(len(matches) > 0, "KEDB search must return matching error resolutions")
        self.assertEqual(matches[0]["error_code"], "ERR-504")

    def test_02_cmdb_and_drift_detection(self):
        asset = self.cmdb.get_asset("Client_PC_01")
        self.assertIsNotNone(asset, "CMDB asset record must exist")
        
        # Test baseline drift detection
        drifts = self.cmdb.detect_configuration_drift("Client_PC_01", {"dns_servers": ["10.0.0.1"]})
        self.assertTrue(len(drifts) > 0, "Configuration drift must be detected when DNS servers change")
        self.assertEqual(drifts[0]["parameter"], "dns_servers")

    def test_03_telemetry_and_log_query(self):
        logs = self.telemetry.query_logs("Client_PC_01")
        self.assertTrue(len(logs) > 0, "Log index query must return relevant log events")
        metrics = self.telemetry.get_metric_snapshot("Client_PC_01")
        self.assertIn("cpu_usage_pct", metrics)

    def test_04_multi_source_aggregation_14_sources(self):
        result = self.aggregator.aggregate_all_sources(
            symptom_text="Gateway Timeout on Client Access Switch",
            device_name="Client_PC_01",
            topology_context="[GraphRAG Context: Client_PC_01 ➔ Gateway_Router_01]"
        )
        self.assertEqual(result["sources_count"], 14, "Aggregator must fuse 14 knowledge sources")
        self.assertIn("FEDERATED MULTI-SOURCE KNOWLEDGE CONTEXT", result["formatted_context"])
        self.assertIn("ERR-504", result["formatted_context"])

if __name__ == "__main__":
    unittest.main()
