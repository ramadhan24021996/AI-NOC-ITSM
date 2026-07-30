"""
Enterprise AI OS — Evidence Scoring Engine & Hallucination Guard
Mengevaluasi kualitas bukti secara deterministik (Multi-dimensional) untuk mencegah halusinasi AI.
"""

import logging
from typing import Dict, List, Any

logger = logging.getLogger("EVIDENCE_SCORING")

class VerdictLevel:
    VERIFIED = "VERIFIED"
    HIGH_CONFIDENCE = "HIGH CONFIDENCE"
    PROBABLE = "PROBABLE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT EVIDENCE"
    CONFLICTING_EVIDENCE = "CONFLICTING EVIDENCE"

class EvidenceScoringEngine:
    def __init__(self):
        # Reliability weights based on source telemetry
        self.source_reliability_map = {
            "CRASHPAD": 1.0,         # OS-level minidump is undeniable
            "CDP": 0.95,             # V8/Chrome DevTools Protocol is highly reliable
            "WINDOWS_EVENT_LOG": 0.9,
            "APM_AGENT": 0.85,
            "WEB_EXTENSION": 0.6,    # High chance of missing OS context
            "WATCHDOG": 0.8,
            "NETWORK_PROBE": 0.8,
            "UNKNOWN": 0.3
        }

    def evaluate_evidence(self, incident: Dict[str, Any], causal_graph: Any = None) -> Dict[str, Any]:
        """
        Mengevaluasi insiden berdasarkan 5 dimensi bukti:
        1. Source Reliability
        2. Evidence Completeness
        3. Cross Correlation
        4. Temporal Consistency
        5. Topology Consistency
        """
        events = incident.get("events", [])
        
        if not events:
            return self._build_result(0.0, VerdictLevel.INSUFFICIENT_EVIDENCE, "Tidak ada event telemetri yang dilampirkan.")

        # 1. Source Reliability
        total_reliability = 0.0
        sources_seen = set()
        for ev in events:
            source = str(ev.get("source") or ev.get("metadata", {}).get("source", "UNKNOWN")).upper()
            rel = self.source_reliability_map.get(source, self.source_reliability_map["UNKNOWN"])
            total_reliability += rel
            sources_seen.add(source)
        
        avg_source_reliability = total_reliability / len(events) if events else 0.0

        # 2. Evidence Completeness
        # We expect a good RCA to have logs, metrics, and ideally traces.
        completeness_score = 0.5
        if len(events) >= 3:
            completeness_score += 0.2
        if any("stack_trace" in str(ev).lower() or "exception" in str(ev).lower() for ev in events):
            completeness_score += 0.3
        completeness_score = min(1.0, completeness_score)

        # 3. Cross Correlation
        # Are there multiple distinct sources confirming the anomaly?
        cross_correlation_score = 0.5
        if len(sources_seen) >= 2:
            cross_correlation_score += 0.3
        if len(sources_seen) >= 3:
            cross_correlation_score += 0.2
            
        # Check for conflicting evidence (e.g. CPU 100% but Watchdog says idle)
        # This is a simplified conflicting check
        if self._check_conflicts(events):
            cross_correlation_score = 0.1

        # 4. Temporal Consistency
        # Check if events happened within a tight, logical time window (e.g. within 60 seconds)
        temporal_consistency_score = self._evaluate_temporal_consistency(events)

        # 5. Topology Consistency
        # Does it align with the known dependency graph?
        topology_consistency_score = 0.5
        if causal_graph and hasattr(causal_graph, "validate_topology"):
            topology_consistency_score = causal_graph.validate_topology(incident)
        elif incident.get("trace_id"):
            topology_consistency_score = 0.9 # High if trace context exists
            
        # Composite Score Calculation (Multiplicative/Weighted)
        # We use a geometric mean-like weighting to severely punish any score that is too low (e.g., conflicting = 0.1)
        composite_score = (
            (avg_source_reliability * 0.3) +
            (completeness_score * 0.25) +
            (cross_correlation_score * 0.2) +
            (temporal_consistency_score * 0.15) +
            (topology_consistency_score * 0.1)
        )
        
        confidence_percentage = round(composite_score * 100, 2)
        
        # Multi-Level Verdict
        verdict = VerdictLevel.PROBABLE
        reasoning = []
        
        if cross_correlation_score <= 0.2:
            verdict = VerdictLevel.CONFLICTING_EVIDENCE
            reasoning.append("Ditemukan kontradiksi antar sumber bukti (Conflicting Evidence).")
        elif completeness_score < 0.4 or confidence_percentage < 40.0:
            verdict = VerdictLevel.INSUFFICIENT_EVIDENCE
            reasoning.append("Bukti terlalu minim untuk menyimpulkan Root Cause.")
        elif confidence_percentage >= 85.0 and completeness_score >= 0.8:
            verdict = VerdictLevel.VERIFIED
            reasoning.append("Bukti sangat kuat, bersumber dari agen reliabilitas tinggi (mis: Crashpad/CDP), dan terkonfirmasi secara lintas topologi.")
        elif confidence_percentage >= 65.0:
            verdict = VerdictLevel.HIGH_CONFIDENCE
            reasoning.append("Bukti cukup kuat dan konsisten, namun masih ada ruang kecil untuk anomali lain.")
        else:
            verdict = VerdictLevel.PROBABLE
            reasoning.append("Dugaan kuat berdasarkan korelasi, namun bukti keras (seperti stack trace) belum lengkap.")

        return self._build_result(confidence_percentage, verdict, " ".join(reasoning), {
            "source_reliability": round(avg_source_reliability, 2),
            "evidence_completeness": round(completeness_score, 2),
            "cross_correlation": round(cross_correlation_score, 2),
            "temporal_consistency": round(temporal_consistency_score, 2),
            "topology_consistency": round(topology_consistency_score, 2)
        })

    def _check_conflicts(self, events: List[Dict]) -> bool:
        """Simulated conflict detection between events."""
        raw_dump = str(events).lower()
        if "cpu saturation" in raw_dump and "cpu usage: low" in raw_dump:
            return True
        if "network timeout" in raw_dump and "latency: 2ms" in raw_dump:
            return True
        return False

    def _evaluate_temporal_consistency(self, events: List[Dict]) -> float:
        """Check if timestamps of events are closely clustered without illogical time-travel."""
        if len(events) < 2:
            return 0.5 # Neutral
            
        timestamps = []
        for ev in events:
            ts = ev.get("timestamp") or ev.get("metadata", {}).get("timestamp")
            if ts:
                try:
                    timestamps.append(float(ts))
                except (ValueError, TypeError):
                    pass
                    
        if len(timestamps) < 2:
            return 0.5
            
        timestamps.sort()
        delta = timestamps[-1] - timestamps[0]
        
        # If events are spread over 1 hour (3600s), they might not be the same incident
        if delta > 3600:
            return 0.3
        elif delta > 300:
            return 0.6
        else:
            return 1.0 # Very tightly clustered (high consistency)

    def _build_result(self, score: float, verdict: str, rationale: str, dimensions: Dict = None) -> Dict[str, Any]:
        return {
            "confidence_score": score,
            "verdict": verdict,
            "rationale": rationale,
            "dimensions": dimensions or {}
        }
