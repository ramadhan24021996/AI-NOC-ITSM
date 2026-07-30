"""
Phase 3 Governance Framework: AI Incident Replay Engine.

Replays historical incidents across multiple prompt versions (e.g., v1.0 vs v1.2 vs v2.0)
to visualize and compare RCA outputs without impacting live production.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from adapters.output_synthesizer import OutputAdapterFacade, SynthesizerConfig, MockOutputSynthesizer
from adapters.prompt_registry import PromptRegistry

logger = logging.getLogger("AIIncidentReplayEngine")


@dataclass
class ReplayOutput:
    prompt_version: str
    clean_final_decision: str
    quality_score: float
    execution_time_ms: float


@dataclass
class IncidentReplayResult:
    incident_id: int
    device_name: str
    historical_raw_decision: str
    evidence: str
    replays: Dict[str, ReplayOutput]


class AIIncidentReplayEngine:
    """Replay Engine for historical incident evaluation across prompt iterations."""

    def __init__(self, target_versions: Optional[List[str]] = None):
        self.target_versions = target_versions or ["v1.0", "v1.2", "v2.0"]

    def replay_incident(
        self,
        incident_id: int,
        device_name: str,
        raw_decision: str,
        evidence: str,
        confidence: float = 0.85
    ) -> IncidentReplayResult:
        """Replays a single historical incident across all target prompt versions."""
        replays: Dict[str, ReplayOutput] = {}

        for version in self.target_versions:
            cfg = SynthesizerConfig(prompt_version=version)
            facade = OutputAdapterFacade(config=cfg, synthesizer=MockOutputSynthesizer(cfg))

            t0 = time.perf_counter()
            resp = facade.process(
                raw_final_decision=raw_decision,
                evidence=evidence,
                confidence=confidence,
                incident_id=incident_id,
                device_name=device_name
            )
            exec_time = (time.perf_counter() - t0) * 1000.0

            replays[version] = ReplayOutput(
                prompt_version=version,
                clean_final_decision=resp.clean_final_decision,
                quality_score=resp.quality_score,
                execution_time_ms=round(exec_time, 2)
            )

        logger.info(f"[AIIncidentReplayEngine] Replayed Incident #{incident_id} across versions: {self.target_versions}")

        return IncidentReplayResult(
            incident_id=incident_id,
            device_name=device_name,
            historical_raw_decision=raw_decision,
            evidence=evidence,
            replays=replays
        )
