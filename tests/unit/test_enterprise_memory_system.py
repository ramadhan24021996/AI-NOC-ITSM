import unittest
import os
import sys
import time
import uuid

# Ensure SERVER package is importable
repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
server_path = os.path.join(repo_root, "SERVER")
python_ai_core_path = os.path.join(server_path, "python_ai_core")

if server_path not in sys.path:
    sys.path.insert(0, server_path)
if python_ai_core_path not in sys.path:
    sys.path.insert(0, python_ai_core_path)

from memory.short_term_memory import ShortTermMemoryManager
from memory.long_term_memory import LongTermMemoryManager
from memory.knowledge_memory import KnowledgeMemoryManager
from memory.experience_memory import ExperienceMemoryManager
from memory.policy_memory import PolicyMemoryManager
from memory.command_handler import TeachingCommandHandler
from memory.unified_memory_manager import UnifiedMemoryManager, get_unified_memory_manager


class TestJarvisEnterpriseMemorySystem(unittest.TestCase):

    def setUp(self):
        self.session_id = f"test_session_{uuid.uuid4().hex[:8]}"

    def test_01_short_term_memory(self):
        stm = ShortTermMemoryManager(default_ttl=5)
        ok = stm.set_session_context(
            session_id=self.session_id,
            user_id="operator_01",
            active_device="srv-accounting-01",
            incident_id=101,
            conversation_state={"intent": "DIAGNOSE_CPU"},
            troubleshooting_steps=[{"step": 1, "action": "CHECK_TOP"}]
        )
        self.assertTrue(ok)

        ctx = stm.get_session_context(self.session_id)
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx["active_device"], "srv-accounting-01")
        self.assertEqual(ctx["incident_id"], 101)

        # Test adding troubleshooting step
        stm.add_troubleshooting_step(self.session_id, {"step": 2, "action": "RESTART_WORKER"})
        ctx2 = stm.get_session_context(self.session_id)
        self.assertEqual(len(ctx2["troubleshooting_steps"]), 2)

        # Test clear session
        stm.clear_session(self.session_id)
        self.assertIsNone(stm.get_session_context(self.session_id))

    def test_02_long_term_memory(self):
        ltm = LongTermMemoryManager()
        rec = ltm.record_event(
            record_type="INCIDENT_HISTORY",
            entity_id="srv-accounting-01",
            data={"cpu_load": 98.5, "cause": "backup_lock"},
            confidence=0.96,
            author="TEST_SUITE"
        )
        self.assertIn("uuid", rec)
        self.assertEqual(rec["record_type"], "INCIDENT_HISTORY")
        self.assertEqual(rec["confidence"], 0.96)
        self.assertEqual(rec["author"], "TEST_SUITE")

        records = ltm.get_records_by_type("INCIDENT_HISTORY", limit=5)
        self.assertTrue(len(records) > 0)

    def test_03_knowledge_memory_and_embedding(self):
        km = KnowledgeMemoryManager()
        # Embedding vector check
        vec = km.generate_embedding("Solusi Latensi BGP Route Flapping pada Router Core")
        self.assertEqual(len(vec), 768)

        # Freshness score check
        freshness = km.calculate_freshness_score(time.time() - 3600)
        self.assertTrue(0.0 < freshness <= 1.0)

        # Insert knowledge
        title = f"Test SOP BGP Dampening {uuid.uuid4().hex[:6]}"
        k_rec = km.insert_knowledge(
            title=title,
            category="MIKROTIK",
            description="Langkah penanganan route flapping",
            symptoms="Packet loss tinggi",
            root_cause="Unstable BGP Peer",
            solution="Apply bgp dampening-rule",
            tags=["bgp", "mikrotik", "routing"],
            severity="HIGH"
        )
        self.assertIn("uuid", k_rec)

        # Hybrid search
        results = km.hybrid_search("bgp dampening routing", category_filter="MIKROTIK", limit=3)
        self.assertTrue(isinstance(results, list))

    def test_04_experience_memory_closed_loop(self):
        em = ExperienceMemoryManager()
        incident_id = 9901
        res = em.process_incident_learning(
            incident_id=incident_id,
            device_name="PC-MKT-NUC",
            rca_id="RCA-9901-A",
            root_cause="Disk I/O lock saturation",
            recovery_action="Clear log cache and restart agent",
            verification_status="SUCCESS"
        )
        self.assertEqual(res["status"], "LEARNING_COMPLETED")
        self.assertIn("experience_uuid", res)
        self.assertIn("knowledge_uuid", res)

    def test_05_policy_memory_evaluation(self):
        pm = PolicyMemoryManager()
        policies = pm.get_all_policies()
        self.assertTrue(len(policies) >= 4)

        # Test router reboot restriction
        res1 = pm.evaluate_command_against_policies("reboot router core-01", risk_level="HIGH")
        self.assertEqual(res1["final_effect"], "REQUIRE_APPROVAL")
        self.assertTrue(res1["requires_approval"])
        self.assertTrue(res1["requires_hitl"])

        # Test production shutdown restriction
        res2 = pm.evaluate_command_against_policies("shutdown service production-db", risk_level="CRITICAL")
        self.assertEqual(res2["final_effect"], "REQUIRE_APPROVAL")
        self.assertTrue(res2["requires_approval"])

    def test_06_teaching_command_handler(self):
        handler = TeachingCommandHandler()
        unique_id = uuid.uuid4().hex[:6]
        raw_cmd = f"""
        Jarvis, simpan pengetahuan berikut
        Judul: Restorasi Koneksi OSPF Area 0 {unique_id}
        Gejala: OSPF Neighbor State Down
        Penyebab: Mismatch MTU pada Interface Ether1
        Solusi: Ubah MTU menjadi 1500 pada kedua interface router
        Kategori: NETWORK
        Tags: ospf, mtu, routing
        Confidence: 0.98
        Source: SENIOR_NETWORK_ENGINEER
        Severity: MEDIUM
        """

        parsed = handler.parse_teaching_command(raw_cmd)
        self.assertTrue(parsed["title"].startswith("Restorasi Koneksi OSPF Area 0"))
        self.assertEqual(parsed["symptoms"], "OSPF Neighbor State Down")
        self.assertEqual(parsed["confidence"], 0.98)

        res = handler.process_teaching_command(raw_cmd, operator_name="ADMIN_TEST")
        self.assertIn(res["status"], ["SUCCESS", "SUCCESS_VALIDATED", "PENDING_HITL_APPROVAL"])
        self.assertIn("uuid", res)
        self.assertIn("completeness_score", res)

    def test_07_unified_memory_manager_facade(self):
        mgr = get_unified_memory_manager()
        self.assertIsNotNone(mgr.short_term)
        self.assertIsNotNone(mgr.long_term)
        self.assertIsNotNone(mgr.knowledge)
        self.assertIsNotNone(mgr.experience)
        self.assertIsNotNone(mgr.policy)
        self.assertIsNotNone(mgr.tools)
        self.assertIsNotNone(mgr.teaching)

        # Test search via facade
        results = mgr.search_knowledge("OSPF MTU", limit=2)
        self.assertTrue(isinstance(results, list))

    def test_08_tools_memory_registry_and_execution_history(self):
        mgr = get_unified_memory_manager()
        tm = mgr.tools

        # 1. Test listing tools
        tools = tm.list_tools()
        self.assertTrue(len(tools) >= 6)
        tool_ids = [t["tool_id"] for t in tools]
        self.assertIn("restart_service", tool_ids)
        self.assertIn("flush_routing_cache", tool_ids)

        # 2. Test registering a custom tool
        t_rec = tm.register_tool(
            tool_id="test_ping_sweep",
            tool_name="Diagnostic ICMP Ping Sweep",
            description="Sweeps subnet for responsive hosts",
            category="NETWORK",
            risk_level="LOW",
            requires_approval=False,
            requires_hitl=False,
            parameter_schema={"subnet": "string"}
        )
        self.assertEqual(t_rec["tool_id"], "test_ping_sweep")

        # 3. Test logging execution history
        exec_rec = tm.log_tool_execution(
            tool_id="test_ping_sweep",
            incident_id=7701,
            device_name="PC-MKT-NUC",
            operator="TEST_SUITE",
            parameters={"subnet": "10.20.0.0/24"},
            execution_duration_ms=145,
            status="SUCCESS",
            output_summary="Ping sweep completed: 18 hosts active"
        )
        self.assertIn("execution_id", exec_rec)
        self.assertEqual(exec_rec["status"], "SUCCESS")

        # 4. Test retrieving execution history
        history = tm.get_execution_history(tool_id="test_ping_sweep", limit=5)
        self.assertTrue(len(history) > 0)
        self.assertEqual(history[0]["device_name"], "PC-MKT-NUC")

        # 5. Test tool analytics
        analytics = tm.get_tool_analytics(tool_id="test_ping_sweep")
        self.assertTrue(analytics["total_executions"] >= 1)
        self.assertEqual(float(analytics["success_rate_percent"]), 100.0)

    def test_09_capability_command_gateway(self):
        mgr = get_unified_memory_manager()
        gateway = mgr.gateway
        self.assertIsNotNone(gateway)

        # 1. Total tools in whitelist should be >= 23
        all_tools = mgr.tools.list_tools()
        self.assertTrue(len(all_tools) >= 23)

        # 2. Test DENIED for non-whitelisted shell command
        res1 = gateway.execute_tool_capability(tool_id="rm_rf_root", parameters={"path": "/"})
        self.assertEqual(res1["status"], "DENIED_NOT_IN_WHITELIST")

        # 3. Test ALLOW & SUCCESS for Whitelisted Low-Risk Diagnostic Tool (ping)
        res2 = gateway.execute_tool_capability(
            tool_id="ping",
            parameters={"target": "8.8.8.8", "count": 4},
            operator="UNIT_TEST"
        )
        self.assertEqual(res2["status"], "SUCCESS")

        # 4. Test ALLOW & SUCCESS for Whitelisted Identity Tool (whoami)
        res3 = gateway.execute_tool_capability(tool_id="whoami", operator="UNIT_TEST")
        self.assertEqual(res3["status"], "SUCCESS")

        # 5. Test HITL ENFORCEMENT for Critical-Risk Command (shutdown_prod_service)
        res4 = gateway.execute_tool_capability(
            tool_id="shutdown_prod_service",
            parameters={"service_name": "billing-api"},
            operator="UNIT_TEST"
        )
        self.assertEqual(res4["status"], "REQUIRE_HITL_APPROVAL")
        self.assertTrue(res4["requires_hitl"])

    def test_10_knowledge_validation_and_policy_conflict_detection(self):
        mgr = get_unified_memory_manager()
        val_engine = mgr.validation_engine
        self.assertIsNotNone(val_engine)

        # Test policy conflict detection: "Reboot router untuk memperbaiki OSPF"
        val_res = val_engine.validate_new_knowledge(
            title="Reboot Router Solusi OSPF",
            solution="Reboot router core untuk memperbaiki OSPF flapping",
            category="NETWORK",
            symptoms="OSPF Neighbor State Down",
            root_cause="OSPF Flapping",
            severity="HIGH"
        )

        self.assertFalse(val_res["is_valid"])
        self.assertIn(val_res["validation_status"], ["PENDING_HITL_APPROVAL", "REJECTED_BY_POLICY"])
        self.assertTrue(val_res["requires_hitl"])
        self.assertIn("NO_UNAPPROVED_ROUTER_REBOOT", [p["policy_code"] for p in val_res.get("triggered_policies", [])])

    def test_11_memory_governance_and_deduplication(self):
        mgr = get_unified_memory_manager()
        gov = mgr.governance
        self.assertIsNotNone(gov)

        title = f"Governance Test SOP {uuid.uuid4().hex[:6]}"
        # 1. First ingestion -> Validated and activated
        res1 = gov.govern_new_knowledge_ingestion(
            title=title,
            solution="Apply route dampening rule",
            category="NETWORK",
            symptoms="BGP Flapping",
            root_cause="Unstable BGP Peer",
            tags=["bgp", "governance"],
            severity="MEDIUM"
        )
        self.assertEqual(res1["status"], "SUCCESS_VALIDATED")
        self.assertTrue(res1["is_active"])

        # 2. Duplicate ingestion attempt -> Rejected by deduplication gate
        res2 = gov.govern_new_knowledge_ingestion(
            title=title,
            solution="Apply route dampening rule",
            category="NETWORK",
            symptoms="BGP Flapping",
            root_cause="Unstable BGP Peer"
        )
        self.assertEqual(res2["status"], "REJECTED_DUPLICATE")
        self.assertFalse(res2["is_active"])

    def test_12_knowledge_lifecycle_versioning_and_confidence_calibration(self):
        mgr = get_unified_memory_manager()
        lc = mgr.lifecycle
        self.assertIsNotNone(lc)

        # 1. Ingest initial v1 knowledge
        k1 = mgr.knowledge.insert_knowledge(
            title="Optimasi MTU Interface Ether1",
            category="NETWORK",
            solution="Ubah MTU menjadi 1492 pada Ether1",
            symptoms="Fragmented packets",
            confidence=0.80
        )
        v1_uuid = k1["uuid"]

        # 2. Publish Version 2 (MTU 1492 -> MTU 1500)
        v2_res = lc.publish_new_version(
            old_knowledge_uuid=v1_uuid,
            new_title="Optimasi MTU Interface Ether1 (v2)",
            new_solution="Ubah MTU menjadi 1500 pada Ether1",
            author="SENIOR_ARCHITECT",
            version_notes="Upgrade MTU 1492 ke 1500 untuk jumbo frames"
        )
        self.assertEqual(v2_res["status"], "VERSION_UPDATED")
        self.assertEqual(v2_res["version"], 2)
        v2_uuid = v2_res["new_uuid"]

        # 3. Dynamic Confidence Calibration on production execution
        # Execution Success -> Confidence +0.05
        cal_res1 = lc.update_confidence_on_outcome(v2_uuid, is_success=True)
        self.assertEqual(cal_res1["confidence"], 1.0)

        # Execution Failure -> Confidence -0.15
        cal_res2 = lc.update_confidence_on_outcome(v2_uuid, is_success=False)
        self.assertEqual(cal_res2["confidence"], 0.85)

        # 4. SOP Deprecation
        dep_res = lc.deprecate_knowledge(v2_uuid, reason="Migrasi ke interface Ether2")
        self.assertEqual(dep_res["validation_status"], "DEPRECATED")
        self.assertFalse(dep_res["is_active"])


if __name__ == '__main__':
    unittest.main()
