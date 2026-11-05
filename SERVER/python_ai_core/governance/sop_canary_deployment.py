"""
Enterprise Agentic AI OS — SOP Canary Deployment & A/B Testing Engine
Sprint Q: Canary Rollout for SOPs (10% -> 50% -> 100% Auto-Promotion & Instant Rollback)

Manages gradual deployment of newly promoted SOPs/knowledge from Sandbox Stage 4:
  1. Stage 1: 10% Canary Traffic Rollout (Deterministic incident hash routing)
  2. Stage 2: Auto-promotion to 50% if Success Rate >= 95% & 0 Side Effects
  3. Stage 3: Auto-promotion to 100% Production Golden Baseline
  4. Auto-Rollback: Instant fallback to previous golden SOP version if failure occurs
"""

import os
import json
import time
import hashlib
import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger("SOP_CANARY_DEPLOYMENT")

class SOPCanaryDeploymentEngine:
    """
    Manages Canary A/B Testing & Automated Rollbacks for SOPs.
    """

    STAGE_10 = "CANARY_10_PERCENT"
    STAGE_50 = "CANARY_50_PERCENT"
    STAGE_100 = "PRODUCTION_100_PERCENT"
    ROLLED_BACK = "ROLLED_BACK_SAFETY_TRIGGERED"

    def __init__(self, storage_file: Optional[str] = None):
        if storage_file is None:
            storage_file = os.path.join(os.path.dirname(__file__), "sop_canary_registry.json")
        self.storage_file = storage_file
        self.registry: Dict[str, Dict[str, Any]] = self._load_registry()

    def _load_registry(self) -> Dict[str, Dict[str, Any]]:
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"[CANARY] Error loading registry: {e}")
        return {}

    def _save_registry(self):
        try:
            os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
            with open(self.storage_file, "w") as f:
                json.dump(self.registry, f, indent=2)
        except Exception as e:
            logger.error(f"[CANARY] Error saving registry: {e}")

    def register_new_sop(
        self,
        sop_id: str,
        sop_title: str,
        sop_content: str,
        previous_version_content: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Registers a new SOP from Sandbox Stage 4 into Canary Stage 1 (10% Traffic).
        """
        entry = {
            "sop_id": sop_id,
            "sop_title": sop_title,
            "canary_stage": self.STAGE_10,
            "canary_traffic_pct": 10,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sop_content": sop_content,
            "previous_version_content": previous_version_content or "",
            "metrics": {
                "total_evaluations": 0,
                "successes": 0,
                "failures": 0,
                "side_effects": 0,
                "success_rate_pct": 0.0
            },
            "history": [
                {
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "event": "REGISTERED_CANARY_10_PERCENT",
                    "details": "SOP entered 10% Canary Rollout traffic"
                }
            ]
        }
        self.registry[sop_id] = entry
        self._save_registry()
        logger.info(f"🐤 [CANARY REGISTERED] SOP '{sop_id}' ({sop_title}) entered 10% Canary Rollout.")
        return entry

    def should_use_canary(self, sop_id: str, incident_id: str) -> Tuple[bool, str]:
        """
        Deterministic Hash Routing to decide if this incident gets the Canary SOP.
        Returns (use_canary: bool, current_sop_content: str).
        """
        entry = self.registry.get(sop_id)
        if not entry:
            return False, ""

        stage = entry.get("canary_stage")

        if stage == self.ROLLED_BACK:
            logger.warning(f"[CANARY] SOP '{sop_id}' is ROLLED BACK. Using previous baseline SOP.")
            return False, entry.get("previous_version_content", "")

        if stage == self.STAGE_100:
            return True, entry.get("sop_content", "")

        traffic_pct = entry.get("canary_traffic_pct", 10)

        # Deterministic hashing of incident_id -> [0..99]
        hash_val = int(hashlib.md5(f"{sop_id}:{incident_id}".encode("utf-8")).hexdigest(), 16)
        slot = hash_val % 100

        use_canary = slot < traffic_pct
        sop_to_use = entry.get("sop_content", "") if use_canary else entry.get("previous_version_content", "")
        
        logger.debug(f"[CANARY ROUTING] Incident '{incident_id}' slot={slot} < {traffic_pct}% -> Canary: {use_canary}")
        return use_canary, sop_to_use

    def record_result(self, sop_id: str, is_success: bool, side_effect_detected: bool = False) -> Dict[str, Any]:
        """
        Record execution result and trigger auto-promotion (10%->50%->100%) or instant rollback.
        """
        entry = self.registry.get(sop_id)
        if not entry:
            return {"error": "SOP not found"}

        if entry["canary_stage"] == self.ROLLED_BACK:
            return entry

        metrics = entry["metrics"]
        metrics["total_evaluations"] += 1
        if is_success and not side_effect_detected:
            metrics["successes"] += 1
        else:
            metrics["failures"] += 1

        if side_effect_detected:
            metrics["side_effects"] += 1

        metrics["success_rate_pct"] = round((metrics["successes"] / metrics["total_evaluations"]) * 100, 1)
        total = metrics["total_evaluations"]
        rate = metrics["success_rate_pct"]
        side_effects = metrics["side_effects"]

        # Check Auto-Rollback Criteria
        if side_effects > 0 or (total >= 5 and rate < 95.0):
            entry["canary_stage"] = self.ROLLED_BACK
            entry["canary_traffic_pct"] = 0
            entry["history"].append({
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "event": "INSTANT_ROLLBACK_TRIGGERED",
                "details": f"Rollback triggered (Success Rate: {rate}%, Side Effects: {side_effects})"
            })
            logger.error(f"🚨 [CANARY INSTANT ROLLBACK] SOP '{sop_id}' failed safety checks (Rate: {rate}%, Side-Effects: {side_effects}). Reverted to baseline!")
            self._save_registry()
            return entry

        # Check Auto-Promotion Criteria
        if entry["canary_stage"] == self.STAGE_10 and total >= 5 and rate >= 95.0:
            entry["canary_stage"] = self.STAGE_50
            entry["canary_traffic_pct"] = 50
            entry["history"].append({
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "event": "AUTO_PROMOTED_50_PERCENT",
                "details": f"Promoted to 50% traffic after {total} evaluations ({rate}% success rate)"
            })
            logger.info(f"📈 [CANARY AUTO-PROMOTION] SOP '{sop_id}' promoted to 50% Traffic Rollout!")

        elif entry["canary_stage"] == self.STAGE_50 and total >= 10 and rate >= 95.0:
            entry["canary_stage"] = self.STAGE_100
            entry["canary_traffic_pct"] = 100
            entry["history"].append({
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "event": "AUTO_PROMOTED_100_PERCENT_GOLDEN",
                "details": f"Promoted to 100% Golden Production Baseline after {total} evaluations ({rate}% success rate)"
            })
            logger.info(f"🏆 [CANARY GOLDEN PROMOTION] SOP '{sop_id}' 100% Promoted to Golden Production Baseline!")

        self._save_registry()
        return entry

    def get_status(self, sop_id: str) -> Optional[Dict[str, Any]]:
        return self.registry.get(sop_id)


# Demo run
if __name__ == "__main__":
    engine = SOPCanaryDeploymentEngine()
    print("=== UJI SOP CANARY DEPLOYMENT ENGINE (10% -> 50% -> 100% AUTO-PROMOTION) ===")

    test_sop_id = "SOP-2026-N8N-FAILOVER"
    engine.register_new_sop(
        sop_id=test_sop_id,
        sop_title="n8n Engine HA Auto-Failover SOP v2.1",
        sop_content="SOP BARU (CANARY): Restart n8n container + failover to Node2 NATS JetStream.",
        previous_version_content="SOP LAMA (BASELINE): Restart n8n container saja."
    )

    print("\n[Testing Deterministic Hash Routing for 10 Incidents]:")
    for i in range(1, 11):
        inc_id = f"INC-2026-00{i}"
        use_canary, content = engine.should_use_canary(test_sop_id, inc_id)
        tag = "🐤 CANARY (10%)" if use_canary else "🏛️ BASELINE (90%)"
        print(f" -> Incident {inc_id}: {tag}")
        # Simulate successful execution
        engine.record_result(test_sop_id, is_success=True, side_effect_detected=False)

    status = engine.get_status(test_sop_id)
    print(f"\n[Final SOP Status]: Stage = {status['canary_stage']} | Traffic = {status['canary_traffic_pct']}% | Success Rate = {status['metrics']['success_rate_pct']}%")
