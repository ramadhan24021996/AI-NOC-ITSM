import unittest
import os
import sys
import uuid
import time
import json

repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
server_path = os.path.join(repo_root, "SERVER")
python_ai_core_path = os.path.join(server_path, "python_ai_core")

if server_path not in sys.path:
    sys.path.insert(0, server_path)
if python_ai_core_path not in sys.path:
    sys.path.insert(0, python_ai_core_path)

from memory.unified_memory_manager import get_unified_memory_manager
from engines.policy_engine import PolicyEngine
from engines.rag_engine import RAGEngine


class TestEnterpriseMemorySystemIntegration(unittest.TestCase):

    def setUp(self):
        self.memory = get_unified_memory_manager()
        self.policy_engine = PolicyEngine()
        self.rag_engine = RAGEngine()

    def test_end_to_end_closed_loop_learning_flow(self):
        """
        Integration Flow:
        1. Incident occurring on device 'srv-accounting-01'
        2. Short-Term Memory tracks active incident & troubleshooting steps
        3. Recovery & Verification executed successfully
        4. Closed-Loop Experience Memory triggers learning pipeline
        5. Knowledge Memory stores pgvector embedding + BM25 tsvector
        6. RAG Engine searches and retrieves newly learned lesson
        """
        session_id = f"integ_sess_{uuid.uuid4().hex[:6]}"
        incident_id = 8842

        # Step 1 & 2: Short-Term Memory Context
        self.memory.short_term.set_session_context(
            session_id=session_id,
            active_device="srv-accounting-01",
            incident_id=incident_id,
            conversation_state={"stage": "ANALYZING"},
            troubleshooting_steps=[{"action": "CHECK_POSTGRES_LOCKS"}]
        )

        ctx = self.memory.short_term.get_session_context(session_id)
        self.assertEqual(ctx["active_device"], "srv-accounting-01")

        # Step 3 & 4: Trigger Closed-Loop Experience Learning
        exp_res = self.memory.learn_from_completed_incident(
            incident_id=incident_id,
            device_name="srv-accounting-01",
            rca_id="RCA-8842-B",
            root_cause="Database Backup Lock Contention pada PostgreSQL",
            recovery_action="Terminate backup connection and restart pg_worker",
            verification_status="SUCCESS"
        )

        self.assertEqual(exp_res["status"], "LEARNING_COMPLETED")
        k_uuid = exp_res["knowledge_uuid"]
        self.assertIsNotNone(k_uuid)

        # Step 5 & 6: Query RAG Engine for newly ingested knowledge
        search_res = self.memory.search_knowledge("Database Backup Lock Contention PostgreSQL", limit=3)
        self.assertTrue(len(search_res) > 0)
        found_titles = [r.get("title", "") for r in search_res]
        self.assertTrue(any("srv-accounting-01" in t or "Lesson Learned" in t for t in found_titles))

        # Long-Term Record verification
        lt_records = self.memory.long_term.get_records_for_entity("srv-accounting-01")
        self.assertTrue(isinstance(lt_records, list))

        # Step 7: Clear short term session after completion
        self.memory.short_term.clear_session(session_id)
        self.assertIsNone(self.memory.short_term.get_session_context(session_id))

    def test_teaching_command_and_policy_integration(self):
        """
        Integration Flow:
        1. Operator issues teaching command: 'Jarvis, simpan pengetahuan berikut'
        2. Teaching Command Handler validates, generates 768-dim vector, inserts pgvector & audit trail
        3. Policy Memory evaluates risk & governance rules for execution
        """
        unique_id = uuid.uuid4().hex[:6]
        raw_cmd = f"""
        Jarvis, simpan pengetahuan berikut
        Judul: Optimasi Sysctl TCP Window Scale {unique_id}
        Gejala: High Socket Buffer Bottleneck
        Penyebab: Parameter net.ipv4.tcp_window_scaling belum diaktifkan
        Solusi: sysctl -w net.ipv4.tcp_window_scaling=1
        Kategori: LINUX
        Tags: sysctl, tcp, tuning
        Confidence: 0.99
        Source: CHIEF_INFRASTRUCTURE_ENGINEER
        Severity: MEDIUM
        """

        teach_res = self.memory.process_teaching_command(raw_cmd, operator_name="PRINCIPAL_ARCHITECT")
        self.assertIn(teach_res["status"], ["SUCCESS", "SUCCESS_VALIDATED"])
        self.assertIn("uuid", teach_res)

        # Policy evaluation check for sysctl execution
        pol_res = self.memory.evaluate_policy("sysctl -w net.ipv4.tcp_window_scaling=1", risk_level="MEDIUM")
        self.assertIn("final_effect", pol_res)


if __name__ == '__main__':
    unittest.main()
