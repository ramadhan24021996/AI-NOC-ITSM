"""
Tahap 2.4 — Tool Execution (Safety-Layered) Test Suite
=======================================================
DoD Criteria:
 1. ToolDispatcher adalah satu-satunya entry point (architecture isolation).
 2. RiskClassifier menetapkan risk level yang benar berdasarkan action & blast radius.
 3. ToolPolicyEngine menolak berdasarkan RBAC, maintenance mode, dan risk level.
 4. ApprovalManager auto-approves confidence >= 92% + LOW risk, PENDING selainnya.
 5. SSHDriver menolak perintah destruktif (forbidden pattern guardrail).
 6. DockerDriver menolak operasi delete/rm tanpa HITL.
 7. MikrotikDriver menolak write ops tanpa dry_run.
 8. SandboxExecutor menghasilkan SANDBOXED/PENDING_APPROVAL tanpa efek nyata.
 9. ToolAuditLogger mencatat SETIAP eksekusi, termasuk yang ditolak.
10. End-to-end: DENIED request melewati seluruh pipeline tanpa crash.
11. End-to-end: AUTO_APPROVED request (confidence 95%, REST, LOW risk) ter-eksekusi.
12. End-to-end: PENDING request (SSH + ai_auto) dikembalikan sebagai PENDING_APPROVAL.
"""
import unittest
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestTahap24ToolExecution(unittest.TestCase):

    # ── Test 1: Import Architecture Isolation ─────────────────────────────────
    def test_tool_dispatcher_is_single_entry_point(self):
        """ToolDispatcher dan semua komponen keamanan dapat diimpor dengan benar."""
        from SERVER.tools.dispatcher import ToolDispatcher
        from SERVER.tools.risk import RiskClassifier
        from SERVER.tools.policy import ToolPolicyEngine
        from SERVER.tools.approval import ApprovalManager
        from SERVER.tools.sandbox import SandboxExecutor
        from SERVER.tools.audit import ToolAuditLogger
        self.assertTrue(callable(ToolDispatcher))
        self.assertTrue(callable(RiskClassifier))
        self.assertTrue(callable(ToolPolicyEngine))
        self.assertTrue(callable(ApprovalManager))
        self.assertTrue(callable(SandboxExecutor))
        self.assertTrue(callable(ToolAuditLogger))

    # ── Test 2: RiskClassifier — keyword & blast radius ───────────────────────
    def test_risk_classifier_destructive_command_critical(self):
        """RiskClassifier memberi risk CRITICAL untuk perintah destruktif."""
        from SERVER.tools.risk import RiskClassifier
        from SERVER.tools.interfaces import ToolRequest, RiskLevel
        clf = RiskClassifier()
        req = ToolRequest(
            request_id="R-001",
            tool_id="ssh:cmd",
            params={"host": "srv-01", "command": "rm -rf /var/data"},
            requestor_role="operator",
            severity="HIGH",
            confidence=0.95,
        )
        result = clf.classify(req, "ssh")
        self.assertIn(result.risk_level, (RiskLevel.HIGH, RiskLevel.CRITICAL))
        self.assertGreater(result.risk_score, 60)

    def test_risk_classifier_fleet_blast_radius_elevates_score(self):
        """RiskClassifier meningkatkan skor jika target adalah fleet/all."""
        from SERVER.tools.risk import RiskClassifier
        from SERVER.tools.interfaces import ToolRequest
        clf = RiskClassifier()
        req = ToolRequest(
            request_id="R-002",
            tool_id="rest:call",
            params={"url": "http://api/", "method": "GET", "target": "all-nodes"},
            requestor_role="operator",
            confidence=0.9,
        )
        result = clf.classify(req, "rest")
        self.assertGreaterEqual(result.risk_score, 30)  # fleet bonus applied
        self.assertEqual(result.blast_radius, "FLEET")

    def test_risk_classifier_low_confidence_penalty(self):
        """RiskClassifier menambahkan penalti skor untuk confidence < 70%."""
        from SERVER.tools.risk import RiskClassifier
        from SERVER.tools.interfaces import ToolRequest
        clf = RiskClassifier()
        req_low = ToolRequest(
            request_id="R-003",
            tool_id="rest:info",
            params={"url": "http://api/status", "method": "GET"},
            requestor_role="operator",
            confidence=0.50,   # rendah
        )
        req_high = ToolRequest(
            request_id="R-004",
            tool_id="rest:info",
            params={"url": "http://api/status", "method": "GET"},
            requestor_role="operator",
            confidence=0.95,   # tinggi
        )
        result_low = clf.classify(req_low, "rest")
        result_high = clf.classify(req_high, "rest")
        self.assertGreater(result_low.risk_score, result_high.risk_score)

    # ── Test 3: PolicyEngine — RBAC, Maintenance, Critical ────────────────────
    def test_policy_engine_rbac_deny_ai_auto_ssh(self):
        """PolicyEngine menolak ai_auto menggunakan SSH (tidak ada di RBAC matrix)."""
        from SERVER.tools.policy import ToolPolicyEngine
        from SERVER.tools.interfaces import ToolRequest, RiskLevel
        engine = ToolPolicyEngine()
        req = ToolRequest(
            request_id="R-005", tool_id="ssh:restart",
            params={}, requestor_role="ai_auto",
        )
        decision = engine.evaluate(req, "ssh", RiskLevel.MEDIUM)
        # ai_auto tidak punya akses ke SSH di RBAC → harus requires_hitl atau not allowed
        self.assertTrue(decision.requires_hitl or not decision.allowed)

    def test_policy_engine_maintenance_mode_blocks_non_admin(self):
        """PolicyEngine memblokir semua non-admin saat maintenance mode aktif."""
        from SERVER.tools.policy import ToolPolicyEngine
        from SERVER.tools.interfaces import ToolRequest, RiskLevel
        engine = ToolPolicyEngine(maintenance_mode=True)
        req = ToolRequest(
            request_id="R-006", tool_id="rest:call",
            params={}, requestor_role="operator",
        )
        decision = engine.evaluate(req, "rest", RiskLevel.LOW)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.policy_rule, "MAINTENANCE_MODE_LOCK")

    def test_policy_engine_maintenance_mode_allows_admin(self):
        """PolicyEngine mengizinkan admin bahkan saat maintenance mode."""
        from SERVER.tools.policy import ToolPolicyEngine
        from SERVER.tools.interfaces import ToolRequest, RiskLevel
        engine = ToolPolicyEngine(maintenance_mode=True)
        req = ToolRequest(
            request_id="R-007", tool_id="rest:call",
            params={}, requestor_role="admin",
        )
        decision = engine.evaluate(req, "rest", RiskLevel.LOW)
        self.assertTrue(decision.allowed)

    def test_policy_engine_critical_always_hitl(self):
        """PolicyEngine selalu meminta HITL untuk risk CRITICAL."""
        from SERVER.tools.policy import ToolPolicyEngine
        from SERVER.tools.interfaces import ToolRequest, RiskLevel
        engine = ToolPolicyEngine()
        req = ToolRequest(
            request_id="R-008", tool_id="ssh:cmd",
            params={}, requestor_role="admin",
        )
        decision = engine.evaluate(req, "ssh", RiskLevel.CRITICAL)
        self.assertTrue(decision.requires_hitl)
        self.assertEqual(decision.policy_rule, "CRITICAL_ALWAYS_HITL")

    # ── Test 4: ApprovalManager ────────────────────────────────────────────────
    def test_approval_manager_auto_approve_high_confidence_low_risk(self):
        """ApprovalManager AUTO_APPROVED untuk confidence>=92% dan risk<=35."""
        from SERVER.tools.approval import ApprovalManager
        from SERVER.tools.interfaces import (
            ToolRequest, RiskAssessment, PolicyDecision, ApprovalStatus, RiskLevel
        )
        mgr = ApprovalManager()
        req = ToolRequest(
            request_id="R-009", tool_id="rest:get",
            params={}, requestor_role="ai_auto",
            confidence=0.95,
        )
        risk = RiskAssessment(risk_level=RiskLevel.LOW, risk_score=20)
        policy = PolicyDecision(allowed=True, reason="Policy pass", requires_hitl=False)
        status = mgr.evaluate(req, risk, policy)
        self.assertEqual(status, ApprovalStatus.AUTO_APPROVED)

    def test_approval_manager_pending_for_low_confidence(self):
        """ApprovalManager mengirim ke PENDING jika confidence rendah."""
        from SERVER.tools.approval import ApprovalManager
        from SERVER.tools.interfaces import (
            ToolRequest, RiskAssessment, PolicyDecision, ApprovalStatus, RiskLevel
        )
        mgr = ApprovalManager()
        req = ToolRequest(
            request_id="R-010", tool_id="ssh:restart",
            params={}, requestor_role="ai_suggested",
            confidence=0.75,
        )
        risk = RiskAssessment(risk_level=RiskLevel.MEDIUM, risk_score=55, requires_hitl=True)
        policy = PolicyDecision(allowed=True, reason="HITL escalation", requires_hitl=True)
        status = mgr.evaluate(req, risk, policy)
        self.assertIn(status, (ApprovalStatus.PENDING, ApprovalStatus.FORCE_HITL))

    def test_approval_manager_rejected_if_policy_denied(self):
        """ApprovalManager langsung REJECTED jika policy tidak mengizinkan."""
        from SERVER.tools.approval import ApprovalManager
        from SERVER.tools.interfaces import (
            ToolRequest, RiskAssessment, PolicyDecision, ApprovalStatus, RiskLevel
        )
        mgr = ApprovalManager()
        req = ToolRequest(request_id="R-011", tool_id="ssh:cmd", params={}, requestor_role="ai_auto")
        risk = RiskAssessment(risk_level=RiskLevel.HIGH, risk_score=80)
        policy = PolicyDecision(allowed=False, reason="RBAC denied")
        status = mgr.evaluate(req, risk, policy)
        self.assertEqual(status, ApprovalStatus.REJECTED)

    # ── Test 5: Driver Guardrails ─────────────────────────────────────────────
    def test_ssh_driver_rejects_destructive_command(self):
        """SSHDriver menolak perintah rm -rf / meskipun driver dipanggil langsung."""
        from SERVER.tools.drivers.ssh_driver import SSHDriver
        from SERVER.tools.interfaces import ToolStatus
        driver = SSHDriver()
        result = driver.execute({"host": "server-01", "command": "rm -rf /"}, dry_run=False)
        self.assertEqual(result.status, ToolStatus.DENIED)

    def test_docker_driver_rejects_rm_without_hitl(self):
        """DockerDriver menolak operasi 'rm' tanpa HITL."""
        from SERVER.tools.drivers.docker_driver import DockerDriver
        from SERVER.tools.interfaces import ToolStatus
        driver = DockerDriver()
        result = driver.execute({"operation": "rm", "container": "app-container"}, dry_run=False)
        self.assertEqual(result.status, ToolStatus.DENIED)

    def test_mikrotik_driver_rejects_write_without_dry_run(self):
        """MikrotikDriver menolak write operations tanpa dry_run."""
        from SERVER.tools.drivers.mikrotik_driver import MikrotikDriver
        from SERVER.tools.interfaces import ToolStatus
        driver = MikrotikDriver()
        result = driver.execute({"host": "router-01", "operation": "add_route"}, dry_run=False)
        self.assertEqual(result.status, ToolStatus.DENIED)

    # ── Test 6: SandboxExecutor ────────────────────────────────────────────────
    def test_sandbox_executor_produces_sandboxed_result(self):
        """SandboxExecutor selalu menghasilkan SANDBOXED tanpa eksekusi nyata."""
        from SERVER.tools.sandbox import SandboxExecutor
        from SERVER.tools.interfaces import ToolRequest, ToolStatus
        executor = SandboxExecutor()
        req = ToolRequest(
            request_id="R-012", tool_id="docker:restart",
            params={"operation": "restart", "container": "nats-server"},
            requestor_role="operator",
        )
        result = executor.execute_dry_run(req, "docker")
        self.assertIn(result.status, (ToolStatus.SANDBOXED, ToolStatus.PENDING_APPROVAL))
        self.assertTrue(result.is_dry_run)

    # ── Test 7: AuditLogger ────────────────────────────────────────────────────
    def test_audit_logger_records_all_executions_including_denied(self):
        """ToolAuditLogger mencatat SEMUA eksekusi, termasuk yang ditolak."""
        from SERVER.tools.audit import ToolAuditLogger
        from SERVER.tools.interfaces import (
            ToolRequest, ToolResult, ToolStatus, ApprovalStatus, RiskLevel
        )
        logger = ToolAuditLogger()
        req = ToolRequest(request_id="R-013", tool_id="ssh:cmd", params={}, requestor_role="ai_auto")
        denied_result = ToolResult(
            request_id="R-013", tool_id="ssh:cmd",
            status=ToolStatus.DENIED, error="RBAC denied",
            executed_by="tool_dispatcher",
        )
        audit_id = logger.log(req, denied_result, ApprovalStatus.REJECTED)
        self.assertTrue(audit_id.startswith("AUD-"))
        self.assertEqual(logger.total_entries, 1)
        denied = logger.get_denied_entries()
        self.assertEqual(len(denied), 1)
        self.assertEqual(denied[0]["execution_status"], "DENIED")

    # ── Test 8: End-to-End — DENIED (ai_auto + ssh + HIGH risk) ──────────────
    def test_e2e_dispatch_denied_ai_auto_ssh_high_risk(self):
        """
        E2E: ai_auto meminta SSH dengan perintah yang di-blok policy RBAC.
        ToolDispatcher harus mengembalikan DENIED/PENDING_APPROVAL tanpa crash.
        """
        from SERVER.tools.dispatcher import ToolDispatcher
        from SERVER.tools.interfaces import ToolRequest, ToolStatus
        dispatcher = ToolDispatcher()
        req = ToolRequest(
            request_id="R-014",
            tool_id="ssh:restart_service",
            params={"host": "server-01", "command": "systemctl restart nginx"},
            requestor_role="ai_auto",
            severity="HIGH",
            confidence=0.85,
            incident_id="INC-9001",
        )
        result = dispatcher.dispatch(req)
        # ai_auto + SSH → policy blocks or sends to sandbox/pending
        self.assertIn(result.status, (
            ToolStatus.DENIED, ToolStatus.PENDING_APPROVAL, ToolStatus.SANDBOXED
        ))
        # Audit trail HARUS tercatat
        trail = dispatcher.get_audit_trail()
        self.assertGreater(len(trail), 0)

    # ── Test 9: End-to-End — AUTO_APPROVED (operator + REST + LOW risk) ───────
    def test_e2e_dispatch_auto_approved_operator_rest_low_risk(self):
        """
        E2E: operator meminta REST GET dengan confidence tinggi.
        ToolDispatcher harus AUTO_APPROVED dan mengeksekusi REST driver.
        """
        from SERVER.tools.dispatcher import ToolDispatcher
        from SERVER.tools.interfaces import ToolRequest, ToolStatus, ApprovalStatus
        dispatcher = ToolDispatcher()
        req = ToolRequest(
            request_id="R-015",
            tool_id="rest:get",
            params={"url": "http://netdata/api/v1/info", "method": "GET"},
            requestor_role="operator",
            severity="LOW",
            confidence=0.95,
            incident_id="INC-9002",
        )
        result = dispatcher.dispatch(req)
        self.assertEqual(result.status, ToolStatus.SUCCESS)
        self.assertEqual(result.approval_status, ApprovalStatus.AUTO_APPROVED)

    # ── Test 10: Maintenance Mode E2E ─────────────────────────────────────────
    def test_e2e_dispatch_blocked_during_maintenance(self):
        """E2E: Semua non-admin request diblokir saat maintenance mode aktif."""
        from SERVER.tools.dispatcher import ToolDispatcher
        from SERVER.tools.interfaces import ToolRequest, ToolStatus
        dispatcher = ToolDispatcher(maintenance_mode=True)
        req = ToolRequest(
            request_id="R-016",
            tool_id="rest:post",
            params={"url": "http://api/restart", "method": "POST"},
            requestor_role="operator",
            confidence=0.99,
        )
        result = dispatcher.dispatch(req)
        self.assertEqual(result.status, ToolStatus.DENIED)

    # ── Test 11: Architecture Rule — Jarvis tidak boleh import drivers ─────────
    def test_jarvis_does_not_import_tool_drivers_directly(self):
        """
        Aturan Arsitektur: SERVER/jarvis TIDAK BOLEH mengimpor driver langsung.
        Hanya ToolDispatcher yang boleh dipanggil dari luar SERVER/tools/.
        """
        import ast
        jarvis_root = os.path.join(PROJECT_ROOT, "SERVER", "jarvis")
        violations = []
        for root, _, files in os.walk(jarvis_root):
            for f in files:
                if not f.endswith(".py"):
                    continue
                fp = os.path.join(root, f)
                with open(fp, encoding="utf-8") as fh:
                    try:
                        tree = ast.parse(fh.read(), filename=fp)
                    except SyntaxError:
                        continue
                for node in ast.walk(tree):
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        module = getattr(node, "module", "") or ""
                        if "tools.drivers" in module or "tools.risk" in module or "tools.policy" in module:
                            violations.append(f"{fp}: imports {module}")
        self.assertEqual(violations, [], f"Architecture violation:\n" + "\n".join(violations))


if __name__ == "__main__":
    unittest.main()
