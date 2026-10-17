"""
SERVER.jarvis.conversation - Conversation Manager
Manages in-session presentation conversation history without touching persistent DBs.

v2.1 (Gap #3 Fix): Tambah VoiceContextMemory untuk multi-turn context awareness.
  - Menyimpan last_device, last_incident, last_action, last_intent per session
  - Memungkinkan JARVIS memahami perintah lanjutan tanpa user menyebut ulang device
  - Contoh: "restart kasir 1" → "cek statusnya" (kasir 1 diingat otomatis)

v3.0 (Agentic AI): Tambah get_messages_for_llm() untuk Deep Multi-Turn Memory.
  - Mengembalikan sliding window 10 turn dalam format messages[] kompatibel Gemini API
  - Digunakan oleh AgenticDispatcher untuk inject conversation context ke Gemini
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone


@dataclass
class ConversationTurn:
    turn_id: str
    sender: str         # "user" | "jarvis"
    text: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class VoiceContextMemory:
    """
    Gap #3: Per-session voice context memory untuk multi-turn conversation awareness.
    Disimpan in-memory — tidak persistent ke DB (sesuai ADR-005).
    """
    last_device: str = ""           # Perangkat terakhir yang dibahas ("KASIR-2", "SERVER-BACKUP")
    last_incident: str = ""         # Insiden terakhir ("INC-001")
    last_action: str = ""           # Aksi terakhir ("EXECUTE_REMEDIATION", "LAUNCH_REMOTE_SESSION")
    last_intent: str = ""           # Intent terakhir ("REMEDIATE", "QUERY", "REMOTE")
    last_site: str = ""             # Site/lokasi terakhir ("GUDANG", "KASIR")
    turn_count: int = 0             # Jumlah turn dalam session ini
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Serialisasi ke dict untuk dikirim ke LLMVoiceCommandTranslator."""
        return {
            "last_device": self.last_device,
            "last_incident": self.last_incident,
            "last_action": self.last_action,
            "last_intent": self.last_intent,
            "last_site": self.last_site,
            "turn_count": self.turn_count,
        }

    def update(
        self,
        device: str = "",
        incident: str = "",
        action: str = "",
        intent: str = "",
        site: str = "",
    ) -> None:
        """Update context setelah turn berhasil diproses. Hanya field non-empty yang di-update."""
        if device:
            self.last_device = device
        if incident:
            self.last_incident = incident
        if action:
            self.last_action = action
        if intent:
            self.last_intent = intent
        if site:
            self.last_site = site
        self.turn_count += 1
        self.updated_at = datetime.now(timezone.utc).isoformat()


class ConversationManager:
    """In-memory presentation conversation history buffer per session.

    v2.1 (Gap #3 Fix): Dilengkapi VoiceContextMemory untuk multi-turn awareness.
    """
    def __init__(self):
        self._histories: Dict[str, List[ConversationTurn]] = {}
        self._contexts: Dict[str, VoiceContextMemory] = {}  # Gap #3: per-session context

    def add_turn(self, session_id: str, sender: str, text: str) -> ConversationTurn:
        turn = ConversationTurn(
            turn_id=f"TURN-{len(self._histories.get(session_id, []))+1:04d}",
            sender=sender,
            text=text,
        )
        if session_id not in self._histories:
            self._histories[session_id] = []
        self._histories[session_id].append(turn)
        return turn

    def get_history(self, session_id: str, limit: int = 10) -> List[ConversationTurn]:
        history = self._histories.get(session_id, [])
        return history[-limit:]

    def get_messages_for_llm(
        self, session_id: str, limit: int = 10
    ) -> List[Dict[str, str]]:
        """
        v3.0 Agentic AI: Kembalikan conversation history dalam format
        messages[] yang kompatibel dengan Gemini dan OpenAI API.

        Format output: [{"role": "user" | "assistant", "content": "..."}]

        Digunakan oleh AgenticDispatcher._build_messages() untuk inject
        full conversation context ke Gemini Tool Calling request.
        """
        history = self._histories.get(session_id, [])[-limit:]
        messages = []
        for turn in history:
            role = "user" if turn.sender == "user" else "assistant"
            messages.append({"role": role, "content": turn.text})
        return messages

    def clear_history(self, session_id: str) -> None:
        self._histories.pop(session_id, None)
        self._contexts.pop(session_id, None)

    # ── Gap #3: Multi-Turn Context Memory ─────────────────────────────────────

    def get_context(self, session_id: str) -> VoiceContextMemory:
        """Ambil context memory untuk session. Buat baru jika belum ada."""
        if session_id not in self._contexts:
            self._contexts[session_id] = VoiceContextMemory()
        return self._contexts[session_id]

    def get_context_dict(self, session_id: str) -> Dict[str, Any]:
        """Ambil context sebagai dict untuk dikirim ke LLMVoiceCommandTranslator.translate()."""
        return self.get_context(session_id).to_dict()

    def update_context(
        self,
        session_id: str,
        device: str = "",
        incident: str = "",
        action: str = "",
        intent: str = "",
        site: str = "",
    ) -> None:
        """
        Gap #3: Update context setelah turn berhasil diproses oleh JarvisRuntime.
        Dipanggil dari jarvis_presentation_runtime.py setelah dispatch berhasil.

        Args:
            session_id: ID sesi voice aktif.
            device:     Nama perangkat yang diproses (e.g. "KASIR-2").
            incident:   ID insiden yang diproses (e.g. "INC-001").
            action:     Nama aksi yang dieksekusi (e.g. "EXECUTE_REMEDIATION").
            intent:     Intent yang terdeteksi (e.g. "REMEDIATE").
            site:       Nama site/lokasi (e.g. "GUDANG").
        """
        ctx = self.get_context(session_id)
        ctx.update(
            device=device,
            incident=incident,
            action=action,
            intent=intent,
            site=site,
        )

