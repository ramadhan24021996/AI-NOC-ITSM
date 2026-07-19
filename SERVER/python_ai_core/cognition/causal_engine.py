"""
Enterprise AI OS — Sprint N: Causal Reasoning Engine
OSI AI Ops

Tujuan:
Membedakan antara "korelasi" (hal yang terjadi bersamaan) 
dan "kausalitas" (hal yang menjadi penyebab hal lain).
Contoh:
Switch Down -> Network Unreachable -> Storage Timeout -> VM Hang -> DB Crash -> App Error.
AI harus tahu bahwa Root Cause adalah Switch, bukan App Error.
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger("CAUSAL_ENGINE")

class CausalReasoningEngine:
    def __init__(self, sdm=None):
        if sdm is None:
            from cognition.service_dependency_map import ServiceDependencyMap
            self.sdm = ServiceDependencyMap()
        else:
            self.sdm = sdm # Service Dependency Map

    def infer_root_cause(self, active_incidents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Causal Graph Traversal
        Mengurutkan rantai sebab-akibat (Cause-Effect Chain)
        """
        logger.info("[CAUSAL ENGINE] Starting Causal Graph Traversal...")
        
        if not active_incidents:
            return {"status": "no_incidents"}
            
        # 1. Map to OSI Layers
        # Physical (L1) -> Data Link (L2) -> Network (L3) -> Transport (L4) 
        # -> Session (L5) -> Presentation (L6) -> Application (L7)
        # Aturan Kausal: Layer yang lebih rendah SELALU menjadi Root Cause 
        # bagi Layer yang lebih tinggi (Top-Down failure).
        
        layer_weights = {
            "L1": 1, "L2": 2, "L3": 3, "L4": 4, 
            "L5": 5, "L6": 6, "L7": 7
        }
        
        deepest_layer = 7
        suspected_root_cause = None
        
        for incident in active_incidents:
            layer = incident.get("osi_layer", "L7") # Default to App layer
            weight = layer_weights.get(layer, 7)
            
            if weight < deepest_layer:
                deepest_layer = weight
                suspected_root_cause = incident
                
        if suspected_root_cause:
            causal_chain = self._build_causal_chain(suspected_root_cause)
            
            logger.info(f"[CAUSAL ENGINE] Root Cause Identified at OSI Layer L{deepest_layer}: {suspected_root_cause.get('component')}")
            
            return {
                "root_cause_incident": suspected_root_cause,
                "causal_chain": causal_chain,
                "explanation": f"Failures at L{deepest_layer} propagate upwards, causing the observed L7 Application errors."
            }
            
        return {"status": "inconclusive"}

    def _build_causal_chain(self, root_incident: Dict[str, Any]) -> str:
        # Build actual DAG causal chain via ServiceDependencyMap
        component = root_incident.get("component", "Unknown")
        involved_services = [component]
        if "affected_components" in root_incident:
            if isinstance(root_incident["affected_components"], list):
                involved_services.extend(root_incident["affected_components"])
            
        correlation = self.sdm.correlate_evidence_to_graph({
            "involved_services": involved_services
        })
        
        chain_list = correlation.get("dependency_chain", [])
        if not chain_list:
            chain_list = involved_services
            
        return " ➔ ".join(str(node) for node in chain_list)

    def _detect_and_break_cycles(self, edges: List[Dict]) -> List[Dict]:
        """
        Tahap Causal DAG v2: Cycle Detection.
        Mendeteksi siklus dalam Directed Graph (DAG) menggunakan DFS dan memutus
        siklus dengan menghapus edge berbobot (weight) terendah.
        """
        from collections import defaultdict
        
        adj = defaultdict(list)
        edge_map = {}
        for idx, e in enumerate(edges):
            u, v = e.get("from"), e.get("to")
            if u and v:
                adj[u].append(v)
                edge_map[(u, v)] = (idx, e.get("weight", 0.5))
                
        visited = set()
        rec_stack = set()
        edges_to_remove = set()
        
        def dfs(node):
            visited.add(node)
            rec_stack.add(node)
            for neighbor in adj[node]:
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    # Cycle detected! (node -> neighbor is a back-edge)
                    logger.warning(f"[CAUSAL DAG v2] Cycle detected between {node} and {neighbor}! Breaking cycle.")
                    idx, _ = edge_map[(node, neighbor)]
                    edges_to_remove.add(idx)
                    return True
            rec_stack.remove(node)
            return False
            
        for n in list(adj.keys()):
            if n not in visited:
                dfs(n)
                
        # Return edges filtering out back-edges
        return [e for i, e in enumerate(edges) if i not in edges_to_remove]

    def _propagate_confidence(self, nodes: List[Dict], edges: List[Dict], root_id: str) -> None:
        """
        Tahap Causal DAG v2: Confidence Propagation & Edge Weighting.
        Menghitung propagated_confidence downstream berdasarkan:
        NodeConfidence = ParentConfidence * EdgeWeight
        """
        from collections import defaultdict, deque
        
        adj = defaultdict(list)
        for e in edges:
            adj[e.get("from")].append((e.get("to"), e.get("weight", 1.0)))
            
        node_map = {n["id"]: n for n in nodes}
        
        # Inisialisasi Root
        if root_id in node_map:
            node_map[root_id]["propagated_confidence"] = node_map[root_id].get("base_confidence", 1.0)
            
        queue = deque([root_id])
        visited = {root_id}
        
        # Tahap 2: Hitung Probabilitas dengan Bayesian Noisy-OR
        # P(Child) = 1 - Product_i(1 - P(Child | Parent_i) * P(Parent_i))
        
        # Track incoming probabilities for each node: list of (P(Child | Parent_i) * P(Parent_i))
        incoming_probs = defaultdict(list)
        
        while queue:
            curr = queue.popleft()
            curr_conf = node_map.get(curr, {}).get("propagated_confidence", 0.0)
            
            for neighbor, weight in adj[curr]:
                if not node_map.get(neighbor): continue
                
                # Independent causal contribution
                contribution = curr_conf * weight
                incoming_probs[neighbor].append(contribution)
                
                # Hitung Bayesian Noisy-OR
                # P = 1 - ( (1 - p1) * (1 - p2) * ... )
                product_not_happening = 1.0
                for p in incoming_probs[neighbor]:
                    product_not_happening *= (1.0 - p)
                
                new_bayes_conf = 1.0 - product_not_happening
                node_map[neighbor]["propagated_confidence"] = round(new_bayes_conf, 3)
                    
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

    async def map_causality(self, telemetry_data: dict) -> dict:
        """
        Causal DAG v2: Dynamically extracts causality, nodes, weighted edges using LLM.
        Applies Cycle Detection and Confidence Propagation.
        """
        import json
        from llm_router import get_router
        
        router = get_router()
        prompt = f"""
        You are an advanced Causal Topology Engine v2. Analyze the following system telemetry.
        Construct a Directed Acyclic Graph (DAG) mapping the Root Cause to its Blast Radius (downstream effects).
        Telemetry: {json.dumps(telemetry_data)}
        
        You MUST provide Edge Weights (0.0 to 1.0) representing the probability of causality.
        You MUST provide Base Confidence (0.0 to 1.0) for the nodes.
        
        Return EXACTLY in this JSON format:
        {{
            "nodes": [
                {{"id": "n1", "label": "Network Switch Down", "type": "root_cause", "base_confidence": 0.95}},
                {{"id": "n2", "label": "DB Timeout", "type": "blast_radius", "base_confidence": 0.80}}
            ],
            "edges": [
                {{"from": "n1", "to": "n2", "weight": 0.90}}
            ],
            "root_id": "n1"
        }}
        """
        
        res = await router.execute_with_retry(75, prompt)
        
        nodes = []
        edges = []
        root_id = "unknown"
        
        if res.get("status") == "SUCCESS":
            try:
                cleaned = str(res.get("response", "")).strip()
                if cleaned.startswith("```"):
                    lines = cleaned.splitlines()
                    if lines[0].startswith("```"): lines = lines[1:]
                    if lines and lines[-1].startswith("```"): lines = lines[:-1]
                    cleaned = "\n".join(lines).strip()
                    
                data = json.loads(cleaned)
                nodes = data.get("nodes", [])
                edges = data.get("edges", [])
                root_id = data.get("root_id", "unknown")
            except Exception as e:
                logger.error(f"[CAUSAL DAG v2] Failed to parse LLM graph: {e}")

        # Fallback if empty
        if not nodes:
            nodes = [{"id": "n1", "label": "Unknown Anomaly", "type": "root_cause", "base_confidence": 0.5}]
            root_id = "n1"
            
        # 1. Cycle Detection & Breaking
        safe_edges = self._detect_and_break_cycles(edges)
        
        # 2. Confidence Propagation
        self._propagate_confidence(nodes, safe_edges, root_id)

        # Temukan label root cause
        root_label = "Unknown Root Cause"
        for n in nodes:
            if n["id"] == root_id:
                root_label = n.get("label", root_label)
                break
                
        return {
            "probable_root_cause": root_label,
            "root_id": root_id,
            "confidence": next((n.get("propagated_confidence", 50.0) * 100 for n in nodes if n["id"] == root_id), 50.0),
            "nodes": nodes,
            "edges": safe_edges
        }

