"""
Active Diagnostic Probe Catalog Module
Defines L1-L4 Diagnostic Probes mapped across OSI Layers L1 to L7.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class RiskLevel(Enum):
    LEVEL_1_READ_ONLY = 1     # Read-only diagnostics (Ping, DNS, TLS, EventLog, SMART, etc.)
    LEVEL_2_LOW_RISK = 2       # Low-risk non-disruptive active (Renew DHCP, Flush DNS, etc.)
    LEVEL_3_MEDIUM_RISK = 3    # Medium-risk (Restart Adapter, Restart Application, etc.)
    LEVEL_4_HIGH_RISK = 4      # High-risk (Reset NetStack, Registry Edit, Driver Swap -> HITL Enforced)


class OSILayer(Enum):
    L1_PHYSICAL = 1
    L2_DATALINK = 2
    L3_NETWORK = 3
    L4_TRANSPORT = 4
    L5_SESSION = 5
    L6_PRESENTATION = 6
    L7_APPLICATION = 7


@dataclass
class DiagnosticProbe:
    probe_id: str
    name: str
    risk_level: RiskLevel
    osi_layer: OSILayer
    target_hypothesis_types: List[str]
    read_only: bool
    estimated_latency_ms: float
    expected_information_gain: float  # Scale 0.0 to 1.0
    command_template: str
    requires_hitl: bool = False
    parent_probe_id: Optional[str] = None


class ProbeCatalog:
    """Catalog of enterprise diagnostic probes across OSI layers L1 to L7."""

    def __init__(self):
        self.probes: Dict[str, DiagnosticProbe] = {}
        self._initialize_catalog()

    def _initialize_catalog(self):
        # Level 1 Read-Only Probes
        self._add(DiagnosticProbe(
            probe_id="PRB-L1-01",
            name="Physical Link & RSSI Check",
            risk_level=RiskLevel.LEVEL_1_READ_ONLY,
            osi_layer=OSILayer.L1_PHYSICAL,
            target_hypothesis_types=["RSSI_Drop", "Cable_Disconnect", "NIC_Fault"],
            read_only=True,
            estimated_latency_ms=10.0,
            expected_information_gain=0.90,
            command_template="read_physical_link_status"
        ))

        self._add(DiagnosticProbe(
            probe_id="PRB-L2-01",
            name="ARP Table & Switch Port Query",
            risk_level=RiskLevel.LEVEL_1_READ_ONLY,
            osi_layer=OSILayer.L2_DATALINK,
            target_hypothesis_types=["BroadcastStorm", "MAC_Mismatch", "VLAN_Misconfig"],
            read_only=True,
            estimated_latency_ms=15.0,
            expected_information_gain=0.85,
            command_template="query_arp_table"
        ))

        self._add(DiagnosticProbe(
            probe_id="PRB-L3-01",
            name="ICMP Ping Gateway Probe",
            risk_level=RiskLevel.LEVEL_1_READ_ONLY,
            osi_layer=OSILayer.L3_NETWORK,
            target_hypothesis_types=["Gateway_Unreachable", "PacketLoss", "High_Latency"],
            read_only=True,
            estimated_latency_ms=25.0,
            expected_information_gain=0.95,
            command_template="ping -c 4 {target_ip}"
        ))

        self._add(DiagnosticProbe(
            probe_id="PRB-L3-02",
            name="DNS Lookup Probe",
            risk_level=RiskLevel.LEVEL_1_READ_ONLY,
            osi_layer=OSILayer.L3_NETWORK,
            target_hypothesis_types=["DNS_Timeout", "DNS_Resolution_Error"],
            read_only=True,
            estimated_latency_ms=30.0,
            expected_information_gain=0.92,
            command_template="nslookup {domain}",
            parent_probe_id="PRB-L3-01"
        ))

        self._add(DiagnosticProbe(
            probe_id="PRB-L4-01",
            name="TCP Socket Handshake Probe",
            risk_level=RiskLevel.LEVEL_1_READ_ONLY,
            osi_layer=OSILayer.L4_TRANSPORT,
            target_hypothesis_types=["TCP_Retransmission", "Port_Closed", "Firewall_Block"],
            read_only=True,
            estimated_latency_ms=40.0,
            expected_information_gain=0.88,
            command_template="nc -zv {target_ip} {port}",
            parent_probe_id="PRB-L3-01"
        ))

        self._add(DiagnosticProbe(
            probe_id="PRB-L5-01",
            name="TLS Handshake Probe",
            risk_level=RiskLevel.LEVEL_1_READ_ONLY,
            osi_layer=OSILayer.L5_SESSION,
            target_hypothesis_types=["TLS_Failure", "Session_Termination"],
            read_only=True,
            estimated_latency_ms=50.0,
            expected_information_gain=0.89,
            command_template="openssl s_client -connect {target_host}:{port}",
            parent_probe_id="PRB-L4-01"
        ))

        self._add(DiagnosticProbe(
            probe_id="PRB-L6-01",
            name="SSL Certificate Validation Probe",
            risk_level=RiskLevel.LEVEL_1_READ_ONLY,
            osi_layer=OSILayer.L6_PRESENTATION,
            target_hypothesis_types=["CertExpired", "Certificate_Untrusted"],
            read_only=True,
            estimated_latency_ms=35.0,
            expected_information_gain=0.94,
            command_template="verify_cert_expiration {target_host}",
            parent_probe_id="PRB-L5-01"
        ))

        self._add(DiagnosticProbe(
            probe_id="PRB-L7-01",
            name="HTTP HEAD Endpoint Probe",
            risk_level=RiskLevel.LEVEL_1_READ_ONLY,
            osi_layer=OSILayer.L7_APPLICATION,
            target_hypothesis_types=["HTTP_502", "HTTP_500", "POS_Error", "API_Down"],
            read_only=True,
            estimated_latency_ms=60.0,
            expected_information_gain=0.91,
            command_template="curl -I http://{target_host}/health",
            parent_probe_id="PRB-L4-01"
        ))

        self._add(DiagnosticProbe(
            probe_id="PRB-L7-02",
            name="SMART Disk Health Read",
            risk_level=RiskLevel.LEVEL_1_READ_ONLY,
            osi_layer=OSILayer.L7_APPLICATION,
            target_hypothesis_types=["SSD_Failure", "IO_Saturation"],
            read_only=True,
            estimated_latency_ms=20.0,
            expected_information_gain=0.87,
            command_template="smartctl -a /dev/sda"
        ))

        self._add(DiagnosticProbe(
            probe_id="PRB-L7-03",
            name="Windows EventViewer / Syslog Inspection",
            risk_level=RiskLevel.LEVEL_1_READ_ONLY,
            osi_layer=OSILayer.L7_APPLICATION,
            target_hypothesis_types=["Service_Crash", "PrintSpooler_Crash"],
            read_only=True,
            estimated_latency_ms=45.0,
            expected_information_gain=0.93,
            command_template="query_event_logs --service PrintSpooler"
        ))

        # Level 2 Low-Risk Active Probes
        self._add(DiagnosticProbe(
            probe_id="PRB-ACT-L2-01",
            name="Flush DNS Cache",
            risk_level=RiskLevel.LEVEL_2_LOW_RISK,
            osi_layer=OSILayer.L3_NETWORK,
            target_hypothesis_types=["DNS_Stale_Cache", "DNS_Timeout"],
            read_only=False,
            estimated_latency_ms=100.0,
            expected_information_gain=0.80,
            command_template="ipconfig /flushdns"
        ))

        self._add(DiagnosticProbe(
            probe_id="PRB-ACT-L2-02",
            name="Renew DHCP Lease",
            risk_level=RiskLevel.LEVEL_2_LOW_RISK,
            osi_layer=OSILayer.L3_NETWORK,
            target_hypothesis_types=["IP_Conflict", "DHCP_Lease_Expired"],
            read_only=False,
            estimated_latency_ms=1500.0,
            expected_information_gain=0.85,
            command_template="ipconfig /renew"
        ))

        # Level 3 Medium-Risk Active Probes
        self._add(DiagnosticProbe(
            probe_id="PRB-ACT-L3-01",
            name="Restart Network Interface",
            risk_level=RiskLevel.LEVEL_3_MEDIUM_RISK,
            osi_layer=OSILayer.L2_DATALINK,
            target_hypothesis_types=["NIC_Hangs", "PacketLoss"],
            read_only=False,
            estimated_latency_ms=3000.0,
            expected_information_gain=0.75,
            command_template="restart_net_adapter {adapter_name}"
        ))

        # Level 4 High-Risk Active Probes (HITL Enforced)
        self._add(DiagnosticProbe(
            probe_id="PRB-ACT-L4-01",
            name="Reset TCP/IP Network Stack",
            risk_level=RiskLevel.LEVEL_4_HIGH_RISK,
            osi_layer=OSILayer.L3_NETWORK,
            target_hypothesis_types=["Corrupt_Network_Stack", "Fatal_Routing_Error"],
            read_only=False,
            estimated_latency_ms=8000.0,
            expected_information_gain=0.70,
            command_template="netsh int ip reset",
            requires_hitl=True
        ))

    def _add(self, probe: DiagnosticProbe):
        self.probes[probe.probe_id] = probe

    def get_probe(self, probe_id: str) -> Optional[DiagnosticProbe]:
        return self.probes.get(probe_id)

    def get_probes_for_hypothesis(self, hypothesis_type: str) -> List[DiagnosticProbe]:
        return [
            p for p in self.probes.values()
            if hypothesis_type in p.target_hypothesis_types
        ]

    def get_probes_by_level(self, risk_level: RiskLevel) -> List[DiagnosticProbe]:
        return [p for p in self.probes.values() if p.risk_level == risk_level]
