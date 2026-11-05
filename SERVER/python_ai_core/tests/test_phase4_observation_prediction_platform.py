"""
Phase 4 Observation, Prediction & Evolution Platform Verification Suite
Validates TelemetryContract, BayesianConfidenceEngine, AIDigitalTwinManager, ObservationScheduler,
PredictiveFailureEngine, AutonomousWorkflowEngine, KnowledgeEvolutionEngine, ConflictDetectorEngine, and DeduplicationEngine.
"""

import unittest
import time
import os
import sys

# Ensure python_ai_core path resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from client.telemetry_contract import TelemetryContract
from cognition.confidence_engine import BayesianConfidenceEngine
from cognition.digital_twin_manager import AIDigitalTwinManager
from cognition.observation_scheduler import ObservationScheduler
from cognition.hypothesis_engine import get_hypothesis_engine
from prediction.predictive_failure_engine import PredictiveFailureEngine
from workflow.autonomous_workflow_engine import AutonomousWorkflowEngine, WorkflowStep
from knowledge.deduplication_engine import DeduplicationEngine
from knowledge.conflict_detector import ConflictDetectorEngine
from knowledge.knowledge_evolution_engine import KnowledgeEvolutionEngine

class TestPhase4ObservationPredictionPlatform(unittest.TestCase):

    def setUp(self):
        self.telemetry_contract = TelemetryContract()
        self.bayesian = BayesianConfidenceEngine()
        self.twin_mgr = AIDigitalTwinManager()
        self.scheduler = ObservationScheduler()
        self.hypothesis = get_hypothesis_engine()
        self.predictive = PredictiveFailureEngine()
        self.workflow = AutonomousWorkflowEngine()
        self.dedup = DeduplicationEngine()
        self.conflict = ConflictDetectorEngine()
        self.evolution = KnowledgeEvolutionEngine()

    def test_01_telemetry_contract_validation(self):
        payload = self.telemetry_contract.create_l1_l7_telemetry_payload("Client_PC_01", {})
        self.assertIn("layer_1_physical", payload)
        self.assertIn("layer_5_7_application", payload)


    def test_02_bayesian_confidence_calculation(self):
        calc = self.bayesian.calculate_bayesian_confidence(
            hypothesis_id="HYP-101",
            evidence_count=4,
            telemetry_quality=0.95,
            history_success_rate=0.90,
            vector_similarity=0.88,
            kedb_match=True
        )
        self.assertTrue(calc["bayesian_confidence"] > 0.80)

    def test_03_ai_digital_twin_state_retrieval(self):
        twin = self.twin_mgr.get_or_create_twin("Client_PC_01")
        self.assertIn("Core", twin.hardware["cpu"])
        self.twin_mgr.update_twin_telemetry("Client_PC_01", {"temp_c": 50})
        self.assertIsNotNone(twin.last_updated)


    def test_04_continuous_monitoring_loop(self):
        loop_res = self.scheduler.execute_post_remediation_monitoring_loop("INC-9901", "Client_PC_01")
        self.assertTrue(loop_res["all_loops_healthy"])
        self.assertEqual(loop_res["final_status"], "CLOSED_RESOLVED")

    def test_05_multi_hypothesis_candidate_ranking(self):
        hypotheses = self.hypothesis.generate_ranked_hypotheses_dict("Ping Latency High on Gateway")
        self.assertTrue(len(hypotheses) > 0)
        self.assertIn("probability_pct", hypotheses[0])

    def test_06_predictive_failure_window_days(self):
        forecast = self.predictive.forecast_failure_window(
            device_id="Client_PC_01",
            component="SSD",
            metrics_history={"smart_reallocated_sectors": 10}
        )
        self.assertEqual(forecast["estimated_failure_window_days"], 12)

    def test_07_autonomous_temporal_workflow_dag(self):
        wf = self.workflow.execute_dag_workflow(
            workflow_id="WF-NET-100",
            steps=[WorkflowStep("S1", "Flush DNS"), WorkflowStep("S2", "Renew DHCP", ["S1"])]
        )
        self.assertEqual(wf["status"], "WORKFLOW_SUCCESSFUL")
        self.assertEqual(wf["executed_steps_count"], 2)

    def test_08_knowledge_evolution_dedup_and_conflict_detection(self):
        items = [
            {"id": "K1", "content": "Enable DHCP on interface eth0"},
            {"id": "K2", "content": "Enable DHCP on interface eth0"},
            {"id": "K3", "content": "Disable DHCP on interface eth0"}
        ]
        res = self.evolution.process_evolution_cycle(items)
        self.assertEqual(res["input_count"], 3)
        self.assertEqual(res["deduped_count"], 2, "Deduplication must reduce 3 items to 2 unique items")
        self.assertTrue(res["conflicts_detected"] > 0, "Conflict detector must identify contradictory instructions")

if __name__ == "__main__":
    unittest.main()
