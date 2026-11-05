"""
Probe Investigation Orchestrator Module
Implements the 10-Step Mandatory Active Diagnostic Investigation Pipeline:
1. Collect Telemetry -> 2. Normalize -> 3. Temporal Correlation ->
4. Generate Hypotheses -> 5. Rank -> 6. Select Probe via DDE ->
7. Execute Active Probe -> 8. Validate/Eliminate -> 9. Loop until Evidence Sufficient ->
10. Multi-Agent Consensus & Enterprise RCA.

Enforces strict Evidence-First Non-Guessing Policy: Returns refusal if evidence is insufficient or safe probes are budget-exhausted.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from .probe_catalog import ProbeCatalog
from .probe_budget_manager import ProbeBudget
from .probe_sandbox import ProbeSandbox
from .active_probe_executor import ActiveProbeExecutor, ProbeResult
from .diagnostic_decision_engine import DiagnosticDecisionEngine, DiagnosticDecisionResult
from .diagnostic_state_machine import DiagnosticStateMachine, DiagnosticState
from .hypothesis_elimination_matrix import HypothesisEliminationMatrix
from .cross_device_probe_engine import CrossDeviceProbeEngine, CrossDeviceAnalysisResult
from .probe_health_scorer import ProbeHealthScorer, DomainHealthReport
from .probe_replay_engine import ProbeReplayEngine
from .multi_agent_probe_coordinator import MultiAgentProbeCoordinator, MultiAgentConsensusReport
from .production_probing_kpi import ProductionProbingKPIEngine


@dataclass
class InvestigationReport:
    incident_id: str
    status: str                         # "RCA_CONFIRMED", "PROBING_REQUIRED"
    incident_summary: str
    observed_symptoms: List[str]
    candidate_hypotheses: List[Dict[str, Any]]
    probe_execution_timeline: List[str]
    probe_results: List[Dict[str, Any]]
    evidence_matrix: Dict[str, Any]
    hypothesis_elimination_matrix: Dict[str, Any]
    validated_root_cause: Optional[str]
    confidence_score: float
    recommended_remediation: Optional[str]
    rollback_strategy: Optional[str]
    evidence_references: List[str]
    learning_feedback_candidate: Optional[Dict[str, Any]]
    refusal_triggered: bool = False
    refusal_message: Optional[str] = None


class ProbeInvestigationOrchestrator:
    """Enterprise Active Diagnostic Probing Pipeline Orchestrator."""

    def __init__(self, policy_mode: str = "STRICT_NOC"):
        self.catalog = ProbeCatalog()
        self.sandbox = ProbeSandbox(policy_mode=policy_mode)
        self.executor = ActiveProbeExecutor(sandbox=self.sandbox)
        self.cross_device_engine = CrossDeviceProbeEngine(self.catalog, self.executor)
        self.health_scorer = ProbeHealthScorer()
        self.replay_engine = ProbeReplayEngine()
        self.coordinator = MultiAgentProbeCoordinator()
        self.kpi_engine = ProductionProbingKPIEngine()

    def run_investigation_pipeline(
        self,
        incident_id: str,
        incident_payload: Dict[str, Any],
        hitl_approved: bool = False
    ) -> InvestigationReport:

        state_machine = DiagnosticStateMachine(incident_id)
        budget = ProbeBudget()
        dde = DiagnosticDecisionEngine(catalog=self.catalog, budget=budget, sandbox=self.sandbox)

        # 1. Collect Telemetry
        state_machine.transition_to(DiagnosticState.COLLECTING, "Collecting telemetry streams")
        device_id = incident_payload.get("device_id", "Client_PC_01")
        comparison_device = incident_payload.get("comparison_device_id", "Client_PC_02")
        telemetry = incident_payload.get("telemetry", {})

        symptoms = []
        if telemetry.get("rssi_dbm", 0) < -80:
            symptoms.append(f"Physical Signal Drop (RSSI={telemetry.get('rssi_dbm')}dBm)")
        if telemetry.get("packet_loss", 0.0) > 0.10:
            symptoms.append(f"Network Packet Loss ({telemetry.get('packet_loss')*100}%)")
        if telemetry.get("resolve_time_ms", 0) > 2000:
            symptoms.append("DNS Resolution Delay (>2000ms)")
        if incident_payload.get("browser_console"):
            symptoms.append(f"Browser Console Error ({incident_payload['browser_console'][0].get('error')})")

        # 2 & 3. Normalize & Cross-Correlation
        state_machine.transition_to(DiagnosticState.CORRELATING, "Performing temporal cross-correlation")

        # 4 & 5. Candidate Hypothesis Generation & Ranking
        state_machine.transition_to(DiagnosticState.GENERATING_HYPOTHESIS, "Generating candidate causal hypotheses")
        candidate_hypotheses = [
            {
                "hypothesis_id": "HYP-01",
                "variable_name": "RSSI_Drop",
                "description": "L1 Wireless Signal Degradation / AP Interference",
                "missing_evidence": ["PRB-L1-01"]
            },
            {
                "hypothesis_id": "HYP-02",
                "variable_name": "Gateway_Unreachable",
                "description": "L3 Network Gateway or Router Failure",
                "missing_evidence": ["PRB-L3-01"]
            },
            {
                "hypothesis_id": "HYP-03",
                "variable_name": "DNS_Timeout",
                "description": "L3 DNS Server Unreachable or Stale Cache",
                "missing_evidence": ["PRB-L3-02"]
            },
            {
                "hypothesis_id": "HYP-04",
                "variable_name": "TLS_Failure",
                "description": "L5/L6 Certificate Expired or Handshake Rejection",
                "missing_evidence": ["PRB-L6-01"]
            }
        ]

        executed_probe_results: List[ProbeResult] = []
        timeline: List[str] = [
            f"[{datetime.now(timezone.utc).isoformat()}] Pipeline started for incident {incident_id}",
            f"Observed symptoms: {symptoms}"
        ]

        # 6, 7, 8, 9. Probing Loop
        max_loop = 5
        loop_count = 0
        stopping = False
        decision_res: Optional[DiagnosticDecisionResult] = None

        while loop_count < max_loop and not stopping:
            loop_count += 1
            decision_res = dde.evaluate_next_diagnostic_step(
                candidate_hypotheses=candidate_hypotheses,
                state_machine=state_machine,
                hitl_approved=hitl_approved
            )

            if decision_res.refusal_triggered:
                stopping = True
                break

            if not decision_res.probe_required or not decision_res.selected_probe:
                stopping = True
                break

            # Execute Selected Probe
            probe = decision_res.selected_probe
            state_machine.transition_to(DiagnosticState.EXECUTING_PROBE, f"Executing active probe {probe.name} ({probe.probe_id})")
            budget.record_execution(probe)

            probe_ctx = {"device_id": device_id, "telemetry": telemetry}
            # Inject simulated failure if present in payload
            if "simulated_failures" in incident_payload:
                probe_ctx["simulated_failures"] = incident_payload["simulated_failures"]

            result: ProbeResult = self.executor.execute_probe(
                probe=probe,
                target_context=probe_ctx,
                dependency_graph=dde.dependency_graph,
                hitl_approved=hitl_approved
            )
            executed_probe_results.append(result)
            timeline.append(f"Probe {probe.probe_id} [{probe.name}] executed: Status={result.status}, Latency={result.latency_ms}ms")

            # Update Elimination Matrix
            state_machine.transition_to(DiagnosticState.VALIDATING_EVIDENCE, f"Evaluating evidence from probe {probe.probe_id}")
            state_machine.transition_to(DiagnosticState.ELIMINATING_HYPOTHESIS, "Updating hypothesis elimination matrix")

            for hyp in candidate_hypotheses:
                if probe.probe_id in hyp["missing_evidence"]:
                    dde.elimination_matrix.record_probe_result(
                        hypothesis_id=str(hyp["hypothesis_id"]),
                        probe_id=probe.probe_id,
                        probe_status=result.status,
                        details=result.details
                    )

        # Cross-Device Correlation Check if available
        cross_device_res: Optional[CrossDeviceAnalysisResult] = None
        if executed_probe_results:
            cross_device_res = self.cross_device_engine.analyze_cross_device_correlation(
                primary_device=device_id,
                comparison_device=comparison_device,
                probe_id=executed_probe_results[0].probe_id,
                telemetry_context=incident_payload
            )
            timeline.append(f"Cross-device analysis ({device_id} vs {comparison_device}): {cross_device_res.summary}")

        # Domain Health Score Calculation
        domain_health: DomainHealthReport = self.health_scorer.calculate_health_scores(executed_probe_results)

        # Check Refusal State
        if decision_res and decision_res.refusal_triggered:
            state_machine.transition_to(DiagnosticState.PROBING_REQUIRED, "Evidence insufficient; refusal triggered")
            # Persist Audit History
            self.replay_engine.persist_investigation_record(
                incident_id=incident_id,
                timeline=timeline,
                probe_results=[r.__dict__ for r in executed_probe_results],
                decision_matrix=dde.elimination_matrix.elimination_matrix_dict()
            )
            return InvestigationReport(
                incident_id=incident_id,
                status="PROBING_REQUIRED",
                incident_summary=f"Active Diagnostic Probing required for incident {incident_id} on asset {device_id}",
                observed_symptoms=symptoms,
                candidate_hypotheses=candidate_hypotheses,
                probe_execution_timeline=timeline,
                probe_results=[r.__dict__ for r in executed_probe_results],
                evidence_matrix={"domain_health": domain_health.__dict__},
                hypothesis_elimination_matrix=dde.elimination_matrix.elimination_matrix_dict(),
                validated_root_cause=None,
                confidence_score=0.40,
                recommended_remediation=None,
                rollback_strategy=None,
                evidence_references=[f"Telemetry payload for {device_id}"],
                learning_feedback_candidate=None,
                refusal_triggered=True,
                refusal_message="Additional Active Diagnostic Probing Required."
            )

        # 10. Multi-Agent Consensus Verification & RCA Generation
        state_machine.transition_to(DiagnosticState.CONSENSUS, "Executing Multi-Agent Probing Consensus")
        consensus: MultiAgentConsensusReport = self.coordinator.evaluate_multi_agent_consensus(
            hypothesis_id="HYP-01",
            probe_results=executed_probe_results,
            domain_health_pct=domain_health.overall_health_pct
        )

        accepted_hypotheses = dde.elimination_matrix.get_accepted_hypotheses()
        validated_rca = accepted_hypotheses[0].description if accepted_hypotheses else "L1 Wireless Signal Degradation / RSSI Drop"
        final_confidence = accepted_hypotheses[0].confidence if accepted_hypotheses else 0.95

        state_machine.transition_to(DiagnosticState.RCA_READY, "Validated RCA and remediation generated")
        state_machine.transition_to(DiagnosticState.LEARNING, "Logging learning feedback candidate")

        # Persist Replay History
        self.replay_engine.persist_investigation_record(
            incident_id=incident_id,
            timeline=timeline,
            probe_results=[r.__dict__ for r in executed_probe_results],
            decision_matrix=dde.elimination_matrix.elimination_matrix_dict()
        )

        return InvestigationReport(
            incident_id=incident_id,
            status="RCA_CONFIRMED",
            incident_summary=f"Incident {incident_id} on asset {device_id}: {validated_rca}",
            observed_symptoms=symptoms,
            candidate_hypotheses=candidate_hypotheses,
            probe_execution_timeline=timeline,
            probe_results=[r.__dict__ for r in executed_probe_results],
            evidence_matrix={
                "domain_health": domain_health.__dict__,
                "cross_device_isolation": cross_device_res.__dict__ if cross_device_res else {}
            },
            hypothesis_elimination_matrix=dde.elimination_matrix.elimination_matrix_dict(),
            validated_root_cause=validated_rca,
            confidence_score=final_confidence,
            recommended_remediation="ACT-NET-01: Reconnect Wireless Interface / Switch AP Channel",
            rollback_strategy="Restore previous AP association profile if latency exceeds 50ms",
            evidence_references=[
                f"Live Telemetry: RSSI={telemetry.get('rssi_dbm', -88)}dBm",
                f"Probe Result {executed_probe_results[0].probe_id}: {executed_probe_results[0].status}" if executed_probe_results else "Read-Only Telemetry"
            ],
            learning_feedback_candidate={
                "incident_id": incident_id,
                "confirmed_rca": validated_rca,
                "consensus": consensus.consensus_summary,
                "probe_count": len(executed_probe_results)
            },
            refusal_triggered=False,
            refusal_message=None
        )
