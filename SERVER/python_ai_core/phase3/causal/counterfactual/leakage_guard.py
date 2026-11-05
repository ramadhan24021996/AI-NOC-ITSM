"""
Phase 3.5: Leakage Guard (phase3/causal/counterfactual/leakage_guard.py)

Enforces Invariant #19 (No Future Data Leakage).
Blocks any data observation with timestamp T > T_decision or cross-incident contamination.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List

logger = logging.getLogger("LEAKAGE_GUARD")


class LeakageGuard:
    @staticmethod
    def validate_temporal_boundary(record_timestamp_iso: str, decision_timestamp_iso: str) -> Dict[str, Any]:
        """
        Invariant #19: Ensures record_timestamp <= decision_timestamp.
        If record_timestamp > decision_timestamp -> DENIED (Future Leakage Attempt!).
        """
        try:
            r_dt = datetime.fromisoformat(record_timestamp_iso.replace("Z", "+00:00"))
            d_dt = datetime.fromisoformat(decision_timestamp_iso.replace("Z", "+00:00"))

            if r_dt > d_dt:
                logger.error(f"[LEAKAGE DENIED] Record timestamp '{record_timestamp_iso}' is in FUTURE relative to decision '{decision_timestamp_iso}'!")
                return {"status": "DENIED", "reason": "FUTURE_DATA_LEAKAGE_ATTEMPT", "record_time": record_timestamp_iso, "decision_time": decision_timestamp_iso}

            return {"status": "PASS", "lag_seconds": (d_dt - r_dt).total_seconds()}
        except Exception as e:
            logger.error(f"[LEAKAGE GUARD] Timestamp validation error: {e}")
            return {"status": "DENIED", "reason": f"TIMESTAMP_PARSE_ERROR: {e}"}

    @staticmethod
    def validate_incident_boundary(record_incident_id: str, target_incident_id: str) -> bool:
        """
        Ensures cross-incident evidence contamination is rejected.
        """
        if record_incident_id != target_incident_id:
            logger.error(f"[CROSS INCIDENT DENIED] Record incident '{record_incident_id}' != target '{target_incident_id}'")
            return False
        return True
