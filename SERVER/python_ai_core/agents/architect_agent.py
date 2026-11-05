"""
Enterprise Autonomous AI Architect (Phase 3 Capability 1)
Acts as the Lead System Architect coordinating the entire Multi-Agent troubleshooting pipeline:
Incident -> Telemetry -> Evidence -> Hypothesis -> Planning -> Task Delegation -> Verification -> Decision
"""

import logging
import time
from typing import Dict, List, Any

from agents.agent_memory_manager import AgentMemoryManager
from agents.tool_registry import ToolRegistry
from agents.agent_capability_registry import AgentCapabilityRegistry
from agents.planner_engine import PlannerEngine
from agents.autonomous_planning_engine import AutonomousPlanningEngine
from agents.ai_developer_agent import AIDeveloperAgent
from agents.predictive_agent import PredictiveAgent
from agents.agent_learning_pipeline import AgentLearningPipeline
from agents.specialist_agents import (
    NetworkAgent, OSAgent, StorageAgent, DatabaseAgent, SecurityAgent,
    ApplicationAgent, IdentityAgent, VirtualizationAgent, CloudAgent,
    BrowserAgent, PrinterAgent, KnowledgeAgent, RemediationAgent, LearningAgent
)

from active_probing import ProbeInvestigationOrchestrator

logger = logging.getLogger("ARCHITECT_AGENT")

class ArchitectAgent:
    """
    Enterprise Principal AI Architect
    Lead Engineer reasoning core that orchestrates 14 Specialist Agents, Memory, Planning, Zero-Trust Execution,
    and Active Diagnostic Probing Engine (Hypothesis-Driven Mode).
    """

    def __init__(self):
        self.memory_mgr = AgentMemoryManager()
        self.tool_reg = ToolRegistry()
        self.cap_reg = AgentCapabilityRegistry()
        self.planner = PlannerEngine()
        self.scenario_planner = AutonomousPlanningEngine()
        self.ai_dev_agent = AIDeveloperAgent()
        self.predictive_agent = PredictiveAgent()
        self.learning_pipeline = AgentLearningPipeline()
        self.active_probing_orchestrator = ProbeInvestigationOrchestrator()

        # Initialize 14 Specialist Agents
        self.specialists: Dict[str, Any] = {
            "NetworkAgent": NetworkAgent(),
            "OSAgent": OSAgent(),
            "StorageAgent": StorageAgent(),
            "DatabaseAgent": DatabaseAgent(),
            "SecurityAgent": SecurityAgent(),
            "ApplicationAgent": ApplicationAgent(),
            "IdentityAgent": IdentityAgent(),
            "VirtualizationAgent": VirtualizationAgent(),
            "CloudAgent": CloudAgent(),
            "BrowserAgent": BrowserAgent(),
            "PrinterAgent": PrinterAgent(),
            "KnowledgeAgent": KnowledgeAgent(),
            "RemediationAgent": RemediationAgent(),
            "LearningAgent": LearningAgent()
        }

    def orchestrate_incident_resolution(self, incident_title: str, symptom_layer: str, affected_asset: str) -> Dict[str, Any]:
        """
        Full Lead Architect Pipeline Execution:
        Incident -> Telemetry -> Evidence -> Hypothesis -> Planning -> Delegation -> Decision
        """
        start_time = time.time()

        # 1. Incident Decomposition & Memory Initialization
        self.memory_mgr.set_working_memory("active_incident", incident_title)
        self.memory_mgr.add_reasoning_step("ArchitectAgent", f"Decomposing incident '{incident_title}' on {affected_asset}", 0.98)

        # 2. Generate DAG Plan
        dag_plan = self.planner.create_incident_plan(incident_title, symptom_layer)

        # 3. Delegate to Specialist Agents
        delegation_results = []
        for task in dag_plan:
            agent = self.specialists.get(task.assigned_agent)
            if agent:
                res = agent.analyze({"asset": affected_asset, "action": task.action})
                delegation_results.append(res)

        # 4. Generate Multi-Scenario Plans A/B/C & Rollback
        scenario_plans = self.scenario_planner.generate_scenario_plans("L3 Gateway Timeout / Duplex Mismatch", affected_asset)

        # 5. Developer Agent Candidate Script
        dev_script = self.ai_dev_agent.develop_remediation_script(incident_title)

        exec_time_ms = (time.time() - start_time) * 1000

        return {
            "architect": "ArchitectAgent Lead Engineer",
            "incident": incident_title,
            "asset": affected_asset,
            "dag_plan_steps": len(dag_plan),
            "delegated_specialists": len(delegation_results),
            "scenario_plans": scenario_plans,
            "candidate_remediation_script": dev_script,
            "execution_time_ms": round(exec_time_ms, 2),
            "confidence_score": 0.98,
            "status": "PLANNING_COMPLETED_AWAITING_HITL"
        }

    def investigate_with_active_probing(
        self,
        incident_id: str,
        payload: Dict[str, Any],
        hitl_approved: bool = False
    ) -> Dict[str, Any]:
        """
        Executes active diagnostic probing pipeline in Hypothesis-Driven Investigation Mode.
        Enforces evidence-first policy: Refuses RCA generation if evidence is insufficient or safe probes are budget-exhausted.
        """
        report = self.active_probing_orchestrator.run_investigation_pipeline(
            incident_id=incident_id,
            incident_payload=payload,
            hitl_approved=hitl_approved
        )
        return report.__dict__

