"""
Unit & Certification Test Suite for Enterprise Autonomous AI Architect Platform (v9.0.0)
Validates Self-Operating & Self-Improving Architecture (10 Capabilities):
1. Strategic AI Planner
2. Multi-Agent Negotiator Engine
3. Economic Decision Engine
4. Uncertainty Handling & Refusal Engine
5. Knowledge Gap Detector & Learning Queue
6. Autonomous Architecture Optimizer
7. Goal-Oriented Remediation Planner
8. 5-Tier Enterprise Memory Hierarchy
9. Continuous AI Quality Evaluator
10. Autonomous Improvement Closed-Loop Pipeline
"""

import unittest
import os
import sys

# Ensure python_ai_core path resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from active_probing import (
    AIStrategicPlanner, StrategicPlan,
    MultiAgentNegotiator, NegotiationOutcome, AgentProposal,
    EconomicDecisionEngine, ActionEconomicMetric,
    UncertaintyHandlingEngine, UncertaintyEvaluationResult,
    KnowledgeGapDetector, KnowledgeGapResult,
    AutonomousArchitectureOptimizer, ArchitectureOptimizationReport,
    GoalOrientedRemediationPlanner, GoalRemediationPlan, ActionCandidatePath,
    EnterpriseMemoryHierarchy, EnterpriseMemorySnapshot,
    ContinuousAIEvaluator, ContinuousAIEvaluationMetrics,
    AutonomousImprovementPipeline, ImprovementPipelineResult
)


class TestEnterpriseV9SelfImprovingPlatform(unittest.TestCase):

    def test_01_ai_strategic_planner(self):
        """Validates goal + constraint strategic plan synthesis."""
        planner = AIStrategicPlanner()
        plan: StrategicPlan = planner.plan_incident_strategy(
            goal="Restore POS Terminal Services",
            constraints=["No DC Restart", "Max Duration 30s"]
        )
        self.assertEqual(plan.strategy_name, "HIGH_AVAILABILITY_ENDPOINT_RECOVERY")
        self.assertIn("Probe L1 Physical & RSSI", plan.action_steps)

    def test_02_multi_agent_negotiator(self):
        """Validates structured multi-agent negotiation when Network vs Security vs Policy conflict."""
        negotiator = MultiAgentNegotiator()
        proposals = [
            AgentProposal("NetworkAgent", "ResetNetworkStack", 0.9),
            AgentProposal("SecurityAgent", "AuditLogs", 0.8),
            AgentProposal("PolicyAgent", "EnforceBusinessHours", 1.0)
        ]
        outcome: NegotiationOutcome = negotiator.negotiate_action_plan(proposals, is_business_hours=True)
        self.assertTrue(outcome.compromise_reached)
        self.assertEqual(outcome.consensus_action, "FlushDNS_With_HITL")

    def test_03_economic_decision_engine(self):
        """Validates economic cost vs risk vs failure probability minimization."""
        econ = EconomicDecisionEngine()
        actions = [
            {"name": "Restart_Core_Switch", "action_cost": 100.0, "risk": 9.0, "success_prob": 0.99, "downtime_cost": 500.0},
            {"name": "Flush_DNS_Cache", "action_cost": 1.0, "risk": 1.0, "success_prob": 0.85, "downtime_cost": 50.0}
        ]
        best: ActionEconomicMetric = econ.select_lowest_cost_action(actions)
        self.assertEqual(best.action_name, "Flush_DNS_Cache")
        self.assertLess(best.total_economic_cost, 50.0)

    def test_04_uncertainty_handling_engine(self):
        """Validates low-confidence refusal when confidence < 50% and safe probes exhausted."""
        uncertainty = UncertaintyHandlingEngine()
        res: UncertaintyEvaluationResult = uncertainty.evaluate_confidence_certainty(
            confidence_score=0.42,
            probes_executed_count=10,
            safe_probes_remaining=False
        )
        self.assertTrue(res.refusal_triggered)
        self.assertEqual(res.action_recommendation, "REFUSE_RCA_FLAG_HUMAN_REVIEW")
        self.assertIn("Additional Active Diagnostic Probing Required", res.fallback_message or "")

    def test_05_knowledge_gap_detector(self):
        """Validates novel pattern detection and routing to human learning queue."""
        detector = KnowledgeGapDetector()
        res: KnowledgeGapResult = detector.detect_knowledge_gap(
            incident_signature="SIG-CUSTOM-APP-99",
            observed_symptoms=["custom_app_crash", "unknown_kernel_panic"]
        )
        self.assertTrue(res.is_knowledge_gap)
        self.assertTrue(res.routed_to_learning_queue)

    def test_06_autonomous_architecture_optimizer(self):
        """Validates self-pruning of unused probes, inactive causal edges, and redundant policy rules."""
        optimizer = AutonomousArchitectureOptimizer()
        probe_stats = {"PRB-L1-01": 50, "PRB-L4-UNUSED": 0}
        edge_stats = {"RSSI->Loss": 120, "STALE_EDGE": 0}

        report: ArchitectureOptimizationReport = optimizer.optimize_architecture(probe_stats, edge_stats)
        self.assertIn("PRB-L4-UNUSED", report.probes_pruned)
        self.assertIn("STALE_EDGE", report.causal_edges_deactivated)
        self.assertGreater(report.efficiency_gain_pct, 0.0)

    def test_07_goal_oriented_remediation_planner(self):
        """Validates multi-path goal-based remediation execution plan generation."""
        planner = GoalOrientedRemediationPlanner()
        plan: GoalRemediationPlan = planner.plan_remediation_goal(
            remediation_goal="Restore POS Terminal Service",
            target_asset="POS-KASIR-01"
        )
        self.assertIsNotNone(plan.selected_path)
        self.assertGreaterEqual(plan.candidate_paths_evaluated, 3)

    def test_08_enterprise_memory_hierarchy(self):
        """Validates 5-tier memory hierarchy (Working, Episodic, Semantic, Causal, Procedural)."""
        memory = EnterpriseMemoryHierarchy()
        memory.store_incident_trajectory("INC-101", {"symptoms": ["DNS Delay"]})
        snap: EnterpriseMemorySnapshot = memory.get_memory_snapshot()

        self.assertEqual(snap.working_memory_active_incidents, 1)
        self.assertEqual(snap.episodic_trajectories_count, 1)
        self.assertGreater(snap.semantic_nodes_count, 0)
        self.assertGreater(snap.causal_edges_count, 0)

    def test_09_continuous_ai_evaluator(self):
        """Validates continuous AI quality evaluation metrics (False RCA < 5%, Hallucination ~ 0%)."""
        evaluator = ContinuousAIEvaluator()
        metrics: ContinuousAIEvaluationMetrics = evaluator.evaluate_ai_quality()

        self.assertTrue(metrics.quality_standards_met)
        self.assertLess(metrics.false_rca_rate_pct, 5.0)
        self.assertEqual(metrics.hallucination_rate_pct, 0.0)

    def test_10_autonomous_improvement_pipeline(self):
        """Validates closed-loop self-improvement pipeline cycle execution."""
        pipeline = AutonomousImprovementPipeline()
        res: ImprovementPipelineResult = pipeline.execute_self_improvement_cycle(
            incident_id="INC-999",
            investigation_data={"status": "RESOLVED"}
        )
        self.assertTrue(res.investigation_completed)
        self.assertTrue(res.knowledge_evolved)
        self.assertTrue(res.architecture_optimized)


if __name__ == "__main__":
    unittest.main()
