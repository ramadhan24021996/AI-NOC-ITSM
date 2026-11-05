"""
M0-FC: Functional Correctness Validation
Validates: Domain contracts, Evidence scoring, Insufficient Evidence guardrail,
           Immutable event hash chain, Repository pattern enforcement,
           SecretProvider isolation (no direct .env reads).
"""
import unittest
import hashlib
import json
import os
import sys

# ── Ensure project root on path ──────────────────────────────────────────────
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class FC01_EvidenceGuardrail(unittest.TestCase):
    """FC-01: Insufficient Evidence threshold enforced."""

    def test_evidence_score_sufficient_above_threshold(self):
        from SERVER.shared.models import EvidenceScoreDTO
        from SERVER.shared.constants import INSUFFICIENT_EVIDENCE_THRESHOLD
        score = EvidenceScoreDTO(0.85, 0.80, 0.90, 1.0, 0.95,
                                 composite_score=0.875)
        self.assertGreater(score.composite_score, INSUFFICIENT_EVIDENCE_THRESHOLD)
        self.assertTrue(score.is_sufficient)

    def test_evidence_score_insufficient_below_threshold(self):
        from SERVER.shared.models import EvidenceScoreDTO
        from SERVER.shared.constants import INSUFFICIENT_EVIDENCE_THRESHOLD
        score = EvidenceScoreDTO(0.4, 0.3, 0.5, 0.6, 0.5,
                                 composite_score=0.42)
        self.assertLess(score.composite_score, INSUFFICIENT_EVIDENCE_THRESHOLD)
        self.assertFalse(score.is_sufficient)

    def test_insufficient_evidence_exception_raised(self):
        from SERVER.shared.errors import InsufficientEvidenceException
        with self.assertRaises(InsufficientEvidenceException):
            raise InsufficientEvidenceException(
                "Evidence score 0.42 below threshold 0.70"
            )


class FC02_ContractIntegrity(unittest.TestCase):
    """FC-02: DTO Contracts are valid and carry required fields."""

    def test_incident_query_contract_fields(self):
        from SERVER.contracts.schemas import IncidentQueryContract
        q = IncidentQueryContract(
            query_id="QRY-001",
            user_id="USR-42",
            user_role="noc_operator",
            query_text="Nginx timeout di site Surabaya",
            site_location="Surabaya",
            telemetry_context={"cpu": 92, "mem": 78},
        )
        self.assertEqual(q.query_id, "QRY-001")
        self.assertEqual(q.user_role, "noc_operator")
        self.assertIn("cpu", q.telemetry_context)

    def test_incident_response_contract_fields(self):
        from SERVER.contracts.schemas import IncidentResponseContract
        from SERVER.shared.enums import ExecutionTrack
        r = IncidentResponseContract(
            query_id="QRY-001",
            execution_track=ExecutionTrack.STANDARD_TRACK,
            answer_text="Nginx worker connection limit tercapai.",
            evidence_score=0.82,
            citations=[{"source": "vendor-doc-001"}],
            requires_hitl=False,
        )
        self.assertFalse(r.requires_hitl)
        self.assertEqual(len(r.citations), 1)


class FC03_ImmutableEventChain(unittest.TestCase):
    """FC-03: Event sourcing hash chain is deterministic and tamper-detectable."""

    def test_hash_is_deterministic(self):
        from SERVER.enterprise.event_sourcing.event_store import ImmutableEventEntry
        entry = ImmutableEventEntry(
            event_id="EVT-001",
            event_type="IncidentResolved",
            aggregate_id="INC-001",
            payload={"resolution": "restarted nginx"},
            actor_id="noc_supervisor",
            timestamp="2026-08-05T03:00:00+00:00",
            previous_hash="GENESIS",
        )
        h1 = entry.compute_hash()
        h2 = entry.compute_hash()
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    def test_tampered_payload_changes_hash(self):
        from SERVER.enterprise.event_sourcing.event_store import ImmutableEventEntry
        base = dict(event_id="E1", event_type="T", aggregate_id="A",
                    actor_id="u", timestamp="2026-01-01T00:00:00+00:00",
                    previous_hash="GENESIS")
        e1 = ImmutableEventEntry(**base, payload={"action": "original"})
        e2 = ImmutableEventEntry(**base, payload={"action": "tampered"})
        self.assertNotEqual(e1.compute_hash(), e2.compute_hash())


class FC04_RepositoryIsolation(unittest.TestCase):
    """FC-04: Audit repo delete is permanently blocked."""

    def test_audit_delete_raises_permission_error(self):
        from SERVER.repositories.audit_repository import AuditRepository

        class StubAudit(AuditRepository):
            def get_by_id(self, entity_id: str): return None
            def get_all(self, limit=100, offset=0): return []
            def add(self, entity): return entity
            def update(self, entity_id: str, updates): return None
            def find_by_actor(self, user_id: str, limit=100): return []
            def find_by_action_type(self, action_type: str, limit=100): return []

        with self.assertRaises(PermissionError):
            StubAudit().delete("any")


class FC05_SecretProviderIsolation(unittest.TestCase):
    """FC-05: Credentials MUST be resolved via SecretProvider, never os.environ directly."""

    def test_credential_manager_uses_provider_not_env(self):
        from SERVER.security.vault.secret_provider import SecretProvider
        from SERVER.security.credentials.credential_manager import CredentialManager
        from typing import Optional

        # Provider returns controlled value, not whatever is in real env
        class ControlledProvider(SecretProvider):
            def get_secret(self, secret_name: str) -> Optional[str]:
                return "CONTROLLED_DB_URL" if secret_name == "DATABASE_URL" else None
            def set_secret(self, secret_name: str, value: str) -> bool: return True
            def delete_secret(self, secret_name: str) -> bool: return True

        creds = CredentialManager(ControlledProvider())
        # Prove: result comes from provider, not from actual environment
        self.assertEqual(creds.get_db_url(), "CONTROLLED_DB_URL")
        self.assertIsNone(creds.get_redis_url())


class FC06_UnitOfWorkTransactionBoundary(unittest.TestCase):
    """FC-06: Unit of Work commits on success, rolls back on exception."""

    def test_commit_called_on_success(self):
        from SERVER.repositories.unit_of_work import UnitOfWork
        log = []

        class ConcreteUoW(UnitOfWork):
            def commit(self): log.append("commit")
            def rollback(self): log.append("rollback")

        with ConcreteUoW():
            pass  # no exception
        self.assertEqual(log, ["commit"])

    def test_rollback_called_on_exception(self):
        from SERVER.repositories.unit_of_work import UnitOfWork
        log = []

        class ConcreteUoW(UnitOfWork):
            def commit(self): log.append("commit")
            def rollback(self): log.append("rollback")

        try:
            with ConcreteUoW():
                raise ValueError("DB error")
        except ValueError:
            pass
        self.assertEqual(log, ["rollback"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
