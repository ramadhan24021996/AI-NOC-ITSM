"""
Negative Evidence Engine Module
Evaluates contradicting evidence to penalize false or invalid hypothesis candidates.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class ContradictingEvidence:
    variable_name: str
    contradicting_metric: str
    observed_value: Any
    penalty_score: float   # e.g. 0.35 (reduces confidence by 35%)
    reason: str


class NegativeEvidenceEngine:
    def evaluate_contradictions(
        self,
        hypothesis_variable: str,
        evidence_payload: Dict[str, Any]
    ) -> Optional[ContradictingEvidence]:
        """
        Checks if negative evidence exists that contradicts hypothesis_variable.
        """
        telemetry = evidence_payload.get("telemetry", {})

        if hypothesis_variable == "PacketLoss":
            # If ping is 1ms RTT and 0% loss observed, PacketLoss is contradicted
            ping_loss = telemetry.get("packet_loss", 0.0)
            ping_rtt = telemetry.get("rtt_ms", 1)
            if ping_loss == 0.0 and ping_rtt < 5:
                return ContradictingEvidence(
                    variable_name="PacketLoss",
                    contradicting_metric="rtt_ms & packet_loss",
                    observed_value=f"RTT={ping_rtt}ms, Loss={ping_loss}%",
                    penalty_score=0.40,
                    reason="Ping telemetry shows 0% loss and 1ms RTT, contradicting Packet Loss hypothesis."
                )

        if hypothesis_variable == "DNS_Timeout":
            dns_time = telemetry.get("resolve_time_ms", 10)
            if dns_time > 0 and dns_time < 50:
                return ContradictingEvidence(
                    variable_name="DNS_Timeout",
                    contradicting_metric="resolve_time_ms",
                    observed_value=f"{dns_time}ms",
                    penalty_score=0.35,
                    reason="DNS resolution time is normal (10ms), contradicting DNS Timeout hypothesis."
                )

        return None
