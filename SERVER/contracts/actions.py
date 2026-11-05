"""
SERVER.contracts.actions — Action Contracts
Defines domain action contracts for the Enterprise AI Operations Platform.
These contracts specify the structure of actions dispatched by Jarvis/AI kernel.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from SERVER.shared.enums import ActionRiskLevel


@dataclass
class ActionContract:
    """Base contract for all dispatchable actions."""
    action_id: str
    action_type: str
    target: str                                  # resource or system to act on
    payload: Dict[str, Any]
    risk_level: ActionRiskLevel = ActionRiskLevel.LOW_RISK
    initiated_by: str = "jarvis"                 # agent or user id
    requires_approval: bool = False
    version: str = "v1.0"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class RemediationActionContract(ActionContract):
    """Action contract for automated remediation steps."""
    incident_id: Optional[str] = None
    rollback_available: bool = False
    estimated_impact: str = "low"

    def __post_init__(self):
        self.action_type = "Remediation"
        # Auto-require approval for HIGH_RISK/CRITICAL_RISK
        if self.risk_level in (ActionRiskLevel.HIGH_RISK, ActionRiskLevel.CRITICAL_RISK):
            self.requires_approval = True


@dataclass
class DiagnosticActionContract(ActionContract):
    """Action contract for diagnostic / read-only operations."""
    scope: str = "local"                         # local | cluster | global
    timeout_seconds: int = 30

    def __post_init__(self):
        self.action_type = "Diagnostic"
        self.risk_level = ActionRiskLevel.READ_ONLY  # diagnostics are always read-only
        self.requires_approval = False


@dataclass
class EscalationActionContract(ActionContract):
    """Action contract for human escalation requests."""
    escalation_level: str = "L1"                # L1 | L2 | L3 | ONCALL
    channel: str = "teams"                      # teams | pagerduty | slack
    sla_minutes: int = 15

    def __post_init__(self):
        self.action_type = "Escalation"
        self.requires_approval = False           # escalations never blocked
