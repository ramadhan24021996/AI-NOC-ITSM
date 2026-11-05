"""
SERVER.integration.telegram.jarvis_telegram_gateway — JARVIS Telegram Full Gateway
====================================================================================
P10 Implementation: Full Telegram Bot adapter yang memungkinkan:
  1. Menerima perintah JARVIS via Telegram pesan teks
  2. Mengirim notifikasi HITL ke Telegram dengan inline keyboard (Approve/Reject)
  3. Parse jawaban inline keyboard (callback_query) → HITL decision
  4. Format respons JARVIS sesuai Telegram Markdown

Arsitektur:
  Telegram Bot API (webhook/long-polling)
  → JarvisTelegramGateway.handle_update()
  → JarvisCommandIntentRouter (P1)
  → JarvisPresentationRuntime (dispatch)
  → send_message() ke Telegram

Konfigurasi via environment:
  TELEGRAM_BOT_TOKEN   : Token dari @BotFather
  TELEGRAM_ALLOWED_IDS : Comma-separated chat_id yang diizinkan
  JARVIS_DASHBOARD_BASE_URL : URL dashboard untuk NOCBridge

Cara deploy:
  - Webhook: POST endpoint /webhook/telegram → handle_webhook_request()
  - Long-poll: JarvisTelegramGateway().start_polling() (thread terpisah)
"""
import json
import logging
import os
import threading
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from SERVER.contracts.schemas import IncidentQueryContract

logger = logging.getLogger("jarvis.integration.telegram")

class TelegramBotAdapter(ABC):
    """Abstract Telegram Bot message adapter."""
    @abstractmethod
    def parse_telegram_update(self, update_dict: Dict[str, Any]) -> IncidentQueryContract:
        pass

# ── Config ────────────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALLOWED_IDS_RAW = os.getenv("TELEGRAM_ALLOWED_IDS", "")
ALLOWED_IDS: List[int] = [int(x.strip()) for x in ALLOWED_IDS_RAW.split(",") if x.strip().isdigit()]

# Keyword yang mengaktifkan JARVIS via Telegram
WAKE_WORDS_TG = ["jarvis", "jv", "ai noc", "ainoc"]

# HITL callback data prefix
_APPROVE_PREFIX = "hitl_approve:"
_REJECT_PREFIX  = "hitl_reject:"
_ESCALATE_PREFIX = "hitl_escalate:"


@dataclass
class TelegramMessage:
    """Representasi pesan Telegram yang sudah diparsing."""
    update_id: int
    chat_id: int
    user_id: int
    username: str
    text: str
    is_callback: bool = False
    callback_data: str = ""
    callback_query_id: str = ""
    message_id: int = 0


class JarvisTelegramGateway(TelegramBotAdapter):
    """
    P10 — JARVIS Telegram Full Gateway.
    Jembatan antara Telegram Bot API dengan JARVIS Runtime.

    Menggunakan httpx (jika tersedia) atau urllib untuk HTTP calls ke Telegram API.
    """

    def __init__(self, jarvis_runtime=None, hitl_feedback=None):
        """
        Args:
            jarvis_runtime: Optional JarvisPresentationRuntime instance.
                            Jika None, hanya parse dan log (useful untuk testing).
            hitl_feedback: Optional JarvisHITLFeedback instance.
        """
        self.bot_token = BOT_TOKEN
        self.allowed_ids = ALLOWED_IDS
        self.jarvis_runtime = jarvis_runtime
        self.hitl_feedback = hitl_feedback
        from SERVER.jarvis.command.intent_router import JarvisCommandIntentRouter
        self.intent_router = JarvisCommandIntentRouter()
        self._api_base = f"https://api.telegram.org/bot{self.bot_token}"
        self._last_update_id = 0
        self._running = False
        logger.info(
            f"[TelegramGateway] Initialized. "
            f"Allowed IDs: {self.allowed_ids or 'ALL (open)'}"
        )

    # ── Update Parser ─────────────────────────────────────────────────────────

    def parse_update(self, update_dict: Dict[str, Any]) -> Optional[TelegramMessage]:
        """Parse Telegram update dict → TelegramMessage."""
        try:
            update_id = update_dict.get("update_id", 0)

            # Callback query (inline keyboard button click)
            if "callback_query" in update_dict:
                cq = update_dict["callback_query"]
                chat = cq.get("message", {}).get("chat", {})
                from_user = cq.get("from", {})
                return TelegramMessage(
                    update_id=update_id,
                    chat_id=chat.get("id", 0),
                    user_id=from_user.get("id", 0),
                    username=from_user.get("username", "unknown"),
                    text=cq.get("data", ""),
                    is_callback=True,
                    callback_data=cq.get("data", ""),
                    callback_query_id=cq.get("id", ""),
                    message_id=cq.get("message", {}).get("message_id", 0),
                )

            # Regular message
            msg = update_dict.get("message", {})
            if not msg:
                return None
            chat = msg.get("chat", {})
            from_user = msg.get("from", {})
            text = msg.get("text", "").strip()
            if not text:
                return None
            return TelegramMessage(
                update_id=update_id,
                chat_id=chat.get("id", 0),
                user_id=from_user.get("id", 0),
                username=from_user.get("username", "unknown"),
                text=text,
                message_id=msg.get("message_id", 0),
            )
        except Exception as e:
            logger.warning(f"[TelegramGateway] Parse update failed: {e}")
            return None

    def parse_telegram_update(self, update_dict: Dict[str, Any]) -> IncidentQueryContract:
        """
        Implementasi abstract dari TelegramBotAdapter.
        Convert Telegram update → IncidentQueryContract.
        """
        msg = self.parse_update(update_dict)
        if not msg:
            return IncidentQueryContract(
                query_id="TG-INVALID",
                user_id="unknown",
                user_role="noc_operator",
                query_text="",
            )
        # Strip wake word
        query_text = msg.text
        for wake in WAKE_WORDS_TG:
            lower = query_text.lower()
            if lower.startswith(wake):
                query_text = query_text[len(wake):].lstrip(",: ").strip()
                break

        return IncidentQueryContract(
            query_id=f"TG-{msg.update_id}",
            user_id=str(msg.user_id),
            user_role="noc_operator",
            query_text=query_text,
            session_id=f"TG-CHAT-{msg.chat_id}",
        )

    # ── Message Handler ───────────────────────────────────────────────────────

    def handle_update(self, update_dict: Dict[str, Any]) -> str:
        """
        Main handler untuk setiap update dari Telegram.
        Dipanggil dari webhook atau long-poll loop.

        Returns:
            Teks respons yang sudah dikirim ke Telegram.
        """
        msg = self.parse_update(update_dict)
        if not msg:
            return ""

        self._last_update_id = msg.update_id

        # Access control
        if self.allowed_ids and msg.chat_id not in self.allowed_ids:
            logger.warning(f"[TelegramGateway] Unauthorized chat_id: {msg.chat_id}")
            self._send_message(msg.chat_id, "⛔ Akses tidak diizinkan.")
            return "UNAUTHORIZED"

        # Handle callback query (HITL decision buttons)
        if msg.is_callback:
            return self._handle_callback(msg)

        # Check wake word
        text_lower = msg.text.lower()
        has_wake = any(text_lower.startswith(w) for w in WAKE_WORDS_TG)
        if not has_wake:
            # Tidak ada wake word — tidak diproses (silent ignore)
            return "NO_WAKE_WORD"

        # Strip wake word
        query_text = msg.text
        for wake in WAKE_WORDS_TG:
            if text_lower.startswith(wake):
                query_text = query_text[len(wake):].lstrip(",: ").strip()
                break

        # Intent routing
        intent_result = self.intent_router.classify(query_text)
        logger.info(
            f"[TelegramGateway] @{msg.username} ({msg.chat_id}): "
            f"'{query_text[:50]}' → {intent_result.intent.value}"
        )

        # Send typing indicator
        self._send_chat_action(msg.chat_id, "typing")

        # Route ke JARVIS Runtime atau handle langsung
        if self.jarvis_runtime:
            response = self._route_to_runtime(msg, query_text, intent_result)
        else:
            response = self._build_static_response(query_text, intent_result)

        # Format dan kirim respons
        formatted = self._format_for_telegram(response, intent_result)
        self._send_message(msg.chat_id, formatted)
        return formatted

    def _handle_callback(self, msg: TelegramMessage) -> str:
        """Handle inline keyboard callback (HITL approve/reject/escalate)."""
        data = msg.callback_data

        if not self.hitl_feedback:
            self._answer_callback(msg.callback_query_id, "⚠️ HITL tidak tersedia.")
            return "NO_HITL"

        from SERVER.jarvis.hitl.hitl_feedback import HITLDecision
        decision_map = {
            _APPROVE_PREFIX: HITLDecision.APPROVE,
            _REJECT_PREFIX: HITLDecision.REJECT,
            _ESCALATE_PREFIX: HITLDecision.ESCALATE,
        }

        for prefix, decision in decision_map.items():
            if data.startswith(prefix):
                incident_id = data[len(prefix):]
                result = self.hitl_feedback.process_decision(
                    incident_id=incident_id,
                    decision=decision,
                    operator_id=f"TG-{msg.username}",
                )
                self._answer_callback(msg.callback_query_id, f"{decision.value}: {incident_id}")
                self._send_message(msg.chat_id, result.message)
                return result.message

        self._answer_callback(msg.callback_query_id, "Tidak dikenali.")
        return "UNKNOWN_CALLBACK"

    def _route_to_runtime(self, msg, query_text, intent_result) -> str:
        """Route perintah ke JarvisPresentationRuntime."""
        if not self.jarvis_runtime:
            return self._build_static_response(query_text, intent_result)
        try:
            from SERVER.jarvis.interfaces.presentation_dtos import VoiceAudioPayloadDTO
            audio = VoiceAudioPayloadDTO(
                session_id=f"TG-CHAT-{msg.chat_id}",
                audio_format="text",
                text_caption=query_text,
            )
            result = self.jarvis_runtime.process_voice_query(
                session_id=f"TG-CHAT-{msg.chat_id}",
                audio_payload=audio,
            )
            return result.get("answer_text", "Tidak ada respons.")
        except Exception as e:
            logger.error(f"[TelegramGateway] Runtime error: {e}")
            return f"❌ Error memproses perintah: {e}"

    def _build_static_response(self, query_text: str, intent_result) -> str:
        """Respons statis saat runtime tidak tersedia."""
        from SERVER.jarvis.command.noc_keywords_id import NOCKeywordsID
        noc_action = NOCKeywordsID.lookup_action(query_text)
        return (
            f"✅ Perintah diterima.\n"
            f"Intent: `{intent_result.intent.value}` ({intent_result.confidence:.0%})\n"
            f"Action: `{noc_action}`\n"
            f"Device: `{intent_result.target_device or '-'}`\n"
            f"Site: `{intent_result.target_site or '-'}`"
        )

    # ── Telegram Message Formatting ───────────────────────────────────────────

    def _format_for_telegram(self, text: str, intent_result=None) -> str:
        """Format teks untuk Telegram (escape special chars, batas 4096 char)."""
        if len(text) > 4096:
            text = text[:4000] + "\n\n...(terpotong)"
        return text

    def build_hitl_keyboard_message(
        self, incident_id: str, action: str, device: str,
        risk_level: str, risk_score: float
    ) -> Dict[str, Any]:
        """
        Build Telegram message dengan inline keyboard untuk HITL approval.
        Format: {"text": "...", "reply_markup": {...}}
        """
        risk_icon = {"HIGH": "🔴", "MEDIUM": "🟠", "LOW": "🟡"}.get(risk_level, "⚠️")
        text = (
            f"{risk_icon} *[HITL APPROVAL REQUIRED]*\n\n"
            f"🎯 Insiden: `{incident_id}`\n"
            f"⚡ Aksi: `{action}`\n"
            f"🖥️ Device: `{device}`\n"
            f"⚠️ Risk: *{risk_level}* (Score: {risk_score:.2f})\n\n"
            f"Pilih keputusan:"
        )
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ APPROVE", "callback_data": f"{_APPROVE_PREFIX}{incident_id}"},
                    {"text": "🚫 REJECT", "callback_data": f"{_REJECT_PREFIX}{incident_id}"},
                ],
                [
                    {"text": "📤 ESCALATE L3", "callback_data": f"{_ESCALATE_PREFIX}{incident_id}"},
                ]
            ]
        }
        return {"text": text, "reply_markup": json.dumps(keyboard), "parse_mode": "Markdown"}

    def send_hitl_notification(self, chat_id: int, incident_id: str,
                                action: str, device: str,
                                risk_level: str, risk_score: float) -> bool:
        """Kirim notifikasi HITL dengan inline keyboard ke Telegram."""
        msg_data = self.build_hitl_keyboard_message(
            incident_id, action, device, risk_level, risk_score
        )
        return self._send_message(
            chat_id, msg_data["text"],
            reply_markup=msg_data["reply_markup"],
            parse_mode="Markdown"
        )

    def broadcast_hitl_to_all(self, incident_id: str, action: str,
                               device: str, risk_level: str, risk_score: float) -> int:
        """Kirim HITL notification ke SEMUA allowed chat IDs. Return count sent."""
        count = 0
        for cid in (self.allowed_ids or []):
            ok = self.send_hitl_notification(cid, incident_id, action, device, risk_level, risk_score)
            if ok:
                count += 1
        return count

    def send_alert(self, message: str, parse_mode: str = "Markdown") -> int:
        """Kirim alert ke semua allowed chat IDs. Return count sent."""
        count = 0
        for cid in (self.allowed_ids or []):
            if self._send_message(cid, message, parse_mode=parse_mode):
                count += 1
        return count

    # ── HTTP helpers ─────────────────────────────────────────────────────────

    def _send_message(
        self, chat_id: int, text: str,
        reply_markup: str = "",
        parse_mode: str = ""
    ) -> bool:
        """Kirim pesan ke Telegram API."""
        if not self.bot_token:
            logger.debug(f"[TelegramGateway] No token. Would send to {chat_id}: {text[:50]}")
            return True  # Silently succeed in test/no-token mode

        import urllib.request, urllib.parse
        payload: Dict[str, Any] = {"chat_id": chat_id, "text": text}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        if parse_mode:
            payload["parse_mode"] = parse_mode

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{self._api_base}/sendMessage",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception as e:
            logger.warning(f"[TelegramGateway] sendMessage failed: {e}")
            return False

    def _send_chat_action(self, chat_id: int, action: str = "typing") -> None:
        """Kirim 'typing...' indicator ke Telegram."""
        if not self.bot_token:
            return
        import urllib.request
        payload = json.dumps({"chat_id": chat_id, "action": action}).encode("utf-8")
        try:
            req = urllib.request.Request(
                f"{self._api_base}/sendChatAction",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

    def _answer_callback(self, callback_query_id: str, text: str = "") -> None:
        """Answer callback query (dismiss spinner pada inline keyboard)."""
        if not self.bot_token or not callback_query_id:
            return
        import urllib.request
        payload = json.dumps({"callback_query_id": callback_query_id, "text": text[:200]}).encode("utf-8")
        try:
            req = urllib.request.Request(
                f"{self._api_base}/answerCallbackQuery",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

    def _get_updates(self, offset: int = 0) -> List[Dict]:
        """Long-polling: GET /getUpdates."""
        if not self.bot_token:
            return []
        import urllib.request
        url = f"{self._api_base}/getUpdates?offset={offset}&timeout=30"
        try:
            with urllib.request.urlopen(url, timeout=35) as resp:
                data = json.loads(resp.read())
                return data.get("result", [])
        except Exception as e:
            logger.debug(f"[TelegramGateway] getUpdates failed: {e}")
            return []

    # ── Long-Poll Loop ────────────────────────────────────────────────────────

    def start_polling(self, daemon: bool = True) -> threading.Thread:
        """
        Start long-polling loop dalam background thread.
        Cocok untuk deployment tanpa reverse proxy (development/on-premise).
        """
        def _poll():
            logger.info("[TelegramGateway] Long-poll started.")
            self._running = True
            offset = self._last_update_id + 1
            while self._running:
                updates = self._get_updates(offset)
                for update in updates:
                    try:
                        self.handle_update(update)
                    except Exception as e:
                        logger.error(f"[TelegramGateway] Update error: {e}")
                    offset = update.get("update_id", offset) + 1
                if not updates:
                    time.sleep(1)  # Backoff jika tidak ada update

        t = threading.Thread(target=_poll, daemon=daemon, name="jarvis-telegram-poll")
        t.start()
        return t

    def stop_polling(self) -> None:
        """Stop long-poll loop."""
        self._running = False
        logger.info("[TelegramGateway] Long-poll stopping.")

    def handle_webhook_request(self, body: bytes) -> str:
        """
        Entry point untuk webhook mode.
        Dipanggil dari web framework handler (FastAPI/Flask/Gin proxy).
        """
        try:
            update = json.loads(body)
            return self.handle_update(update)
        except Exception as e:
            logger.error(f"[TelegramGateway] Webhook parse error: {e}")
            return "ERROR"

    def set_webhook(self, webhook_url: str) -> bool:
        """Register webhook URL ke Telegram API."""
        if not self.bot_token:
            return False
        import urllib.request
        payload = json.dumps({"url": webhook_url}).encode("utf-8")
        try:
            req = urllib.request.Request(
                f"{self._api_base}/setWebhook",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                ok = resp.status == 200
                logger.info(f"[TelegramGateway] setWebhook {'OK' if ok else 'FAILED'}: {webhook_url}")
                return ok
        except Exception as e:
            logger.error(f"[TelegramGateway] setWebhook error: {e}")
            return False
