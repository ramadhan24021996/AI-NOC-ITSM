"""
SERVER/jarvis/runtime/intent_action_handler.py
----------------------------------------------
Action intent handler: Remediate, HITL confirmation, and remote session launcher.
"""
import logging
import time
import re

from SERVER.jarvis.hitl.hitl_feedback import HITLDecision
from SERVER.jarvis.command.noc_keywords_id import NOCKeywordsID
from SERVER.jarvis.workflow.workflow_governance_control_plane import (
    BlastRadiusCategory,
    get_workflow_governance_control_plane_v38,
)

logger = logging.getLogger("JARVIS.intent_action_handler")


from typing import Any


class IntentActionHandlerMixin:
    """Mixin for remediation, HITL approvals, and remote desktop launches."""

    # Mixin attribute declarations for IDE type checkers
    catalog_validator: Any
    hitl_feedback: Any
    noc_bridge: Any
    remote_session_mgr: Any
    remote_mgr: Any
    gateway: Any
    prompt_mgr: Any
    persona_reg: Any
    kb_learning_bridge: Any

    def _handle_remediate(self, query_text, intent_result, session_id, session, action_context):
        """Handle remediation via RBAC Gate → 10 Control Gates V4.0 → ActionCatalogValidator → Sandbox Verifier → UnifiedGateway → Rule #6 Dual-Evidence Lock."""
        # [WS-J4] RBAC Operator Role Gate — block read-only/viewer roles from executing mutations
        operator_role = (getattr(session, "user_role", None) or "noc_operator").strip().lower()
        if operator_role in ("viewer", "read_only", "readonly", "guest", "auditor"):
            action_context.execution_status = "FORBIDDEN_RBAC"
            action_context.policy_effect = f"RBAC_DENIED:{operator_role.upper()}"
            return (
                f"⛔ Akses ditolak (RBAC): Peran '{operator_role}' hanya memiliki izin baca (read-only) "
                f"dan tidak diizinkan mengeksekusi perintah remediasi.",
                action_context,
            )

        # Check One-Click Voice Pending Action
        if hasattr(self, "one_click_remediator") and self.one_click_remediator and self.one_click_remediator.is_confirmation_query(query_text):
            pending = self.one_click_remediator.get_pending_action(session_id)
            if pending:
                query_text = pending["action_code"]
                intent_result.target_device = pending["device"]
                self.one_click_remediator.clear_pending_action(session_id)
                logger.info(f"[IntentActionHandler] Resolved One-Click Voice action={query_text} for device={pending['device']}")

        noc_action = NOCKeywordsID.lookup_action(query_text)
        action_context.action_taken = noc_action
        target_device = intent_result.target_device or "target-device"

        # [WS-J6] Wire 10 Control Gates V4.0 (Kill-Switch, Blast Radius GATE-05, Autonomy Budget GATE-07)
        wf_cp = get_workflow_governance_control_plane_v38()
        ks_active, ks_reason = wf_cp.kill_switch.is_active()
        if ks_active:
            action_context.execution_status = "BLOCKED_BY_KILL_SWITCH"
            action_context.policy_effect = f"GLOBAL_KILL_SWITCH:{ks_reason or 'ACTIVE'}"
            return (
                f"🚨 Global Automation Kill-Switch sedang AKTIF ({ks_reason or 'EMERGENCY_STOP'}). "
                f"Seluruh eksekusi remediasi suara ditangguhkan.",
                action_context,
            )

        blast_cat, blast_policy = wf_cp.blast_evaluator.evaluate_blast_radius(target_device)
        action_context.blast_radius = blast_cat.value
        if blast_cat == BlastRadiusCategory.BLOCK_MASS_REMEDIATION:
            action_context.execution_status = "CANCELLED"
            action_context.policy_effect = blast_policy
            return (
                f"⛔ Remediasi massal pada '{target_device}' diblokir oleh kebijakan Blast Radius Gate (GATE-05).",
                action_context,
            )

        within_budget, budget_narrative = wf_cp.autonomy_budget.check_autonomy_budget(target_device, noc_action)
        if not within_budget:
            action_context.execution_status = "AUTONOMY_BUDGET_EXCEEDED"
            action_context.policy_effect = "RULE_AUTO_007_LOOP_BLOCKED"
            return budget_narrative, action_context

        # Sandbox Dry-Run Safety Verification
        sbx_msg = ""
        if hasattr(self, "sandbox_verifier") and self.sandbox_verifier:
            sbx_res = self.sandbox_verifier.verify_action(noc_action, target_device)
            sbx_msg = f"\n\n{sbx_res.message}"

        # P15: Action Catalog Validation
        val_result = dict(self.catalog_validator.validate(query_text))
        if blast_cat in (
            BlastRadiusCategory.DUAL_APPROVAL_CORE,
            BlastRadiusCategory.SENIOR_APPROVAL_CLUSTER,
            BlastRadiusCategory.ELEVATED_CLUSTER,
        ) and val_result.get("verdict") != "REJECTED":
            val_result["verdict"] = "HITL_REQUIRED"
            val_result["risk_level"] = "CRITICAL" if blast_cat == BlastRadiusCategory.DUAL_APPROVAL_CORE else "HIGH"

        action_context.risk_level = val_result.get("risk_level", "MEDIUM")

        if val_result["verdict"] == "REJECTED":
            # Action tidak dikenal di catalog → Blocked!
            action_context.execution_status = "CANCELLED"
            action_context.policy_effect = "REJECTED_NOT_IN_CATALOG"
            return val_result["reason"], action_context

        elif val_result["verdict"] == "HITL_REQUIRED":
            # High risk atau action catalog requires HITL → Enqueue HITL langsung
            incident_id = intent_result.target_incident or f"INC-{int(time.time())}"
            device = target_device
            item = self.hitl_feedback.enqueue(
                incident_id=incident_id,
                device=device,
                candidate_action=val_result.get("action_id") or noc_action,
                risk_level=val_result.get("risk_level", "HIGH"),
                risk_score=0.85,
                blast_radius=val_result.get("blast_radius_estimate", 10),
                policy_effect="CATALOG_FORCE_HITL",
                llm_confidence=0.90,
            )
            action_context.hitl_queue_id = item.queue_id
            action_context.requires_hitl_approval = True
            action_context.execution_status = "HITL_QUEUED"
            action_context.requires_followup = True
            action_context.followup_message = (
                f"Silakan konfirmasi approval insiden {incident_id} melalui tombol HITL di Dashboard NOC."
            )

            # P7: Format persona HITL acknowledgment
            ack = self.persona_reg.format_acknowledgment(
                session.active_persona_id if session else "noc_engineer",
                "hitl",
                action=val_result.get("action_name", noc_action),
                target=device,
                risk_level=val_result.get("risk_level", "HIGH"),
                hitl_queue_id=item.queue_id,
                incident_id=incident_id,
            )
            return ack or self.hitl_feedback.format_notification(item), action_context

        # APPROVED: Send request ke gateway
        raw_request = {
            "query_id": f"JARVIS-REMEDIATE-{session_id}-{int(time.time())}",
            "user_id": session.user_id if session else "voice_user",
            "user_role": operator_role,
            "query_text": query_text,
            "session_id": session_id,
            "intent": "REMEDIATE",
            "noc_action_hint": noc_action,
            "catalog_action_id": val_result.get("action_id"),
        }

        try:
            response_dict = self.gateway.handle_request(raw_request)
        except Exception as e:
            logger.error(f"[JarvisRuntime] Gateway error: {e}")
            action_context.execution_status = "FAILED"
            return f"❌ Gateway error: {e}", action_context

        answer = response_dict.get("answer_text", "Perintah remediasi diproses.")
        policy = response_dict.get("policy_effect", "")
        requires_hitl = response_dict.get("requires_hitl", False)

        action_context.policy_effect = policy
        action_context.risk_level = response_dict.get("risk_level", action_context.risk_level)
        action_context.risk_score = response_dict.get("risk_score")

        if requires_hitl or "HITL" in policy:
            incident_id = response_dict.get("incident_id", f"INC-{int(time.time())}")
            device = target_device
            item = self.hitl_feedback.enqueue(
                incident_id=incident_id,
                device=device,
                candidate_action=noc_action,
                risk_level=action_context.risk_level or "HIGH",
                risk_score=action_context.risk_score or 0.9,
                blast_radius=response_dict.get("blast_radius_size", 1),
                policy_effect=policy,
                llm_confidence=response_dict.get("llm_confidence", 0.85),
            )
            action_context.hitl_queue_id = item.queue_id
            action_context.requires_hitl_approval = True
            action_context.execution_status = "HITL_QUEUED"
            action_context.requires_followup = True
            action_context.followup_message = (
                f"Silakan konfirmasi approval insiden {incident_id} melalui tombol HITL di Dashboard NOC."
            )
            answer = self.hitl_feedback.format_notification(item)
        else:
            # [WS-J5 / Axiom Rule #6] Zero Assumption of Success & Dual-Evidence Binding:
            # Dispatching a remediation command NEVER transitions execution_status to SUCCESS
            # and MUST NOT trigger auto_learn_from_resolution before execution_evidence +
            # post_remediation_evidence are verified on the same incident.
            action_context.execution_status = "PENDING_VERIFICATION"
            action_context.policy_effect = policy or "RULE6_DUAL_EVIDENCE_REQUIRED"
            rule6_note = (
                " Status: PENDING_VERIFICATION (menunggu execution_evidence dan "
                "post_remediation_evidence terverifikasi pada insiden yang sama sesuai Rule #6)."
            )
            if "PENDING_VERIFICATION" not in answer:
                answer = answer.rstrip() + rule6_note

        if sbx_msg and "PASSED" in sbx_msg:
            answer += sbx_msg

        return answer, action_context

    def _handle_hitl(self, query_text, intent_result, session, action_context):
        """Handle HITL decisions (approve/reject/escalate) with K-07 Voice Approval Prohibition."""
        q = query_text.lower()
        incident_id = intent_result.target_incident or ""

        # Detect decision type
        if any(k in q for k in ["approve", "setujui", "izinkan", "ya lakukan", "proceed"]):
            decision = HITLDecision.APPROVE
        elif any(k in q for k in ["reject", "tolak", "batalkan", "jangan", "cancel"]):
            decision = HITLDecision.REJECT
        elif any(k in q for k in ["escalate", "eskalasi", "teruskan", "naikan"]):
            decision = HITLDecision.ESCALATE
        elif any(k in q for k in ["defer", "tunda", "maintenance"]):
            decision = HITLDecision.DEFER
        elif any(k in q for k in ["override", "paksa", "force"]):
            decision = HITLDecision.OVERRIDE
        elif any(k in q for k in ["antrian", "queue", "siapa", "berapa", "pending"]):
            # Query HITL queue status
            action_context.action_taken = "GET_HITL_QUEUE"
            action_context.execution_status = "SUCCESS"
            return self.hitl_feedback.format_queue_summary(), action_context
        else:
            action_context.execution_status = "FAILED"
            return (
                "Perintah HITL tidak dikenali. Gunakan: "
                "'approve', 'reject', 'escalate', atau 'queue status'.", action_context
            )

        # Ekstrak incident ID dari teks jika belum ada
        if not incident_id:
            m = re.search(r"INC[-\s]?\d{3,}", query_text, re.IGNORECASE)
            if m:
                incident_id = m.group(0).upper().replace(" ", "-")

        # [WS-J5 / K-07] Block unverified voice approval/rejection/override of HITL actions.
        # Operators must confirm cryptographically via the authenticated NOC Dashboard UI.
        if decision in (HITLDecision.APPROVE, HITLDecision.REJECT, HITLDecision.OVERRIDE):
            target_label = f" untuk insiden {incident_id}" if incident_id else ""
            action_context.action_taken = "REQUEST_DASHBOARD_CONFIRMATION"
            action_context.execution_status = "PENDING_DASHBOARD_CONFIRMATION"
            action_context.requires_hitl_approval = True
            return (
                f"🔒 Demi keamanan operasional (Kebijakan K-07), keputusan HITL ({decision.value}){target_label} "
                f"tidak dapat dieksekusi hanya melalui perintah suara. Silakan klik tombol Konfirmasi HITL "
                f"secara langsung pada panel Approval di Dashboard NOC.",
                action_context,
            )

        if not incident_id:
            # Tidak ada incident ID, tampilkan queue
            pending = self.hitl_feedback.get_pending_items()
            if pending:
                incident_id = pending[0].incident_id
            else:
                action_context.action_taken = f"HITL_{decision.value}"
                action_context.execution_status = "SUCCESS"
                return (
                    "❓ Tidak ada incident ID yang disebutkan dan tidak ada aksi pending.",
                    action_context,
                )

        result = self.hitl_feedback.process_decision(
            incident_id=incident_id,
            decision=decision,
            operator_id=session.user_id if session else "operator",
        )

        action_context.action_taken = f"HITL_{decision.value}"
        action_context.execution_status = "SUCCESS" if result.executed or result.next_action != "NONE" else "FAILED"
        return result.message, action_context

    def _handle_remote(self, query_text, intent_result, session, action_context):
        """Handle remote access and browser control commands."""
        q = query_text.lower()
        target_dev = intent_result.target_device or "PC-STORE-01"

        if any(k in q for k in ["tutup", "disconnect", "akhiri", "putuskan", "hentikan", "matikan"]):
            # Tutup sesi remote
            res = self.remote_mgr.close_session(target_dev)
            success = res.get("success", False) if isinstance(res, dict) else bool(res)
            action_context.action_taken = "CLOSE_REMOTE_SESSION"
            action_context.execution_status = "SUCCESS" if success else "FAILED"
            msg = f"Sesi remote ke {target_dev} telah ditutup." if success else f"Tidak ada sesi aktif ke {target_dev}."
            return msg, action_context

        # Request sesi remote baru
        tool = "rustdesk"
        if "anydesk" in q:
            tool = "anydesk"
        elif "vnc" in q:
            tool = "vnc"
        elif "ssh" in q:
            tool = "ssh"
        elif "rdp" in q:
            tool = "rdp"

        remote_resp = self.remote_mgr.open_session(
            operator_id=session.user_id if session else "operator",
            tool=tool,
            host=target_dev,
            target_device=target_dev,
        )
        success = remote_resp.get("success", False) if isinstance(remote_resp, dict) else True
        msg = remote_resp.get("message", f"Sesi {tool.upper()} ke {target_dev} berhasil dibuka.") if isinstance(remote_resp, dict) else str(remote_resp)
        action_context.action_taken = f"REQUEST_REMOTE_{tool.upper()}"
        action_context.execution_status = "SUCCESS" if success else "FAILED"
        return msg, action_context
