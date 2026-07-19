"""
Enterprise Autonomous AI OS — Phase 4: Step 4.2
Decision Engine

Menentukan postur tindakan AI:
  ACT      → Eksekusi otomatis (confidence tinggi, risiko rendah, policy izinkan)
  LEARN    → Kirim ke learning queue untuk memperdalam pengetahuan dulu
  WAIT     → Tunda karena sistem sibuk atau resource habis
  ESCALATE → Human-in-the-Loop wajib

Wraps policy_engine.py dan goal_engine.py — tidak menggantikan mereka.
"""

import logging
import os
from enum import Enum
from typing import Dict, Any, Optional

logger = logging.getLogger("DECISION_ENGINE")


class DecisionSignal(str, Enum):
    ACT      = "ACT"
    LEARN    = "LEARN"
    WAIT     = "WAIT"
    ESCALATE = "ESCALATE"


class DecisionEngine:
    """
    Central decision hub that combines:
    - Policy Engine result
    - Goal Engine alignment score
    - Runtime resource availability
    - Trust score
    to emit a single DecisionSignal.
    """

    # Thresholds
    MIN_CONFIDENCE_AUTO  = 75.0   # Required for ACT
    MIN_ALIGNMENT_AUTO   = 0.6    # Required for ACT
    MIN_TRUST_AUTO       = 70.0   # Required for ACT
    RESOURCE_CPU_MAX     = 85.0   # Defer if CPU > this

    def __init__(self, db_conn=None):
        self._conn = db_conn

    def decide(
        self,
        action: str,
        confidence: float,
        risk: str,
        severity: str,
        policy_effect: str,
        trust_score: float = 80.0,
        cpu_load_pct: float = 0.0,
        goal_alignment: float = 0.5,
        force_hitl: bool = False,
    ) -> Dict[str, Any]:
        """
        Evaluate all signals and return a DecisionSignal with rationale.

        Returns:
          {
            "signal":    "ACT" | "LEARN" | "WAIT" | "ESCALATE",
            "rationale": [...reasons...],
            "confidence": float,
            "alignment":  float,
          }
        """
        rationale = []

        # Hard gates — always override
        if force_hitl:
            rationale.append("Force HITL gate triggered (cognitive or immutable)")
            return self._result(DecisionSignal.ESCALATE, rationale, confidence, goal_alignment)

        if severity.upper() == "CRITICAL" or risk.upper() == "CRITICAL":
            rationale.append(f"severity={severity}/risk={risk} → mandatory HITL")
            return self._result(DecisionSignal.ESCALATE, rationale, confidence, goal_alignment)

        if policy_effect == "REJECT":
            rationale.append("Policy Engine: action REJECTED")
            return self._result(DecisionSignal.ESCALATE, rationale, confidence, goal_alignment)

        # Resource gate — defer learning if system overloaded
        if cpu_load_pct > self.RESOURCE_CPU_MAX:
            rationale.append(f"CPU load {cpu_load_pct:.0f}% exceeds threshold — deferring")
            return self._result(DecisionSignal.WAIT, rationale, confidence, goal_alignment)

        # Evaluate ESCALATE conditions
        if policy_effect == "FORCE_HITL":
            rationale.append("Policy Engine: FORCE_HITL")
            return self._result(DecisionSignal.ESCALATE, rationale, confidence, goal_alignment)

        if confidence < 50.0:
            rationale.append(f"Confidence {confidence:.1f}% < 50% threshold")
            return self._result(DecisionSignal.ESCALATE, rationale, confidence, goal_alignment)

        # Evaluate LEARN conditions (medium confidence, low trust)
        if confidence < self.MIN_CONFIDENCE_AUTO:
            rationale.append(f"Confidence {confidence:.1f}% < {self.MIN_CONFIDENCE_AUTO}% → queue learning")
            return self._result(DecisionSignal.LEARN, rationale, confidence, goal_alignment)

        if trust_score < self.MIN_TRUST_AUTO:
            rationale.append(f"Agent trust {trust_score:.1f} < {self.MIN_TRUST_AUTO} → queue learning")
            return self._result(DecisionSignal.LEARN, rationale, confidence, goal_alignment)

        if goal_alignment < self.MIN_ALIGNMENT_AUTO:
            rationale.append(f"Goal alignment {goal_alignment:.2f} < {self.MIN_ALIGNMENT_AUTO} → queue learning")
            return self._result(DecisionSignal.LEARN, rationale, confidence, goal_alignment)

        # All gates passed → ACT
        rationale.append(
            f"All gates passed: confidence={confidence:.1f}%, trust={trust_score:.1f}, "
            f"alignment={goal_alignment:.2f}, policy={policy_effect}"
        )
        return self._result(DecisionSignal.ACT, rationale, confidence, goal_alignment)

    def _result(self, signal: DecisionSignal, rationale: list, confidence: float, alignment: float) -> Dict:
        result = {
            "signal":    signal.value,
            "rationale": rationale,
            "confidence": confidence,
            "alignment":  alignment,
        }
        logger.info("[DECISION_ENGINE] Signal=%s | Rationale: %s", signal.value, "; ".join(rationale))
        return result

    def record_decision(self, incident_id: int, decision_result: Dict, action: str) -> bool:
        """Persist decision to ai_audit_trail planning_trace."""
        if not self._conn:
            return False
        import json
        try:
            with self._conn.cursor() as cur:
                cur.execute("""
                    UPDATE ai_audit_trail
                    SET planning_trace = planning_trace || %s::jsonb
                    WHERE incident_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (
                    json.dumps({"decision_engine": decision_result, "proposed_action": action}),
                    incident_id
                ))
            self._conn.commit()
            return True
        except Exception as e:
            logger.warning("[DECISION_ENGINE] Failed to record decision: %s", e)
            return False
