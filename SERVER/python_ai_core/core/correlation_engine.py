import json
import logging
from .timeline_builder import TimelineBuilder

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from cognition.causal_inference import CausalGraphEngine

logger = logging.getLogger("CORRELATION_ENGINE")

class CorrelationEngine:
    def __init__(self, db_conn=None):
        self.timeline_builder = TimelineBuilder(db_conn)
        self.causal_mapper = CausalGraphEngine()

    async def correlate_incident(self, pc_name: str, telemetry_data: dict) -> dict:
        timeline = self.timeline_builder.build_timeline(pc_name)
        causal_results = self.causal_mapper.infer_root_cause(telemetry_data)
        
        if causal_results is None:
            return {
                "timeline": timeline,
                "root_event": "Unknown (Insufficient Evidence)",
                "downstream_effects": [],
                "confidence": 0.0,
                "nodes": [],
                "edges": [],
                "status": "INSUFFICIENT_EVIDENCE"
            }
        
        return {
            "timeline": timeline,
            "root_event": causal_results.get("inferred_root_cause", "Unknown"),
            "downstream_effects": causal_results.get("causal_chain", []),
            "confidence": causal_results.get("confidence", 95.0),
            "remediation": causal_results.get("remediation", "MANUAL_INVESTIGATION_REQUIRED"),
            "nodes": [],
            "edges": []
        }
