"""
SERVER.jarvis.sessions - User Session Manager
Manages isolated user presentation sessions in memory without accessing DB/Repositories directly.
"""
from typing import Dict, Optional, Any
from SERVER.jarvis.interfaces.presentation_dtos import ConversationContextDTO

class SessionManager:
    """In-memory presentation session manager for isolating user interaction states."""
    def __init__(self):
        self._sessions: Dict[str, ConversationContextDTO] = {}

    def create_session(
        self, session_id: str, user_id: str, persona_id: str = "noc_engineer"
    ) -> ConversationContextDTO:
        ctx = ConversationContextDTO(
            session_id=session_id,
            user_id=user_id,
            active_persona_id=persona_id,
        )
        self._sessions[session_id] = ctx
        return ctx

    def get_session(self, session_id: str) -> Optional[ConversationContextDTO]:
        return self._sessions.get(session_id)

    def close_session(self, session_id: str) -> bool:
        return bool(self._sessions.pop(session_id, None))

    def active_session_count(self) -> int:
        return len(self._sessions)
