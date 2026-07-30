"""
Enterprise AI OS — Causal Graph Inference Engine
Memanfaatkan Directed Acyclic Graph (DAG) sebagai basis logika deterministik 
untuk mencari Root Cause sebelum menggunakan LLM.
"""

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("CAUSAL_INFERENCE")

class CausalNode:
    def __init__(self, node_id: str, node_type: str, status: str = "UNKNOWN"):
        self.node_id = node_id
        self.node_type = node_type
        self.status = status
        self.parents: List['CausalNode'] = []
        self.children: List['CausalNode'] = []

class CausalGraphEngine:
    def __init__(self):
        # Default causal relationships for well-known failure modes
        self.nodes = {}
        self._build_base_topology()

    def _build_base_topology(self):
        """
        Membangun base dependency graph (DAG) untuk inferensi.
        Contoh:
        CPU Saturation -> Renderer Thread Blocked -> Heartbeat Timeout
        Network Timeout -> API Retry -> Socket Exhaustion
        """
        # Node Definitions
        cpu_sat = self._add_node("cpu_saturation", "RESOURCE")
        renderer_block = self._add_node("renderer_thread_blocked", "PROCESS")
        heartbeat_timeout = self._add_node("heartbeat_timeout", "APPLICATION")
        browser_crash = self._add_node("browser_crash", "APPLICATION")
        
        network_timeout = self._add_node("network_timeout", "NETWORK")
        api_retry = self._add_node("api_retry_storm", "NETWORK")
        socket_exhaust = self._add_node("socket_exhaustion", "OS")
        
        # Edges (Cause -> Effect)
        self._add_edge(cpu_sat, renderer_block)
        self._add_edge(renderer_block, heartbeat_timeout)
        self._add_edge(heartbeat_timeout, browser_crash)
        
        self._add_edge(network_timeout, api_retry)
        self._add_edge(api_retry, socket_exhaust)
        self._add_edge(socket_exhaust, browser_crash)

    def _add_node(self, node_id: str, node_type: str) -> CausalNode:
        if node_id not in self.nodes:
            self.nodes[node_id] = CausalNode(node_id, node_type)
        return self.nodes[node_id]

    def _add_edge(self, cause: CausalNode, effect: CausalNode):
        if effect not in cause.children:
            cause.children.append(effect)
        if cause not in effect.parents:
            effect.parents.append(cause)

    def map_evidence_to_graph(self, incident: Dict[str, Any]) -> List[CausalNode]:
        """Memetakan bukti dari telemetry events ke Node di dalam Causal DAG."""
        active_nodes = []
        events = incident.get("events", [])
        raw_text = str(events).lower()
        
        if "cpu" in raw_text and "high" in raw_text or "saturation" in raw_text:
            active_nodes.append(self.nodes["cpu_saturation"])
        if "timeout" in raw_text and "network" in raw_text:
            active_nodes.append(self.nodes["network_timeout"])
        if "crash" in raw_text or "exception" in raw_text:
            active_nodes.append(self.nodes["browser_crash"])
        if "timeout" in raw_text and "heartbeat" in raw_text:
            active_nodes.append(self.nodes["heartbeat_timeout"])
        if "socket" in raw_text:
            active_nodes.append(self.nodes["socket_exhaustion"])
            
        for node in active_nodes:
            node.status = "ACTIVE"
            
        return active_nodes

    def infer_root_cause(self, incident: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Menyimpulkan akar penyebab dengan menelusuri DAG secara mundur (Backtracking)
        dari node yang berstatus ACTIVE hingga mencapai Root Node (Node tanpa parent yang aktif).
        """
        active_nodes = self.map_evidence_to_graph(incident)
        if not active_nodes:
            return None
            
        # Mencari Root Cause: node yang aktif dan tidak memiliki parent yang aktif
        root_causes = set()
        for node in active_nodes:
            # Jika tidak punya parent, atau semua parent-nya tidak aktif
            has_active_parent = any(p.status == "ACTIVE" for p in node.parents)
            if not has_active_parent:
                root_causes.add(node.node_id)
                
        # Traverse graph untuk membangun causal chain
        chain = self._build_causal_chain(list(root_causes)[0]) if root_causes else []
                
        # Define deterministic remediation actions mapped to known root causes
        remediation_map = {
            "cpu_saturation": "KILL_RESOURCE_HOG_PROCESS",
            "network_timeout": "RESTART_NETWORK_ADAPTER",
            "socket_exhaustion": "FLUSH_SOCKETS_AND_RESTART_SERVICE"
        }
        
        if root_causes:
            primary_rc = list(root_causes)[0]
            remediation = remediation_map.get(primary_rc, "NO_SAFE_AUTO_REMEDIATION_AVAILABLE")
            
            return {
                "inferred_root_cause": primary_rc,
                "causal_chain": chain,
                "remediation": remediation,
                "confidence": 95.0, # Deterministik DAG menghasilkan confidence tinggi
                "method": "CAUSAL_DAG_INFERENCE"
            }
        
        return None
        
    def _build_causal_chain(self, start_node_id: str) -> List[str]:
        chain = [start_node_id]
        current = self.nodes.get(start_node_id)
        while current and current.children:
            # Simple traversal (ambil child pertama yang relevan)
            next_node = None
            for child in current.children:
                if child.status == "ACTIVE":
                    next_node = child
                    break
            
            if next_node:
                chain.append(next_node.node_id)
                current = next_node
            else:
                break
        return chain
