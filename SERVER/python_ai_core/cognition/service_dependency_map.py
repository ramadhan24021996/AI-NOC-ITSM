"""
Enterprise AI OS — OSI Cognitive Framework: Framework 8
Sprint G2: Service Dependency Map (SDM) & Enterprise Knowledge Graph

Tujuan:
Memetakan topologi layanan untuk menghitung Blast Radius dan mendukung Casual Reasoning.
Tidak hanya graf statis, tapi mencatat Evidence dan Confidence Propagation.
"""

import networkx as nx
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("SDM")

class ServiceDependencyMap:
    def __init__(self):
        # Directed graph: A -> B means A depends on B
        self.graph = nx.DiGraph()
        self._initialize_baseline_topology()

    def _initialize_baseline_topology(self):
        """
        Seeding baseline enterprise topology.
        Di skenario nyata, ini di-sync dari CMDB, Kubernetes manifes, atau APM agent.
        """
        # Node format: (ID, attributes)
        nodes = [
            ("Portal", {"type": "Application", "layer": 7}),
            ("API Gateway", {"type": "Service", "layer": 7}),
            ("Authentication", {"type": "Service", "layer": 7}),
            ("Nginx", {"type": "Web Server", "layer": 7}),
            ("Tomcat", {"type": "App Server", "layer": 7}),
            ("Java", {"type": "Runtime", "layer": 7}),
            ("PostgreSQL", {"type": "Database", "layer": 6}),
            ("Redis", {"type": "Database", "layer": 6}),
            ("Storage", {"type": "Infrastructure", "layer": 1}),
        ]
        self.graph.add_nodes_from(nodes)

        # Edges (Dependency mapping)
        edges = [
            ("Portal", "API Gateway"),
            ("Portal", "Nginx"),
            ("API Gateway", "Authentication"),
            ("Authentication", "Redis"),
            ("Nginx", "Tomcat"),
            ("Tomcat", "Java"),
            ("Java", "PostgreSQL"),
            ("PostgreSQL", "Storage"),
            ("Redis", "Storage"),
        ]
        self.graph.add_edges_from(edges)

    def update_dynamic_topology(self, source_node: str, target_node: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Memperbarui Service Dependency Map secara dinamis berdasarkan temuan Auto-Discovery (netstat/eBPF).
        Ini dipanggil oleh AI Core ketika menerima telemetry 'topology_discovery'.
        """
        if not metadata:
            metadata = {}
            
        # Tambahkan node jika belum ada
        if not self.graph.has_node(source_node):
            self.graph.add_node(source_node, type="Dynamic_Component", layer=7)
            logger.info(f"[SDM] Auto-discovered new node: {source_node}")
            
        if not self.graph.has_node(target_node):
            self.graph.add_node(target_node, type="Dynamic_Component", layer=7)
            logger.info(f"[SDM] Auto-discovered new node: {target_node}")

        # Tambahkan edge ketergantungan (source depends on target)
        if not self.graph.has_edge(source_node, target_node):
            self.graph.add_edge(source_node, target_node, **metadata)
            logger.info(f"[SDM] Auto-discovered new dependency: {source_node} -> {target_node}")

    def calculate_blast_radius(self, failing_component: str) -> Dict[str, Any]:
        """
        Menghitung komponen mana saja yang terdampak jika satu komponen mati.
        Blast radius adalah semua node upstream yang bergantung pada node yang mati.
        """
        if failing_component not in self.graph:
            return {"affected_nodes": [], "radius_score": 0, "summary": "Unknown component"}

        # Karena A -> B artinya A depends on B, maka jika B mati, A terdampak.
        # Kita perlu mencari semua node yang bisa mencapai 'failing_component'
        # dengan membalik arah graph (ancestors).
        affected = list(nx.ancestors(self.graph, failing_component))
        
        # Categorize impact
        impact_summary = {"Application": 0, "Service": 0, "Database": 0, "Web Server": 0}
        for node in affected:
            ntype = self.graph.nodes[node].get("type", "Unknown")
            if ntype in impact_summary:
                impact_summary[ntype] += 1
            else:
                impact_summary[ntype] = 1

        return {
            "root_component": failing_component,
            "affected_nodes": affected,
            "radius_score": len(affected),
            "summary": impact_summary
        }

    def correlate_evidence_to_graph(self, correlated_incident: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fase G3: Evidence Graph Mapping.
        Mencocokkan CorrelatedIncident dari G1 dengan SDM untuk menentukan Root Cause Node
        dan melakukan Confidence Propagation.
        """
        involved = correlated_incident.get("involved_services", [])
        if not involved:
            return {"root_cause": "Unknown", "confidence": 0, "chain": []}

        # Cari komponen terdalam (sink) yang mengalami error dari daftar involved
        # Jika Nginx (Error) -> Tomcat -> Java -> PostgreSQL (Error)
        # PostgreSQL adalah root cause karena dia adalah leaf dependency.
        
        # Sederhanakan: filter involved yang benar-benar ada di graph
        valid_nodes = [n for n in involved if n in self.graph]
        if not valid_nodes:
            return {"root_cause": involved[0] if involved else "Unknown", "confidence": 50, "chain": involved}

        # Root cause heuristic: Node yang tidak memiliki edge KELUAR ke node lain dalam daftar `valid_nodes`.
        # (Artinya dia adalah titik terdalam dari kegagalan berantai ini)
        subgraph = self.graph.subgraph(valid_nodes)
        
        root_candidates = []
        for n in subgraph.nodes():
            # out_degree di subgraph: berapa banyak node yang DIA depend di antara node error
            if subgraph.out_degree(n) == 0:
                root_candidates.append(n)

        root_cause = root_candidates[0] if root_candidates else valid_nodes[0]
        
        # Rantai sebab-akibat (dependency chain dari titik masuk ke root cause)
        chain = []
        try:
            # Asumsi valid_nodes[0] adalah entry point (misal Portal/Nginx)
            if valid_nodes[0] != root_cause:
                chain = nx.shortest_path(self.graph, source=valid_nodes[0], target=root_cause)
            else:
                chain = [root_cause]
        except nx.NetworkXNoPath:
            chain = valid_nodes

        # Confidence Propagation
        # Makin panjang rantai evidence logis yang mendukung, makin tinggi confidence.
        base_confidence = 70
        confidence_bonus = len(chain) * 8
        final_confidence = min(98, base_confidence + confidence_bonus)

        return {
            "root_cause_node": root_cause,
            "dependency_chain": chain,
            "propagated_confidence": final_confidence,
            "blast_radius": self.calculate_blast_radius(root_cause)
        }
