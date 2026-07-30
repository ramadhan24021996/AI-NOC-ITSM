"""
EVENT CORRELATION ENGINE (CROSS-LAYER L1-L7 & 30-SECOND TIME-WINDOW CLUSTERING)
Correlates incoming telemetry & log signals across 7 architectural layers:
- Layer 1: Network Ping, Interface Telemetry, Socket Connections
- Layer 2: Data Link / Switch Port
- Layer 3: Microservices / Systemd Daemons / Database Engines
- Layer 4: Transport Layer / API Gateways
- Layer 5: Session / Auth Services
- Layer 6: Presentation / Static Web Portal
- Layer 7: Application / Browser Extension / POS Terminal

Implements 30-Second Sliding Time-Window Clustering to group correlated events
and identify Cascading Failure Propagation Chains (e.g. Gateway Down -> DB Timeout -> HTTP 500).
"""

import time
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("EVENT_CORRELATION_ENGINE")


class EventCorrelationEngine:
    def __init__(self, time_window_seconds: int = 30):
        self.time_window_seconds = time_window_seconds
        # Layer priority mapping for cascading root cause determination (lower layer = root origin)
        self.layer_hierarchy = {
            "L1_NETWORK": 1,
            "L1_PHYSICAL": 1,
            "L2_DATALINK": 2,
            "L3_MICROSERVICE": 3,
            "L3_DATABASE": 3,
            "L4_TRANSPORT": 4,
            "L5_SESSION": 5,
            "L6_PRESENTATION": 6,
            "L7_APPLICATION": 7,
            "L7_BROWSER_EXT": 7
        }

    def parse_timestamp(self, ts_input: Any) -> float:
        """Helper to parse float timestamp or ISO string into unix epoch seconds."""
        if isinstance(ts_input, (int, float)):
            return float(ts_input)
        if not ts_input:
            return time.time()
        try:
            return float(str(ts_input))
        except ValueError:
            pass
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(str(ts_input).replace('Z', '+00:00'))
            return dt.timestamp()
        except Exception:
            return time.time()

    def cluster_events_by_window(self, events: List[Dict[str, Any]], window_seconds: Optional[int] = None) -> List[List[Dict[str, Any]]]:
        """
        Groups event log items occurring within a sliding time window (default 30 seconds).
        Returns a list of event clusters.
        """
        if not events:
            return []

        win_sec = window_seconds if window_seconds is not None else self.time_window_seconds

        # Sort events by timestamp ascending
        sorted_events = sorted(events, key=lambda e: self.parse_timestamp(e.get("timestamp", 0)))
        clusters = []
        current_cluster = [sorted_events[0]]
        cluster_start_ts = self.parse_timestamp(sorted_events[0].get("timestamp", 0))

        for ev in sorted_events[1:]:
            ev_ts = self.parse_timestamp(ev.get("timestamp", 0))
            if (ev_ts - cluster_start_ts) <= win_sec:
                current_cluster.append(ev)
            else:
                clusters.append(current_cluster)
                current_cluster = [ev]
                cluster_start_ts = ev_ts

        if current_cluster:
            clusters.append(current_cluster)

        logger.info(f"[CORRELATION] Clustered {len(events)} events into {len(clusters)} 30-sec window clusters.")
        return clusters

    def correlate_cross_layer_cascading(self, event_cluster: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyzes a cluster of events across Layer 1 - Layer 7 to detect cascading failure propagation:
        Determines the inferred Root Cause Event (lowest architectural layer with earliest timestamp)
        and traces the propagation chain down to higher layers.
        """
        if not event_cluster:
            return {
                "root_cause_event": None,
                "cascading_chain": [],
                "affected_layers": [],
                "confidence": 0.0,
                "summary": "No events provided in cluster"
            }

        # Tag layer levels if missing
        tagged_events = []
        for ev in event_cluster:
            layer_name = ev.get("layer", "L3_MICROSERVICE").upper()
            layer_level = self.layer_hierarchy.get(layer_name, 3)
            tagged_events.append({
                **ev,
                "layer": layer_name,
                "layer_level": layer_level,
                "parsed_ts": self.parse_timestamp(ev.get("timestamp", 0))
            })

        # Sort by layer level ascending (lowest layer first), then by timestamp ascending
        tagged_events.sort(key=lambda x: (x["layer_level"], x["parsed_ts"]))

        root_event = tagged_events[0]
        cascading_chain = tagged_events[1:]
        affected_layers = list(dict.fromkeys([e["layer"] for e in tagged_events]))

        # Calculate correlation confidence score based on layer separation & timestamp tightness
        ts_span = tagged_events[-1]["parsed_ts"] - tagged_events[0]["parsed_ts"]
        base_confidence = 96.0 if len(affected_layers) > 1 else 85.0
        confidence = max(60.0, base_confidence - (ts_span * 0.5))

        root_dev = root_event.get("device_id") or root_event.get("pc_name") or "Network Gateway / Host"
        summary = (
            f"CASCADING FAILURE DETECTED: Root cause originated at {root_event['layer']} ({root_dev}) "
            f"propagated across {len(affected_layers)} layers in {ts_span:.1f}s."
        )

        logger.info(f"[CORRELATION] Cross-layer analysis complete. Root Layer: {root_event['layer']}. Confidence: {confidence:.1f}%")

        return {
            "root_cause_event": root_event,
            "cascading_chain": cascading_chain,
            "affected_layers": affected_layers,
            "time_span_seconds": round(ts_span, 2),
            "confidence": round(confidence, 1),
            "is_cascading_failure": len(affected_layers) > 1,
            "summary": summary
        }

    def build_causal_matrix(self, event_cluster: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generates graph nodes and edges for rendering Causal DAG visualization on dashboard UI.
        """
        correl_res = self.correlate_cross_layer_cascading(event_cluster)
        root_ev = correl_res.get("root_cause_event")

        nodes = []
        edges = []

        if not root_ev:
            return {"nodes": [], "edges": [], "root_id": None}

        # Add root node
        root_node_id = f"node-{root_ev.get('layer')}-{root_ev.get('event_id', 'root')}"
        nodes.append({
            "id": root_node_id,
            "label": f"ROOT CAUSE ({root_ev.get('layer')})\n{root_ev.get('description', 'Initial Event')}",
            "type": "ROOT_CAUSE",
            "layer": root_ev.get("layer"),
            "confidence": correl_res.get("confidence")
        })

        prev_node_id = root_node_id
        base_conf = float(correl_res.get("confidence") or 80.0)

        # Add downstream cascading nodes & edges
        for idx, downstream in enumerate(correl_res.get("cascading_chain", [])):
            ds_node_id = f"node-{downstream.get('layer')}-{idx}"
            nodes.append({
                "id": ds_node_id,
                "label": f"EFFECT ({downstream.get('layer')})\n{downstream.get('description', 'Downstream Symptom')}",
                "type": "CASCADING_EFFECT",
                "layer": downstream.get("layer"),
                "confidence": max(50.0, base_conf - (idx + 1) * 5)
            })
            edges.append({
                "from": prev_node_id,
                "to": ds_node_id,
                "label": f"Causes ({round(0.95 - idx * 0.05, 2)})",
                "weight": round(0.95 - idx * 0.05, 2)
            })
            prev_node_id = ds_node_id
            prev_node_id = ds_node_id

        return {
            "root_id": root_node_id,
            "nodes": nodes,
            "edges": edges,
            "summary": correl_res.get("summary"),
            "is_cascading": correl_res.get("is_cascading_failure")
        }
