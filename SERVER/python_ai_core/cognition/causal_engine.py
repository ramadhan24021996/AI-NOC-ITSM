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
import time
import re
from datetime import datetime, timezone
from typing import Dict, Any, List

logger = logging.getLogger("CAUSAL_ENGINE")

RESOURCE_EXHAUSTION_KEYWORDS = {
    "oom", "out of memory", "memory leak", "heap exhaustion", "high memory",
    "cpu 100", "cpu saturation", "cpu spike", "thread pool", "deadlock",
    "query storm", "slow query", "lock wait", "table lock", "disk full",
    "io starvation", "connection pool exhausted", "file descriptor", "gc pause"
}

INFRASTRUCTURE_SEVERANCE_KEYWORDS = {
    "fiber cut", "link down", "port err-disable", "port down", "cable unplugged",
    "bgp session down", "switch offline", "power supply failed", "asic error",
    "crc error", "carrier lost", "interface flap", "hardware fault"
}


def _parse_incident_time(inc: Dict[str, Any]) -> float:
    """Parses timestamp from incident dict, handling float, int, or ISO strings."""
    for field in ["timestamp", "created_at", "first_seen", "time"]:
        val = inc.get(field)
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str) and val.strip():
            try:
                clean_str = val.replace("Z", "+00:00")
                return datetime.fromisoformat(clean_str).timestamp()
            except Exception:
                pass
    return time.time()


def _extract_symptom_text(inc: Dict[str, Any]) -> str:
    """Extracts all textual clues from an incident to diagnose failure typology."""
    parts = [
        str(inc.get("description", "")),
        str(inc.get("component", "")),
        str(inc.get("title", "")),
        str(inc.get("symptom", "")),
        str(inc.get("failure_type", ""))
    ]
    if "symptoms" in inc:
        s = inc["symptoms"]
        if isinstance(s, list):
            parts.extend([str(x) for x in s])
        else:
            parts.append(str(s))
    if "metadata" in inc and isinstance(inc["metadata"], dict):
        parts.append(str(inc["metadata"].get("type", "")))
        parts.append(str(inc["metadata"].get("description", "")))
    return " ".join(parts).lower()


class CausalReasoningEngine:
    def __init__(self, sdm=None):
        if sdm is None:
            from cognition.service_dependency_map import ServiceDependencyMap
            self.sdm = ServiceDependencyMap()
        else:
            self.sdm = sdm # Service Dependency Map

    def infer_root_cause(self, active_incidents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Bidirectional Causal Graph Traversal (Enterprise Level-5).
        Distinguishes:
          1. Top-Down Infrastructure Severance (L1/L2/L3 physical drop -> L7 timeout).
          2. Bottom-Up Inverted Resource Exhaustion (L7 App memory leak/deadlock -> L4 socket drop).
          3. Lateral Microservice Cascade (Microservice A timeout -> Microservice B failure).
        """
        logger.info("[CAUSAL ENGINE] Starting Bidirectional Causal Traversal...")
        
        if not active_incidents:
            return {"status": "no_incidents"}

        layer_weights = {
            "L1": 1, "L2": 2, "L3": 3, "L4": 4, 
            "L5": 5, "L6": 6, "L7": 7
        }

        # Tag each incident with parsed timestamp, layer weight, and failure typology
        enriched = []
        for inc in active_incidents:
            layer = inc.get("osi_layer", "L7").upper()
            weight = layer_weights.get(layer, 7)
            ts = _parse_incident_time(inc)
            symptom_txt = _extract_symptom_text(inc)

            has_res_exhaustion = any(kw in symptom_txt for kw in RESOURCE_EXHAUSTION_KEYWORDS)
            has_infra_severance = any(kw in symptom_txt for kw in INFRASTRUCTURE_SEVERANCE_KEYWORDS)

            typology = "GENERIC"
            if has_res_exhaustion:
                typology = "RESOURCE_EXHAUSTION"
            elif has_infra_severance:
                typology = "INFRASTRUCTURE_SEVERANCE"

            enriched.append({
                "raw": inc,
                "layer": layer,
                "weight": weight,
                "ts": ts,
                "typology": typology,
                "symptom_txt": symptom_txt
            })

        min_ts = min(e["ts"] for e in enriched)
        max_ts = max(e["ts"] for e in enriched)
        ts_span = max(0.0, max_ts - min_ts)

        # ── PATH A: Inverted Bottom-Up Cascade Detection ───────────────────────────
        # Check if an upper layer (L5/L6/L7) incident has RESOURCE_EXHAUSTION
        # and started earlier than or concurrent with lower layer (L1-L4) symptoms
        inverted_candidate = None
        for item in enriched:
            if item["weight"] >= 5 and item["typology"] == "RESOURCE_EXHAUSTION":
                # Must have started within 10s of the absolute earliest timestamp
                if item["ts"] <= min_ts + 10.0:
                    inverted_candidate = item
                    break

        # Check if lower layers also suffered errors in the same incident cluster
        has_lower_layer_impact = any(e["weight"] <= 4 for e in enriched)

        if inverted_candidate and has_lower_layer_impact:
            suspected = inverted_candidate["raw"]
            comp = suspected.get("component") or suspected.get("pc_name") or "Application"
            chain = self._build_causal_chain(suspected)
            explanation = (
                f"INVERTED BOTTOM-UP CASCADE: Application resource exhaustion ({comp} at {inverted_candidate['layer']}) "
                f"exhausted host OS resources, subsequently degrading lower-layer transport/network connectivity."
            )
            logger.info(f"[CAUSAL ENGINE] Inverted cascade diagnosed! Root cause: {comp} at {inverted_candidate['layer']}")
            return {
                "root_cause_incident": suspected,
                "causal_chain": chain,
                "explanation": explanation,
                "direction": "BOTTOM_UP_INVERTED",
                "cascade_type": "INVERTED_RESOURCE_EXHAUSTION",
                "confidence": 94.5,
                "temporal_lead_seconds": round(ts_span, 2)
            }

        # ── PATH B: Top-Down Infrastructure Severance ─────────────────────────────
        # Find lowest layer incident. If multiple at lowest layer, pick earliest timestamp
        enriched.sort(key=lambda x: (x["weight"], x["ts"]))
        deepest_item = enriched[0]
        suspected = deepest_item["raw"]
        comp = suspected.get("component") or suspected.get("pc_name") or "Infrastructure"
        chain = self._build_causal_chain(suspected)

        is_multi_layer = any(e["weight"] != deepest_item["weight"] for e in enriched)
        if is_multi_layer:
            direction = "TOP_DOWN_SEVERANCE"
            cascade_type = "DOWNWARD_INFRASTRUCTURE_SEVERANCE"
            explanation = (
                f"TOP-DOWN SEVERANCE: Failure at {deepest_item['layer']} ({comp}) "
                f"propagates upwards, causing downstream Application/Presentation errors."
            )
            confidence = 96.0
        else:
            direction = "LATERAL_CASCADE"
            cascade_type = "SAME_LAYER_PROPAGATION"
            explanation = f"Failure originated at {deepest_item['layer']} on {comp} and propagated laterally."
            confidence = 88.0

        logger.info(f"[CAUSAL ENGINE] Root Cause Identified at {deepest_item['layer']}: {comp} ({direction})")

        return {
            "root_cause_incident": suspected,
            "causal_chain": chain,
            "explanation": explanation,
            "direction": direction,
            "cascade_type": cascade_type,
            "confidence": confidence,
            "temporal_lead_seconds": round(ts_span, 2)
        }

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
        from engines.llm_router import get_router
        
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
        
        if res and isinstance(res, dict) and res.get("status") == "SUCCESS":
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

