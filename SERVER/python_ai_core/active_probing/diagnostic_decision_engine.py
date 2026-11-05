"""
Diagnostic Decision Engine (DDE) Module
Acts as the central decision core for active diagnostic probing:
- Answers: Is probing required? Is evidence sufficient? Which probe is safest?
  What is the remaining budget? When should the investigation stop?
- Enforces strict Evidence-First Non-Guessing Policy: Returns refusal if evidence is insufficient or probes exhausted.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from .probe_catalog import ProbeCatalog, DiagnosticProbe, RiskLevel
from .probe_budget_manager import ProbeBudget
from .probe_dependency_graph import ProbeDependencyGraph
from .probe_sandbox import ProbeSandbox
from .active_probe_executor import ActiveProbeExecutor, ProbeResult
from .hypothesis_elimination_matrix import HypothesisEliminationMatrix, HypothesisStatus
from .diagnostic_state_machine import DiagnosticStateMachine, DiagnosticState


@dataclass
class DiagnosticDecisionResult:
    probe_required: bool
    evidence_sufficient: bool
    selected_probe: Optional[DiagnosticProbe]
    stopping_reason: Optional[str]
    confidence_score: float
    refusal_triggered: bool
    refusal_message: Optional[str] = None


class DiagnosticDecisionEngine:
    """Enterprise Diagnostic Decision Engine (DDE) orchestrating active diagnostic probing."""

    def __init__(
        self,
        catalog: Optional[ProbeCatalog] = None,
        budget: Optional[ProbeBudget] = None,
        sandbox: Optional[ProbeSandbox] = None
    ):
        self.catalog = catalog or ProbeCatalog()
        self.budget = budget or ProbeBudget()
        self.sandbox = sandbox or ProbeSandbox()
        self.executor = ActiveProbeExecutor(sandbox=self.sandbox)
        self.dependency_graph = ProbeDependencyGraph(catalog=self.catalog)
        self.elimination_matrix = HypothesisEliminationMatrix()

    def evaluate_next_diagnostic_step(
        self,
        candidate_hypotheses: List[Dict[str, Any]],
        state_machine: DiagnosticStateMachine,
        hitl_approved: bool = False
    ) -> DiagnosticDecisionResult:

        # Register hypotheses in elimination matrix
        for hyp in candidate_hypotheses:
            hyp_id = str(hyp.get("hypothesis_id") or hyp.get("variable_name") or "HYP-01")
            var_name = str(hyp.get("variable_name") or "Unknown_Variable")
            desc = str(hyp.get("description") or "Candidate incident cause")
            missing = list(hyp.get("missing_evidence") or ["PRB-L3-01"])
            self.elimination_matrix.register_hypothesis(hyp_id, var_name, desc, missing)

        state_machine.transition_to(DiagnosticState.SELECTING_PROBE, "Evaluating candidate hypotheses for probe selection")

        # 1. Check if an Accepted Hypothesis already has high confidence (> 0.90) and no missing evidence
        accepted = self.elimination_matrix.get_accepted_hypotheses()
        if accepted:
            top_accepted = sorted(accepted, key=lambda x: x.confidence, reverse=True)[0]
            if top_accepted.confidence >= 0.90 and len(top_accepted.missing_evidence) == 0:
                state_machine.transition_to(DiagnosticState.RCA_READY, "Sufficient evidence collected; RCA ready")
                return DiagnosticDecisionResult(
                    probe_required=False,
                    evidence_sufficient=True,
                    selected_probe=None,
                    stopping_reason=f"Sufficient evidence acquired for hypothesis '{top_accepted.hypothesis_id}'",
                    confidence_score=top_accepted.confidence,
                    refusal_triggered=False
                )

        # 2. Check Probe Budget / Time Exhaustion
        if self.budget.is_time_exhausted():
            state_machine.transition_to(DiagnosticState.PROBING_REQUIRED, "Investigation time budget exhausted")
            return DiagnosticDecisionResult(
                probe_required=False,
                evidence_sufficient=False,
                selected_probe=None,
                stopping_reason="Probe budget / time limit reached without sufficient evidence",
                confidence_score=0.40,
                refusal_triggered=True,
                refusal_message="Additional Active Diagnostic Probing Required."
            )

        # 3. Select Probe with Highest Expected Information Gain (EIG)
        unknown_hypotheses = self.elimination_matrix.get_unknown_hypotheses()
        if not unknown_hypotheses and not accepted:
            state_machine.transition_to(DiagnosticState.PROBING_REQUIRED, "No active hypotheses remaining")
            return DiagnosticDecisionResult(
                probe_required=False,
                evidence_sufficient=False,
                selected_probe=None,
                stopping_reason="No viable candidate hypotheses to probe",
                confidence_score=0.30,
                refusal_triggered=True,
                refusal_message="Additional Active Diagnostic Probing Required."
            )

        candidate_probes: List[DiagnosticProbe] = []
        for hyp in (unknown_hypotheses or accepted):
            for probe_id in hyp.missing_evidence:
                p = self.catalog.get_probe(probe_id)
                if p and not self.dependency_graph.is_pruned(p.probe_id):
                    candidate_probes.append(p)

        if not candidate_probes:
            # Fallback to default L1/L3 read-only diagnostic probe
            candidate_probes = [p for p in self.catalog.probes.values() if p.read_only]

        # Rank candidate probes by EIG / risk_level ratio
        ranked_probes = sorted(
            candidate_probes,
            key=lambda p: (p.expected_information_gain / p.risk_level.value),
            reverse=True
        )

        selected_probe: Optional[DiagnosticProbe] = None
        for p in ranked_probes:
            allowed, _ = self.budget.can_execute(p, hitl_approved=hitl_approved)
            if allowed:
                selected_probe = p
                break

        if not selected_probe:
            state_machine.transition_to(DiagnosticState.PROBING_REQUIRED, "All candidate probes blocked or budget exhausted")
            return DiagnosticDecisionResult(
                probe_required=False,
                evidence_sufficient=False,
                selected_probe=None,
                stopping_reason="Probing budget exhausted or safe candidate probes unavailable",
                confidence_score=0.45,
                refusal_triggered=True,
                refusal_message="Additional Active Diagnostic Probing Required."
            )

        return DiagnosticDecisionResult(
            probe_required=True,
            evidence_sufficient=False,
            selected_probe=selected_probe,
            stopping_reason=None,
            confidence_score=selected_probe.expected_information_gain,
            refusal_triggered=False
        )
