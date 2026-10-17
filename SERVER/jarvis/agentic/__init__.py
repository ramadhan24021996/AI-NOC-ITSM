"""
SERVER.jarvis.agentic — JARVIS Agentic AI Package
==================================================
Tiga pilar JARVIS Agentic AI:
  1. AgenticToolRegistry   — JSON Schema semua tool JARVIS (146+ action catalog)
  2. AgenticDispatcher     — ReAct Loop: Gemini Tool Calling → deterministic executor
  3. ProactiveReasoner     — Post-action proactive insight synthesizer

Filosofi: HYBRID DISPATCH — ZERO DELETION
  - Hardcoded regex/rules tetap UTUH sebagai executor yang handal (Layer 2)
  - Gemini sebagai orchestrator cerdas yang MEMUTUSKAN tool mana yang dipanggil (Layer 1)
  - Jika Gemini gagal/timeout → fallback ke JarvisCommandIntentRouter lama (Layer 3)
  - Tiga lapis = sistem semakin kaya, bukan diganti

Alur:
  User Query
    → FastTrack (<50ms deterministik, bypass LLM)
    → AgenticDispatcher (Gemini tool calling)
        → execute via existing _handle_query / _handle_action / etc.
        → ProactiveReasoner (LLM insight append)
    → ConversationMemory update
    → TTS response
"""

from SERVER.jarvis.agentic.tool_registry import JarvisToolRegistry
from SERVER.jarvis.agentic.agentic_dispatcher import AgenticDispatcher
from SERVER.jarvis.agentic.proactive_reasoner import ProactiveReasoner

__all__ = [
    "JarvisToolRegistry",
    "AgenticDispatcher",
    "ProactiveReasoner",
]
