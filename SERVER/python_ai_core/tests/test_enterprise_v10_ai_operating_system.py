"""
Unit & Certification Test Suite for Enterprise AI Operating System (v10.0.0 Master Architecture)
Validates 10 Master Binding Engines & 16-Step Enterprise Intelligence Loop:
1. Enterprise World Model Engine
2. 1,000 Scenario Monte Carlo Simulation Engine
3. Utility-Based Decision Engine
4. Mission Manager Engine
5. Meta-Reasoning & Bias Evaluation Engine
6. Long-Term Strategy & 30-Day Replacement Engine
7. Enterprise Business Service Graph
8. Autonomous Change Planner (ITIL CR Lifecycle)
9. AI Safety Layer Guardrails
10. Master 16-Step Enterprise Intelligence Loop Orchestrator
"""

import unittest
import os
import sys

# Ensure python_ai_core path resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from active_probing import (
    EnterpriseWorldModel, EnterpriseWorldModelState,
    EnterpriseSimulationEngine, MultiScenarioSimulationReport, SimulationStrategyResult,
    UtilityDecisionEngine, ActionUtilityScore,
    MissionManager, EnterpriseMission,
    MetaReasoningEngine, MetaReasoningAuditReport,
    LongTermStrategyEngine, LongTermTrendRecommendation,
    EnterpriseServiceGraph, BusinessImpactAnalysis,
    AutonomousChangePlanner, ChangeRequestRecord,
    AISafetyLayer, SafetyGuardrailResult,
    EnterpriseIntelligenceLoop, MasterLoopExecutionReport
)


class TestEnterpriseV10AIOperatingSystem(unittest.TestCase):

    def test_01_enterprise_world_model(self):
        """Validates Enterprise World Model state updates across assets, services, and health metrics."""
        world = EnterpriseWorldModel()
        state: EnterpriseWorldModelState = world.update_world_state(incident_id="INC-1001", health_delta=-0.5, affected_users=120)
        self.assertEqual(state.active_incidents_count, 1)
        self.assertLess(state.overall_health_pct, 100.0)
        self.assertGreater(state.physical_assets_count, 1000)

    def test_02_enterprise_simulation_engine(self):
        """Validates Monte Carlo 1,000 scenario rollouts across candidate strategy paths."""
        sim = EnterpriseSimulationEngine()
        report: MultiScenarioSimulationReport = sim.simulate_strategy_rollouts(
            candidate_strategies=["Failover ISP", "Flush DNS", "Restart Firewall"],
            rollouts_per_strategy=1000
        )
        self.assertEqual(report.best_strategy_name, "Failover ISP")
        self.assertGreaterEqual(report.confidence_distribution["Failover ISP"], 95.0)

    def test_03_utility_decision_engine(self):
        """Validates Utility score maximization: Utility = Recovery + SLA + Value - Risk - Cost - Downtime."""
        utility_engine = UtilityDecisionEngine()
        options = [
            {"name": "Failover_ISP", "recovery": 95.0, "sla": 30.0, "value": 100.0, "risk": 2.0, "cost": 10.0, "downtime": 5.0},
            {"name": "Restart_Core_Switch", "recovery": 50.0, "sla": 0.0, "value": 10.0, "risk": 9.0, "cost": 50.0, "downtime": 100.0}
        ]
        best: ActionUtilityScore = utility_engine.select_maximum_utility_strategy(options)
        self.assertEqual(best.strategy_name, "Failover_ISP")
        self.assertGreater(best.net_utility_score, 150.0)

    def test_04_mission_manager(self):
        """Validates Mission Manager alignment enforcing SLA availability goals."""
        mission_mgr = MissionManager()
        aligned, msg = mission_mgr.evaluate_mission_alignment("MISSION-POS-01", proposed_action_impact_pct=0.001)
        self.assertTrue(aligned)
        self.assertIn("ALIGNED", msg)

    def test_05_meta_reasoning_engine(self):
        """Validates Meta-Reasoning self-reflection detecting overconfidence and GraphRAG bias."""
        meta = MetaReasoningEngine()

        # High confidence with 0 active probes -> Overconfidence detected
        report: MetaReasoningAuditReport = meta.evaluate_reasoning_quality(
            hypothesis_confidence=0.96,
            probes_executed_count=0,
            graphrag_similarity_weight=0.90
        )
        self.assertTrue(report.overconfidence_flag)
        self.assertTrue(report.bias_detected)

    def test_06_long_term_strategy_engine(self):
        """Validates 6-month CRC error drift trend detection and 30-day predictive replacement recommendation."""
        lt_strategy = LongTermStrategyEngine()
        rec: LongTermTrendRecommendation = lt_strategy.analyze_asset_lifecycle_trends(
            asset_id="SW-FLOOR-01",
            six_month_crc_errors=8400,
            reboot_frequency_count=15
        )
        self.assertEqual(rec.recommended_action, "SCHEDULE_HARDWARE_REPLACEMENT_WITHIN_30_DAYS")
        self.assertLessEqual(rec.predicted_failure_days, 30)

    def test_07_enterprise_service_graph(self):
        """Validates business service mapping and revenue loss impact analysis."""
        service_graph = EnterpriseServiceGraph()
        impact: BusinessImpactAnalysis = service_graph.analyze_business_impact("FW-HQ-01")
        self.assertEqual(impact.business_criticality_tier, "TIER_0_MISSION_CRITICAL")
        self.assertGreater(impact.estimated_revenue_loss_per_hour_usd, 0.0)

    def test_08_autonomous_change_planner(self):
        """Validates ITIL Change Request creation, simulation validation, and CAB approval gates."""
        change_planner = AutonomousChangePlanner()
        cr: ChangeRequestRecord = change_planner.create_change_request(
            asset_id="POS-KASIR-01",
            requested_change="FlushDNSProfile",
            risk_level="LOW",
            simulation_passed=True
        )
        self.assertEqual(cr.cab_approval_status, "APPROVED")
        self.assertEqual(cr.execution_status, "SCHEDULED")

    def test_09_ai_safety_layer(self):
        """Validates AI Safety Layer guardrails: low confidence freeze and dual-redundant pair blocking."""
        safety = AISafetyLayer()

        # Low confidence (<50%) triggers freeze
        res1: SafetyGuardrailResult = safety.validate_action_safety("FW-HQ-01", "Restart", confidence_score=0.40)
        self.assertFalse(res1.action_permitted)
        self.assertIn("Low-Confidence Freeze", res1.safety_rule_tripped)

        # Permitted under safe parameters
        res2: SafetyGuardrailResult = safety.validate_action_safety("FW-HQ-01", "Restart", confidence_score=0.92)
        self.assertTrue(res2.action_permitted)

    def test_10_master_enterprise_intelligence_loop(self):
        """Validates master 16-step Enterprise Intelligence Loop orchestrator execution."""
        master_loop = EnterpriseIntelligenceLoop()
        report: MasterLoopExecutionReport = master_loop.execute_master_intelligence_loop(
            incident_id="INC-MASTER-001",
            initial_telemetry={"symptoms": ["RSSI Attenuation"]}
        )
        self.assertEqual(report.steps_completed_count, 16)
        self.assertEqual(report.loop_status, "SUCCESS_STABLE")
        self.assertTrue(report.world_model_updated)


if __name__ == "__main__":
    unittest.main()
