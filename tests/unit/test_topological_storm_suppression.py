"""
tests/unit/test_topological_storm_suppression.py
================================================
Verifies Cross-Layer Flapping & Topological Storm Suppression (Upstream-Downstream Correlation):
1. Direct & 2-Hop Upstream Parent Outage Suppression (`UPSTREAM_PARENT_OUTAGE`):
   When an upstream switch/gateway (`SW-CABANG-01` or `GW-CABANG-01`) has an active incident,
   20 downstream PCs reporting anomalies are bound as child symptoms (`[CHILD_SYMPTOM:PC-XX]`)
   to the parent incident and suppressed at the ingest gate (`should_suppress_pipeline = True`).
2. Implicit Common-Parent Sibling Storm Deduction (`COMMON_PARENT_SIBLING_STORM`):
   When an unmanaged switch dies (no ticket of its own) and `PC-01` opens an incident #501,
   subsequent alerts from `PC-02`..`PC-20` sharing `depends_on = 'SW-CABANG-01'` are automatically
   correlated into Root Incident #501 (`[STORM_CHILD:PC-XX@via:SW-CABANG-01]`) and suppressed.
3. Same-Host Cross-Layer Flapping Suppression (`SAME_HOST_FLAPPING_COOLDOWN`):
   Repeated flapping telemetry on the same host within the active episode window is appended
   to the existing incident's evidence and suppressed at the ingest gate.
4. Ingest Gate Short-Circuit in `incident_triage.message_handler`:
   Verifies `message_handler` acknowledges the NATS message and returns early without creating
   duplicate tickets or invoking LLM/RAG when `should_suppress_pipeline` is True.
"""

import asyncio
import json
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PYTHON_AI_CORE = os.path.join(PROJECT_ROOT, "SERVER", "python_ai_core")
if PYTHON_AI_CORE in sys.path:
    sys.path.remove(PYTHON_AI_CORE)
if PROJECT_ROOT in sys.path:
    sys.path.remove(PROJECT_ROOT)
sys.path.insert(0, PYTHON_AI_CORE)
sys.path.insert(0, PROJECT_ROOT)

from SERVER.python_ai_core.cognition.diagnostic_prober import EpisodeDeduplicator


class TestTopologicalStormSuppression(unittest.TestCase):
    def test_01_upstream_parent_outage_suppresses_20_downstream_pcs(self):
        """Scenario 1: Switch SW-CABANG-01 has active Incident #700 -> 20 downstream PCs are bound & suppressed."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        dedup = EpisodeDeduplicator(db_conn=mock_conn)

        for i in range(1, 21):
            pc_name = f"PC-CABANG-{i:02d}"
            # Query 1 (upstream check) returns active parent incident #700 on SW-CABANG-01
            mock_cur.fetchone.side_effect = [
                ("SW-CABANG-01", "NETWORK_SWITCH", 700, "OPEN", "Switch port trunk down"),
            ]
            res = dedup.find_or_correlate_active_episode(
                device_name=pc_name,
                symptoms="Gateway unreachable / Packet loss 100%",
            )
            self.assertEqual(res["existing_incident_id"], 700)
            self.assertTrue(res["is_upstream_storm_suppressed"])
            self.assertTrue(res["should_suppress_pipeline"])
            self.assertEqual(res["suppression_reason"], "UPSTREAM_PARENT_OUTAGE")
            self.assertEqual(res["upstream_root_incident"]["parent_device"], "SW-CABANG-01")

        # Verify UPDATE incidents SET evidence was called to attach child symptoms on Root Incident #700
        self.assertTrue(mock_cur.execute.called)
        self.assertEqual(mock_conn.commit.call_count, 20)

    def test_02_common_parent_sibling_storm_deduction(self):
        """Scenario 2: Unmanaged switch has no ticket, PC-01 opened #801, PC-02..PC-20 correlate via common parent."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        dedup = EpisodeDeduplicator(db_conn=mock_conn)

        # Query 1 (direct upstream incident) -> None
        # Query 2 (sibling sharing common parent SW-UNMANAGED-01) -> returns sibling PC-01's Incident #801
        mock_cur.fetchone.side_effect = [
            None,
            ("SW-UNMANAGED-01", "L2_SWITCH", "PC-CABANG-01", 801, "INGESTED", "NIC link down"),
        ]

        res = dedup.find_or_correlate_active_episode(
            device_name="PC-CABANG-02",
            symptoms="Network unreachable",
        )
        self.assertEqual(res["existing_incident_id"], 801)
        self.assertTrue(res["is_upstream_storm_suppressed"])
        self.assertTrue(res["should_suppress_pipeline"])
        self.assertEqual(res["suppression_reason"], "COMMON_PARENT_SIBLING_STORM")
        self.assertEqual(res["upstream_root_incident"]["parent_device"], "SW-UNMANAGED-01")
        self.assertEqual(res["upstream_root_incident"]["leader_sibling_device"], "PC-CABANG-01")

    def test_03_same_host_flapping_suppression(self):
        """Scenario 3: Same host PC-01 flaps repeatedly within 10-minute episode window."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        dedup = EpisodeDeduplicator(db_conn=mock_conn)

        # Query 1 (upstream) -> None, Query 2 (sibling) -> None, Query 3 (same-host) -> Incident #905
        mock_cur.fetchone.side_effect = [
            None,
            None,
            (905, "IN_PROGRESS", "Initial link flap detected"),
        ]

        res = dedup.find_or_correlate_active_episode(
            device_name="PC-FLAP-01",
            symptoms="Link down flap #2 on eth0",
        )
        self.assertEqual(res["existing_incident_id"], 905)
        self.assertTrue(res["is_duplicate_episode"])
        self.assertTrue(res["should_suppress_pipeline"])
        self.assertEqual(res["suppression_reason"], "SAME_HOST_FLAPPING_COOLDOWN")

    def test_04_ingest_gate_short_circuits_in_incident_triage(self):
        """Scenario 4: incident_triage.message_handler acks NATS message and short-circuits on storm suppression."""
        from SERVER.python_ai_core.supervisor.handlers import incident_triage

        mock_msg = MagicMock()
        mock_msg.data = json.dumps({
            "event_id": "evt-storm-pc05",
            "pc_name": "PC-CABANG-05",
            "site_id": "cabang_bandara",
            "message": {
                "title": "Network Unreachable",
                "symptoms": "Ping to gateway 100% loss",
                "metadata": {"severity": "HIGH"},
            },
        }).encode("utf-8")
        mock_msg.ack = AsyncMock()

        mock_rag = MagicMock()
        mock_rag.conn = MagicMock()

        suppressed_result = {
            "existing_incident_id": 700,
            "is_duplicate_episode": False,
            "is_upstream_storm_suppressed": True,
            "should_suppress_pipeline": True,
            "suppression_reason": "UPSTREAM_PARENT_OUTAGE",
            "upstream_root_incident": {
                "parent_device": "GW-BANDARA-01",
                "dep_type": "GATEWAY",
                "parent_incident_id": 700,
                "parent_state": "OPEN",
                "parent_evidence": "WAN Link Down",
            },
            "suppression_note": "Suppressed child storm on PC-CABANG-05",
        }

        with patch("engines.rag_engine.get_rag_engine", return_value=mock_rag), \
             patch("cognition.diagnostic_prober.EpisodeDeduplicator.find_or_correlate_active_episode", return_value=suppressed_result), \
             patch("cognition.diagnostic_prober.ActiveDiagnosticProber.run_pre_triage_probes", new_callable=AsyncMock) as mock_probe:
            asyncio.run(incident_triage.message_handler(mock_msg))
            # NATS message must be acknowledged
            mock_msg.ack.assert_awaited_once()
            # Pre-triage probe and downstream LLM pipeline must NOT be called because gate short-circuited!
            mock_probe.assert_not_Called() if hasattr(mock_probe, "assert_not_Called") else mock_probe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
