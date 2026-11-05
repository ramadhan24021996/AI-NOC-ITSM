"""
Sprint 3 — Repositories, Enterprise & Security Domain Test Suite
DoD: No SQL in business logic, immutable event chain, state persistence interface,
     secrets via provider, observability without touching python_ai_core, 0 circular imports.
"""
import unittest
import hashlib
import json


class TestSprint3Repositories(unittest.TestCase):
    def test_repository_imports(self):
        from SERVER.repositories import (
            BaseRepository, UnitOfWork, IncidentRepository,
            KnowledgeEntityRepository, MemoryEntityRepository,
            AuditRepository, VectorRepository,
        )
        self.assertTrue(issubclass(IncidentRepository, object))
        self.assertTrue(issubclass(VectorRepository, object))

    def test_unit_of_work_rollback_on_exception(self):
        from SERVER.repositories.unit_of_work import UnitOfWork
        committed = []
        rolled_back = []

        class ConcreteUoW(UnitOfWork):
            def commit(self): committed.append(True)
            def rollback(self): rolled_back.append(True)

        try:
            with ConcreteUoW():
                raise RuntimeError("Simulated failure")
        except RuntimeError:
            pass
        self.assertEqual(len(rolled_back), 1)
        self.assertEqual(len(committed), 0)

    def test_audit_repository_delete_is_forbidden(self):
        from SERVER.repositories.audit_repository import AuditRepository
        from typing import List, Dict, Any, Optional

        class ConcreteAudit(AuditRepository):
            def get_by_id(self, entity_id: str): return None
            def get_all(self, limit=100, offset=0): return []
            def add(self, entity): return entity
            def update(self, entity_id: str, updates): return None
            def find_by_actor(self, user_id: str, limit=100): return []
            def find_by_action_type(self, action_type: str, limit=100): return []

        repo = ConcreteAudit()
        with self.assertRaises(PermissionError):
            repo.delete("any-id")


class TestSprint3Enterprise(unittest.TestCase):
    def test_enterprise_imports(self):
        from SERVER.enterprise import (
            GovernancePolicyEngine, GovernancePolicy,
            StateManager, EventStore, ImmutableEventEntry,
            ObservabilityCollector, CapabilityRegistry, AgentCapability,
        )
        self.assertTrue(issubclass(GovernancePolicyEngine, object))

    def test_immutable_event_hash_chain(self):
        from SERVER.enterprise.event_sourcing.event_store import ImmutableEventEntry
        entry = ImmutableEventEntry(
            event_id="e001",
            event_type="IncidentCreated",
            aggregate_id="INC-001",
            payload={"severity": "critical"},
            actor_id="supervisor_agent",
            previous_hash="GENESIS",
        )
        h = entry.compute_hash()
        self.assertEqual(len(h), 64)          # SHA-256 hex = 64 chars
        self.assertEqual(h, entry.compute_hash())  # deterministic

    def test_capability_registry(self):
        from SERVER.enterprise import CapabilityRegistry, AgentCapability
        reg = CapabilityRegistry()
        cap = AgentCapability(
            agent_id="rag-agent-01",
            agent_type="RAGAgent",
            capabilities=["knowledge_retrieval", "evidence_scoring"],
            max_risk_level="read_only",
        )
        reg.register(cap)
        self.assertTrue(reg.can_perform("rag-agent-01", "evidence_scoring"))
        self.assertFalse(reg.can_perform("rag-agent-01", "execute_remediation"))
        self.assertIsNone(reg.get("nonexistent-agent"))


class TestSprint3Security(unittest.TestCase):
    def test_security_imports(self):
        from SERVER.security import (
            SecretProvider, CredentialManager,
            KeyRotationManager, EncryptionHelper, SecurityAuditLogger,
        )
        self.assertTrue(issubclass(SecretProvider, object))

    def test_credential_manager_via_provider(self):
        from SERVER.security import SecretProvider, CredentialManager
        from typing import Optional

        class InMemoryProvider(SecretProvider):
            def __init__(self):
                self._store = {
                    "DATABASE_URL": "postgresql://localhost:5432/ainos",
                    "GEMINI_API_KEY": "test-key-123",
                }
            def get_secret(self, secret_name: str) -> Optional[str]:
                return self._store.get(secret_name)
            def set_secret(self, secret_name: str, value: str) -> bool:
                self._store[secret_name] = value; return True
            def delete_secret(self, secret_name: str) -> bool:
                return bool(self._store.pop(secret_name, None))

        provider = InMemoryProvider()
        cred_mgr = CredentialManager(provider)
        self.assertEqual(cred_mgr.get_db_url(), "postgresql://localhost:5432/ainos")
        self.assertEqual(cred_mgr.get_api_key("gemini"), "test-key-123")
        self.assertIsNone(cred_mgr.get_redis_url())   # not in store → None

    def test_encryption_helper_roundtrip(self):
        from SERVER.security import EncryptionHelper
        helper = EncryptionHelper(secret_key="sprint3-test-key")
        plaintext = "Sensitive NOC credential value"
        encrypted = helper.encrypt(plaintext)
        self.assertNotEqual(encrypted, plaintext)
        decrypted = helper.decrypt(encrypted)
        self.assertEqual(decrypted, plaintext)

    def test_security_audit_logger(self):
        from SERVER.security import SecurityAuditLogger, SecurityAuditEvent
        logger = SecurityAuditLogger()
        event = SecurityAuditEvent(
            event_type="AUTH_FAILURE",
            actor_id="user_unknown",
            resource="/api/v1/diagnose",
            outcome="DENIED",
        )
        self.assertIsNotNone(event.timestamp)
        # Should not raise any exception
        logger.log(event)


if __name__ == "__main__":
    unittest.main()
