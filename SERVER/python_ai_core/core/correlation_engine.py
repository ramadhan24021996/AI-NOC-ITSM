import json
import logging
from .timeline_builder import TimelineBuilder

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from cognition.causal_engine import CausalReasoningEngine

logger = logging.getLogger("CORRELATION_ENGINE")

class CorrelationEngine:
    def __init__(self, db_conn=None):
        self.timeline_builder = TimelineBuilder(db_conn)
        self.causal_mapper = CausalReasoningEngine()

    async def correlate_incident(self, pc_name: str, telemetry_data: dict) -> dict:
        timeline = self.timeline_builder.build_timeline(pc_name)
        causal_results = await self.causal_mapper.map_causality(telemetry_data)
        
        return {
            "timeline": timeline,
            "root_event": causal_results.get("probable_root_cause", "Unknown"),
            "downstream_effects": causal_results.get("downstream_effects", []),
            "confidence": causal_results.get("confidence", 50.0),
            "nodes": causal_results.get("nodes", []),
            "edges": causal_results.get("edges", [])
        }
