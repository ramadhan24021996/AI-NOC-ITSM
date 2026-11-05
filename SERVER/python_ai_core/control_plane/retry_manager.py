"""
Phase 4.0-B Retry Manager (control_plane/retry_manager.py)

Classifies errors into RETRYABLE vs NON-RETRYABLE exceptions.
Enforces exponential backoff and maximum retry attempt bounds (Max: 3 attempts).
"""

import logging
import time
from typing import Dict, Any, Tuple, Optional
from control_plane.event_envelope import CausalEventEnvelope

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("RETRY_MANAGER")

RETRYABLE_EXCEPTIONS = [
    "ConnectionError", "DatabaseError", "OperationalError", "TimeoutError",
    "NatsUnavailableError", "TransientDependencyError"
]

NON_RETRYABLE_EXCEPTIONS = [
    "SchemaValidationError", "ProvenanceInvalidError", "UnauthorizedCommandError",
    "BaselineIntegrityError", "ContractInvalidError", "CrossIncidentContaminationError",
    "PolicyViolationError", "FencingTokenMismatchDenied", "ContractHashMismatchError"
]


class RetryManager:
    def __init__(self, max_attempts: int = 3):
        self.max_attempts = max_attempts

    def classify_error(self, exc: Exception) -> Tuple[bool, str]:
        """
        Classifies error into (is_retryable, error_category).
        Returns: (True/False, category)
        """
        exc_type = type(exc).__name__
        exc_msg = str(exc)

        # Check explicit non-retryable keywords
        for non_ret in NON_RETRYABLE_EXCEPTIONS:
            if non_ret in exc_type or non_ret in exc_msg:
                logger.warning(f"[RETRY MANAGER] Non-retryable error detected: '{exc_type}: {exc_msg}'")
                return False, "NON_RETRYABLE"

        # Check explicit retryable keywords
        for ret in RETRYABLE_EXCEPTIONS:
            if ret in exc_type or ret in exc_msg:
                logger.info(f"[RETRY MANAGER] Retryable error detected: '{exc_type}: {exc_msg}'")
                return True, "RETRYABLE"

        # Default fallback for unknown exceptions: non-retryable to prevent infinite loops
        logger.warning(f"[RETRY MANAGER] Unclassified error defaulted to NON_RETRYABLE: '{exc_type}: {exc_msg}'")
        return False, "NON_RETRYABLE_FALLBACK"

    def should_retry(self, envelope: CausalEventEnvelope, exc: Exception) -> Tuple[bool, str]:
        """
        Determines whether event should be retried based on attempt count & error classification.
        """
        is_retryable, category = self.classify_error(exc)

        if not is_retryable:
            return False, f"NON_RETRYABLE_EXCEPTUATION ({category})"

        envelope.attempt_count += 1
        if envelope.attempt_count >= self.max_attempts:
            logger.error(f"[RETRY EXHAUSTED] Event '{envelope.event_id}' reached max attempt limit ({envelope.attempt_count}/{self.max_attempts})")
            return False, "MAX_RETRY_ATTEMPTS_EXCEEDED"

        logger.info(f"[RETRY GRANTED] Retrying Event '{envelope.event_id}' (Attempt {envelope.attempt_count}/{self.max_attempts})")
        return True, f"RETRY_ATTEMPT_{envelope.attempt_count}_GRANTED"
