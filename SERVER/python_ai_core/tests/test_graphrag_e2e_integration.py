"""
Production Readiness Test Suite for GraphRAG L1-L7 Enterprise Integration Engine
Validates End-to-End Pipeline:
1. DynamicKnowledgeGraph & Expanded SEMANTIC_EDGE_RULES
2. GraphContextBuilder Prompt Formatting
3. GraphEmbeddingEngine Vector Calculation
4. RCAExplainabilityEngine Report Generation
5. KnowledgeGraphService Facade API
6. RAGEngine Graph Context Injection & Hybrid Search
"""

import unittest
import time
import json
import os
import sys

# Ensure python_ai_core path resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cognition.knowledge_graph import DynamicKnowledgeGraph, GraphNode, GraphEdge, _DB_OFFLINE_CACHE_TS
import cognition.knowledge_graph as kg_mod
kg_mod._DB_OFFLINE_CACHE_TS = time.time()
kg_mod.HAS_REDIS = False


from cognition.graph_context_builder import GraphContextBuilder
from learning.graph_embedding import GraphEmbeddingEngine
from cognition.rca_explainability import RCAExplainabilityEngine
from services.knowledge_graph_service import get_knowledge_graph_service
from engines.rag_engine import RAGEngine
RAGEngine._init_pool = lambda self: None


class TestGraphRAGE2EIntegration(unittest.TestCase):


    def setUp(self):
        self.kg_svc = get_knowledge_graph_service()
        self.kg = self.kg_svc.kg

        # Populate sample L1-L7 Enterprise Topology
        self.kg.add_node(GraphNode(node_id="Client_PC_01", node_type="PC", criticality=2, status="CRITICAL", ip_address="192.168.10.45"))
        self.kg.add_node(GraphNode(node_id="WiFi_AP_Floor1", node_type="Access Point", criticality=3, status="HEALTHY"))
        self.kg.add_node(GraphNode(node_id="Switch_Access_01", node_type="Access Switch", criticality=4, status="DEGRADED"))
        self.kg.add_node(GraphNode(node_id="Gateway_Router_01", node_type="Gateway", criticality=5, status="CRITICAL"))
        self.kg.add_node(GraphNode(node_id="Firewall_Cluster_01", node_type="Firewall Cluster", criticality=5, status="HEALTHY"))
        self.kg.add_node(GraphNode(node_id="DNS_Server_Master", node_type="DNS", criticality=5, status="HEALTHY"))
        self.kg.add_node(GraphNode(node_id="Web_Portal_App", node_type="Application", criticality=4, status="DEGRADED"))

        # Add directed edge relationships
        self.kg.add_edge(GraphEdge(source_id="Client_PC_01", target_id="WiFi_AP_Floor1", relationship="CONNECTED_TO"))
        self.kg.add_edge(GraphEdge(source_id="WiFi_AP_Floor1", target_id="Switch_Access_01", relationship="CONNECTED_VIA"))
        self.kg.add_edge(GraphEdge(source_id="Switch_Access_01", target_id="Gateway_Router_01", relationship="ROUTES_TO"))
        self.kg.add_edge(GraphEdge(source_id="Gateway_Router_01", target_id="Firewall_Cluster_01", relationship="PROXIED_BY"))
        self.kg.add_edge(GraphEdge(source_id="Firewall_Cluster_01", target_id="DNS_Server_Master", relationship="RESOLVED_BY"))
        self.kg.add_edge(GraphEdge(source_id="DNS_Server_Master", target_id="Web_Portal_App", relationship="DEPENDS_ON"))

    def test_01_knowledge_graph_traversal(self):
        rca = self.kg_svc.traverse("Client_PC_01", top_n=3)
        self.assertTrue(len(rca) > 0, "RCA traversal should return candidate root causes")
        top_cause = rca[0]
        self.assertIn("node_id", top_cause)
        self.assertIn("score", top_cause)

    def test_02_graph_context_builder(self):
        context = self.kg_svc.get_graph_context("Client_PC_01")
        self.assertIn("GRAPH CONTEXT INJECTION", context)
        self.assertIn("Client_PC_01", context)

    def test_03_graph_embedding_engine(self):
        emb = self.kg_svc.get_node_embedding("Client_PC_01")
        self.assertEqual(len(emb), 128, "Node embedding vector dimension must be 128")
        sim = self.kg_svc.calculate_graph_similarity("Client_PC_01", "Gateway_Router_01")
        self.assertGreaterEqual(sim, -1.0)
        self.assertLessEqual(sim, 1.0)

    def test_04_rca_explainability(self):
        rca = self.kg_svc.traverse("Client_PC_01", top_n=1)
        blast = self.kg_svc.calculate_blast_radius("Gateway_Router_01")
        report = self.kg_svc.explainability_engine.generate_explainability_report(
            incident_id="INC-1009",
            symptom_node_id="Client_PC_01",
            rca_candidates=rca,
            blast_radius=blast
        )
        self.assertEqual(report["incident_id"], "INC-1009")
        self.assertIn("dependency_chain", report)
        self.assertIn("suggested_fix", report)

    def test_05_live_topology_update(self):
        payload = {
            "agent_id": "Client_PC_02",
            "site_id": "JAKARTA-HQ",
            "ip_address": "192.168.20.15",
            "network": {"gateway": "192.168.20.1", "ssid": "Corp-WiFi"},
            "switch": {"switch_port": "Gi0/12"}
        }
        ok = self.kg_svc.process_live_topology_update(payload)
        self.assertTrue(ok, "Live topology update must process successfully")
        self.assertTrue(self.kg.graph.has_node("Client_PC_02"))
        self.assertTrue(self.kg.graph.has_node("Gateway_192.168.20.1"))

    def test_06_rag_graph_context_injection(self):
        rag = RAGEngine()
        # Mock conn as None to test offline fallback & context injection without DB network delay
        rag.conn = None
        res = rag.embed_and_query("Client_PC_01 Web Portal Timeout", limit=2)
        self.assertIn("graph_context", res)
        self.assertIn("results", res)
        self.assertIn("embedding_vector", res)

if __name__ == "__main__":
    unittest.main()

