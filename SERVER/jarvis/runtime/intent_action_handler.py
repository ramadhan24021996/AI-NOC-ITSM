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
        """Handle remediation via ActionCatalogValidator → Sandbox Verifier → UnifiedGateway → Safety Gate."""
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

        # Sandbox Dry-Run Safety Verification
        sbx_msg = ""
        if hasattr(self, "sandbox_verifier") and self.sandbox_verifier:
            sbx_res = self.sandbox_verifier.verify_action(noc_action, intent_result.target_device or "target-device")
            sbx_msg = f"\n\n{sbx_res.message}"

        # P15: Action Catalog Validation
        val_result = self.catalog_validator.validate(query_text)
        action_context.risk_level = val_result.get("risk_level", "MEDIUM")

        if val_result["verdict"] == "REJECTED":
            # Action tidak dikenal di catalog → Blocked!
            action_context.execution_status = "CANCELLED"
            action_context.policy_effect = "REJECTED_NOT_IN_CATALOG"
            return val_result["reason"], action_context

        elif val_result["verdict"] == "HITL_REQUIRED":
            # High risk atau action catalog requires HITL → Enqueue HITL langsung
            incident_id = intent_result.target_incident or f"INC-{int(time.time())}"
            device = intent_result.target_device or "target-device"
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
            action_context.followup_message = f"Ketik 'Jarvis, approve {incident_id}' untuk melanjutkan."

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
            "user_role": "noc_operator",
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
            device = intent_result.target_device or "target-device"
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
            action_context.followup_message = f"Ketik 'Jarvis, approve {incident_id}' untuk melanjutkan."
            answer = self.hitl_feedback.format_notification(item)
        else:
            action_context.execution_status = "SUCCESS"

            # P13: Auto-learn SOP jika remediate sukses
            if val_result.get("action_id"):
                self.kb_learning_bridge.auto_learn_from_resolution({
                    "incident_id": f"INC-RESOLVED-{int(time.time())}",
                    "intent": val_result.get("action_id"),
                    "device_id": intent_result.target_device or "GLOBAL",
                    "root_cause": f"Diagnosa otomatis: {val_result.get('action_name')}",
                    "solution": val_result.get('action_name'),
                })

        if sbx_msg and "PASSED" in sbx_msg:
            answer += sbx_msg

        return answer, action_context

    def _handle_hitl(self, query_text, intent_result, session, action_context):
        """Handle HITL decisions (approve/reject/escalate)."""
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
            import re
            m = re.search(r"INC[-\s]?\d{3,}", query_text, re.IGNORECASE)
            if m:
                incident_id = m.group(0).upper().replace(" ", "-")

        if not incident_id:
            # Tidak ada incident ID, tampilkan queue
            pending = self.hitl_feedback.get_pending_items()
            if pending:
                incident_id = pending[0].incident_id
            else:
                action_context.action_taken = f"HITL_{decision.value}"
                action_context.execution_status = "SUCCESS"
                return (
                    "❓ Tidak ada incident ID yang disebutkan dan tidak ada aksi pending. "
                    "Contoh: 'Jarvis, approve INC-001'", action_context
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
