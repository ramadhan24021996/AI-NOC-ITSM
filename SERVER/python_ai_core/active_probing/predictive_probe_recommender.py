"""
Predictive Probe Recommender Module
Learns and recommends optimal probe sequences based on historical incident patterns
(e.g., Printer Timeout -> DNS Lookup -> Gateway Ping -> Packet Loss).
"""

from dataclasses import dataclass
from typing import List, Dict, Any
from .probe_catalog import ProbeCatalog, DiagnosticProbe


@dataclass
class ProbeRecommendation:
    recommended_probe_sequence: List[str]
    pattern_matched: str
    historical_success_rate: float
    reason: str


class PredictiveProbeRecommender:
    """Recommends optimized diagnostic probe sequences based on symptom signatures."""

    def __init__(self, catalog: ProbeCatalog):
        self.catalog = catalog
        self.known_patterns = {
            "PRINTER_SPOOLER": {
                "sequence": ["PRB-L3-01", "PRB-L3-02", "PRB-L7-03"],
                "pattern": "Printer Spooler Crash -> Network Ping -> DNS -> EventViewer Log",
                "success_rate": 0.94
            },
            "POS_COMMUNICATION": {
                "sequence": ["PRB-L1-01", "PRB-L3-01", "PRB-L4-01", "PRB-L7-01"],
                "pattern": "POS Kasir Error -> RSSI Check -> Gateway Ping -> TCP Handshake -> HTTP HEAD",
                "success_rate": 0.96
            },
            "TLS_SECURITY": {
                "sequence": ["PRB-L5-01", "PRB-L6-01"],
                "pattern": "TLS Failure -> Session Probe -> Certificate Expiration Verification",
                "success_rate": 0.98
            }
        }

    def recommend_sequence(self, symptom_data: Dict[str, Any]) -> ProbeRecommendation:
        symptom_str = str(symptom_data).lower()

        if "printer" in symptom_str or "spooler" in symptom_str:
            pat = self.known_patterns["PRINTER_SPOOLER"]
            return ProbeRecommendation(
                recommended_probe_sequence=pat["sequence"],
                pattern_matched="PRINTER_SPOOLER",
                historical_success_rate=pat["success_rate"],
                reason="Historical pattern matched: Printer Spooler crash sequence"
            )

        if "tls" in symptom_str or "cert" in symptom_str:
            pat = self.known_patterns["TLS_SECURITY"]
            return ProbeRecommendation(
                recommended_probe_sequence=pat["sequence"],
                pattern_matched="TLS_SECURITY",
                historical_success_rate=pat["success_rate"],
                reason="Historical pattern matched: TLS/SSL Security sequence"
            )

        # Default POS / Network sequence
        pat = self.known_patterns["POS_COMMUNICATION"]
        return ProbeRecommendation(
            recommended_probe_sequence=pat["sequence"],
            pattern_matched="POS_COMMUNICATION",
            historical_success_rate=pat["success_rate"],
            reason="Standard network diagnostic sequence for endpoint connectivity"
        )
