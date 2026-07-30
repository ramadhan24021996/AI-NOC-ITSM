"""
Phase 15: Unit, Integration, Stress, and Chaos Test Suite for Enterprise Knowledge Graph
Coverage Target: >95%
"""

import sys
import os
import time
import unittest
from datetime import datetime, timezone

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

try:
    from cognition.knowledge_graph import (
        DynamicKnowledgeGraph,
        GraphNode,
        GraphEdge,
        TopologyDiscoveryEngine,
        SEMANTIC_EDGE_RULES
    )
except ImportError:
    from SERVER.python_ai_core.cognition.knowledge_graph import (
        DynamicKnowledgeGraph,
        GraphNode,
        GraphEdge,
        TopologyDiscoveryEngine,
        SEMANTIC_EDGE_RULES
    )


class TestEnterpriseKnowledgeGraph(unittest.TestCase):

    def setUp(self):
        self.kg = DynamicKnowledgeGraph()
        
        # Build test topology
        # Core Router -> Switch A -> DB Master -> App Web
        self.kg.add_node(GraphNode(node_id="Core_Router_01", node_type="Switch", criticality=5, status="HEALTHY"))
        self.kg.add_node(GraphNode(node_id="Switch_Site_A", node_type="Switch", criticality=4, status="HEALTHY"))
        self.kg.add_node(GraphNode(node_id="DB_Master_01", node_type="Database", criticality=5, status="CRITICAL"))
        self.kg.add_node(GraphNode(node_id="App_Server_01", node_type="Application", criticality=3, status="DEGRADED"))
        self.kg.add_node(GraphNode(node_id="App_Server_02", node_type="Application", criticality=3, status="DEGRADED"))

        self.kg.add_edge(GraphEdge(source_id="App_Server_01", target_id="DB_Master_01", relationship="DEPENDS_ON", confidence=0.95))
        self.kg.add_edge(GraphEdge(source_id="App_Server_02", target_id="DB_Master_01", relationship="DEPENDS_ON", confidence=0.90))
        self.kg.add_edge(GraphEdge(source_id="DB_Master_01", target_id="Switch_Site_A", relationship="CONNECTED_TO", confidence=0.98))
        self.kg.add_edge(GraphEdge(source_id="Switch_Site_A", target_id="Core_Router_01", relationship="CONNECTED_TO", confidence=0.99))

    def test_multi_path_rca(self):
        """Phase 1: Multi-path probabilistic RCA test"""
        results = self.kg.traverse_root_cause(symptom_node_id="App_Server_01", top_n=3)
        self.assertTrue(len(results) > 0)
        top_cause = results[0]
        self.assertIn("node_id", top_cause)
        self.assertIn("score", top_cause)
        self.assertIn("confidence", top_cause)
        self.assertIn("blast_radius", top_cause)
        self.assertIn("evidence", top_cause)

    def test_common_cause_analysis(self):
        """Phase 3: Common Cause Analysis test"""
        common_causes = self.kg.find_common_ancestor(symptom_nodes=["App_Server_01", "App_Server_02"])
        self.assertTrue(len(common_causes) > 0)
        candidate_ids = [c["node_id"] for c in common_causes]
        self.assertIn("DB_Master_01", candidate_ids)

    def test_blast_radius_engine(self):
        """Phase 5: Blast Radius calculation test"""
        blast = self.kg.calculate_blast_radius("DB_Master_01")
        self.assertIn("severity_score", blast)
        self.assertIn("affected_devices", blast)
        self.assertIn("affected_services", blast)
        self.assertIn("business_impact", blast)
        self.assertTrue(blast["severity_score"] > 0)

    def test_semantic_edge_rules(self):
        """Phase 6: Semantic Edge rules verification"""
        self.assertIn("DEPENDS_ON", SEMANTIC_EDGE_RULES)
        self.assertIn("HOSTED_ON", SEMANTIC_EDGE_RULES)
        self.assertIn("POWERED_BY", SEMANTIC_EDGE_RULES)

    def test_counterfactual_validation(self):
        """Phase 8: Counterfactual Validation test"""
        is_valid = self.kg.validate_counterfactual("App_Server_01", "DB_Master_01")
        self.assertIsInstance(is_valid, bool)

    def test_feedback_learning(self):
        """Phase 9: Feedback Learning test"""
        ok = self.kg.record_feedback(
            incident_id="INC_1001",
            candidate_node_id="DB_Master_01",
            feedback_type="CORRECT",
            reviewer="NOC_ENGINEER",
            notes="Root cause verified as DB connection pool exhaustion"
        )
        self.assertTrue(ok)

    def test_topology_discovery(self):
        """Phase 12: Real Topology Discovery test"""
        discovery = TopologyDiscoveryEngine(self.kg)
        scan_res = discovery.trigger_full_scan()
        self.assertEqual(len(scan_res), 4)

    def test_benchmark_performance(self):
        """Phase 14: Benchmark Performance sub-300ms SLA test"""
        start = time.time()
        for _ in range(10):
            self.kg.traverse_root_cause("App_Server_01", top_n=3)
        duration = (time.time() - start) / 10.0
        self.assertLess(duration, 0.30)  # Sub 300ms threshold


if __name__ == "__main__":
    unittest.main()
