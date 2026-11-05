"""
Tahap 2.1 — Concrete Persistence Layer & Compatibility Bridge Test Suite
DoD Criteria:
1. Compatibility bridge maps legacy structures seamlessly to DTOs.
2. PostgresIncidentRepository performs CRUD and site/severity filtering.
3. PgVectorRepository performs vector embedding cosine similarity search.
4. RedisStateManager stores and retrieves persistent states.
5. PostgresUnitOfWork manages transaction boundaries cleanly.
6. 100% backward compatibility maintained.
"""
import unittest
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestTahap21PersistenceAndCompatibility(unittest.TestCase):
    def test_compatibility_layer_imports(self):
        from SERVER.compatibility import (
            LegacyModelAdapter, LegacyRepositoryBridge, LegacyEventBridge, LegacyAPIBridge, MigrationAdapter
        )
        self.assertTrue(issubclass(LegacyModelAdapter, object))
        self.assertTrue(MigrationAdapter.is_migration_active())

    def test_legacy_model_and_api_bridges(self):
        from SERVER.compatibility import LegacyModelAdapter, LegacyAPIBridge
        from SERVER.contracts.schemas import IncidentResponseContract
        from SERVER.shared.enums import ExecutionTrack

        # Model conversion test
        raw_dict = {"chunk_id": "c1", "title": "SOP Nginx", "text": "Content", "trust_rating": "official_vendor"}
        dto = LegacyModelAdapter.dict_to_chunk_dto(raw_dict)
        self.assertEqual(dto.chunk_id, "c1")
        back_dict = LegacyModelAdapter.chunk_dto_to_dict(dto)
        self.assertEqual(back_dict["title"], "SOP Nginx")

        # API conversion test
        contract_req = LegacyAPIBridge.legacy_request_to_contract({
            "query_id": "Q-100", "user": "alice", "role": "operator", "query": "Check BGP"
        })
        self.assertEqual(contract_req.query_id, "Q-100")
        self.assertEqual(contract_req.user_role, "operator")

        legacy_resp = LegacyAPIBridge.contract_to_legacy_response(IncidentResponseContract(
            query_id="Q-100", execution_track=ExecutionTrack.FAST_TRACK, answer_text="BGP normal", evidence_score=0.95
        ))
        self.assertEqual(legacy_resp["answer"], "BGP normal")

    def test_postgres_incident_repository(self):
        from SERVER.repositories import PostgresIncidentRepository
        repo = PostgresIncidentRepository()

        # Add entity
        inc = repo.add({"site_name": "Surabaya-DC1", "severity": "critical", "description": "Core switch failure"})
        eid = inc["incident_id"]
        self.assertIsNotNone(eid)

        # Retrieve
        retrieved = repo.get_by_id(eid)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["site_name"], "Surabaya-DC1")

        # Filter by site and severity
        by_site = repo.find_by_site("Surabaya-DC1")
        self.assertEqual(len(by_site), 1)

        by_sev = repo.find_by_severity("critical")
        self.assertEqual(len(by_sev), 1)

        # Update
        repo.update(eid, {"status": "resolved"})
        self.assertEqual(repo.get_by_id(eid)["status"], "resolved")

        # Delete
        repo.delete(eid)
        self.assertIsNone(repo.get_by_id(eid))

    def test_pgvector_knowledge_repository(self):
        from SERVER.repositories import PgVectorRepository
        v_repo = PgVectorRepository()

        v_repo.upsert_embedding("chunk_1", [1.0, 0.0, 0.0], {"title": "Nginx SOP"})
        v_repo.upsert_embedding("chunk_2", [0.0, 1.0, 0.0], {"title": "BGP SOP"})
        v_repo.upsert_embedding("chunk_3", [0.9, 0.1, 0.0], {"title": "Nginx Timeout SOP"})

        # Similarity search for query embedding close to chunk_1 & chunk_3
        results = v_repo.similarity_search([1.0, 0.0, 0.0], top_k=2, threshold=0.70)
        self.assertEqual(len(results), 2)
        # First match should be chunk_1 (similarity 1.0)
        self.assertEqual(results[0][0], "chunk_1")
        self.assertAlmostEqual(results[0][1], 1.0)
        # Second match should be chunk_3
        self.assertEqual(results[1][0], "chunk_3")

        v_repo.delete_embedding("chunk_1")
        results_after = v_repo.similarity_search([1.0, 0.0, 0.0], top_k=2, threshold=0.70)
        self.assertEqual(results_after[0][0], "chunk_3")

    def test_redis_state_manager(self):
        from SERVER.repositories import RedisStateManager
        redis_mgr = RedisStateManager()

        redis_mgr.set_state("session:1001", {"user_id": "usr_alice", "step": "diagnosing"})
        val = redis_mgr.get_state("session:1001")
        self.assertIsNotNone(val)
        self.assertEqual(val["user_id"], "usr_alice")

        all_sess = redis_mgr.get_all_states(prefix="session:")
        self.assertEqual(len(all_sess), 1)

        redis_mgr.delete_state("session:1001")
        self.assertIsNone(redis_mgr.get_state("session:1001"))

    def test_postgres_unit_of_work(self):
        from SERVER.repositories import PostgresUnitOfWork
        uow = PostgresUnitOfWork()

        with uow:
            uow.incidents.add({"site_name": "Jakarta-DC2", "severity": "high"})

        self.assertTrue(uow.committed)
        self.assertFalse(uow.rolled_back)


if __name__ == "__main__":
    unittest.main()
