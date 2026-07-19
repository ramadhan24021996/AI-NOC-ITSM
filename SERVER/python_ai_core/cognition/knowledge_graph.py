from typing import Dict, List, Any, Set, Optional
from dataclasses import dataclass, field
import networkx as nx
from datetime import datetime

@dataclass
class GraphNode:
    node_id: str
    node_type: str  # Server, VM, Switch, Firewall, Storage, Database, Application, Unknown
    properties: Dict[str, Any] = field(default_factory=dict)
    criticality: int = 1
    status: str = "HEALTHY"

@dataclass
class GraphEdge:
    source_id: str
    target_id: str
    relationship: str  # connects_to, uplink, hosted_on, stored_on, depends_on
    confidence: float  # 0.0 to 1.0
    source_engine: str # CMDB, LLDP, SNMP, LLM Inference, Manual

@dataclass
class GraphVersion:
    version_id: int
    timestamp: datetime
    nodes_count: int
    edges_count: int
    disconnected_nodes: int
    coverage_score: float

class DynamicKnowledgeGraph:
    """
    Sprint Q: Dynamic Knowledge Graph
    Sprint Q.5: Enterprise Topology Discovery
    Maintains versioned topology with weighted confidence.
    """
    def __init__(self):
        self.graph = nx.DiGraph()
        self.version_history: List[GraphVersion] = []
        self._current_version_id = 1
        self._last_sync = datetime.now()

    def create_new_version(self):
        disconnected = list(nx.isolates(self.graph))
        total_nodes = self.graph.number_of_nodes()
        coverage = ((total_nodes - len(disconnected)) / total_nodes) * 100 if total_nodes > 0 else 0

        gv = GraphVersion(
            version_id=self._current_version_id,
            timestamp=datetime.now(),
            nodes_count=total_nodes,
            edges_count=self.graph.number_of_edges(),
            disconnected_nodes=len(disconnected),
            coverage_score=coverage
        )
        self.version_history.append(gv)
        self._current_version_id += 1
        self._last_sync = datetime.now()

    def add_node(self, node: GraphNode):
        self.graph.add_node(node.node_id, **node.__dict__)

    def add_edge(self, edge: GraphEdge):
        # Handle Unknown dependency injection
        if edge.target_id.lower() == "unknown":
            unknown_node = GraphNode(node_id=f"unknown_dep_of_{edge.source_id}", node_type="Unknown", properties={"flag": "Need Topology Discovery"})
            self.add_node(unknown_node)
            edge.target_id = unknown_node.node_id
            edge.confidence *= 0.5  # Heavy penalty for unknown

        self.graph.add_edge(edge.source_id, edge.target_id, relationship=edge.relationship, confidence=edge.confidence, source_engine=edge.source_engine)

    def traverse_root_cause(self, symptom_node_id: str) -> List[Dict[str, Any]]:
        """
        Follows dependencies upstream.
        Returns a list of dicts with node and confidence score of the edge traversed.
        """
        if not self.graph.has_node(symptom_node_id):
            return [{"status": "DEGRADED", "error": "node_not_found_in_graph", "target": symptom_node_id}]
        
        path = []
        current = symptom_node_id
        while current:
            path.append({"node": current})
            successors = list(self.graph.successors(current))
            if not successors:
                break
            
            # Sort by highest confidence edge if multiple paths exist
            best_succ = None
            best_conf = -1.0
            for succ in successors:
                edge_data = self.graph.get_edge_data(current, succ)
                if edge_data and edge_data.get("confidence", 0) > best_conf:
                    best_conf = edge_data["confidence"]
                    best_succ = succ
            
            if best_succ:
                path[-1]["next_edge_confidence"] = best_conf
                current = best_succ
            else:
                break
                
        return path

    def calculate_blast_radius(self, failure_node_id: str) -> Dict[str, Any]:
        """
        Calculates downstream impact (descendants) if this node fails.
        """
        if not self.graph.has_node(failure_node_id):
            return {"target": failure_node_id, "impacted_nodes": []}
            
        descendants = list(nx.descendants(self.graph, failure_node_id))
        return {
            "target": failure_node_id,
            "impacted_nodes": descendants
        }

class TopologyDiscoveryEngine:
    """
    Sprint Q.5: Enterprise Topology Discovery
    Agents for LLDP, CDP, SNMP, VMware, K8s, Docker, AD, DB, Service Mesh.
    """
    def __init__(self, graph: DynamicKnowledgeGraph):
        self.graph = graph
        
    def run_lldp_discovery(self):
        return {"status": "DEGRADED", "error": "discovery_agent_unreachable", "agent": "lldp"}
        
    def run_vmware_discovery(self):
        return {"status": "DEGRADED", "error": "discovery_agent_unreachable", "agent": "vmware"}
        
    def run_k8s_discovery(self):
        return {"status": "DEGRADED", "error": "discovery_agent_unreachable", "agent": "k8s"}
        
    def trigger_full_scan(self):
        res = []
        res.append(self.run_lldp_discovery())
        res.append(self.run_vmware_discovery())
        res.append(self.run_k8s_discovery())
        self.graph.create_new_version()
        return res
