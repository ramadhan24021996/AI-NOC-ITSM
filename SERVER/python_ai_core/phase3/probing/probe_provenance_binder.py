"""
Phase 3.3: Probe Provenance Binder (phase3/probing/probe_provenance_binder.py)

Enforces Invariant #11 (Probe Result Provenance Binding) & Invariant #12 (Probe Failure != Refutation).
Converts raw probe execution output into a CanonicalEvidenceObject bound to PostgreSQL trace_id.
"""

import logging
import hashlib
from typing import Dict, Any, Optional
from phase3.causal.canonical_evidence_schema import CanonicalEvidenceObject

logger = logging.getLogger("PROBE_PROVENANCE_BINDER")


class ProbeProvenanceBinder:
    @staticmethod
    def bind_probe_result_to_evidence(incident_id: str, trace_id: str, probe_result: Dict[str, Any], target_hypothesis: str) -> Optional[CanonicalEvidenceObject]:
        """
        Invariant #11: Converts probe execution result to CanonicalEvidenceObject with provenance binding.
        Invariant #12: If probe execution failed (PROBE_EXECUTION_FAILED), returns None (Zero contribution, NO REFUTATION).
        """
        status = probe_result.get("status")

        # Invariant #12: Probe failure is NOT evidence against candidate
        if status != "SUCCESS":
            logger.warning(f"[INVARIANT 12] Probe '{probe_result.get('probe_id')}' execution status is '{status}'. No evidence contribution created (Not refuting candidate).")
            return None

        probe_id = probe_result["probe_id"]
        target = probe_result["target"]
        stdout = probe_result.get("stdout", "")
        t_now = "2026-08-12T13:00:00Z"

        # Construct CanonicalEvidenceObject bound to trace_id
        ev = CanonicalEvidenceObject(
            evidence_id=f"EV-Probe-{probe_id}",
            incident_id=incident_id,
            source_type="SYSTEMD_JOURNAL" if "lpstat" in stdout or "ps" in stdout else "OS_KERNEL_PROCESS",
            source_instance=target,
            source_record_id=f"probe_results:{probe_id}:{trace_id}",
            observed_at=t_now,
            collected_at=t_now,
            entity_id=target,
            signal=f"PROBE_{probe_id}_OUTPUT",
            value=stdout[:100],  # Truncated output value
            unit="text_signal",
            reliability=0.90,
            independence_group=f"PROBE:{target}:{probe_id}",
            provenance={
                "table": "system_audits",
                "record_id": f"PROBE_{probe_id}",
                "trace_id": trace_id,
                "probe_id": probe_id,
                "target": target
            }
        )

        logger.info(f"[PROVENANCE BINDER] Bound probe '{probe_id}' result to Canonical Evidence '{ev.evidence_id}' (Trace: {trace_id})")
        return ev
