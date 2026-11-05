"""
Probe Replay Engine Module
Persists complete investigation timelines under probe_history/<incident_id>/
Includes timeline.json, probe_result.json, and decision.json for auditing, model evaluation, and training replay.
"""

from dataclasses import dataclass
from typing import Dict, List, Any
import os
import json
from datetime import datetime, timezone


class ProbeReplayEngine:
    """Manages probe history persistence and replay serialization."""

    def __init__(self, base_dir: str = "/tmp/probe_history"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def persist_investigation_record(
        self,
        incident_id: str,
        timeline: List[str],
        probe_results: List[Dict[str, Any]],
        decision_matrix: Dict[str, Any]
    ) -> str:
        incident_dir = os.path.join(self.base_dir, incident_id)
        os.makedirs(incident_dir, exist_ok=True)

        # 1. Timeline Record
        with open(os.path.join(incident_dir, "timeline.json"), "w") as f:
            json.dump({
                "incident_id": incident_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "timeline": timeline
            }, f, indent=2)

        # 2. Probe Results Record
        with open(os.path.join(incident_dir, "probe_result.json"), "w") as f:
            json.dump({
                "incident_id": incident_id,
                "total_probes": len(probe_results),
                "probe_results": probe_results
            }, f, indent=2)

        # 3. Decision Matrix Record
        with open(os.path.join(incident_dir, "decision.json"), "w") as f:
            json.dump({
                "incident_id": incident_id,
                "decision_matrix": decision_matrix
            }, f, indent=2)

        return incident_dir

    def load_replay(self, incident_id: str) -> Dict[str, Any]:
        incident_dir = os.path.join(self.base_dir, incident_id)
        if not os.path.exists(incident_dir):
            return {"error": f"Incident replay dir {incident_dir} not found"}

        with open(os.path.join(incident_dir, "timeline.json")) as f:
            timeline_data = json.load(f)
        with open(os.path.join(incident_dir, "probe_result.json")) as f:
            probe_data = json.load(f)
        with open(os.path.join(incident_dir, "decision.json")) as f:
            decision_data = json.load(f)

        return {
            "incident_id": incident_id,
            "timeline": timeline_data.get("timeline", []),
            "probe_results": probe_data.get("probe_results", []),
            "decision_matrix": decision_data.get("decision_matrix", {})
        }
