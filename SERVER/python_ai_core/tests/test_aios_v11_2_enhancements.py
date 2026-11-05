"""
Unit & Integration Test Suite for Enterprise AIOS Enhancements (AIOS v11.2.0 Expansion)
Validates 3 High-Impact Capabilities:
1. Resource Optimization AI Engine (VM Resize, Docker Placement, Storage Rebalancing)
2. Root Cause Confidence Calibration Engine (ECE & Platt Scaling for Overconfidence Correction)
3. Explainability Graph Visualizer (Mermaid Diagram Generation & Visual Node/Edge Payloads)
"""

import unittest
import os
import sys

# Ensure python_ai_core path resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from active_probing import (
    AIOSResourceOptimizer, ResourceOptimizationRecommendation,
    AIOSConfidenceCalibrator, ConfidenceCalibrationResult,
    AIOSExplainabilityGraphVisualizer, ExplainabilityGraphPayload
)


class TestAIOSV112Enhancements(unittest.TestCase):

    def test_01_resource_optimization_ai_engine(self):
        """Validates VM overallocation detection (CPU 95% + RAM 20%) and auto-resize recommendation synthesis."""
        optimizer = AIOSResourceOptimizer()
        rec: ResourceOptimizationRecommendation = optimizer.analyze_resource_utilization(
            asset_id="VM-APP-SERVER-01",
            asset_type="VM",
            cpu_usage_pct=95.0,
            ram_usage_pct=20.0
        )
        self.assertEqual(rec.target_asset_id, "VM-APP-SERVER-01")
        self.assertIn("Over-allocated", rec.detected_anomaly)
        self.assertTrue(rec.is_automated_execution_ready)
        self.assertGreater(rec.estimated_savings_pct, 0.0)

    def test_02_confidence_calibration_engine(self):
        """Validates Expected Calibration Error (ECE) calculation and raw overconfidence correction (95% -> ~72%)."""
        calibrator = AIOSConfidenceCalibrator(historical_accuracy_factor=0.76)
        res: ConfidenceCalibrationResult = calibrator.calibrate_confidence(raw_confidence=0.95)

        self.assertEqual(res.raw_confidence, 0.95)
        self.assertLess(res.calibrated_confidence, 0.95)
        self.assertAlmostEqual(res.calibrated_confidence, 0.722, delta=0.01)
        self.assertEqual(res.calibration_tier, "HIGH_OVERCONFIDENCE_CORRECTED")

    def test_03_explainability_graph_visualizer(self):
        """Validates visual graph payload construction and Mermaid diagram rendering."""
        visualizer = AIOSExplainabilityGraphVisualizer()
        payload: ExplainabilityGraphPayload = visualizer.generate_explainability_graph(
            incident_id="INC-VIS-001",
            rca_title="Gateway Router FW-01 Packet Loss",
            confidence_score=0.92
        )

        self.assertEqual(payload.incident_id, "INC-VIS-001")
        self.assertGreater(len(payload.nodes), 0)
        self.assertGreater(len(payload.edges), 0)
        self.assertIn("graph TD", payload.mermaid_diagram_markdown)
        self.assertIn("Gateway Router", payload.mermaid_diagram_markdown)
        self.assertGreater(len(payload.timeline_sequence), 0)


if __name__ == "__main__":
    unittest.main()
