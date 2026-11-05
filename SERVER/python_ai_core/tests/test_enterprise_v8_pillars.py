"""
Unit & Certification Test Suite for Enterprise Autonomous AI Architect Platform (v8.0.0)
Validates World-Class 5-Pillar Architecture:
1. Enterprise Policy Reasoning Layer (Policy-as-Code & CAB Approval Gate)
2. Enterprise Resource Scheduler & Worker Pool (Priority Queue & Concurrency Control)
3. Global End-to-End Dependency Graph (L1-L7 Topology Failure Cascade Projection)
4. Continuous Causal Validation Engine (SCM Edge Weight Re-evaluation & Pruning)
5. Autonomous SOP & Runbook Generator (Markdown Runbook Synthesis for KEDB)
"""

import unittest
import os
import sys

# Ensure python_ai_core path resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from active_probing import (
    PolicyAsCodeEngine, PolicyReasoningResult, PolicyRule,
    EnterpriseResourceScheduler, SchedulerPoolStatus, ScheduledProbingTask, IncidentPriority,
    GlobalDependencyGraph, ImpactProjectionReport, TopologyNode,
    ContinuousCausalValidation, CausalEdgeValidationStatus,
    AutonomousSOPGenerator, GeneratedSOPDocument
)


class TestEnterpriseV8Pillars(unittest.TestCase):

    def test_01_policy_as_code_engine(self):
        """Validates Policy-as-Code declarative rule evaluation and CAB approval gates."""
        pac = PolicyAsCodeEngine()

        # RestartService on Domain Controller denied without CAB & HITL approval
        res1: PolicyReasoningResult = pac.evaluate_action_policy(
            asset_role="Domain Controller",
            action_name="RestartService",
            is_business_hours=True,
            hitl_approved=False,
            cab_approved=False
        )
        self.assertFalse(res1.allowed)
        self.assertTrue(res1.requires_cab_approval)

        # Permitted when CAB and HITL approved
        res2: PolicyReasoningResult = pac.evaluate_action_policy(
            asset_role="Domain Controller",
            action_name="RestartService",
            is_business_hours=True,
            hitl_approved=True,
            cab_approved=True
        )
        self.assertTrue(res2.allowed)

    def test_02_enterprise_resource_scheduler(self):
        """Validates priority queue scheduling (CRITICAL > HIGH > LOW) and worker pool concurrency bounds."""
        scheduler = EnterpriseResourceScheduler(max_worker_capacity=2)

        # Enqueue low and critical tasks
        scheduler.enqueue_task("INC-LOW-01", "PC-01", "PRB-L1-01", "ping", IncidentPriority.LOW)
        scheduler.enqueue_task("INC-CRIT-01", "DC-01", "PRB-L3-01", "gateway_ping", IncidentPriority.CRITICAL)

        # First worker acquires CRITICAL task
        worker1_task = scheduler.acquire_worker_slot()
        self.assertIsNotNone(worker1_task)
        assert worker1_task is not None
        self.assertEqual(worker1_task.incident_id, "INC-CRIT-01")

        # Second worker acquires LOW task
        worker2_task = scheduler.acquire_worker_slot()
        self.assertIsNotNone(worker2_task)
        assert worker2_task is not None
        self.assertEqual(worker2_task.incident_id, "INC-LOW-01")

        # Worker pool is now full (2/2)
        worker3_task = scheduler.acquire_worker_slot()
        self.assertIsNone(worker3_task)

        # Release worker slot
        scheduler.release_worker_slot()
        self.assertEqual(scheduler.pool_status().active_workers, 1)

    def test_03_global_dependency_graph(self):
        """Validates L1-L7 topology failure projection from Core Firewall down to endpoint assets."""
        graph = GlobalDependencyGraph()
        report: ImpactProjectionReport = graph.project_failure_impact("FW-HQ-01")
        self.assertEqual(report.impacted_layer, "FIREWALL")
        self.assertGreater(report.total_affected_endpoints, 0)
        self.assertIn("POS-KASIR-01", report.affected_endpoint_ids)

    def test_04_continuous_causal_validation(self):
        """Validates continuous SCM edge probability updating and stale edge pruning."""
        causal_val = ContinuousCausalValidation()
        edge: CausalEdgeValidationStatus = causal_val.reevaluate_causal_edge(
            edge_id="DNS_Timeout->TLS_Failure",
            recent_supporting_count=5,
            recent_contradicting_count=90
        )
        self.assertIn(edge.status, ["WEIGHT_DECREASED", "PRUNED"])
        self.assertTrue(edge.drift_alert)

    def test_05_autonomous_sop_generator(self):
        """Validates automated SOP runbook markdown generation from completed investigation reports."""
        generator = AutonomousSOPGenerator()
        inv_report = {
            "incident_summary": "L1 Wireless RSSI Drop on Kasir 01",
            "observed_symptoms": ["RSSI = -88dBm", "Packet loss = 85%"],
            "probe_execution_timeline": ["Executed PRB-L1-01 [Physical Link]: FAILED"],
            "validated_root_cause": "Wireless Access Point Signal Degradation",
            "recommended_remediation": "Reconnect AP Interface / Change WiFi Channel",
            "rollback_strategy": "Restore AP Channel 6 Profile",
            "confidence_score": 0.96
        }
        sop: GeneratedSOPDocument = generator.generate_sop_from_investigation("INC-9090", inv_report)
        self.assertEqual(sop.status, "DRAFT_AWAITING_HUMAN_REVIEW")
        self.assertIn("# Standard Operating Procedure", sop.markdown_content)
        self.assertIn("Wireless Access Point Signal Degradation", sop.markdown_content)


if __name__ == "__main__":
    unittest.main()
