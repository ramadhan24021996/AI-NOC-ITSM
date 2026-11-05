"""
Phase 4.0-B Recovery Controller (control_plane/recovery_controller.py)

Manages crashed worker recovery and claim re-acquisition.
Uses Fencing Tokens to safely invalidate stale worker claims.
"""

import logging
import uuid
import psycopg2
import json
from typing import Dict, Any, Tuple, Optional
from control_plane.event_claim_manager import EventClaimManager, STATE_RECOVERING, STATE_NEW

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("RECOVERY_CONTROLLER")


class RecoveryController:
    def __init__(self, claim_manager: EventClaimManager):
        self.claim_manager = claim_manager

    def recover_stale_claim(self, event_id: str, old_worker_id: str, new_worker_id: str) -> Tuple[bool, Optional[str], str]:
        """
        Recovers a claim from a crashed worker by re-assigning a new fencing token.
        Old worker attempting to use old fencing token will be DENIED.
        """
        new_token = f"FENCE-RECOVER-{uuid.uuid4().hex[:10]}"

        if event_id in self.claim_manager.active_claims:
            old_token, worker, state, disp = self.claim_manager.active_claims[event_id]
            logger.warning(f"[RECOVERY CLAIM] Invalidating old token '{old_token[:8]}...' for worker '{old_worker_id}'. Assigning new token '{new_token[:8]}...' to worker '{new_worker_id}'")
            self.claim_manager.active_claims[event_id] = (new_token, new_worker_id, STATE_RECOVERING, disp)
            return True, new_token, "RECOVERY_CLAIM_GRANTED"

        # If not in active memory, register recovery claim
        self.claim_manager.active_claims[event_id] = (new_token, new_worker_id, STATE_RECOVERING, None)
        logger.info(f"[RECOVERY REGISTERED] Granted recovery claim to worker '{new_worker_id}' with token '{new_token[:8]}...'")
        return True, new_token, "RECOVERY_CLAIM_REGISTERED"
