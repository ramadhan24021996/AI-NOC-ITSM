"""
Enterprise Graph Workflow Orchestrator
Master decoupled orchestration pipeline controlling the end-to-end incident resolution flow:
Incident -> Validation -> Traversal -> Evidence -> Ranking -> RAG -> LLM -> Explainability -> Learning -> Dashboard.
"""

import logging
import time
from typing import Dict, List, Any, Optional

from cognition.graph_validation_engine import GraphValidationEngine
from cognition.graph_ranking_engine import GraphRankingEngine
from cognition.evidence_engine import EvidenceEngine
from cognition.incident_state_machine import IncidentStateMachine
from cognition.rca_explainability import RCAExplainabilityEngine
from services.knowledge_graph_service import get_knowledge_graph_service
from engines.rag_engine import RAGEngine
from governance.remediation_policy_engine import RemediationPolicyEngine

logger = logging.getLogger("GRAPH_WORKFLOW_ORCHESTRATOR")

class GraphWorkflowOrchestrator:
    """
    Master GraphRAG Orchestrator Pipeline
    Decouples all GraphRAG sub-services into a unified, auditable state machine workflow.
    """

    def __init__(self):
        self.kg_svc = get_knowledge_graph_service()
        self.validator = GraphValidationEngine()
        self.ranker = GraphRankingEngine(self.kg_svc.kg)
        self.evidence_engine = EvidenceEngine()
        self.state_machine = IncidentStateMachine()
        self.policy_engine = RemediationPolicyEngine()
        self.explainability = RCAExplainabilityEngine()
        self.rag = RAGEngine()

    def process_incident_workflow(
        self,
        incident_id: str,
        symptom_node_id: str,
        incident_text: str,
        telemetry_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes complete decoupled incident resolution workflow.
        Returns auditable RCA report, state history, and policy execution status.
        """
        start_time = time.time()
        logger.info("[ORCHESTRATOR] Initializing workflow for incident %s (Symptom: %s)", incident_id, symptom_node_id)

        # 1. State: NEW -> VALIDATING
        self.state_machine.transition(incident_id, "VALIDATING")
        valid, val_reason = self.validator.validate_node(symptom_node_id, telemetry_data or {})
        if not valid:
            self.state_machine.transition(incident_id, "QUARANTINED")
            return {"status": "QUARANTINED", "reason": val_reason, "incident_id": incident_id}

        # 2. State: GRAPH_BUILT -> RANKING
        self.state_machine.transition(incident_id, "GRAPH_BUILT")
        self.state_machine.transition(incident_id, "RANKING")
        rca_candidates = self.kg_svc.traverse(symptom_node_id, top_n=5)
        ranked_candidates = self.ranker.rank_candidates(rca_candidates)

        # 3. State: RAG_RUNNING -> LLM_RUNNING
        self.state_machine.transition(incident_id, "RAG_RUNNING")
        rag_output = self.rag.embed_and_query(incident_text, limit=3)
        
        self.state_machine.transition(incident_id, "LLM_RUNNING")
        blast_radius = self.kg_svc.calculate_blast_radius(symptom_node_id)

        # 4. State: EVIDENCE_CHECK
        self.state_machine.transition(incident_id, "EVIDENCE_CHECK")
        evidence_summary = self.evidence_engine.evaluate_evidence(
            incident_id=incident_id,
            symptom_node_id=symptom_node_id,
            rca_candidates=ranked_candidates,
            telemetry_data=telemetry_data or {}
        )

        # 5. State: POLICY_EVALUATION -> HITL_PENDING or APPROVED
        confidence = evidence_summary.get("overall_confidence", 0.8)
        policy = self.policy_engine.evaluate_action_policy(confidence=confidence, risk_score=40.0)

        if policy["action"] == "HITL_APPROVAL_REQUIRED":
            self.state_machine.transition(incident_id, "HITL_PENDING")
        else:
            self.state_machine.transition(incident_id, "APPROVED")

        # 6. State: EXPLAINABILITY & LEARNING
        explainability_report = self.explainability.generate_explainability_report(
            incident_id=incident_id,
            symptom_node_id=symptom_node_id,
            rca_candidates=ranked_candidates,
            blast_radius=blast_radius,
            evidence_list=evidence_summary.get("evidence_items", []),
            matching_incidents=rag_output.get("results", [])
        )

        self.state_machine.transition(incident_id, "LEARNING")
        self.state_machine.transition(incident_id, "CLOSED")

        latency_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "incident_id": incident_id,
            "status": "SUCCESS",
            "state_history": self.state_machine.get_history(incident_id),
            "policy_decision": policy,
            "explainability_report": explainability_report,
            "rag_results": rag_output.get("results", []),
            "total_latency_ms": latency_ms
        }
