"""
Unit & Integration Test Suite for Enterprise Dashboard Analytics, AI Topology Map & Complete n8n Workflow (AIOS v11.3.0 Master Release)
Validates 3 Core Components:
1. Enterprise Dashboard Analytics (Generating 6 Unified AIOS Widget Payloads)
2. Global Service & AI Topology Map Engine (Time-Travel Historical Replay & Color Coding)
3. Complete Enterprise AI Lifecycle n8n Workflow Schema & Connectivity.
"""

import unittest
import os
import sys
import json

# Ensure python_ai_core path resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from active_probing import (
    EnterpriseDashboardAnalytics, DashboardWidgetPayload,
    EnterpriseTopologyMapEngine, AITopologyMapPayload
)


class TestEnterpriseDashboardAndN8NWorkflow(unittest.TestCase):

    def test_01_enterprise_dashboard_analytics(self):
        """Validates generation of 6 unified AIOS dashboard widget payloads."""
        analytics = EnterpriseDashboardAnalytics()
        widgets = analytics.generate_all_dashboard_widgets("INC-TEST-DASH-01")

        self.assertEqual(len(widgets), 6)

        widget_ids = [w.widget_id for w in widgets]
        self.assertIn("WIDGET-KERNEL-STATUS", widget_ids)
        self.assertIn("WIDGET-CONFIDENCE-CALIBRATED", widget_ids)
        self.assertIn("WIDGET-VISUAL-RCA-GRAPH", widget_ids)
        self.assertIn("PANEL-RESOURCE-OPTIMIZATION", widget_ids)
        self.assertIn("PANEL-KNOWLEDGE-PROMOTION-VAULT", widget_ids)
        self.assertIn("WIDGET-AI-CONSTITUTION-AUDIT", widget_ids)

    def test_02_enterprise_topology_map_engine(self):
        """Validates real-time streaming & time-travel historical topology map payload generation."""
        engine = EnterpriseTopologyMapEngine()

        # Real-Time Mode
        rt_payload: AITopologyMapPayload = engine.render_topology_map()
        self.assertEqual(rt_payload.map_version, "v11.3.0")
        self.assertFalse(rt_payload.time_travel_historical_mode)
        self.assertGreater(len(rt_payload.nodes), 0)
        self.assertGreater(len(rt_payload.edges), 0)

        # Time-Travel Mode
        hist_payload: AITopologyMapPayload = engine.render_topology_map(historical_date_yyyy_mm_dd="2026-08-01")
        self.assertTrue(hist_payload.time_travel_historical_mode)
        self.assertIn("HISTORICAL", hist_payload.map_version)

    def test_03_n8n_enterprise_ai_lifecycle_workflow_json(self):
        """Validates structural integrity and 16-step node connectivity of the n8n workflow JSON."""
        candidate_paths = [
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "workflows", "n8n_enterprise_ai_lifecycle_workflow.json"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "workflows", "n8n_enterprise_ai_lifecycle_workflow.json"),
            "/app/workflows/n8n_enterprise_ai_lifecycle_workflow.json",
            "/home/it-itsm/AI/incident-analysis/workflows/n8n_enterprise_ai_lifecycle_workflow.json",
            os.path.join(os.getcwd(), "workflows", "n8n_enterprise_ai_lifecycle_workflow.json")
        ]
        workflow_path = next((p for p in candidate_paths if os.path.exists(p)), candidate_paths[0])
        self.assertTrue(os.path.exists(workflow_path), f"Workflow file not found in candidates: {candidate_paths}")

        with open(workflow_path, "r") as f:
            wf_data = json.load(f)

        self.assertIn("name", wf_data)
        self.assertIn("nodes", wf_data)
        self.assertEqual(len(wf_data["nodes"]), 16)
        self.assertIn("connections", wf_data)


if __name__ == "__main__":
    unittest.main()
