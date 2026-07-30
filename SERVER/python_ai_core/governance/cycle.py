import logging
import asyncio
from typing import Dict, Any

from .benchmark_engine import BenchmarkEngine
from .drift_detection import DriftDetectionEngine
from .evidence_quality import EvidenceQualityEngine
from .root_cause_validation import RootCauseValidationEngine
from .prompt_evaluation import PromptEvaluationEngine

logger = logging.getLogger("GOVERNANCE_CYCLE")

async def trigger_governance_cycle(incident_id: int, telemetry_data: Dict[str, Any], ai_prediction: str, human_resolution: str = None, conn=None):
    """
    Called by AI Supervisor or Daemons whenever an incident completes a lifecycle stage.
    Runs O1-O11 evaluations in the background.
    """
    if not conn:
        logger.warning("[Sprint O] No database connection provided to governance cycle.")
        return

    logger.info(f"[Sprint O] Executing Real-Time Governance Cycle for Incident {incident_id}")
    try:
        if isinstance(telemetry_data, list):
            telemetry_data = {"log": str(telemetry_data), "cpu": 0.0}
        elif not isinstance(telemetry_data, dict):
            telemetry_data = {"log": str(telemetry_data), "cpu": 0.0}

        # O7: Evidence Quality
        evidence_engine = EvidenceQualityEngine(conn)
        evidence_engine.calculate_evidence_score(
            incident_id=str(incident_id),
            telemetry={
                "metrics": {"cpu": telemetry_data.get("cpu", 0.0)},
                "logs": [telemetry_data.get("log", "")],
                "topology": {"nodes": 1}
            }
        )
        
        # O6: Prompt Evaluation (Simulate validation on current version)
        prompt_engine = PromptEvaluationEngine(conn)
        prompt_engine.evaluate_prompt("v3.5", str(incident_id))

        # If incident is fully resolved, run Benchmark & RCA Validation
        if human_resolution:
            # O1: Engineer Benchmark
            bm_engine = BenchmarkEngine(conn)
            bm_engine.log_engineer_benchmark(
                incident_id=str(incident_id),
                ai_diagnosis="Automated Diagnosis",
                human_diagnosis="Engineer Diagnosis",
                ai_solution="Automated Solution",
                human_solution=human_resolution,
                ai_rca=ai_prediction,
                human_rca=human_resolution
            )

            # O8: RCA Validation
            rca_engine = RootCauseValidationEngine(conn)
            rca_engine.validate_rca(str(incident_id), ai_prediction, human_resolution)

            # O2: Trigger Drift Detection passively
            drift_engine = DriftDetectionEngine(conn)
            drift_engine.calculate_all_drifts()
            
    except Exception as e:
        logger.error(f"[Sprint O] Governance Cycle Error: {e}")
