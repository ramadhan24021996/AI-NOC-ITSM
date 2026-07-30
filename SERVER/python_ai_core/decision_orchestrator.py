import json
import logging
import os
from typing import Dict, Any
from schemas.decision_schema import DecisionPackageSchema

logger = logging.getLogger("DECISION_ORCHESTRATOR")

class DecisionOrchestrator:
    def __init__(self):
        self.system_prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        possible_paths = [
            os.path.join(os.path.dirname(__file__), "..", "..", "DOCUMENTATION", "prompts", "decision_orchestrator.md"),
            os.path.join(os.path.dirname(__file__), "..", "DOCUMENTATION", "prompts", "decision_orchestrator.md"),
            os.path.join(os.path.dirname(__file__), "DOCUMENTATION", "prompts", "decision_orchestrator.md"),
            "/app/DOCUMENTATION/prompts/decision_orchestrator.md",
            "/home/it-itsm/AI/incident-analysis/DOCUMENTATION/prompts/decision_orchestrator.md"
        ]
        for path in possible_paths:
            abspath = os.path.abspath(path)
            if os.path.exists(abspath):
                try:
                    with open(abspath, "r") as f:
                        return f.read()
                except Exception as e:
                    logger.warning(f"Failed reading prompt at {abspath}: {e}")
        return "You are the Enterprise Incident Commander and HITL Governance Engine. Output strict JSON."

    async def generate_decision_package(
        self,
        router,
        severity_score: int,
        incident_details: Dict[str, Any],
        historical_context: list,
        evidence_pkg: Any,
        causal_dag: Dict[str, Any],
        critic_res: Dict[str, Any],
        consensus_verdict: Dict[str, Any]
    ) -> DecisionPackageSchema:
        """
        Executes the Sprint R Decision Orchestrator prompt via the LLM Router.
        Returns a strongly-typed DecisionPackageSchema.
        """
        from ai_supervisor import execute_validated_llm
        
        # Build the dynamic payload
        payload = {
            "incident": incident_details,
            "historical_knowledge": historical_context,
            "evidence": evidence_pkg.to_dict() if hasattr(evidence_pkg, "to_dict") else str(evidence_pkg),
            "causal_graph": causal_dag,
            "critic_feedback": critic_res,
            "consensus_verdict": consensus_verdict
        }

        prompt = (
            f"{self.system_prompt}\n\n"
            f"--- CURRENT INCIDENT CONTEXT ---\n"
            f"{json.dumps(payload, indent=2, default=str)}\n\n"
            f"Generate the final Decision Package JSON now."
        )

        logger.info(f"Generating Enterprise Decision Package for incident {incident_details.get('incident_id')}...")
        
        # execute_validated_llm will enforce the output to match DecisionPackageSchema perfectly
        decision_package = await execute_validated_llm(
            router=router,
            severity_score=severity_score,
            prompt=prompt,
            schema_class=DecisionPackageSchema,
            max_attempts=3
        )
        
        return decision_package

def get_decision_orchestrator():
    return DecisionOrchestrator()
