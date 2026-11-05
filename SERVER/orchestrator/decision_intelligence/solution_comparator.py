"""
SERVER.orchestrator.decision_intelligence.solution_comparator
==============================================================
Component: Solution Comparator & Alternative Generator

Generates and compares primary SOP solutions with fallback alternatives if primary SOP fails or is rejected:
  1. Stop Backup Job (Primary)
  2. Throttle Backup Process (Alternative 1)
  3. Restart PostgreSQL Service (Alternative 2)
"""
import logging
from typing import Dict, Any, List
from SERVER.contracts.schemas import SolutionCandidate

logger = logging.getLogger("orchestrator.decision.comparator")


class SolutionComparator:
    """
    Generates alternative recovery options to ensure Jarvis never stalls when an SOP is rejected.
    """

    def generate_candidate_solutions(
        self, topic: str, target_device: str
    ) -> List[SolutionCandidate]:
        candidates = [
            SolutionCandidate(
                rank=1,
                action_name="Stop Backup Job (cron_backup.sh)",
                confidence_pct=97,
                risk_level="LOW",
                has_rollback=True,
                eta_seconds=15,
            ),
            SolutionCandidate(
                rank=2,
                action_name="Throttle Backup Process (nice -n 19)",
                confidence_pct=92,
                risk_level="LOW",
                has_rollback=True,
                eta_seconds=30,
            ),
            SolutionCandidate(
                rank=3,
                action_name="Restart PostgreSQL Service Container",
                confidence_pct=64,
                risk_level="MEDIUM",
                has_rollback=True,
                eta_seconds=60,
            ),
            SolutionCandidate(
                rank=4,
                action_name="Restart Physical Server Node",
                confidence_pct=35,
                risk_level="HIGH",
                has_rollback=False,
                eta_seconds=300,
            ),
        ]

        logger.debug(f"[SolutionComparator] Generated {len(candidates)} candidate solutions for {target_device}")
        return candidates
