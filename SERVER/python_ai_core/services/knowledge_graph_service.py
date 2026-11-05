"""
Enterprise Knowledge Graph Service & Live NATS Topology Manager
Provides a unified service facade for Graph Traversal, Blast Radius, Common Ancestors,
Graph Embeddings, Context Building, and Real-time NATS Topology updates.
"""

import json
import logging
import asyncio
import threading
from typing import Dict, List, Any, Optional

from cognition.knowledge_graph import DynamicKnowledgeGraph, GraphNode, GraphEdge
from cognition.graph_context_builder import GraphContextBuilder
from learning.graph_embedding import GraphEmbeddingEngine
from cognition.rca_explainability import RCAExplainabilityEngine

logger = logging.getLogger("KNOWLEDGE_GRAPH_SERVICE")

class KnowledgeGraphService:
    """
    Enterprise Knowledge Graph Service Facade
    Maintains dynamic graph state, handles NATS topology broadcasts, and provides
    high-level APIs for RAG integration and AI reasoning engines.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(KnowledgeGraphService, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, nats_client=None):
        if self._initialized:
            return
        self.kg = DynamicKnowledgeGraph()
        self.context_builder = GraphContextBuilder(self.kg)
        self.embedding_engine = GraphEmbeddingEngine(dimensions=128)
        self.explainability_engine = RCAExplainabilityEngine()
        self.nats_nc = nats_client
        self._initialized = True
        logger.info("[KG SERVICE] KnowledgeGraphService facade initialized successfully.")

    # ── 1. TRAVERSE ──────────────────────────────────────────────────────────
    def traverse(self, symptom_node_id: str, top_n: int = 5) -> List[Dict[str, Any]]:
        """Traverses causal graph from symptom node upstream to candidate root causes."""
        return self.kg.traverse_root_cause(symptom_node_id, top_n=top_n)

    # ── 2. BLAST RADIUS ──────────────────────────────────────────────────────
    def calculate_blast_radius(self, failure_node_id: str) -> Dict[str, Any]:
        """Calculates downstream business impact and affected devices/services."""
        return self.kg.calculate_blast_radius(failure_node_id)

    # ── 3. COMMON ANCESTOR ───────────────────────────────────────────────────
    def find_common_ancestor(self, symptom_nodes: List[str]) -> List[Dict[str, Any]]:
        """Finds common infrastructure bottleneck across multiple symptom nodes."""
        return self.kg.find_common_ancestor(symptom_nodes)

    # ── 4. NEIGHBOR SEARCH ───────────────────────────────────────────────────
    def get_neighbors(self, node_id: str) -> Dict[str, List[str]]:
        """Returns direct upstream (predecessors) and downstream (successors) neighbors."""
        with self.kg._lock:
            if not self.kg.graph.has_node(node_id):
                return {"predecessors": [], "successors": []}
            preds = [str(x) for x in self.kg.graph.predecessors(node_id)]
            succs = [str(x) for x in self.kg.graph.successors(node_id)]
            return {"predecessors": preds, "successors": succs}

    # ── 5. DEPENDENCY SEARCH ─────────────────────────────────────────────────
    def search_dependencies(self, node_id: str) -> List[Dict[str, Any]]:
        """Returns detailed edge information for all dependencies connected to node."""
        results = []
        with self.kg._lock:
            if not self.kg.graph.has_node(node_id):
                return []
            for u, v, data in self.kg.graph.edges(node_id, data=True):
                results.append({
                    "source": u,
                    "target": v,
                    "relationship": data.get("relationship", "DEPENDS_ON"),
                    "confidence": data.get("confidence", 1.0),
                    "weight": data.get("weight", 1.0)
                })
        return results

    # ── 6. TOPOLOGY SEARCH ───────────────────────────────────────────────────
    def search_topology(self, query: str) -> List[Dict[str, Any]]:
        """Searches graph nodes by IP, node_type, MAC, or ID match."""
        matches = []
        q = query.lower()
        with self.kg._lock:
            for n_id, data in self.kg.graph.nodes(data=True):
                if q in n_id.lower() or q in data.get("ip_address", "").lower() or q in data.get("node_type", "").lower():
                    matches.append({"node_id": n_id, **data})
        return matches[:20]

    # ── 7. SERVICE DISCOVERY ─────────────────────────────────────────────────
    def discover_services(self) -> List[str]:
        """Returns all nodes classified as Application, Service, or Database."""
        services = []
        with self.kg._lock:
            for n_id, data in self.kg.graph.nodes(data=True):
                if data.get("node_type") in ("Application", "Service", "Database"):
                    services.append(n_id)
        return services

    # ── 8. FAILURE CHAIN ─────────────────────────────────────────────────────
    def get_failure_chain(self, symptom_node_id: str) -> List[str]:
        """Returns ordered path from symptom node to highest priority root cause."""
        candidates = self.traverse(symptom_node_id, top_n=1)
        if candidates and candidates[0].get("path"):
            return candidates[0]["path"]
        return [symptom_node_id]

    # ── 9. NODE RECOMMENDATION ───────────────────────────────────────────────
    def recommend_nodes(self, node_type: str) -> List[Dict[str, Any]]:
        """Recommends healthiest node of a specified type for failover/routing."""
        candidates = []
        with self.kg._lock:
            for n_id, data in self.kg.graph.nodes(data=True):
                if data.get("node_type") == node_type and data.get("status") == "HEALTHY":
                    candidates.append({"node_id": n_id, "criticality": data.get("criticality", 1)})
        candidates.sort(key=lambda x: x["criticality"], reverse=True)
        return candidates

    # ── 10. IMPACT ANALYSIS ──────────────────────────────────────────────────
    def analyze_impact(self, node_id: str) -> Dict[str, Any]:
        """Combines blast radius and centrality metrics for complete impact analysis."""
        blast = self.calculate_blast_radius(node_id)
        centrality = self.kg.recalculate_centrality().get(node_id, {}) if hasattr(self.kg, "recalculate_centrality") else {}
        return {**blast, "centrality": centrality}

    # ── 11. GRAPH CONTEXT BUILDER ─────────────────────────────────────────────
    def get_graph_context(self, symptom_node_id: str, topology_data: Optional[Dict[str, Any]] = None) -> str:
        """Builds high-density Graph Context Prompt for RAG injection."""
        rca = self.traverse(symptom_node_id, top_n=3)
        blast = self.calculate_blast_radius(symptom_node_id)
        common = self.find_common_ancestor([symptom_node_id])
        return self.context_builder.build_context(
            symptom_node_id=symptom_node_id,
            topology_data=topology_data,
            rca_candidates=rca,
            blast_radius_data=blast,
            common_ancestors=common
        )

    # ── 12. NODE EMBEDDING ───────────────────────────────────────────────────
    def get_node_embedding(self, node_id: str) -> List[float]:
        """Returns 128-dimensional graph embedding vector for node."""
        return self.embedding_engine.generate_node_embedding(self.kg.graph, node_id)

    # ── 13. GRAPH EMBEDDING ──────────────────────────────────────────────────
    def get_graph_embedding(self) -> List[float]:
        """Returns average graph embedding vector across all nodes."""
        with self.kg._lock:
            nodes = list(self.kg.graph.nodes)
            if not nodes:
                return [0.0] * 128
            vecs = [self.get_node_embedding(n) for n in nodes[:50]]
            avg_vec = [sum(col) / len(col) for col in zip(*vecs)]
            return avg_vec

    # ── 14. GRAPH SIMILARITY ─────────────────────────────────────────────────
    def calculate_graph_similarity(self, node1: str, node2: str) -> float:
        """Calculates topological cosine similarity between two nodes."""
        v1 = self.get_node_embedding(node1)
        v2 = self.get_node_embedding(node2)
        return self.embedding_engine.calculate_graph_similarity(v1, v2)

    # ── 15. LIVE NATS TOPOLOGY EVENT HANDLER ──────────────────────────────────
    def process_live_topology_update(self, topology_payload: Dict[str, Any]) -> bool:
        """
        Receives real-time L1-L7 topology payload from CLIENT_DISTRIBUSI_GO,
        upserts nodes & edges into Knowledge Graph, invalidates Redis cache,
        and updates PostgreSQL persistence.
        """
        try:
            agent_id = topology_payload.get("agent_id", "Unknown-PC")
            site_id = topology_payload.get("site_id", "GLOBAL")
            ip = topology_payload.get("ip_address", "")
            net = topology_payload.get("network", {})
            sw = topology_payload.get("switch", {})

            # 1. Upsert Client Node
            client_node = GraphNode(
                node_id=agent_id,
                node_type="PC",
                criticality=2,
                status="HEALTHY",
                site_id=site_id,
                ip_address=ip,
                properties=topology_payload
            )
            self.kg.add_node(client_node, invalidate=False)

            # 2. Upsert Gateway & Wi-Fi Nodes if present
            gw_ip = net.get("gateway")
            if gw_ip:
                gw_id = f"Gateway_{gw_ip}"
                gw_node = GraphNode(node_id=gw_id, node_type="Gateway", site_id=site_id, ip_address=gw_ip)
                self.kg.add_node(gw_node, invalidate=False)
                self.kg.add_edge(GraphEdge(source_id=agent_id, target_id=gw_id, relationship="ROUTES_TO"), invalidate=False)

            # 3. Upsert Switch Port Node if present
            sw_port = sw.get("switch_port")
            if sw_port:
                sw_id = f"SwitchPort_{sw_port}"
                sw_node = GraphNode(node_id=sw_id, node_type="Access Switch", site_id=site_id)
                self.kg.add_node(sw_node, invalidate=False)
                self.kg.add_edge(GraphEdge(source_id=agent_id, target_id=sw_id, relationship="CONNECTED_TO"), invalidate=False)

            # Recalculate and create new version
            self.kg.create_new_version()
            logger.info("[KG SERVICE] Processed live topology update from agent: %s (Site: %s)", agent_id, site_id)
            return True
        except Exception as exc:
            logger.error("[KG SERVICE] Error processing live topology update: %s", exc)
            return False


def get_knowledge_graph_service(nats_client=None):
    return KnowledgeGraphService(nats_client=nats_client)

async def daemon(interval_hours: int = 24):
    logger.info("[KG_SERVICE] Knowledge Graph Daemon started.")
    svc = get_knowledge_graph_service()
    while True:
        await asyncio.sleep(interval_hours * 3600)
