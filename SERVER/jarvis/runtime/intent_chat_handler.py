"""
SERVER/jarvis/runtime/intent_chat_handler.py
--------------------------------------------
Chat, issue reporting, gateway fallback, and queue summaries for JARVIS runtime.
"""
import logging
import time
import re

logger = logging.getLogger("JARVIS.intent_chat_handler")


from typing import Any


class IntentChatHandlerMixin:
    """Mixin for operator live chat, issue ticket creation, and notifications."""

    # Mixin attribute declarations for IDE type checkers
    noc_bridge: Any
    gateway: Any
    prompt_mgr: Any
    hitl_feedback: Any
    audit: Any
    remote_mgr: Any

    def _get_chat_engine(self):
        """Lazy-init ConversationalLLMEngine (CHAT-1)."""
        engine = getattr(self, "_chat_engine", None)
        if engine is None:
            try:
                from SERVER.jarvis.conversation.conversational_llm import ConversationalLLMEngine
                engine = ConversationalLLMEngine()
            except Exception as e:
                logger.warning(f"[JarvisRuntime] ConversationalLLMEngine unavailable: {e}")
                engine = False
            self._chat_engine = engine
        return engine or None

    def _handle_chat(self, query_text, intent_result, action_context, session_id=None):
        """Handle conversational queries: chat ops via real NOC API, free talk via LLM."""
        q = query_text.lower()
        if any(k in q for k in [
            "siapa kamu", "siapa anda", "kamu siapa", "anda siapa", "namamu siapa", "nama kamu",
            "diprogram", "di program", "dibuat untuk", "dibuat buat", "buat apa", "untuk apa",
            "tugasmu", "tugas kamu", "fungsi kamu", "kamu bisa apa", "bisa apa", "di program buat apa", "diprogram buat apa"
        ]):
            action_context.action_taken = "IDENTITY_PROMPT"
            action_context.execution_status = "SUCCESS"
            return (
                "Saya JARVIS, Copilot NOC dan Asisten AI Infrastruktur Senior Anda! "
                "Saya diprogram untuk membantu otomatisasi operasional IT, pemantauan telemetri real-time, "
                "deteksi dan analisis insiden, mengeksekusi aksi remediasi aman dengan persetujuan Anda, "
                "serta mengelola infrastruktur jaringan dan server Anda. Ada yang bisa saya bantu, Bosku?", action_context
            )

        # Handle specific chat operations from catalog (Domain 7)
        # CHAT-2: semua hasil berasal dari NOC Bridge sungguhan — tidak ada data dummy.
        if any(k in q for k in ["buka chat", "tutup chat", "eskalasi chat", "kirim pesan", "balas chat", "chat terbaru", "pesan terbaru", "baca chat", "saran balasan", "update status chat"]):
            chat_sid = "NOC-LIVE"

            def _fail(action, resp=None, err=None):
                reason = err or getattr(resp, "error", None) or "NOC API tidak merespons"
                action_context.action_taken = action
                action_context.execution_status = "FAILED"
                return f"⚠️ {action} gagal: {reason}. Tidak ada perubahan yang terjadi.", action_context

            status_map = [("buka", "OPEN", "OPEN_CHAT_SESSION"),
                          ("tutup", "CLOSED", "CLOSE_CHAT_SESSION"),
                          ("eskalasi", "ESCALATED", "ESCALATE_CHAT_SESSION")]
            for kw, status, action in status_map:
                if kw in q:
                    try:
                        resp = self.noc_bridge.update_chat_session_status(chat_sid, status)
                    except Exception as e:
                        return _fail(action, err=str(e))
                    if not resp.success:
                        return _fail(action, resp)
                    action_context.action_taken = action
                    action_context.execution_status = "SUCCESS"
                    return f"💬 Sesi chat {chat_sid} → status {status} (dikonfirmasi NOC API).", action_context

            if ("kirim" in q or "balas" in q) and "saran" not in q:
                action = "SEND_CHAT_MESSAGE" if "kirim" in q else "REPLY_CHAT"
                clean_body = re.sub(r'\b(kirim|balas|pesan|chat|jarvis|javis|jarfis|yarvis|jabis|jabes)\b', '', q, flags=re.IGNORECASE).strip(' ,:.-')
                if not clean_body or len(clean_body) <= 2:
                    action_context.action_taken = "PROMPT_CHAT_RECIPIENT"
                    action_context.execution_status = "SUCCESS"
                    return "Siap Bosku! Mau kirim pesan apa dan ke siapa? (Contoh: 'kirim pesan ke teknisi Budi server CPU normal')", action_context
                try:
                    resp = self.noc_bridge.send_chat_message(session_id=chat_sid, message=clean_body, sender_type="OPERATOR")
                except Exception as e:
                    return _fail(action, err=str(e))
                if not resp.success:
                    return _fail(action, resp)
                action_context.action_taken = action
                action_context.execution_status = "SUCCESS"
                return f"💬 Pesan terkirim ke {chat_sid} (dikonfirmasi NOC API): '{clean_body}'", action_context

            if "saran" in q:
                try:
                    resp = self.noc_bridge.get_chat_suggestion(chat_sid, context=query_text)
                except Exception as e:
                    return _fail("GET_CHAT_SUGGESTION", err=str(e))
                suggestion = (getattr(resp, "data", None) or {}).get("suggestion", "") if resp.success else ""
                if not suggestion:
                    return _fail("GET_CHAT_SUGGESTION", resp, None if not resp.success else "belum ada saran dari AI")
                action_context.action_taken = "GET_CHAT_SUGGESTION"
                action_context.execution_status = "SUCCESS"
                return f"💬 Saran balasan: {suggestion}", action_context

            # Baca riwayat chat: belum ada endpoint riwayat di NOC Bridge → jujur.
            action_context.action_taken = "GET_CHAT_MESSAGES"
            action_context.execution_status = "UNSUPPORTED"
            return ("Maaf Bosku, saya belum punya akses ke riwayat chat dashboard (endpoint belum tersedia). "
                    "Silakan buka panel Dashboard Chat untuk melihatnya."), action_context

        # CHAT-1: obrolan bebas → LLM percakapan multi-turn (text-only, tanpa aksi).
        engine = self._get_chat_engine()
        if engine is not None:
            history = []
            conv_mgr = getattr(self, "conv_mgr", None)
            if conv_mgr is not None and session_id:
                try:
                    history = conv_mgr.get_messages_for_llm(session_id, limit=10)
                except Exception:
                    history = []
            reply = engine.reply(query_text, history=history, voice_mode=True)
            if reply is not None:
                action_context.action_taken = "CHAT_RESPONSE"
                action_context.execution_status = "SUCCESS"
                return reply.text, action_context

        action_context.action_taken = "CHAT_RESPONSE"
        action_context.execution_status = "DEGRADED"
        return ("Maaf Bosku, modul percakapan AI saya sedang tidak tersedia, jadi saya belum bisa mengobrol bebas. "
                "Perintah operasional NOC tetap bisa saya jalankan."), action_context

    def _handle_issue(self, query_text, intent_result, action_context):
        """Handle issue/ticket creation."""
        target_dev = getattr(intent_result, "target_device", None) or "PC-STORE-01"
        issue_resp = self.noc_bridge.report_issue(
            pc_name=target_dev,
            severity="MEDIUM",
            details=query_text,
        )
        action_context.action_taken = "CREATE_ISSUE_TICKET"
        action_context.execution_status = "SUCCESS" if issue_resp.success else "FAILED"
        return issue_resp.summary or f"Tiket insiden untuk {target_dev} berhasil dilaporkan.", action_context

    def _handle_gateway_fallback(self, query_text, session_id, session, action_context):
        """Fallback: kirim query langsung ke UnifiedGateway."""
        raw_request = {
            "query_id": f"JARVIS-VOICE-{session_id}-{int(time.time())}",
            "user_id": session.user_id if session else "voice_user",
            "user_role": "noc_operator",
            "query_text": query_text,
            "session_id": session_id,
        }
        try:
            response_dict = self.gateway.handle_request(raw_request)
            answer = response_dict.get("answer_text", "Perintah diproses.")
            action_context.execution_status = "SUCCESS"
            return answer, action_context
        except Exception as e:
            logger.error(f"[JarvisRuntime] Gateway fallback error: {e}")
            action_context.execution_status = "FAILED"
            return f"❌ Error: {e}", action_context

    def _hitl_notify(self, message: str, channels: list) -> None:
        """Kirim notifikasi HITL ke channel yang ditentukan."""
        logger.info(f"[HITL_NOTIFY] Channels: {channels} | Message: {message[:60]}...")
        try:
            if "desktop" in channels:
                self.noc_bridge.push_notification(f"🔔 {message}")
        except Exception as e:
            logger.warning(f"[HITL_NOTIFY] Notification dispatch failed: {e}")

    def get_hitl_queue_summary(self) -> str:
        """Ringkasan antrian HITL untuk dashboard."""
        return self.hitl_feedback.format_queue_summary()

    def get_audit_summary(self) -> str:
        """Ringkasan audit log untuk dashboard."""
        return str(self.audit.get_recent(5))

    def get_active_remote_sessions(self) -> str:
        """Ringkasan sesi remote aktif."""
        return str(self.remote_mgr.get_active_sessions())
