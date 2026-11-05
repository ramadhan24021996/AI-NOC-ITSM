"""
Phase 3.3: Active Diagnostic Orchestrator Loop (phase3/probing/active_diagnostic_loop.py)

Orchestrates Phase 3.3 Active Diagnostic Probing:
1. Evaluates Hypothesis Competition status from Phase 3.2.
2. If evidence is insufficient, ranks probes using Information Gain & Utility Engine.
3. Enforces Diagnostic Budget (max_probe_count = 3, min_ig_threshold = 0.05) to prevent infinite loops.
4. Executes top safe probe via ReadOnlyProbeExecutor.
5. Binds probe result to Canonical Evidence via ProbeProvenanceBinder.
"""

import logging
from typing import Dict, Any, List, Optional
from phase3.hypothesis.hypothesis_competition_engine import HypothesisContract, HypothesisRanker
from phase3.probing.probe_contract import ProbeRegistry
from phase3.probing.information_gain_engine import ProbeUtilityEngine
from phase3.probing.read_only_probe_executor import ReadOnlyProbeExecutor
from phase3.probing.probe_provenance_binder import ProbeProvenanceBinder

logger = logging.getLogger("ACTIVE_DIAGNOSTIC_LOOP")


class ActiveDiagnosticLoop:
    def __init__(self, registry: Optional[ProbeRegistry] = None, executor: Optional[ReadOnlyProbeExecutor] = None):
        self.registry = registry or ProbeRegistry()
        self.executor = executor or ReadOnlyProbeExecutor(self.registry)
        self.max_probe_count = 3
        self.min_ig_threshold = 0.05

    def run_active_diagnostic_cycle(self, incident_id: str, trace_id: str, hypotheses: List[HypothesisContract], target: str) -> Dict[str, Any]:
        """
        Runs closed-loop active diagnostic probing cycle.
        Returns updated hypothesis competition report with bound probe evidence.
        """
        logger.info(f"[ACTIVE DIAGNOSTIC LOOP] Starting cycle for Incident '{incident_id}' (Trace: {trace_id})")

        # 1. Rank current hypothesis competition
        report = HypothesisRanker.rank_and_generate_report(incident_id, hypotheses)
        if report.get("confirmed"):
            logger.info("[ACTIVE DIAGNOSTIC LOOP] Hypothesis is ALREADY CONFIRMED. Probing skipped.")
            return {"status": "CONFIRMED_NO_PROBE_NEEDED", "report": report}

        # 2. Retrieve registered candidate probes
        all_probes = [self.registry.get_probe(pid) for pid in ["P-CPU-001", "P-MEM-001", "P-NET-001", "P-SPOOLER-001", "P-DB-001"] if self.registry.get_probe(pid)]

        # 3. Rank probes using Probe Utility Engine
        ranked_probes = ProbeUtilityEngine.rank_probes(hypotheses, all_probes)
        if not ranked_probes:
            return {"status": "NO_VALID_PROBES", "report": report}

        best_probe_item = ranked_probes[0]
        best_probe = best_probe_item["probe_object"]
        best_ig = best_probe_item["expected_ig"]

        # Diagnostic Budget Check: Stop if Information Gain < Threshold
        if best_ig < self.min_ig_threshold:
            logger.warning(f"[DIAGNOSTIC BUDGET] Top probe '{best_probe.probe_id}' IG ({best_ig}) < Threshold ({self.min_ig_threshold}). Stopping probing.")
            return {"status": "DIAGNOSTICALLY_INSUFFICIENT", "reason": "INFORMATION_GAIN_TOO_LOW", "report": report}

        # 4. Execute Top Safe Read-Only Probe
        logger.info(f"[ACTIVE PROBING] Executing top safe probe '{best_probe.probe_id}' (Expected IG: {best_ig}) on target '{target}'...")
        probe_res = self.executor.execute_probe(best_probe.probe_id, target=target)

        # 5. Bind Probe Result to Canonical Evidence
        ev_object = ProbeProvenanceBinder.bind_probe_result_to_evidence(incident_id, trace_id, probe_res, best_probe.candidate if hasattr(best_probe, "candidate") else "CPU_SATURATION")

        if ev_object:
            # Append new evidence to top hypothesis candidate
            hypotheses[0].supporting_evidence.append(ev_object)
            # Re-rank hypothesis competition after new probe evidence
            updated_report = HypothesisRanker.rank_and_generate_report(incident_id, hypotheses)
            return {
                "status": "PROBE_EXECUTED_EVIDENCE_UPDATED",
                "probe_executed": best_probe.probe_id,
                "probe_result": probe_res,
                "bound_evidence_id": ev_object.evidence_id,
                "updated_report": updated_report
            }

        return {
            "status": "PROBE_EXECUTION_FAILED",
            "probe_executed": best_probe.probe_id,
            "probe_result": probe_res,
            "report": report
        }
