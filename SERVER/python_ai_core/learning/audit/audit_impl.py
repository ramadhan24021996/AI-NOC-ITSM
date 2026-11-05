"""
LF-1 Learning Framework — Audit Logger (Concrete Implementation)
Wires IAuditLogger to the existing production SHA-256 chained audit trail
in services/audit_logger.py. Falls back to structured file logging.
"""
import json
import logging
import os
import time
from typing import Dict, Any

from .interfaces import IAuditLogger, AuditEvent

logger = logging.getLogger("LF1_AUDIT")

# Path for file-based fallback audit log
_FALLBACK_LOG_DIR  = os.getenv("LF1_AUDIT_LOG_DIR", "/tmp/lf1_audit")
_FALLBACK_LOG_FILE = os.path.join(_FALLBACK_LOG_DIR, "lf1_audit.jsonl")


class LearningAuditLogger(IAuditLogger):
    """
    Concrete audit logger for LF-1 Learning Framework.

    Primary path:
        Delegates to services.audit_logger.write_audit_log() which writes
        to the PostgreSQL immutable_audit_log table with SHA-256 block-chaining.

    Fallback path:
        Appends structured JSONL records to a local file when DB is unreachable.
    """

    # Mapping from AuditEvent enum to action_type string used by the DB schema
    _EVENT_MAP: Dict[AuditEvent, str] = {
        AuditEvent.LEARNING_STARTED:   "LF1_LEARNING_STARTED",
        AuditEvent.LEARNING_FINISHED:  "LF1_LEARNING_FINISHED",
        AuditEvent.EVALUATION_STARTED: "LF1_EVAL_STARTED",
        AuditEvent.EVALUATION_FINISHED:"LF1_EVAL_FINISHED",
        AuditEvent.FEATURE_CREATED:    "LF1_FEATURE_CREATED",
        AuditEvent.FEATURE_UPDATED:    "LF1_FEATURE_UPDATED",
        AuditEvent.MODEL_REGISTERED:   "LF1_MODEL_REGISTERED",
        AuditEvent.MODEL_DEPRECATED:   "LF1_MODEL_DEPRECATED",
    }

    def __init__(self, actor: str = "lf1_learning_framework"):
        self._actor = actor
        os.makedirs(_FALLBACK_LOG_DIR, exist_ok=True)
        logger.info("[LF1-AUDIT] LearningAuditLogger initialized. Actor: %s", actor)

    # ------------------------------------------------------------------
    # IAuditLogger implementation
    # ------------------------------------------------------------------
    def log(self, event: AuditEvent, details: Dict[str, Any]) -> None:
        """
        Records a learning lifecycle event to the immutable audit trail.

        Args:
            event:   AuditEvent enum value (e.g., AuditEvent.LEARNING_STARTED)
            details: Dict with context — job_id, model_version, score, etc.
        """
        action_type = self._EVENT_MAP.get(event, event.value)
        target = details.get("job_id", details.get("model_id", "UNKNOWN"))

        # Primary: write to PostgreSQL SHA-256 chain
        if not self._write_to_db(action_type, target, details):
            # Fallback: write to local JSONL file
            self._write_to_file(action_type, target, details)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _write_to_db(self, action_type: str, target: str, details: Dict[str, Any]) -> bool:
        """Delegates to the existing shared audit_logger service."""
        try:
            from services.audit_logger import write_audit_log
            write_audit_log(
                action_type=action_type,
                actor=self._actor,
                target=target,
                payload=details,
            )
            logger.info("[LF1-AUDIT] DB audit written: %s | target=%s", action_type, target)
            return True
        except ImportError:
            logger.debug("[LF1-AUDIT] audit_logger service not importable (test mode).")
        except Exception as e:
            logger.warning("[LF1-AUDIT] DB write failed, falling back to file: %s", e)
        return False

    def _write_to_file(self, action_type: str, target: str, details: Dict[str, Any]) -> None:
        """Appends a JSONL record to the fallback audit log file."""
        record = {
            "ts":          time.time(),
            "iso_ts":      time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "actor":       self._actor,
            "action_type": action_type,
            "target":      target,
            "details":     details,
        }
        try:
            with open(_FALLBACK_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
            logger.info("[LF1-AUDIT] File audit written: %s | target=%s", action_type, target)
        except OSError as e:
            logger.error("[LF1-AUDIT] CRITICAL — both DB and file audit failed: %s", e)
