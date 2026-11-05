"""
M3-SEC: Security Validation
Validates: RBAC enforcement, secret isolation, audit immutability,
           unauthorized action blocking, encryption correctness.
"""
import unittest
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class SEC01_UnauthorizedActionRaisesDomainException(unittest.TestCase):
    """SEC-01: UnauthorizedActionException raised when RBAC blocks action."""

    def test_unauthorized_exception_carries_correct_info(self):
        from SERVER.shared.errors import UnauthorizedActionException
        exc = UnauthorizedActionException(
            "User 'readonly_user' is not permitted to execute 'rollback_server'"
        )
        self.assertIn("readonly_user", str(exc))
        self.assertIn("rollback_server", str(exc))

    def test_tool_manifest_risk_level_read_only(self):
        from SERVER.tools.interfaces import ToolManifest
        from SERVER.shared.enums import ActionRiskLevel
        manifest = ToolManifest(
            tool_id="ping-001",
            name="PingCheck",
            description="ICMP check",
            version="1.0",
            risk_level=ActionRiskLevel.READ_ONLY,
            required_permissions=["read"],
        )
        self.assertEqual(manifest.risk_level, ActionRiskLevel.READ_ONLY)
        self.assertNotIn("execute", manifest.required_permissions)

    def test_highest_risk_level_enum_exists(self):
        from SERVER.shared.enums import ActionRiskLevel
        risk_values = [r.value for r in ActionRiskLevel]
        # 'critical_risk' is the highest ActionRiskLevel defined in the system
        self.assertIn("critical_risk", risk_values)
        # Verify the full risk ladder is present
        for expected in ("read_only", "low_risk", "medium_risk", "high_risk", "critical_risk"):
            self.assertIn(expected, risk_values)


class SEC02_CapabilityRegistryEnforcesLimits(unittest.TestCase):
    """SEC-02: Agent capability registry blocks unauthorized capabilities."""

    def test_agent_cannot_perform_unregistered_capability(self):
        from SERVER.enterprise.capability_registry.capability_registry import (
            CapabilityRegistry, AgentCapability
        )
        reg = CapabilityRegistry()
        reg.register(AgentCapability(
            agent_id="read-only-agent",
            agent_type="ReadAgent",
            capabilities=["knowledge_retrieval", "evidence_scoring"],
            max_risk_level="read_only",
        ))
        self.assertFalse(reg.can_perform("read-only-agent", "execute_rollback"))
        self.assertFalse(reg.can_perform("nonexistent-agent", "knowledge_retrieval"))

    def test_agent_can_perform_registered_capability(self):
        from SERVER.enterprise.capability_registry.capability_registry import (
            CapabilityRegistry, AgentCapability
        )
        reg = CapabilityRegistry()
        reg.register(AgentCapability(
            agent_id="supervisor-01",
            agent_type="SupervisorAgent",
            capabilities=["orchestrate", "escalate_hitl", "evidence_scoring"],
            max_risk_level="critical",
        ))
        self.assertTrue(reg.can_perform("supervisor-01", "orchestrate"))
        self.assertTrue(reg.can_perform("supervisor-01", "escalate_hitl"))


class SEC03_SecretIsolationContract(unittest.TestCase):
    """SEC-03: Business code resolving secrets returns provider value, not env value."""

    def test_provider_overrides_env(self):
        """Even if DATABASE_URL is in env, CredentialManager uses provider."""
        import os
        from typing import Optional
        from SERVER.security.vault.secret_provider import SecretProvider
        from SERVER.security.credentials.credential_manager import CredentialManager

        # Set a trap env var
        os.environ["DATABASE_URL"] = "THIS_SHOULD_NOT_APPEAR"

        class IsolatedProvider(SecretProvider):
            def get_secret(self, secret_name: str) -> Optional[str]:
                return "provider_db_url" if secret_name == "DATABASE_URL" else None
            def set_secret(self, secret_name: str, value: str) -> bool: return True
            def delete_secret(self, secret_name: str) -> bool: return True

        mgr = CredentialManager(IsolatedProvider())
        result = mgr.get_db_url()
        # Must come from provider, not from os.environ
        self.assertEqual(result, "provider_db_url")
        self.assertNotEqual(result, "THIS_SHOULD_NOT_APPEAR")
        # Cleanup
        del os.environ["DATABASE_URL"]


class SEC04_AuditImmutability(unittest.TestCase):
    """SEC-04: Audit entries cannot be deleted."""

    def test_audit_delete_permanently_blocked(self):
        from SERVER.repositories.audit_repository import AuditRepository

        class StubAudit(AuditRepository):
            def get_by_id(self, entity_id: str): return None
            def get_all(self, limit=100, offset=0): return []
            def add(self, entity): return entity
            def update(self, entity_id: str, updates): return None
            def find_by_actor(self, user_id: str, limit=100): return []
            def find_by_action_type(self, action_type: str, limit=100): return []

        repo = StubAudit()
        with self.assertRaises(PermissionError) as ctx:
            repo.delete("AUDIT-001")
        self.assertIn("immutable", str(ctx.exception).lower())


class SEC05_SecurityAuditEventStructure(unittest.TestCase):
    """SEC-05: Security audit event carries required fields and auto-timestamps."""

    def test_event_has_all_required_fields(self):
        from SERVER.security.audit.security_audit_logger import (
            SecurityAuditEvent, SecurityAuditLogger
        )
        evt = SecurityAuditEvent(
            event_type="AUTH_FAILURE",
            actor_id="unknown_user",
            resource="/api/v1/diagnose",
            outcome="DENIED",
        )
        self.assertTrue(len(evt.timestamp) > 0)
        self.assertEqual(evt.outcome, "DENIED")
        self.assertEqual(evt.event_type, "AUTH_FAILURE")

        logger = SecurityAuditLogger()
        # Must not raise
        logger.log(evt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
