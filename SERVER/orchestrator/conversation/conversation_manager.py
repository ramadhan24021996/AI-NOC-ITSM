"""
SERVER.orchestrator.conversation.conversation_manager
======================================================
Component 1 of Pre-LLM Pipeline: Conversation Manager

Tugas:
  - Mengelola state dan riwayat percakapan multi-turn berdasarkan `conversation_id` / `session_id`.
  - Mencegah memory bloat dengan sliding-window pruning (max_turns).
  - Menyediakan ringkasan thread percakapan untuk komponen downstream (Context Builder).
"""
import time
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

logger = logging.getLogger("orchestrator.conversation.manager")


@dataclass
class ConversationTurn:
    """Mewakili satu turn interaksi dalam percakapan."""
    turn_id: int
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: float = field(default_factory=time.time)
    trace_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
            "metadata": self.metadata,
        }


class ConversationManager:
    """
    State manager untuk percakapan multi-turn NOC platform.
    Menyimpan history per conversation_id dengan batas maksimal turn.
    """

    def __init__(self, default_max_turns: int = 10):
        self._stores: Dict[str, List[ConversationTurn]] = {}
        self.default_max_turns = default_max_turns

    def add_turn(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        trace_id: str = "",
    ) -> ConversationTurn:
        """
        Menambahkan 1 turn baru ke percakapan. Auto-prune jika melebihi default_max_turns.
        """
        if not conversation_id:
            conversation_id = "default_session"

        if conversation_id not in self._stores:
            self._stores[conversation_id] = []

        history = self._stores[conversation_id]
        turn_id = len(history) + 1
        turn = ConversationTurn(
            turn_id=turn_id,
            role=role,
            content=content,
            timestamp=time.time(),
            trace_id=trace_id,
            metadata=metadata or {},
        )
        history.append(turn)

        # Auto prune
        self.prune_history(conversation_id, self.default_max_turns)
        logger.debug(
            f"[ConversationManager] Added turn {turn_id} for conv={conversation_id} | role={role}"
        )
        return turn

    def get_history(
        self, conversation_id: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Mengembalikan riwayat percakapan sebagai list dictionary.
        """
        if not conversation_id or conversation_id not in self._stores:
            return []

        turns = self._stores[conversation_id]
        if limit and limit > 0:
            turns = turns[-limit:]

        return [t.to_dict() for t in turns]

    def get_raw_turns(self, conversation_id: str) -> List[ConversationTurn]:
        """Mengembalikan objek ConversationTurn asli."""
        return self._stores.get(conversation_id, [])

    def prune_history(self, conversation_id: str, max_turns: int = 10) -> int:
        """
        Memotong riwayat agar tidak melebihi max_turns (sliding window).
        """
        if conversation_id not in self._stores:
            return 0

        turns = self._stores[conversation_id]
        excess = len(turns) - max_turns
        if excess > 0:
            self._stores[conversation_id] = turns[-max_turns:]
            logger.info(
                f"[ConversationManager] Pruned {excess} turns from conv={conversation_id}"
            )
            return excess
        return 0

    def clear_history(self, conversation_id: str) -> bool:
        """Menghapus seluruh percakapan untuk session tertentu."""
        if conversation_id in self._stores:
            del self._stores[conversation_id]
            return True
        return False

    def get_thread_summary(self, conversation_id: str) -> str:
        """
        Menghasilkan teks ringkasan riwayat singkat untuk prompt injection.
        """
        history = self.get_history(conversation_id)
        if not history:
            return "Belum ada riwayat percakapan."

        lines = []
        for item in history:
            role_label = "User" if item["role"] == "user" else "Assistant"
            snippet = item["content"][:150] + ("..." if len(item["content"]) > 150 else "")
            lines.append(f"{role_label}: {snippet}")

        return "\n".join(lines)
