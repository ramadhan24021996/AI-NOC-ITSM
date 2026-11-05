"""
SERVER.orchestrator.cognitive.tool_requirement_detector
=========================================================
Component: Tool Requirement Detector

Determines whether telemetry/tool execution is needed:
  - "Jelaskan VLAN" -> No tool required
  - "Cek penggunaan RAM server" -> Telemetry / Tool required (Netdata/Agent)
"""
import re
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("orchestrator.cognitive.tool_detector")


@dataclass
class ToolRequirementResult:
    requires_tool: bool
    recommended_tool: Optional[str] = None
    reason: str = ""


class ToolRequirementDetector:
    """
    Evaluates query intent to determine tool execution necessity.
    """

    def detect(self, query_text: str) -> ToolRequirementResult:
        query_lower = query_text.lower()

        # Pure knowledge questions (no tool required)
        conceptual_keywords = ["jelaskan", "apa itu", "bagaimana cara kerja", "definisi", "konsep", "pengertian"]
        if any(query_lower.startswith(kw) for kw in conceptual_keywords):
            return ToolRequirementResult(
                requires_tool=False,
                reason="Kueri bersifat konseptual/penjelasan teoritis, tidak memerlukan eksekusi tool.",
            )

        # Operational inspection / execution triggers
        if any(kw in query_lower for kw in ["cek", "periksa", "lihat", "status", "metrik", "ram", "cpu", "ping", "netdata"]):
            return ToolRequirementResult(
                requires_tool=True,
                recommended_tool="netdata_telemetry_fetch",
                reason="Kueri memerlukan inspeksi metrik telemetri real-time.",
            )

        if any(kw in query_lower for kw in ["restart", "reboot", "clear cache", "isolate", "run probe"]):
            return ToolRequirementResult(
                requires_tool=True,
                recommended_tool="active_probe_or_action_runner",
                reason="Kueri memerlukan eksekusi tindakan operasional.",
            )

        return ToolRequirementResult(requires_tool=False, reason="Tidak ditemukan pemicu eksekusi tool.")
