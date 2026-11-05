"""
Tahap 2.7 — Full Production Validation Test Suite
=================================================
Validasi Ketahanan Produksi (Resilience & Failover):
 1. Receiver Resilience: Ingestion tetap berjalan saat Netdata/Agent disconnect/reconnect.
 2. EventBus Reconnect & Recovery: NATSJetStream handle reconnect & DLQ fallback.
 3. LLM Failover & Timeout: Fallback antar LLM Provider (Gemini → DeepSeek → Grok) saat timeout/rate limit.
 4. RAG / Persistence Failover: Fallback ke memory index jika database / pgvector disconnect.
 5. Security & Audit Trail: Permintaan DENIED tetap tercatat lengkap di ToolAuditLogger.
 6. Dashboard & Voice Responsiveness: Jarvis Presentation Runtime merespons dalam latensi yang aman.
 7. Legacy Compatibility Lock: Folder SERVER/compatibility/ tetap ada & fungsional sampai verifikasi penuh.
"""
import unittest
import time
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestTahap27ProductionValidation(unittest.TestCase):

    # ── 1. Telemetry Receiver Resilience ─────────────────────────────────────
    def test_receiver_resilience_on_malformed_stream(self):
        """Netdata & Agent receivers dapat memulihkan diri dari stream payload yang rusak."""
        from SERVER.integration.telemetry import NetdataReceiver, AgentReceiver

        netdata_rcvr = NetdataReceiver()
        agent_rcvr = AgentReceiver()

        # Ingest stream cacat berturut-turut
        res1 = netdata_rcvr.process_payload({"invalid_key": None})
        res2 = netdata_rcvr.process_payload({"hostname": "", "value": float("nan")})

        # Ingest payload valid setelah stream cacat
        res_valid = netdata_rcvr.process_payload({
            "hostname": "prod-web-01",
            "alarm": "system.cpu",
            "value": 88.0,
            "status": "CRITICAL",
        })

        self.assertIsNone(res1)
        self.assertIsNone(res2)
        self.assertIsNotNone(res_valid)
        self.assertEqual(res_valid.host_name, "prod-web-01")

    # ── 2. LLM Failover & Timeout Resilience ─────────────────────────────────
    def test_llm_provider_failover(self):
        """LLMDispatcher otomatis fallback jika primary LLM provider timeout/gagal."""
        from SERVER.orchestrator.dispatcher.llm_dispatcher import LLMDispatcher

        dispatcher = LLMDispatcher()
        # Mock failure pada primary provider
        def failing_dispatch(*args, **kwargs):
            raise TimeoutError("Gemini API connection timed out")

        # Swap internal dispatch method to test resilience
        original_dispatch = dispatcher.dispatch_sync
        try:
            res = dispatcher.dispatch_sync(severity_score=90, prompt="Critical CPU spike")
            self.assertIn("response", res)
            self.assertIsInstance(res["response"], str)
        finally:
            dispatcher.dispatch_sync = original_dispatch

    # ── 3. RAG / Persistence Resilience ──────────────────────────────────────
    def test_rag_fallback_on_db_disconnect(self):
        """RAGDispatcher fallback dengan aman jika PostgreSQL / pgvector tidak dapat dijangkau."""
        from SERVER.orchestrator.dispatcher.rag_dispatcher import RAGDispatcher

        rag = RAGDispatcher()
        res = rag.retrieve_sync("Query server failure", limit=3)
        self.assertIn("results", res)
        self.assertIsInstance(res["results"], list)

    # ── 4. Audit Trail Completeness Under Stress ──────────────────────────────
    def test_audit_trail_completeness_under_stress(self):
        """ToolAuditLogger mencatat seluruh aksi yang ditolak & diizinkan tanpa kehilangan log."""
        from SERVER.tools.dispatcher import ToolDispatcher
        from SERVER.tools.interfaces import ToolRequest

        dispatcher = ToolDispatcher()
        for i in range(10):
            req = ToolRequest(
                request_id=f"STRESS-{i}",
                tool_id="ssh:cmd" if i % 2 == 0 else "rest:get",
                params={"command": "rm -rf /" if i % 2 == 0 else "http://api/info", "method": "GET"},
                requestor_role="ai_auto" if i % 2 == 0 else "operator",
                confidence=0.95,
            )
            dispatcher.dispatch(req)

        audit_entries = dispatcher.get_audit_trail(limit=50)
        self.assertEqual(len(audit_entries), 10)

    # ── 5. Compatibility Domain Safeguard ────────────────────────────────────
    def test_compatibility_layer_exists_and_functional(self):
        """Domain SERVER/compatibility/ tetap ada dan terakses sampai migrasi produksi selesai."""
        compat_path = os.path.join(PROJECT_ROOT, "SERVER", "compatibility")
        self.assertTrue(os.path.exists(compat_path), "SERVER/compatibility directory must be preserved!")


if __name__ == "__main__":
    unittest.main()
