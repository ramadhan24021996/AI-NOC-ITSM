"""
Multi-Agent Negotiator Module
Structured Multi-Agent Negotiation Protocol balancing domain specialist trade-offs:
Network Agent (Wants interface restart) vs Security Agent (Wants Zero-Trust audit) vs
Application Agent (Wants high uptime) vs Policy Agent (Enforces CAB business hours).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any


@dataclass
class AgentProposal:
    agent_name: str
    proposed_action: str
    priority_weight: float
    objections: List[str] = field(default_factory=list)


@dataclass
class NegotiationOutcome:
    consensus_action: str
    compromise_reached: bool
    participating_agents: List[str]
    negotiation_summary: str


class MultiAgentNegotiator:
    """Orchestrates multi-agent negotiations to resolve domain conflicts."""

    def negotiate_action_plan(
        self,
        proposals: List[AgentProposal],
        is_business_hours: bool = True
    ) -> NegotiationOutcome:

        agents = [p.agent_name for p in proposals]
        sec_proposal = next((p for p in proposals if p.agent_name == "SecurityAgent"), None)
        net_proposal = next((p for p in proposals if p.agent_name == "NetworkAgent"), None)
        policy_proposal = next((p for p in proposals if p.agent_name == "PolicyAgent"), None)

        # Conflict resolution logic
        if net_proposal and net_proposal.proposed_action in ("ResetNetworkStack", "RestartService") and is_business_hours:
            if sec_proposal or policy_proposal:
                # Negotiated Compromise: Switch to Non-Disruptive Flush DNS + HITL Gate
                summary = (
                    f"Negotiation Reached: NetworkAgent proposed '{net_proposal.proposed_action}', "
                    f"but SecurityAgent/PolicyAgent objected during business hours. "
                    f"Compromise action 'FlushDNS_With_HITL' selected."
                )
                return NegotiationOutcome(
                    consensus_action="FlushDNS_With_HITL",
                    compromise_reached=True,
                    participating_agents=agents,
                    negotiation_summary=summary
                )

        top_proposal = sorted(proposals, key=lambda p: p.priority_weight, reverse=True)[0] if proposals else AgentProposal("ArchitectAgent", "ReadDiagnostics", 1.0)
        return NegotiationOutcome(
            consensus_action=top_proposal.proposed_action,
            compromise_reached=False,
            participating_agents=agents,
            negotiation_summary=f"Unanimous agreement reached on '{top_proposal.proposed_action}'"
        )
