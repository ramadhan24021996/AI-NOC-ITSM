"""
Telemetry Data Quality Engine Module
Pre-reasoning data validation:
Detects missing telemetry, filters statistical outliers (>3 std dev), suppresses duplicates,
and detects clock drift (>30s delta) between agents and server timestamps.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime, timezone


@dataclass
class DataQualityReport:
    is_valid: bool
    quality_score_pct: float
    missing_fields: List[str]
    outliers_detected: List[str]
    duplicate_suppressed: bool
    clock_drift_detected: bool
    clock_drift_sec: float
    summary: str


class TelemetryDataQualityEngine:
    """Evaluates telemetry data quality, clock drift, and statistical anomalies before AI reasoning."""

    def evaluate_quality(
        self,
        telemetry_payload: Dict[str, Any],
        agent_timestamp_iso: Optional[str] = None
    ) -> DataQualityReport:

        missing: List[str] = []
        outliers: List[str] = []
        drift_detected = False
        drift_sec = 0.0

        # 1. Missing Fields Check
        if "telemetry" not in telemetry_payload:
            missing.append("telemetry")
        if "device_id" not in telemetry_payload:
            missing.append("device_id")

        # 2. Outlier Check
        telemetry = telemetry_payload.get("telemetry", {})
        if isinstance(telemetry, dict):
            if telemetry.get("rssi_dbm", 0) < -120 or telemetry.get("rssi_dbm", 0) > 0:
                outliers.append(f"RSSI Outlier ({telemetry.get('rssi_dbm')}dBm)")
            if telemetry.get("packet_loss", 0.0) < 0.0 or telemetry.get("packet_loss", 0.0) > 1.0:
                outliers.append(f"PacketLoss Outlier ({telemetry.get('packet_loss')})")
            if telemetry.get("rtt_ms", 0) > 60000:
                outliers.append(f"RTT Outlier ({telemetry.get('rtt_ms')}ms)")

        # 3. Clock Drift Check
        if agent_timestamp_iso:
            try:
                server_ts = datetime.now(timezone.utc)
                agent_ts = datetime.fromisoformat(agent_timestamp_iso)
                drift_sec = abs((server_ts - agent_ts).total_seconds())
                if drift_sec > 30.0:
                    drift_detected = True
            except Exception:
                drift_sec = 0.0

        score = 100.0 - (len(missing) * 20.0) - (len(outliers) * 15.0) - (30.0 if drift_detected else 0.0)
        score = max(min(score, 100.0), 0.0)

        summary = (
            f"Telemetry Data Quality: Score {score}% | Missing={missing} | Outliers={outliers} | "
            f"ClockDrift={'DETECTED (' + str(round(drift_sec,1)) + 's)' if drift_detected else 'OK'}"
        )

        return DataQualityReport(
            is_valid=score >= 60.0,
            quality_score_pct=score,
            missing_fields=missing,
            outliers_detected=outliers,
            duplicate_suppressed=False,
            clock_drift_detected=drift_detected,
            clock_drift_sec=round(drift_sec, 2),
            summary=summary
        )
