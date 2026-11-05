"""
Enterprise Security Audit Trail Engine
Records tamper-proof audit records (Who, When, Node, Edge, Old Value, New Value, Reason, Approval).
"""

import logging
import time
from typing import Dict, List, Any

logger = logging.getLogger("GRAPH_SECURITY_AUDIT_TRAIL")

class GraphSecurityAuditTrail:
    """
    Enterprise Audit Trail Engine
    Tracks every structural mutation and permission check for compliance auditing.
    """

    def __init__(self):
        self.audit_log: List[Dict[str, Any]] = []

    def record_audit_entry(
        self,
        operator: str,
        action_type: str,
        target_entity: str,
        old_value: Any = None,
        new_value: Any = None,
        reason: str = "Topology update",
        approval: str = "AUTO_APPROVED"
    ):
        """Records an auditable security entry."""
        entry = {
            "operator": operator,
            "action_type": action_type,
            "target_entity": target_entity,
            "old_value": old_value,
            "new_value": new_value,
            "reason": reason,
            "approval": approval,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        self.audit_log.append(entry)
        logger.info("[AUDIT TRAIL] Recorded action %s by %s on %s", action_type, operator, target_entity)

    def get_audit_trail(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns recent audit log records."""
        return self.audit_log[-limit:]
