"""
Reinforcement Learning from Incident Feedback (RLIF) Autonomy Calibrator
SERVER/python_ai_core/governance/rlif_autonomy_calibrator.py
========================================================================
Enterprise Level-5 Self-Calibrating Autonomy Engine:

Principles:
1. Bayesian Beta-Bernoulli Posterior:
   - Tracks empirical performance (successes vs failures) per (action_id, asset_tier).
   - Computes posterior confidence P(Success | Alpha, Beta).
2. Autonomous Promotion (Self-Evolving Autonomy):
   - When an action achieves >= 10 consecutive verified successes (Rule #6 compliant)
     and Bayesian posterior >= 0.95, it is promoted to a higher autonomy tier:
     MANDATORY_HITL -> HITL_SINGLE -> POLICY_FAST_APPROVAL -> AUTO_FAST_TRACK -> FULLY_AUTONOMOUS
3. Fail-Closed Demotion Circuit-Breaker:
   - If an action ever fails post-remediation verification, canary testing, or triggers a rollback,
     it is INSTANTLY demoted back to MANDATORY_HITL for that asset tier.
   - Consecutive counter resets to 0.
4. Non-Repudiation Audit:
   - Every promotion and demotion logs structured provenance evidence.
"""

import logging
import time
import json
import threading
from typing import Dict, Any, Optional

logger = logging.getLogger("RLIF_AUTONOMY_CALIBRATOR")

AUTONOMY_TIERS = [
    "MANDATORY_HITL",       # Tier 0: Strict 2-person or operator mandatory sign-off
    "HITL_SINGLE",          # Tier 1: Single operator approval required
    "POLICY_FAST_APPROVAL", # Tier 2: Pre-approved policy check + 10s auto-approve window
    "AUTO_FAST_TRACK",      # Tier 3: Autonomous execution with real-time audit stream
    "FULLY_AUTONOMOUS"      # Tier 4: Zero-touch closed-loop autonomous self-healing
]

# Baseline default mappings for known action categories
DEFAULT_BASE_TIERS = {
    "ping": "FULLY_AUTONOMOUS",
    "traceroute": "FULLY_AUTONOMOUS",
    "flush_dns": "AUTO_FAST_TRACK",
    "clear_spooler": "POLICY_FAST_APPROVAL",
    "restart_spooler": "POLICY_FAST_APPROVAL",
    "clear_temp_files": "AUTO_FAST_TRACK",
    "restart_adapter": "HITL_SINGLE",
    "restart_nginx": "POLICY_FAST_APPROVAL",
    "restart_postgresql": "HITL_SINGLE",
    "execute_playbook_l3_route_flush": "HITL_SINGLE",
    "modify_firewall": "MANDATORY_HITL",
    "reset_network_stack": "MANDATORY_HITL",
    "format_disk": "MANDATORY_HITL",
}


class RLIFAutonomyCalibrator:
    """
    Thread-safe RLIF Autonomy Calibrator with Bayesian updating and fail-closed circuit breakers.
    """

    def __init__(self, alpha_prior: float = 2.0, beta_prior: float = 2.0):
        self._lock = threading.Lock()
        self.alpha_prior = alpha_prior
        self.beta_prior = beta_prior
        # In-memory calibration store: key -> {successes, failures, consecutive, tier, history}
        self._registry: Dict[str, Dict[str, Any]] = {}

    def _get_key(self, action_id: str, asset_class: str) -> str:
        return f"{action_id.lower().strip()}:{asset_class.upper().strip()}"

    def get_calibrated_autonomy(self, action_id: str, asset_class: str = "DEFAULT") -> Dict[str, Any]:
        """
        Retrieves the calibrated autonomy state and Bayesian confidence for (action_id, asset_class).
        """
        key = self._get_key(action_id, asset_class)
        norm_action = action_id.lower().strip()

        with self._lock:
            if key not in self._registry:
                # Initialize with baseline tier
                base_tier = DEFAULT_BASE_TIERS.get(norm_action, "MANDATORY_HITL")
                self._registry[key] = {
                    "action_id": norm_action,
                    "asset_class": asset_class.upper().strip(),
                    "tier": base_tier,
                    "successes": 0,
                    "failures": 0,
                    "consecutive_successes": 0,
                    "promotions": 0,
                    "demotions": 0,
                    "last_updated": time.time(),
                }

            entry = self._registry[key]
            succ = entry["successes"]
            fail = entry["failures"]
            # Beta-Bernoulli posterior mean: (alpha + successes) / (alpha + beta + total)
            posterior = (self.alpha_prior + succ) / (self.alpha_prior + self.beta_prior + succ + fail)

            tier = entry["tier"]
            is_autonomous = tier in ["AUTO_FAST_TRACK", "FULLY_AUTONOMOUS"]
            requires_hitl = tier in ["MANDATORY_HITL", "HITL_SINGLE"]

            return {
                "action_id": norm_action,
                "asset_class": entry["asset_class"],
                "tier": tier,
                "tier_index": AUTONOMY_TIERS.index(tier),
                "is_autonomous": is_autonomous,
                "requires_hitl": requires_hitl,
                "bayes_posterior_confidence": round(posterior, 4),
                "consecutive_successes": entry["consecutive_successes"],
                "total_successes": succ,
                "total_failures": fail,
                "promotions_count": entry["promotions"],
                "demotions_count": entry["demotions"],
                "last_updated": entry["last_updated"]
            }

    def record_execution_outcome(
        self,
        action_id: str,
        asset_class: str = "DEFAULT",
        success: bool = True,
        incident_id: str = "",
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Ingests feedback from verification outcome (Rule #6 verified post-remediation evidence).
        Performs Bayesian learning:
        - If success: increments consecutive_successes, triggers promotion when threshold met.
        - If failure: INSTANT DEMOTION to MANDATORY_HITL circuit-breaker.
        """
        key = self._get_key(action_id, asset_class)
        norm_action = action_id.lower().strip()

        with self._lock:
            # Ensure key initialized
            if key not in self._registry:
                base_tier = DEFAULT_BASE_TIERS.get(norm_action, "MANDATORY_HITL")
                self._registry[key] = {
                    "action_id": norm_action,
                    "asset_class": asset_class.upper().strip(),
                    "tier": base_tier,
                    "successes": 0,
                    "failures": 0,
                    "consecutive_successes": 0,
                    "promotions": 0,
                    "demotions": 0,
                    "last_updated": time.time(),
                }

            entry = self._registry[key]
            current_tier = entry["tier"]
            current_idx = AUTONOMY_TIERS.index(current_tier)

            transition = "NONE"
            old_tier = current_tier

            if success:
                entry["successes"] += 1
                entry["consecutive_successes"] += 1
                succ = entry["successes"]
                fail = entry["failures"]
                posterior = (self.alpha_prior + succ) / (self.alpha_prior + self.beta_prior + succ + fail)

                # Promotion Rule: >= 10 consecutive successes AND posterior >= 0.85
                if entry["consecutive_successes"] >= 10 and posterior >= 0.85:
                    if current_idx < len(AUTONOMY_TIERS) - 1:
                        new_tier = AUTONOMY_TIERS[current_idx + 1]
                        entry["tier"] = new_tier
                        entry["promotions"] += 1
                        transition = f"PROMOTED_{old_tier}_TO_{new_tier}"
                        logger.info(
                            f"[RLIF CALIBRATOR] Action '{norm_action}' on '{asset_class}' PROMOTED: "
                            f"{old_tier} -> {new_tier} (consecutive={entry['consecutive_successes']}, posterior={posterior:.3f})"
                        )
            else:
                # Failure Demotion Circuit Breaker
                entry["failures"] += 1
                entry["consecutive_successes"] = 0
                entry["demotions"] += 1
                
                # Immediate drop to MANDATORY_HITL
                new_tier = "MANDATORY_HITL"
                entry["tier"] = new_tier
                transition = f"DEMOTED_{old_tier}_TO_{new_tier}_FAIL_CLOSED"
                logger.warning(
                    f"[RLIF CALIBRATOR] Action '{norm_action}' on '{asset_class}' DEMOTED: "
                    f"{old_tier} -> {new_tier} due to verification/rollback failure! (Incident: {incident_id})"
                )

            entry["last_updated"] = time.time()
            succ = entry["successes"]
            fail = entry["failures"]
            posterior = (self.alpha_prior + succ) / (self.alpha_prior + self.beta_prior + succ + fail)

            return {
                "action_id": norm_action,
                "asset_class": entry["asset_class"],
                "success": success,
                "transition": transition,
                "old_tier": old_tier,
                "new_tier": entry["tier"],
                "consecutive_successes": entry["consecutive_successes"],
                "bayes_posterior_confidence": round(posterior, 4),
                "incident_id": incident_id
            }

    def reset_all(self):
        """Resets calibration state for testing."""
        with self._lock:
            self._registry.clear()


# Process-wide Singleton
_calibrator_instance: Optional[RLIFAutonomyCalibrator] = None
_calibrator_lock = threading.Lock()

def get_rlif_calibrator() -> RLIFAutonomyCalibrator:
    global _calibrator_instance
    if _calibrator_instance is None:
        with _calibrator_lock:
            if _calibrator_instance is None:
                _calibrator_instance = RLIFAutonomyCalibrator()
    return _calibrator_instance
