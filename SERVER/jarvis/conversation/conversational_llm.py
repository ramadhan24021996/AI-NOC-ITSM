"""
SERVER/jarvis/conversation/conversational_llm.py
------------------------------------------------
CHAT-1 / CHAT-4 / CHAT-5: Mesin percakapan natural untuk JARVIS.

Prinsip:
- Teks saja (TANPA tool calling) → obrolan bebas TIDAK PERNAH memicu aksi /
  remediasi. Aksi tetap wajib lewat intent router + HITL (Rule #6).
- Multi-turn: memakai riwayat dari ConversationManager.get_messages_for_llm().
- Provider: Gemini REST → Ollama lokal. Jika semua gagal → return None
  (caller wajib jujur, bukan mengarang jawaban).
- Mode suara: jawaban ringkas 1–3 kalimat agar enak didengar via TTS.
"""
import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger("JARVIS.conversational_llm")

_PLACEHOLDER_KEYS = {"", "YOUR_GEMINI_API_KEY_HERE"}

SYSTEM_PROMPT = (
    "Kamu adalah JARVIS, asisten AI senior untuk tim NOC/ITSM. "
    "Bicara dalam Bahasa Indonesia yang natural, hangat, dan sopan; boleh menyapa "
    "operator dengan 'Bosku' sesekali. Kamu boleh mengobrol santai, menjelaskan "
    "konsep IT, dan menjawab pertanyaan umum.\n"
    "ATURAN KERAS:\n"
    "1. Jangan pernah mengklaim telah menjalankan aksi, remediasi, restart, atau "
    "mengirim pesan. Kamu hanya berbicara. Jika operator ingin aksi, sarankan "
    "perintah eksplisit (mis. 'restart service X di PC-01') yang akan melalui "
    "persetujuan HITL.\n"
    "2. Jangan mengarang data telemetri, status server, angka, atau nama tiket. "
    "Jika tidak tahu, katakan tidak tahu dan sarankan cara mengeceknya.\n"
    "3. Pahami konteks percakapan sebelumnya (kata 'tadi', 'itu', 'yang sama').\n"
)
VOICE_STYLE = "Jawab ringkas maksimal 3 kalimat, tanpa markdown, tanpa emoji, karena akan diucapkan."
TEXT_STYLE = "Jawab jelas dan ringkas; markdown sederhana diperbolehkan."


@dataclass
class ChatReply:
    text: str
    provider: str


def load_gemini_key_pool() -> List[str]:
    """Load all configured Gemini API keys (env + .env + LLMRouter pool) for zero-downtime 429 rotation."""
    keys: List[str] = []

    def _add(raw_val: str):
        for part in (raw_val or "").replace(";", ",").split(","):
            val = part.strip().strip("\"'")
            if val and val not in _PLACEHOLDER_KEYS and val not in keys:
                keys.append(val)

    _add(os.getenv("GEMINI_API_KEY", ""))
    _add(os.getenv("GEMINI_API_KEYS", ""))
    for idx in range(1, 10):
        _add(os.getenv(f"GEMINI_API_KEY_{idx}", ""))

    for env_path in ("/app/.env", ".env", "../.env"):
        try:
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith(("GEMINI_API_KEY=", "GEMINI_API_KEYS=")):
                        _add(line.split("=", 1)[1])
        except (FileNotFoundError, PermissionError):
            continue

    try:
        from SERVER.python_ai_core.engines.llm_router import load_ai_config, load_keys_for_provider
        cfg = load_ai_config()
        for k in load_keys_for_provider("gemini", cfg):
            _add(k)
    except Exception:
        pass

    return keys


def _load_gemini_key() -> str:
    pool = load_gemini_key_pool()
    return pool[0] if pool else ""


def resolve_gemini_models(primary: Optional[str] = None) -> List[str]:
    """Daftar model Gemini berurutan (primary + fallback), dipakai bersama oleh
    chat engine, AgenticDispatcher, dan ProactiveReasoner."""
    primary = primary or os.getenv("JARVIS_CHAT_MODEL", "gemini-3.1-flash-lite-preview")
    if primary == "gemini-3.5-flash":
        primary = "gemini-3.1-flash-lite-preview"
    extra = [
        m.strip()
        for m in os.getenv(
            "JARVIS_CHAT_FALLBACK_MODELS",
            "gemini-3-flash-preview,gemini-2.5-flash-lite,gemini-2.5-flash,gemma-4-31b-it",
        ).split(",")
        if m.strip()
    ]
    return list(dict.fromkeys([primary] + extra))


class ConversationalLLMEngine:
    """Engine obrolan natural multi-turn, text-only (aman dari side-effect)."""

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        gemini_model: Optional[str] = None,
        ollama_url: Optional[str] = None,
        ollama_model: Optional[str] = None,
        timeout: float = 8.0,
    ):
        self._gemini_keys = [gemini_api_key] if gemini_api_key is not None else load_gemini_key_pool()
        self._gemini_key = self._gemini_keys[0] if self._gemini_keys else ""
        self._key_idx = 0
        # Fallback antar model Gemini (mengatasi 404 model pensiun / 503 overload)
        self._gemini_models = resolve_gemini_models(gemini_model)
        self._ollama_url = (ollama_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self._ollama_model = ollama_model or os.getenv("JARVIS_OLLAMA_MODEL", "")
        self._timeout = timeout

    # ── Public API ────────────────────────────────────────────────────────────
    def reply(
        self,
        user_text: str,
        history: Optional[List[Dict[str, str]]] = None,
        voice_mode: bool = True,
    ) -> Optional[ChatReply]:
        """Hasilkan balasan. Return None jika tidak ada provider yang berhasil."""
        history = self._dedupe_current(history or [], user_text)
        system = SYSTEM_PROMPT + (VOICE_STYLE if voice_mode else TEXT_STYLE)

        if self._gemini_key:
            text = self._call_gemini(system, history, user_text)
            if text:
                return ChatReply(text=text, provider="gemini")
        if self._ollama_model:
            text = self._call_ollama(system, history, user_text)
            if text:
                return ChatReply(text=text, provider="ollama")
        return None

    @property
    def available(self) -> bool:
        return bool(self._gemini_key or self._ollama_model)

    # ── Helpers ───────────────────────────────────────────────────────────────
    @staticmethod
    def _dedupe_current(history: List[Dict[str, str]], user_text: str) -> List[Dict[str, str]]:
        """Runtime sudah add_turn(user) sebelum routing → buang turn terakhir jika identik."""
        if history and history[-1].get("role") == "user" and history[-1].get("content") == user_text:
            return history[:-1]
        return history

    def _post_json(self, url: str, payload: dict) -> Optional[dict]:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            logger.warning("[ConversationalLLM] HTTP %s from %s", e.code, url.split("?")[0])
        except Exception as e:  # network / timeout / JSON
            logger.warning("[ConversationalLLM] request failed (%s): %s", url.split("?")[0], e)
        return None

    def _call_gemini(self, system: str, history: List[Dict[str, str]], user_text: str) -> Optional[str]:
        contents = [
            {"role": "model" if m.get("role") == "assistant" else "user", "parts": [{"text": m.get("content", "")}]}
            for m in history if m.get("content")
        ]
        contents.append({"role": "user", "parts": [{"text": user_text}]})
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": contents,
            "generationConfig": {"temperature": 0.6, "maxOutputTokens": 2048},
        }
        keys = self._gemini_keys or ([self._gemini_key] if self._gemini_key else [])
        if not keys:
            return None
        for model in self._gemini_models:
            for _ in range(len(keys)):
                active_key = keys[self._key_idx % len(keys)]
                url = (
                    "https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{model}:generateContent?key={active_key}"
                )
                data = self._post_json(url, payload)
                if data is None and len(keys) > 1:
                    self._key_idx = (self._key_idx + 1) % len(keys)
                    continue
                try:
                    parts = data["candidates"][0]["content"]["parts"]  # type: ignore[index]
                    text = "".join(p.get("text", "") for p in parts).strip()
                    if text:
                        return text
                except (TypeError, KeyError, IndexError):
                    break
        return None

    def _call_ollama(self, system: str, history: List[Dict[str, str]], user_text: str) -> Optional[str]:
        messages = [{"role": "system", "content": system}]
        messages += [{"role": m["role"], "content": m["content"]} for m in history if m.get("content")]
        messages.append({"role": "user", "content": user_text})
        data = self._post_json(f"{self._ollama_url}/api/chat", {
            "model": self._ollama_model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.6},
        })
        try:
            text = (data or {}).get("message", {}).get("content", "").strip()
            return text or None
        except AttributeError:
            return None
