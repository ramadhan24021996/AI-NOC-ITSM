"""
Structural Causal Model (SCM) Module
Defines explicit causal variables and structural equations across Layers 1 to 7.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional


class LayerType(str, Enum):
    L1_PHYSICAL = "L1"
    L2_DATALINK = "L2"
    L3_NETWORK = "L3"
    L4_TRANSPORT = "L4"
    L5_SESSION = "L5"
    L6_PRESENTATION = "L6"
    L7_APPLICATION = "L7"


@dataclass
class CausalVariable:
    name: str
    layer: LayerType
    value: Any
    default_normal_value: Any
    description: str = ""

    def is_anomalous(self) -> bool:
        return self.value != self.default_normal_value


class StructuralCausalModel:
    def __init__(self):
        self.variables: Dict[str, CausalVariable] = {}
        self._initialize_default_scm()

    def _initialize_default_scm(self):
        """Initializes standard Layer 1 - Layer 7 Causal Variables"""
        # Layer 1 - Physical / Hardware
        self.add_variable("CableConnected", LayerType.L1_PHYSICAL, True, True, "Physical Ethernet Cable Status")
        self.add_variable("LinkSpeed", LayerType.L1_PHYSICAL, 1000, 1000, "NIC Link Speed Mbps")
        self.add_variable("RSSI", LayerType.L1_PHYSICAL, -55, -55, "WiFi Signal RSSI dBm")
        self.add_variable("SignalNoise", LayerType.L1_PHYSICAL, -90, -90, "WiFi Signal Noise dBm")
        self.add_variable("Temperature", LayerType.L1_PHYSICAL, 45, 45, "Hardware CPU Temp C")
        self.add_variable("SMART_Health", LayerType.L1_PHYSICAL, "PASSED", "PASSED", "SMART Disk Status")

        # Layer 2 - Data Link
        self.add_variable("BroadcastStorm", LayerType.L2_DATALINK, False, False, "L2 Broadcast Storm Detected")
        self.add_variable("CRC_Error", LayerType.L2_DATALINK, 0, 0, "CRC Frame Errors Count")
        self.add_variable("FrameDrop", LayerType.L2_DATALINK, 0, 0, "Dropped L2 Frames Count")

        # Layer 3 - Network
        self.add_variable("PacketLoss", LayerType.L3_NETWORK, 0.0, 0.0, "Network Packet Loss Ratio")
        self.add_variable("GatewayLatency", LayerType.L3_NETWORK, 10, 10, "Gateway RTT Latency MS")
        self.add_variable("DNS_Timeout", LayerType.L3_NETWORK, False, False, "DNS Lookup Timeout Event")

        # Layer 4 - Transport
        self.add_variable("TCP_Retransmission", LayerType.L4_TRANSPORT, 0, 0, "TCP Retransmit Count")
        self.add_variable("PortClosed", LayerType.L4_TRANSPORT, False, False, "Target Socket Port Closed")
        self.add_variable("ConnectionTimeout", LayerType.L4_TRANSPORT, False, False, "TCP Connection Timeout")

        # Layer 5 - Session
        self.add_variable("TLS_Failure", LayerType.L5_SESSION, False, False, "TLS Handshake Failed")
        self.add_variable("SessionExpired", LayerType.L5_SESSION, False, False, "App Session Expired")

        # Layer 6 - Presentation
        self.add_variable("CertExpired", LayerType.L6_PRESENTATION, False, False, "SSL/TLS Certificate Expired")
        self.add_variable("SerializationError", LayerType.L6_PRESENTATION, False, False, "JSON/Protobuf Serialization Fail")

        # Layer 7 - Application
        self.add_variable("HTTP_502", LayerType.L7_APPLICATION, False, False, "HTTP 502 Bad Gateway")
        self.add_variable("POS_Error", LayerType.L7_APPLICATION, False, False, "POS Application Transaction Error")
        self.add_variable("Printer_Offline", LayerType.L7_APPLICATION, False, False, "Print Spooler / Printer Error")
        self.add_variable("Chrome_Crash", LayerType.L7_APPLICATION, False, False, "Browser Chrome Extension Crash")

    def add_variable(self, name: str, layer: LayerType, value: Any, default_value: Any, description: str = ""):
        self.variables[name] = CausalVariable(name, layer, value, default_value, description)

    def set_value(self, name: str, value: Any):
        if name in self.variables:
            self.variables[name].value = value

    def get_variable(self, name: str) -> Optional[CausalVariable]:
        return self.variables.get(name)

    def reset_to_normal(self):
        for var in self.variables.values():
            var.value = var.default_normal_value
