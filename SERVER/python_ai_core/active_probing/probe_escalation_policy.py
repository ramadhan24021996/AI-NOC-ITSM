"""
Probe Escalation Policy Module
Manages gradual, step-wise diagnostic probing escalation:
Level 1 (Read-Only) -> Level 2 (Low-Risk Active) -> Level 3 (Medium-Risk) -> HITL Gate -> Level 4 (High-Risk).
Prevents premature jump to high-risk active commands.
"""

from dataclasses import dataclass
from typing import List, Optional
from .probe_catalog import DiagnosticProbe, RiskLevel


@dataclass
class EscalationDecision:
    current_level: RiskLevel
    next_level: RiskLevel
    probe_to_execute: Optional[DiagnosticProbe]
    requires_hitl: bool
    reason: str


class ProbeEscalationPolicy:
    """Enforces step-wise risk level escalation for diagnostic probing."""

    def __init__(self):
        self.current_risk_level = RiskLevel.LEVEL_1_READ_ONLY

    def evaluate_escalation(
        self,
        candidate_probes: List[DiagnosticProbe],
        level1_evidence_sufficient: bool,
        level2_evidence_sufficient: bool,
        hitl_approved: bool = False
    ) -> EscalationDecision:
        """Determines next probe to execute adhering to strict escalation hierarchy."""

        # 1. First exhaust Level 1 Read-Only Probes
        level1_probes = [p for p in candidate_probes if p.risk_level == RiskLevel.LEVEL_1_READ_ONLY]
        if level1_probes and not level1_evidence_sufficient:
            return EscalationDecision(
                current_level=RiskLevel.LEVEL_1_READ_ONLY,
                next_level=RiskLevel.LEVEL_1_READ_ONLY,
                probe_to_execute=level1_probes[0],
                requires_hitl=False,
                reason="Executing safe Level 1 Read-Only diagnostic probe"
            )

        # 2. Escalate to Level 2 Low-Risk Active Probes if Level 1 evidence is insufficient
        level2_probes = [p for p in candidate_probes if p.risk_level == RiskLevel.LEVEL_2_LOW_RISK]
        if level2_probes and not level2_evidence_sufficient:
            return EscalationDecision(
                current_level=RiskLevel.LEVEL_1_READ_ONLY,
                next_level=RiskLevel.LEVEL_2_LOW_RISK,
                probe_to_execute=level2_probes[0],
                requires_hitl=False,
                reason="Level 1 evidence insufficient; escalating to Level 2 Low-Risk active probe"
            )

        # 3. Escalate to Level 3 Medium-Risk Active Probes
        level3_probes = [p for p in candidate_probes if p.risk_level == RiskLevel.LEVEL_3_MEDIUM_RISK]
        if level3_probes:
            return EscalationDecision(
                current_level=RiskLevel.LEVEL_2_LOW_RISK,
                next_level=RiskLevel.LEVEL_3_MEDIUM_RISK,
                probe_to_execute=level3_probes[0],
                requires_hitl=False,
                reason="Escalating to Level 3 Medium-Risk probe after Level 1-2 probes"
            )

        # 4. Escalate to Level 4 High-Risk Probes (Requires HITL)
        level4_probes = [p for p in candidate_probes if p.risk_level == RiskLevel.LEVEL_4_HIGH_RISK]
        if level4_probes:
            if not hitl_approved:
                return EscalationDecision(
                    current_level=RiskLevel.LEVEL_3_MEDIUM_RISK,
                    next_level=RiskLevel.LEVEL_4_HIGH_RISK,
                    probe_to_execute=None,
                    requires_hitl=True,
                    reason="Level 4 High-Risk probe required but blocked awaiting Human-in-the-Loop approval"
                )
            return EscalationDecision(
                current_level=RiskLevel.LEVEL_3_MEDIUM_RISK,
                next_level=RiskLevel.LEVEL_4_HIGH_RISK,
                probe_to_execute=level4_probes[0],
                requires_hitl=True,
                reason="Level 4 High-Risk probe authorized by Human-in-the-Loop operator"
            )

        return EscalationDecision(
            current_level=self.current_risk_level,
            next_level=self.current_risk_level,
            probe_to_execute=None,
            requires_hitl=False,
            reason="No additional candidate probes available for escalation"
        )
