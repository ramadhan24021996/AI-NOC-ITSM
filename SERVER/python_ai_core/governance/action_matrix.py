"""
Enterprise Action Matrix (Phase 3.4)
Classifies actions into 7 Risk Levels (A0 - A6) with explicit approval guardrails:
- A0 (Observation): Ping, SNMP, WMI, SMART Read -> AUTO
- A1 (Diagnostic): Traceroute, DNS Query, Process List -> AUTO
- A2 (Safe Remediation): Flush DNS, Renew DHCP, Restart Service Non-Critical -> AUTO/Fast-Track
- A3 (Controlled Remediation): Restart Adapter, Clear Cache, Restart Browser -> Policy + Fast Approval
- A4 (Privileged Remediation): Firewall Change, Service Config -> HITL
- A5 (Critical System Change): Registry, Driver, Network Stack -> Mandatory HITL
- A6 (Destructive): Disk Operation, OS Reset, File Deletion -> Dual Approval (Mandatory)
"""

import logging
from enum import Enum
from typing import Dict, Any

logger = logging.getLogger("ACTION_MATRIX")

class ActionLevel(Enum):
    A0_OBSERVATION = "A0_OBSERVATION"
    A1_DIAGNOSTIC = "A1_DIAGNOSTIC"
    A2_SAFE_REMEDIATION = "A2_SAFE_REMEDIATION"
    A3_CONTROLLED_REMEDIATION = "A3_CONTROLLED_REMEDIATION"
    A4_PRIVILEGED_REMEDIATION = "A4_PRIVILEGED_REMEDIATION"
    A5_CRITICAL_SYSTEM_CHANGE = "A5_CRITICAL_SYSTEM_CHANGE"
    A6_DESTRUCTIVE = "A6_DESTRUCTIVE"

class ActionMatrix:
    """
    Enterprise Action Matrix Classifier
    Enforces risk level assignment and required approval type.
    """

    def __init__(self):
        self.matrix: Dict[str, Dict[str, Any]] = {
            "ping": {"level": ActionLevel.A0_OBSERVATION, "approval": "AUTO", "risk_score": 5},
            "traceroute": {"level": ActionLevel.A1_DIAGNOSTIC, "approval": "AUTO", "risk_score": 10},
            "flush_dns": {"level": ActionLevel.A2_SAFE_REMEDIATION, "approval": "AUTO_FAST_TRACK", "risk_score": 20},
            "restart_adapter": {"level": ActionLevel.A3_CONTROLLED_REMEDIATION, "approval": "POLICY_FAST_APPROVAL", "risk_score": 40},
            "modify_firewall": {"level": ActionLevel.A4_PRIVILEGED_REMEDIATION, "approval": "HITL_SINGLE", "risk_score": 65},
            "reset_network_stack": {"level": ActionLevel.A5_CRITICAL_SYSTEM_CHANGE, "approval": "MANDATORY_HITL", "risk_score": 85},
            "format_disk": {"level": ActionLevel.A6_DESTRUCTIVE, "approval": "DUAL_APPROVAL_MANDATORY", "risk_score": 100}
        }

    def classify_action(self, action_id: str) -> Dict[str, Any]:
        """Classifies action into risk level and approval requirement. Default-deny for unknown actions."""
        if not action_id or not isinstance(action_id, str):
            return {
                "action_id": action_id,
                "level": "UNKNOWN",
                "approval": "UNKNOWN_ACTION_BLOCKED",
                "risk_score": 999
            }

        info = self.matrix.get(action_id.lower())
        if not info:
            logger.warning(f"[ACTION_MATRIX] Unknown action_id '{action_id}' encountered. Defaulting to UNKNOWN_ACTION_BLOCKED.")
            return {
                "action_id": action_id,
                "level": "UNKNOWN",
                "approval": "UNKNOWN_ACTION_BLOCKED",
                "risk_score": 999
            }

        return {
            "action_id": action_id,
            "level": info["level"].value,
            "approval": info["approval"],
            "risk_score": info["risk_score"]
        }
