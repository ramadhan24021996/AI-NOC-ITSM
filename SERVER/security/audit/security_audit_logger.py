"""
SERVER.security.audit - Security Audit Logger
Immutable security event logger for access, auth failures, and anomalies.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("security.audit")

@dataclass
class SecurityAuditEvent:
    event_type: str       # e.g. LOGIN_SUCCESS, AUTH_FAILURE, SECRET_ROTATED
    actor_id: str
    resource: str
    outcome: str          # SUCCESS | FAILURE | DENIED
    timestamp: str = ""
    details: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

class SecurityAuditLogger:
    """Security audit logger. All events are logged immutably."""

    def log(self, event: SecurityAuditEvent) -> None:
        logger.info(
            "[SECURITY_AUDIT] type=%s actor=%s resource=%s outcome=%s ts=%s details=%s",
            event.event_type, event.actor_id, event.resource,
            event.outcome, event.timestamp, event.details
        )
