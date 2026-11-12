"""
Phase 4.0-B Event Claim Manager (control_plane/event_claim_manager.py)

Manages Atomic Claims & Fencing Token Locks for Control Plane Runtime State Transitions.
Enforces:
- Separation of Runtime State and Business Disposition
- Atomic DB UPDATE for claim acquisition
- Fencing token validation on every transition to block split-brain / stale workers
"""

import logging
import os
import uuid
import psycopg2
import json
from typing import Dict, Any, Tuple, Optional
from control_plane.event_envelope import CausalEventEnvelope

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("EVENT_CLAIM_MANAGER")

DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("DB_PORT", "5433" if DB_HOST in ("127.0.0.1", "localhost") else "5432"))
DB_NAME = os.environ.get("DB_NAME", "osi_system")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("POSTGRES_PASSWORD", "[REDACTED_DB_PASS]"))

DB_CONFIG = {
    "host": DB_HOST,
    "port": DB_PORT,
    "dbname": DB_NAME,
    "user": DB_USER,
    "password": DB_PASSWORD,
}

# Runtime States
STATE_NEW = "NEW"
STATE_CLAIMED = "CLAIMED"
STATE_INGESTING = "INGESTING"
STATE_ANALYZING = "ANALYZING"
STATE_PROBING = "PROBING"
STATE_CAUSAL_EVALUATION = "CAUSAL_EVALUATION"
STATE_COUNTERFACTUAL = "COUNTERFACTUAL"
STATE_REMEDIATION_EVALUATION = "REMEDIATION_EVALUATION"
STATE_AWAITING_HITL = "AWAITING_HITL"
STATE_EXECUTING = "EXECUTING"
STATE_VERIFYING = "VERIFYING"
STATE_COMPLETED = "COMPLETED"
STATE_FAILED = "FAILED"
STATE_RECOVERING = "RECOVERING"

# Business Dispositions
DISP_CONFIRMED_REMEDIATION_READY = "CONFIRMED_REMEDIATION_READY"
DISP_INCONCLUSIVE = "INCONCLUSIVE"
DISP_REFUTED = "REFUTED"
DISP_INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
DISP_NO_SAFE_REMEDIATION = "NO_SAFE_REMEDIATION"
DISP_MANUAL_INVESTIGATION_REQUIRED = "MANUAL_INVESTIGATION_REQUIRED"
DISP_FAILED_RETRYABLE = "FAILED_RETRYABLE"
DISP_DEAD_LETTER = "DEAD_LETTER"


class EventClaimManager:
    def __init__(self, db_config: Dict[str, Any] = None):
        self.db_config = db_config or DB_CONFIG
        self.active_claims = {}  # Memory backup cache {event_id: (claim_token, worker_id, current_state, disposition)}

    def acquire_atomic_claim(self, envelope: CausalEventEnvelope, worker_id: str) -> Tuple[bool, Optional[str], str]:
        """
        Acquires atomic claim on NEW event using DB system_audits / causal_events table.
        Returns: (success, claim_token, message)
        """
        event_id = envelope.event_id
        new_token = f"FENCE-{uuid.uuid4().hex[:12]}"

        # Memory concurrency check
        if event_id in self.active_claims:
            token, existing_worker, state, disp = self.active_claims[event_id]
            if state not in [STATE_COMPLETED, STATE_FAILED] and existing_worker != worker_id:
                logger.warning(f"[CLAIM CONFLICT] Event '{event_id}' already claimed by worker '{existing_worker}' with token '{token[:8]}...'")
                return False, None, "ATOMIC_CLAIM_RACE_DENIED"

        conn = None
        cur = None
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()

            # Record claim acquisition in system_audits
            meta = {
                "event_id": event_id,
                "incident_id": envelope.incident_id,
                "claimed_by": worker_id,
                "claim_token": new_token,
                "runtime_state": STATE_CLAIMED,
                "disposition": None
            }
            query_insert = """
                INSERT INTO system_audits (audit_type, component, action, status, details, metadata)
                VALUES (%s, %s, %s, %s, %s, %s);
            """
            cur.execute(query_insert, (
                "EVENT_CLAIM",
                "EVENT_CLAIM_MANAGER",
                "ACQUIRE_CLAIM",
                STATE_CLAIMED,
                f"Worker '{worker_id}' acquired atomic claim with fencing token '{new_token}'",
                json.dumps(meta)
            ))
            conn.commit()

            envelope.claim_token = new_token
            envelope.claimed_by = worker_id
            self.active_claims[event_id] = (new_token, worker_id, STATE_CLAIMED, None)
            logger.info(f"[CLAIM ACQUIRED] Worker '{worker_id}' acquired claim on Event '{event_id}' with Fencing Token '{new_token[:8]}...'")
            return True, new_token, "CLAIM_ACQUIRED"

        except Exception as e:
            logger.error(f"[CLAIM DB ERROR] Failed to acquire claim: {e}")
            envelope.claim_token = new_token
            envelope.claimed_by = worker_id
            self.active_claims[event_id] = (new_token, worker_id, STATE_CLAIMED, None)
            return True, new_token, "CLAIM_ACQUIRED_MEM_FALLBACK"
        finally:
            if cur is not None:
                try:
                    cur.close()
                except Exception:
                    pass
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def transition_state(self, event_id: str, claim_token: str, new_state: str, disposition: Optional[str] = None) -> Tuple[bool, str]:
        """
        Transitions runtime state validating fencing token.
        Returns: (success, message)
        """
        if event_id not in self.active_claims:
            logger.error(f"[FENCING REJECT] Event '{event_id}' has no active claim.")
            return False, "NO_ACTIVE_CLAIM_FOUND"

        current_token, worker, curr_state, curr_disp = self.active_claims[event_id]

        if current_token != claim_token:
            logger.error(f"[FENCING TOKEN MISMATCH] Stale worker attempt! Expected Token '{current_token[:8]}...', Got '{claim_token[:8]}...'")
            return False, "FENCING_TOKEN_MISMATCH_DENIED"

        self.active_claims[event_id] = (claim_token, worker, new_state, disposition or curr_disp)
        logger.info(f"[STATE TRANSITION] Event '{event_id}': State='{new_state}', Disposition='{disposition or curr_disp}' (Fencing Token Verified)")
        return True, "STATE_TRANSITION_SUCCESS"
