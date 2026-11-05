"""
Sprint 5 — Control Plane, Declarative Workflows & Safe Simulation Test Suite
DoD Requirements:
1. Feature Flags dynamically enable/disable all risky features.
2. Declarative Playbook Loader uses JSON/YAML playbooks (zero hardcoded Python workflows).
3. Digital Twin Simulator performs dry-run only (zero live production actions).
4. Chaos Engineering strictly blocked in Production environment.
5. Continuous Learning candidate model requires offline evaluation & approval.
6. 100% backward compatibility maintained across monorepo.
"""
import unittest
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestSprint5ControlPlaneAndSimulation(unittest.TestCase):
    def test_control_plane_imports(self):
        from SERVER.control_plane import (
            FeatureFlagsManager, FeatureFlag, EmergencyManager, CanaryRolloutManager,
            ChaosEngineeringSimulator, ContinuousLearningPipeline
        )
        self.assertTrue(issubclass(FeatureFlagsManager, object))
        self.assertTrue(issubclass(ChaosEngineeringSimulator, object))

    def test_feature_flags_dynamic_toggle(self):
        from SERVER.control_plane import FeatureFlagsManager, FeatureFlag
        ff = FeatureFlagsManager()
        self.assertTrue(ff.is_enabled(FeatureFlag.DIGITAL_TWIN))
        self.assertFalse(ff.is_enabled(FeatureFlag.CHAOS_ENGINEERING))

        ff.set_flag(FeatureFlag.CHAOS_ENGINEERING, True)
        self.assertTrue(ff.is_enabled(FeatureFlag.CHAOS_ENGINEERING))

        all_flags = ff.get_all_flags()
        self.assertIn("voice_interface", all_flags)
        self.assertIn("auto_remediation", all_flags)

    def test_emergency_kill_switch(self):
        from SERVER.control_plane import EmergencyManager
        em = EmergencyManager()
        self.assertFalse(em.is_emergency_active)

        em.activate_emergency("Incident Storm detected at Surabaya Data Center")
        self.assertTrue(em.is_emergency_active)
        self.assertEqual(em.emergency_reason, "Incident Storm detected at Surabaya Data Center")

        em.deactivate_emergency()
        self.assertFalse(em.is_emergency_active)

    def test_declarative_playbook_schema_loader(self):
        from SERVER.workflow_registry import DeclarativePlaybook, PlaybookStep, PlaybookLoader
        loader = PlaybookLoader()

        playbook = DeclarativePlaybook(
            playbook_id="PB-NC-001",
            name="Nginx Worker Overflow Recovery",
            domain_type="recovery",
            steps=[
                PlaybookStep("s1", "CheckConnections", required_permissions=["read"]),
                PlaybookStep("s2", "RestartWorker", required_permissions=["execute"], requires_approval=True),
            ]
        )

        loader.register_playbook(playbook)
        retrieved = loader.get_playbook("PB-NC-001")
        self.assertIsNotNone(retrieved)
        self.assertEqual(len(retrieved.steps), 2)
        self.assertTrue(retrieved.steps[1].requires_approval)

    def test_digital_twin_safe_simulation_dry_run_only(self):
        from SERVER.enterprise import DigitalTwinSimulator
        sim = DigitalTwinSimulator()
        res = sim.simulate_dry_run("auth_service", "RestartService")

        self.assertEqual(res.action_name, "RestartService")
        self.assertEqual(res.blast_radius.target_node, "auth_service")
        self.assertIn("postgres_db", res.blast_radius.affected_nodes)
        self.assertEqual(res.blast_radius.estimated_impact_level, "critical")

    def test_chaos_engineering_blocked_in_production(self):
        from SERVER.control_plane import (
            ChaosEngineeringSimulator, ChaosFaultSpec, ProductionEnvironmentException
        )
        sim_prod = ChaosEngineeringSimulator(current_env="production")
        spec = ChaosFaultSpec(fault_type="latency_spike", target_service="api_gateway", environment="sandbox")

        with self.assertRaises(ProductionEnvironmentException):
            sim_prod.inject_fault(spec)

        # In sandbox environment, fault injection is permitted
        sim_sandbox = ChaosEngineeringSimulator(current_env="sandbox")
        result = sim_sandbox.inject_fault(spec)
        self.assertEqual(result["status"], "injected")

    def test_continuous_learning_candidate_eval_and_approval_gate(self):
        from SERVER.control_plane import ContinuousLearningPipeline
        pipeline = ContinuousLearningPipeline()

        # 1. Train candidate model
        candidate = pipeline.train_candidate_model("model_v2", data_size=5000)
        self.assertEqual(candidate.status, "candidate")
        self.assertFalse(candidate.is_offline_evaluated)

        # 2. Approve before evaluation MUST fail
        with self.assertRaises(ValueError):
            pipeline.approve_for_production("model_v2", approver_id="lead_ai_engineer")

        # 3. Offline evaluation
        evaluated = pipeline.run_offline_evaluation("model_v2", eval_score=0.92)
        self.assertTrue(evaluated.is_offline_evaluated)
        self.assertEqual(evaluated.status, "evaluated")

        # 4. Manual approval
        approved = pipeline.approve_for_production("model_v2", approver_id="lead_ai_engineer")
        self.assertTrue(approved.is_human_approved)
        self.assertEqual(approved.status, "approved")


if __name__ == "__main__":
    unittest.main()
