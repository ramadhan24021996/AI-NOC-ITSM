"""
Unit Tests for Enterprise Causal Intelligence Platform Expansion
Tests EvidenceCollector, DependencyDiscovery, CausalModelBuilder, SimulationCache, InterventionPlanner, CausalMemory.
"""

import unittest
import os
from causal_engine import (
    EvidenceCollector, UnifiedEvidence,
    DependencyDiscovery, LayerDependency, LayerType,
    CausalModelBuilder, ProposedCausalEdge,
    SimulationCache, CounterfactualResult,
    InterventionPlanner, ActionableRemediationStep,
    CausalMemory, CausalMemoryRecord
)


class TestCausalPlatformExpansion(unittest.TestCase):
    def test_evidence_collector(self):
        raw = {
            "device_id": "POS-KASIR-99",
            "telemetry": {"cpu": 85},
            "windows_events": [{"event_id": 7036}],
            "syslog": [{"msg": "Link Down"}]
        }
        collector = EvidenceCollector()
        evd = collector.collect_all_evidence(raw)
        self.assertEqual(evd.device_id, "POS-KASIR-99")
        self.assertEqual(evd.telemetry["cpu"], 85)
        self.assertEqual(len(evd.event_viewer), 1)

    def test_dependency_discovery(self):
        disc = DependencyDiscovery()
        chain = disc.traverse_bottom_up("Printer_Offline")
        self.assertGreaterEqual(len(chain), 2)
        # Printer_Offline -> ConnectionTimeout -> DNS_Timeout -> PacketLoss -> RSSI
        target_nodes = [c.source_node for c in chain]
        self.assertIn("ConnectionTimeout", target_nodes)

    def test_causal_model_builder(self):
        builder = CausalModelBuilder()
        builder.record_occurrence("RSSI", "PacketLoss")
        builder.record_occurrence("RSSI", "PacketLoss")
        builder.record_occurrence("RSSI", "PacketLoss")

        proposals = builder.discover_new_edges(min_occurrences=3)
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0].cause, "RSSI")
        self.assertEqual(proposals[0].effect, "PacketLoss")

        applied = builder.validate_and_apply_proposal("RSSI", "PacketLoss")
        self.assertTrue(applied)

    def test_simulation_cache(self):
        cache = SimulationCache(ttl_seconds=60)
        res = CounterfactualResult(
            target_variable="PacketLoss",
            intervention_value=0.0,
            real_world_state={"PacketLoss": 0.85},
            counterfactual_state={"PacketLoss": 0.0},
            primary_symptom_resolved=True,
            is_root_cause_candidate=True,
            impact_score=0.95
        )

        cache.put("PacketLoss", {"PacketLoss": 0.85}, res)
        cached_res = cache.get("PacketLoss", {"PacketLoss": 0.85})

        self.assertIsNotNone(cached_res)
        self.assertTrue(cached_res.primary_symptom_resolved)

    def test_intervention_planner(self):
        planner = InterventionPlanner()
        steps = planner.get_actionable_steps("PacketLoss")
        self.assertGreaterEqual(len(steps), 1)
        self.assertEqual(steps[0].action_id, "ACT-NET-01")
        self.assertIn("ip link set", steps[0].command_template)

    def test_causal_memory(self):
        db_file = "/tmp/test_causal_memory.db"
        if os.path.exists(db_file):
            os.remove(db_file)

        mem = CausalMemory(db_path=db_file)
        record = CausalMemoryRecord(
            incident_id="INC-9901",
            device_id="POS-01",
            timestamp="2026-08-04T14:00:00Z",
            root_cause_variable="PacketLoss",
            confidence_score=96.0,
            evidence_summary={"ping": "failed"}
        )

        mem.store_memory(record)
        stored = mem.get_memory("INC-9901")
        self.assertIsNotNone(stored)
        self.assertEqual(stored.root_cause_variable, "PacketLoss")

        mem.record_feedback("INC-9901", "CONFIRMED", True)
        updated = mem.get_memory("INC-9901")
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated.operator_feedback, "CONFIRMED")
        self.assertTrue(updated.remediation_success)

        if os.path.exists(db_file):
            os.remove(db_file)


if __name__ == "__main__":
    unittest.main()
