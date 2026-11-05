"""
SERVER.orchestrator.cognitive.capability_registry
==================================================
Component: Capability Registry

Maintains explicit capability boundaries (CAN vs CANNOT) to prevent LLM hallucinations:
  CAN: RCA, Telemetry, SOPs, Sandbox, Voice, Trend Analysis, Docker/PostgreSQL Monitoring
  CANNOT: Direct unapproved server login, Deleting files, Unsafe restarts without HITL
"""
import logging
from SERVER.contracts.schemas import CapabilityMatrix

logger = logging.getLogger("orchestrator.cognitive.capabilities")

SUPPORTED_CAPABILITIES = [
    "Root Cause Analysis (RCA)",
    "Incident Diagnostics & Troubleshooting",
    "SOP Knowledge Retrieval & Staging",
    "Real-time Telemetry Monitoring (Netdata & Host Agent)",
    "Sandbox Safety Simulations",
    "Voice STT & EdgeTTS Audio Generation",
    "Trend & Anomaly Analysis",
    "Docker Container Status Inspection",
    "PostgreSQL Health Audit",
]

FORBIDDEN_ACTIONS = [
    "Direct unapproved SSH server login",
    "Deleting production files without operator approval",
    "Restarting critical services without HITL authorization",
    "Modifying production database schemas directly",
    "Bypassing policy security layers",
]


class CapabilityRegistry:
    """
    Registry maintaining capability matrix.
    """

    def get_capabilities(self) -> CapabilityMatrix:
        matrix = CapabilityMatrix(
            supported_capabilities=list(SUPPORTED_CAPABILITIES),
            forbidden_actions=list(FORBIDDEN_ACTIONS),
        )
        return matrix
