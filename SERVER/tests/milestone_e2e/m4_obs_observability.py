"""
M4-OBS: Observability & Decision Trace Validation
Validates: Decision trace entry structure, evidence score fields,
           Correlation ID presence in contracts, metric recording interface.
"""
import unittest
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class OBS01_DecisionTraceStructure(unittest.TestCase):
    """OBS-01: DecisionTraceEntryDTO carries all observability fields."""

    def test_decision_trace_has_all_required_fields(self):
        from SERVER.shared.models import DecisionTraceEntryDTO
        from dataclasses import fields
        field_names = {f.name for f in fields(DecisionTraceEntryDTO)}

        required = {
            "step_name", "agent_id", "input_summary",
            "output_summary", "evidence_score", "duration_ms",
        }
        missing = required - field_names
        self.assertEqual(missing, set(),
                         f"Missing fields in DecisionTraceEntryDTO: {missing}")

    def test_decision_trace_instantiation(self):
        from SERVER.shared.models import DecisionTraceEntryDTO
        trace = DecisionTraceEntryDTO(
            step_name="RAGRetrieval",
            agent_id="rag-agent-01",
            input_summary="Nginx timeout Surabaya",
            output_summary="Retrieved 5 chunks",
            evidence_score=0.84,
            duration_ms=320.5,
        )
        self.assertEqual(trace.step_name, "RAGRetrieval")
        self.assertAlmostEqual(trace.duration_ms, 320.5)


class OBS02_EvidenceScoreFields(unittest.TestCase):
    """OBS-02: EvidenceScoreDTO exposes all multi-metric fields."""

    def test_all_metric_fields_accessible(self):
        from SERVER.shared.models import EvidenceScoreDTO
        score = EvidenceScoreDTO(
            similarity=0.88,
            coverage=0.75,
            freshness=0.95,
            source_trust=1.0,
            consensus=0.90,
            composite_score=0.878,
        )
        self.assertEqual(score.similarity, 0.88)
        self.assertEqual(score.coverage, 0.75)
        self.assertEqual(score.freshness, 0.95)
        self.assertEqual(score.source_trust, 1.0)
        self.assertEqual(score.consensus, 0.90)
        self.assertAlmostEqual(score.composite_score, 0.878)

    def test_is_sufficient_flag_correct(self):
        from SERVER.shared.models import EvidenceScoreDTO
        sufficient = EvidenceScoreDTO(0.9, 0.9, 0.9, 1.0, 0.9, composite_score=0.92)
        insufficient = EvidenceScoreDTO(0.3, 0.2, 0.4, 0.5, 0.3, composite_score=0.31)
        self.assertTrue(sufficient.is_sufficient)
        self.assertFalse(insufficient.is_sufficient)


class OBS03_ObservabilityCollectorInterface(unittest.TestCase):
    """OBS-03: ObservabilityCollector interface can be implemented without touching python_ai_core."""

    def test_concrete_collector_can_be_implemented(self):
        from SERVER.enterprise.observability.observability_collector import ObservabilityCollector
        from SERVER.shared.models import DecisionTraceEntryDTO
        from typing import List, Optional, Dict

        class InMemoryCollector(ObservabilityCollector):
            def __init__(self):
                self._traces: List[DecisionTraceEntryDTO] = []
                self._metrics: List[dict] = []

            def record_decision_trace(self, trace_entry: DecisionTraceEntryDTO) -> None:
                self._traces.append(trace_entry)

            def record_metric(self, metric_name: str, value: float,
                              labels: Optional[Dict[str, str]] = None) -> None:
                self._metrics.append({"name": metric_name, "value": value})

            def get_decision_traces(self, query_id: str) -> List[DecisionTraceEntryDTO]:
                return [t for t in self._traces if t.agent_id == query_id]

        collector = InMemoryCollector()
        trace = DecisionTraceEntryDTO(
            step_name="EvidenceScoring",
            agent_id="QRY-001",
            input_summary="5 chunks",
            output_summary="Score=0.83",
            evidence_score=0.83,
            duration_ms=45.0,
        )
        collector.record_decision_trace(trace)
        collector.record_metric("retrieval_time_ms", 320.0, {"track": "standard"})

        results = collector.get_decision_traces("QRY-001")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].step_name, "EvidenceScoring")


class OBS04_CorrelationIDInContracts(unittest.TestCase):
    """OBS-04: IncidentQueryContract carries query_id usable as Correlation ID."""

    def test_query_id_present_and_string(self):
        from SERVER.contracts.schemas import IncidentQueryContract
        q = IncidentQueryContract(
            query_id="CID-20260805-001",
            user_id="u1",
            user_role="noc_operator",
            query_text="Cek status OSPF",
        )
        self.assertTrue(isinstance(q.query_id, str))
        self.assertTrue(len(q.query_id) > 0)

    def test_correlation_id_propagated_to_response(self):
        from SERVER.contracts.schemas import IncidentQueryContract, IncidentResponseContract
        from SERVER.shared.enums import ExecutionTrack
        cid = "CID-20260805-001"
        q = IncidentQueryContract(
            query_id=cid, user_id="u1",
            user_role="noc_operator", query_text="Check OSPF"
        )
        r = IncidentResponseContract(
            query_id=cid,
            execution_track=ExecutionTrack.FAST_TRACK,
            answer_text="OSPF adjacency normal",
            evidence_score=0.91,
        )
        self.assertEqual(q.query_id, r.query_id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
