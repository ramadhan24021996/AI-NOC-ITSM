"""
Sprint 1 Core Foundation Domain Import & Integrity Test
Verifies that SERVER.shared, SERVER.contracts, SERVER.knowledge, SERVER.memory, and SERVER.tools
can be imported cleanly without depending on python_ai_core.
"""
import unittest

class TestSprint1CoreFoundation(unittest.TestCase):
    def test_shared_domain_imports(self):
        from SERVER.shared import IncidentSeverity, ExecutionTrack, TrustRating, ActionRiskLevel
        from SERVER.shared import DomainException, InsufficientEvidenceException
        from SERVER.shared import KnowledgeChunkDTO, EvidenceScoreDTO

        self.assertEqual(IncidentSeverity.CRITICAL.value, "critical")
        self.assertEqual(ExecutionTrack.FAST_TRACK.value, "fast_track")
        self.assertEqual(TrustRating.OFFICIAL_VENDOR.value, "official_vendor")

        score = EvidenceScoreDTO(0.8, 0.8, 0.9, 1.0, 0.9, 0.85)
        self.assertTrue(score.is_sufficient)

    def test_shared_adapters(self):
        from SERVER.shared.adapters import legacy_chunk_dict_to_dto, compute_composite_evidence_score
        from SERVER.shared import TrustRating

        raw_chunk = {
            "chunk_id": "c101",
            "title": "Nginx Timeout SOP",
            "text": "Check worker connections",
            "trust_rating": "official_vendor",
            "similarity_score": 0.88
        }
        dto = legacy_chunk_dict_to_dto(raw_chunk)
        self.assertEqual(dto.chunk_id, "c101")
        self.assertEqual(dto.trust_rating, TrustRating.OFFICIAL_VENDOR)

        ev_score = compute_composite_evidence_score(similarity=0.9, coverage=0.8)
        self.assertGreater(ev_score.composite_score, 0.70)
        self.assertTrue(ev_score.is_sufficient)

    def test_contracts_domain_imports(self):
        from SERVER.contracts import IncidentQueryContract, IncidentResponseContract, IncidentCreatedEvent

        query = IncidentQueryContract("q1", "u1", "operator", "Cek Nginx")
        self.assertEqual(query.query_id, "q1")

        event = IncidentCreatedEvent("e1", "IncidentCreated", "2026-08-05", {})
        self.assertEqual(event.event_type, "IncidentCreated")

    def test_knowledge_domain_imports(self):
        from SERVER.knowledge import KnowledgeProvider, KnowledgeRepository, KnowledgeRetriever, KnowledgeValidator

        self.assertTrue(issubclass(KnowledgeProvider, object))

    def test_memory_domain_imports(self):
        from SERVER.memory import MemoryStore, ConversationMemory, EpisodeMemory, SemanticMemory

        self.assertTrue(issubclass(MemoryStore, object))

    def test_tools_domain_imports(self):
        from SERVER.tools import Tool, ToolManifest, ToolExecutor, PermissionChecker, TimeoutManager
        from SERVER.shared import ActionRiskLevel

        manifest = ToolManifest("t1", "Ping", "Check ICMP", "1.0", ActionRiskLevel.READ_ONLY)
        self.assertEqual(manifest.tool_id, "t1")

if __name__ == "__main__":
    unittest.main()
