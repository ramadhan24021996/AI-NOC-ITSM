"""
Intervention Planner Module
Maps abstract do(X = False) counterfactual interventions to concrete actionable remediation catalog steps.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any


@dataclass
class ActionableRemediationStep:
    action_id: str
    action_name: str
    target_component: str
    command_template: str
    risk_level: str       # "LOW", "MEDIUM", "HIGH"
    requires_hitl: bool


class InterventionPlanner:
    def __init__(self):
        # target_variable -> List[ActionableRemediationStep]
        self._catalog: Dict[str, List[ActionableRemediationStep]] = {}
        self._initialize_default_catalog()

    def _initialize_default_catalog(self):
        """Initializes concrete remediation catalog for SCM target variables"""
        self._catalog["PacketLoss"] = [
            ActionableRemediationStep("ACT-NET-01", "Restart Network Interface", "NetworkAdapter", "ip link set {interface} down && ip link set {interface} up", "LOW", False),
            ActionableRemediationStep("ACT-NET-02", "Renew DHCP Lease", "DHCPClient", "dhclient -r {interface} && dhclient {interface}", "LOW", False),
            ActionableRemediationStep("ACT-NET-03", "Switch Wireless AP", "WiFiManager", "nmcli dev wifi connect {ssid_backup}", "MEDIUM", True)
        ]

        self._catalog["DNS_Timeout"] = [
            ActionableRemediationStep("ACT-DNS-01", "Flush DNS Cache", "DNSResolver", "systemd-resolve --flush-caches", "LOW", False),
            ActionableRemediationStep("ACT-DNS-02", "Fallback to Secondary DNS", "DNSResolver", "echo 'nameserver 8.8.8.8' >> /etc/resolv.conf", "MEDIUM", False)
        ]

        self._catalog["Printer_Offline"] = [
            ActionableRemediationStep("ACT-PRN-01", "Restart Print Spooler", "PrintSpooler", "systemctl restart cups", "LOW", False),
            ActionableRemediationStep("ACT-PRN-02", "Clear Print Queue", "PrintSpooler", "cancel -a -x", "MEDIUM", False)
        ]

        self._catalog["POS_Error"] = [
            ActionableRemediationStep("ACT-APP-01", "Restart POS Service", "POSService", "systemctl restart pos-terminal", "MEDIUM", True)
        ]

    def get_actionable_steps(self, target_variable: str) -> List[ActionableRemediationStep]:
        """
        Returns concrete remediation steps for an abstract counterfactual target variable.
        """
        return self._catalog.get(target_variable, [
            ActionableRemediationStep(
                action_id=f"ACT-GEN-01",
                action_name=f"Generic Service Restart ({target_variable})",
                target_component=target_variable,
                command_template=f"systemctl restart {target_variable.lower()}",
                risk_level="MEDIUM",
                requires_hitl=True
            )
        ])
