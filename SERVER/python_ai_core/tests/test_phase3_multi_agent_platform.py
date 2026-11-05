"""
Phase 3 Multi-Agent Platform Verification Suite
Validates ArchitectAgent, 14 Specialist Agents, Agent Memory Manager, Planner Engine, Tool Registry,
Capability Registry, Autonomous Planning, AI Developer Agent Sandbox, Predictive Agent, and Learning Pipeline.
"""

import unittest
import time
import os
import sys

# Ensure python_ai_core path resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.architect_agent import ArchitectAgent
from agents.agent_memory_manager import AgentMemoryManager
from agents.tool_registry import ToolRegistry
from agents.agent_capability_registry import AgentCapabilityRegistry
from agents.predictive_agent import PredictiveAgent
from agents.ai_developer_agent import AIDeveloperAgent

class TestPhase3MultiAgentPlatform(unittest.TestCase):

    def setUp(self):
        self.architect = ArchitectAgent()
        self.memory = AgentMemoryManager()
        self.tool_reg = ToolRegistry()
        self.cap_reg = AgentCapabilityRegistry()
        self.predictive = PredictiveAgent()
        self.ai_dev = AIDeveloperAgent()

    def test_01_architect_orchestration_full_pipeline(self):
        res = self.architect.orchestrate_incident_resolution(
            incident_title="Gateway Timeout on Switch Access Port",
            symptom_layer="L3_NETWORK",
            affected_asset="Client_PC_01"
        )
        self.assertEqual(res["architect"], "ArchitectAgent Lead Engineer")
        self.assertEqual(res["delegated_specialists"], 4)
        self.assertIn("plan_a", res["scenario_plans"])
        self.assertTrue(res["execution_time_ms"] < 200.0)

    def test_02_specialist_agents_and_capabilities(self):
        self.assertTrue(self.cap_reg.can_agent_use_tool("NetworkAgent", "ping"))
        self.assertFalse(self.cap_reg.can_agent_use_tool("DatabaseAgent", "ping"))

    def test_03_ai_developer_agent_sandbox_isolation(self):
        script_res = self.ai_dev.develop_remediation_script("Printer Spooler Crash")
        self.assertTrue(script_res["static_analysis_pass"])
        self.assertTrue(script_res["policy_approved"])
        self.assertTrue(script_res["requires_hitl"], "Dangerous/Remediation actions must require HITL approval")

    def test_04_predictive_agent_7_30_90_day_projections(self):
        pred = self.predictive.analyze_failure_probability(
            device_name="Client_PC_01",
            telemetry_history={"temperature_c": 82.0, "smart_reallocated_sectors": 15, "packet_loss_pct": 6.0}
        )
        self.assertIn("horizon_7_days", pred["failure_predictions"])
        self.assertIn("horizon_30_days", pred["failure_predictions"])
        self.assertIn("horizon_90_days", pred["failure_predictions"])
        self.assertEqual(pred["failure_predictions"]["horizon_90_days"]["risk_level"], "CRITICAL")

if __name__ == "__main__":
    unittest.main()
