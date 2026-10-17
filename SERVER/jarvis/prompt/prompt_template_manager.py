"""
SERVER.jarvis.prompt - Presentation Prompt Templates
Formats text responses according to active persona styles for voice/chat presentation.
"""
from typing import Optional
from SERVER.jarvis.personas.persona_registry import PersonaConfig

class PresentationPromptManager:
    """Formats output text for presentation based on active persona."""

    def format_presentation_response(self, text: str, persona: Optional[PersonaConfig]) -> str:
        if not persona:
            return text
        if persona.tone == "technical":
            return f"{persona.greeting}\n\n{text}\n\n{persona.closing}"
        elif persona.tone == "executive":
            # Executive mode: concise bullet-point framing
            return f"{persona.greeting}\n• Ringkasan: {text}\n{persona.closing}"
        else:
            return f"{persona.greeting}\n{text}\n{persona.closing}"
