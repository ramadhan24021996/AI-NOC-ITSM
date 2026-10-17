"""
SERVER.jarvis.proactive — JARVIS Proactive Real-Time Voice Alert Engine
=======================================================================
Transforms JARVIS from passive (reactive) to proactive (event-driven).

Components:
  JarvisProactiveAnnouncer  — Main engine: cooldown + LLM narrate + TTS
  AlertCooldownManager      — Anti-spam dengan cooldown tinggi per event type
  EventCorrelator           — Batch event sejenis, 1 narasi untuk N event
  NarrativeContextMemory    — Ingat history, cegah repetisi kalimat
  LLMDynamicNarrator        — Generate narasi unik via LLM (non-template)
  GlobalRateLimiter         — Max 3 announcement/menit absolute cap
"""
