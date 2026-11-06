"""
tests/unit/test_critical_bottleneck_fixes.py
=============================================
Regression and verification test suite for the 4 Critical Engineering Fixes:
1. Database Connection Pooling in memory modules via ThreadedConnectionPool.
2. Deterministic Sub-Second Decision Package Fast-Path for L1/L2 network outages.
3. CPU-aware TTS concurrency limiter (BoundedSemaphore).
4. Autonomous pgvector & telemetry VACUUM (ANALYZE) execution.
"""
import unittest
import time
import os
import sys
import threading
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PYTHON_AI_CORE = os.path.join(PROJECT_ROOT, "SERVER", "python_ai_core")
if PYTHON_AI_CORE not in sys.path:
    sys.path.append(PYTHON_AI_CORE)
if PROJECT_ROOT in sys.path:
    sys.path.remove(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)

from shared.db_pool import get_pg_pool, get_db_connection, _PooledConnectionProxy
from services.decision_orchestrator import DecisionOrchestrator
from schemas.decision_schema import DecisionPackageSchema
from SERVER.jarvis.voice.tts_service import TTSService, _CPU_SYNTHESIS_SEMAPHORE


class TestCriticalBottleneckFixes(unittest.TestCase):
    def test_01_db_pool_connection_proxy_return(self):
        """Fix 1: get_db_connection returns a pooled proxy, conn.close() returns it to pool without socket drop."""
        mock_raw_conn = MagicMock()
        mock_raw_conn.closed = False
        mock_pool = MagicMock()
        mock_pool.getconn.return_value = mock_raw_conn

        with patch("shared.db_pool.get_pg_pool", return_value=mock_pool):
            conn = get_db_connection()
            self.assertIsInstance(conn, _PooledConnectionProxy)
            # Use cursor
            cursor = conn.cursor()
            self.assertIsNotNone(cursor)

            # Close should put connection back to pool
            conn.close()
            mock_pool.putconn.assert_called_once_with(mock_raw_conn)

    def test_02_memory_modules_use_db_pool(self):
        """Fix 1: LongTermMemoryManager and KnowledgeMemoryManager acquire connection from pool."""
        from memory.long_term_memory import LongTermMemoryManager
        from memory.knowledge_memory import KnowledgeMemoryManager

        mock_proxy = MagicMock()
        with patch("shared.db_pool.get_db_connection", return_value=mock_proxy) as mock_get_conn:
            ltm = LongTermMemoryManager()
            conn1 = ltm._get_connection()
            self.assertEqual(conn1, mock_proxy)
            mock_get_conn.assert_called_once()

        with patch("shared.db_pool.get_db_connection", return_value=mock_proxy) as mock_get_conn2:
            km = KnowledgeMemoryManager()
            conn2 = km._get_connection()
            self.assertEqual(conn2, mock_proxy)
            mock_get_conn2.assert_called_once()

    def test_03_l1_l2_deterministic_fast_path_bypasses_llm(self):
        """Fix 2: L1/L2 network outages bypass LLM cloud roundtrip and return sub-second DecisionPackageSchema."""
        orch = DecisionOrchestrator()

        mock_router = MagicMock()
        # Mock router should NEVER be called for L1/L2
        mock_router.execute_with_retry = MagicMock()

        incident_details = {
            "incident_id": "INC-NET-991",
            "hostname": "core-sw-01",
            "site": "DC-JKT",
            "severity": "CRITICAL",
            "layer": "L1_PHYSICAL",
            "symptoms": ["LINK_DOWN on ge-0/0/1", "Transceiver signal lost"]
        }

        import asyncio
        t0 = time.time()
        pkg = asyncio.run(orch.generate_decision_package(
            router=mock_router,
            severity_score=9,
            incident_details=incident_details,
            historical_context=[],
            evidence_pkg={},
            causal_dag={},
            critic_res={"recommended_action": "RESET_INTERFACE_AND_ALERT_FIELD_TECH"},
            consensus_verdict={"root_cause": "Fiber transceiver hardware fault"}
        ))
        elapsed_ms = (time.time() - t0) * 1000

        # Verification
        mock_router.execute_with_retry.assert_not_called()
        self.assertIsInstance(pkg, DecisionPackageSchema)
        self.assertEqual(pkg.incident_id, "INC-NET-991")
        self.assertEqual(pkg.osi_layer, "L1_PHYSICAL")
        self.assertEqual(pkg.policy_result, "ALLOW_FASTPATH")
        self.assertLess(elapsed_ms, 50.0, "Fast-path must execute in < 50ms")

    def test_04_llm_failure_falls_back_to_deterministic_decision_package(self):
        """Fix 2: If LLM raises timeout or schema error, decision orchestrator falls back to deterministic package."""
        orch = DecisionOrchestrator()

        mock_router = MagicMock()
        # Simulate LLM timeout error
        mock_router.execute_with_retry = MagicMock(side_effect=TimeoutError("Gemini/DeepSeek 10000ms timeout"))

        incident_details = {
            "incident_id": "INC-APP-772",
            "hostname": "api-gateway-02",
            "site": "DC-JKT",
            "severity": "HIGH",
            "layer": "L7_APPLICATION",
            "symptoms": ["High 504 Gateway Timeout"]
        }

        import asyncio
        pkg = asyncio.run(orch.generate_decision_package(
            router=mock_router,
            severity_score=7,
            incident_details=incident_details,
            historical_context=[],
            evidence_pkg={},
            causal_dag={},
            critic_res={"recommended_action": "RECYCLE_BACKEND_WORKERS"},
            consensus_verdict={"root_cause": "Upstream socket pool exhausted"}
        ))

        self.assertIsInstance(pkg, DecisionPackageSchema)
        self.assertEqual(pkg.incident_id, "INC-APP-772")
        self.assertIn("Fast-path deterministic decision", pkg.summary)

    def test_05_tts_semaphore_caps_concurrency(self):
        """Fix 3: TTSService uses BoundedSemaphore to prevent CPU neural synthesis thread storming."""
        self.assertEqual(_CPU_SYNTHESIS_SEMAPHORE._initial_value, 2)
        mock_provider = MagicMock()
        mock_provider.provider_name = "MockProvider"
        mock_provider.synthesize_text.return_value = MagicMock(audio_bytes=b"123" * 20)

        tts = TTSService(provider=mock_provider)
        res = tts.synthesize("Status sistem normal", skip_normalization=True)
        self.assertIsNotNone(res)
        mock_provider.synthesize_text.assert_called_once()

    def test_06_vacuum_analyze_execution_in_background_loops(self):
        """Fix 4: autonomous_data_retention executes autocommit VACUUM (ANALYZE) on vector & telemetry tables."""
        import supervisor.handlers.background_loops as bg_loops

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur

        executed_sqls = []
        def fake_execute(query, *args):
            executed_sqls.append(query)

        mock_cur.execute = fake_execute

        with patch("psycopg2.connect", return_value=mock_conn):
            with patch("asyncio.sleep", side_effect=InterruptedError("Loop breaker")):
                with patch("supervisor.handlers.background_loops._cleanup_sop_sprawl"):
                    try:
                        import asyncio
                        asyncio.run(bg_loops.autonomous_data_retention())
                    except InterruptedError:
                        pass

        # Verify autocommit was set for vacuum
        self.assertTrue(mock_conn.autocommit)
        # Verify VACUUM (ANALYZE) was called for knowledge_vectors
        self.assertTrue(any("VACUUM (ANALYZE) knowledge_vectors" in q for q in executed_sqls))
        self.assertTrue(any("VACUUM (ANALYZE) fleet_incidents" in q for q in executed_sqls))


if __name__ == "__main__":
    unittest.main()
