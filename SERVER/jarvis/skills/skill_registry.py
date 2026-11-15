"""
SERVER.jarvis.skills.skill_registry — Pluggable Domain Skill Registry
=====================================================================
Pilar 1 Evolusi JARVIS:
Arsitektur berbasis registri skill (@jarvis_skill) sehingga domain baru
(Self-Learning, Operator Personalization, Cloud/K8s, Security, dll.) dapat
ditambahkan secara plug-and-play tanpa memperbesar intent_query_handler.py.

STRICTLY COMPLIANT WITH ADR-005 & Governance Rule #6.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("jarvis.skills.registry")

SkillHandlerFn = Callable[[Any, str, Any, Any, str], Optional[Tuple[str, Any]]]


@dataclass
class JarvisSkillSpec:
    """Metadata dan handler untuk satu Pluggable Skill JARVIS."""
    name: str
    domain: str
    triggers: List[str] = field(default_factory=list)
    priority: int = 50
    description: str = ""
    handler: Optional[SkillHandlerFn] = None


class JarvisSkillRegistry:
    """Registri terpusat untuk semua Pluggable Domain Skills JARVIS."""

    def __init__(self) -> None:
        self._skills: Dict[str, JarvisSkillSpec] = {}

    def register_skill(
        self,
        name: str,
        domain: str,
        triggers: List[str],
        handler: SkillHandlerFn,
        priority: int = 50,
        description: str = "",
    ) -> JarvisSkillSpec:
        spec = JarvisSkillSpec(
            name=name,
            domain=domain,
            triggers=[t.lower().strip() for t in triggers if t and t.strip()],
            priority=priority,
            description=description,
            handler=handler,
        )
        self._skills[name] = spec
        logger.debug("[SkillRegistry] Registered skill '%s' (domain=%s, priority=%d)", name, domain, priority)
        return spec

    def skill(
        self,
        name: str,
        domain: str,
        triggers: List[str],
        priority: int = 50,
        description: str = "",
    ) -> Callable[[SkillHandlerFn], SkillHandlerFn]:
        """Decorator untuk mendaftarkan fungsi sebagai Pluggable Skill JARVIS."""
        def _decorator(fn: SkillHandlerFn) -> SkillHandlerFn:
            self.register_skill(
                name=name,
                domain=domain,
                triggers=triggers,
                handler=fn,
                priority=priority,
                description=description or (fn.__doc__ or "").strip(),
            )
            return fn
        return _decorator

    def list_skills(self) -> List[Dict[str, Any]]:
        """Kembalikan daftar skill terurut berdasarkan prioritas."""
        ordered = sorted(self._skills.values(), key=lambda s: s.priority, reverse=True)
        return [
            {
                "name": s.name,
                "domain": s.domain,
                "priority": s.priority,
                "triggers_count": len(s.triggers),
                "description": s.description,
            }
            for s in ordered
        ]

    def dispatch(
        self,
        runtime: Any,
        query_text: str,
        intent_result: Any,
        action_context: Any,
        session_id: str = "default-session",
    ) -> Optional[Tuple[str, Any]]:
        """
        Cek apakah query cocok dengan salah satu skill terdaftar.
        Jika cocok dan handler mengembalikan hasil non-None, kembalikan (answer, action_context).
        """
        q = (query_text or "").lower().strip()
        if not q:
            return None

        ordered = sorted(self._skills.values(), key=lambda s: s.priority, reverse=True)
        for spec in ordered:
            if not spec.handler:
                continue
            if any(trig in q for trig in spec.triggers):
                try:
                    res = spec.handler(runtime, query_text, intent_result, action_context, session_id)
                    if res is not None:
                        logger.info("[SkillRegistry] Executed skill '%s' for query=%r", spec.name, query_text[:60])
                        return res
                except Exception as exc:
                    logger.warning("[SkillRegistry] Skill '%s' raised exception: %s", spec.name, exc)
        return None


# ─── Singleton Registry & Built-in Self-Evolution Skills ──────────────────────

_GLOBAL_REGISTRY = JarvisSkillRegistry()


def get_skill_registry() -> JarvisSkillRegistry:
    return _GLOBAL_REGISTRY


def jarvis_skill(
    name: str,
    domain: str,
    triggers: List[str],
    priority: int = 50,
    description: str = "",
) -> Callable[[SkillHandlerFn], SkillHandlerFn]:
    return _GLOBAL_REGISTRY.skill(
        name=name,
        domain=domain,
        triggers=triggers,
        priority=priority,
        description=description,
    )


@jarvis_skill(
    name="voice_feedback_learning",
    domain="SELF_EVOLUTION",
    triggers=[
        "koreksi analisa",
        "bukan itu penyebabnya",
        "penyebab sebenarnya",
        "masalah sebenarnya",
        "analisa tadi tepat",
        "solusi tadi berhasil",
        "catat bahwa",
        "ingat bahwa",
    ],
    priority=95,
    description="Closed-Loop Voice RLHF/DPO & Episodic Fact Learning (Pilar 4)",
)
def _handle_voice_feedback_learning(
    runtime: Any,
    query_text: str,
    intent_result: Any,
    action_context: Any,
    session_id: str,
) -> Optional[Tuple[str, Any]]:
    target_dev = getattr(intent_result, "target_device", "") or ""
    target_inc = getattr(intent_result, "target_incident", "") or ""
    session = runtime.session_mgr.get_session(session_id) if hasattr(runtime, "session_mgr") else None
    operator_id = getattr(session, "user_id", "noc_operator") if session else "noc_operator"

    kb_bridge = getattr(runtime, "kb_learning_bridge", None)
    if kb_bridge and hasattr(kb_bridge, "record_operator_voice_feedback"):
        answer = kb_bridge.record_operator_voice_feedback(
            operator_id=operator_id,
            query_text=query_text,
            target_device=target_dev,
            target_incident=target_inc,
        )
    else:
        from SERVER.jarvis.memory.episodic_memory import get_episodic_memory
        mem = get_episodic_memory()
        mem.remember(f"operator_note:{int(__import__('time').time())}", query_text, confidence=0.92)
        answer = f"🧠 Catatan Anda telah saya simpan ke Episodic Memory: \"{query_text}\"."

    action_context.action_taken = "VOICE_FEEDBACK_LEARNING"
    action_context.execution_status = "SUCCESS"
    return answer, action_context


@jarvis_skill(
    name="adaptive_operator_profile",
    domain="PERSONALIZATION",
    triggers=[
        "jawab singkat saja",
        "mode singkat",
        "mode ringkas",
        "jelaskan secara detail",
        "mode detail",
        "status memori episodik",
        "profil operator saya",
    ],
    priority=90,
    description="Adaptive Operator Brevity & Episodic Memory Inspection (Pilar 2)",
)
def _handle_adaptive_operator_profile(
    runtime: Any,
    query_text: str,
    intent_result: Any,
    action_context: Any,
    session_id: str,
) -> Optional[Tuple[str, Any]]:
    from SERVER.jarvis.memory.episodic_memory import get_episodic_memory

    mem = getattr(runtime, "_episodic_memory", None) or get_episodic_memory()
    session = runtime.session_mgr.get_session(session_id) if hasattr(runtime, "session_mgr") else None
    operator_id = getattr(session, "user_id", "noc_operator") if session else "noc_operator"
    q_low = query_text.lower()

    if "status memori episodik" in q_low:
        action_context.action_taken = "EPISODIC_MEMORY_SUMMARY"
        action_context.execution_status = "SUCCESS"
        return mem.get_summary(), action_context

    if any(k in q_low for k in ("singkat", "ringkas")):
        mem.update_operator_preference(operator_id, "preferred_brevity", "SHORT")
        action_context.action_taken = "OPERATOR_PROFILE_SHORT"
        action_context.execution_status = "SUCCESS"
        return (
            "✅ Preferensi komunikasi Anda telah diatur ke mode RINGKAS (SHORT). "
            "Mulai sekarang saya akan merangkum jawaban suara dalam 1 kalimat inti.",
            action_context,
        )

    if "detail" in q_low:
        mem.update_operator_preference(operator_id, "preferred_brevity", "DETAILED")
        action_context.action_taken = "OPERATOR_PROFILE_DETAILED"
        action_context.execution_status = "SUCCESS"
        return (
            "✅ Preferensi komunikasi Anda telah diatur ke mode MENDALAM (DETAILED). "
            "Saya akan menyertakan rincian teknis dan analisis Chain-of-Thought secara lengkap.",
            action_context,
        )

    ctx = mem.get_operator_context(operator_id)
    action_context.action_taken = "OPERATOR_PROFILE_STATUS"
    action_context.execution_status = "SUCCESS"
    return (
        f"👤 Profil Operator ({operator_id}):\n"
        f"├── Gaya Bicara (Brevity) : {ctx.get('preferred_brevity', 'NORMAL')}\n"
        f"├── Bahasa Preferensi     : {ctx.get('preferred_language', 'ID')}\n"
        f"├── Perangkat Terakhir    : {ctx.get('last_device') or 'Belum ada'}\n"
        f"└── Insiden Terakhir      : {ctx.get('last_incident') or 'Belum ada'}",
        action_context,
    )


@jarvis_skill(
    name="skill_registry_introspection",
    domain="META_COGNITION",
    triggers=[
        "daftar skill",
        "skill jarvis",
        "kemampuan modular",
        "modul skill aktif",
    ],
    priority=85,
    description="Menampilkan daftar skill modular yang terdaftar di JarvisSkillRegistry (Pilar 1)",
)
def _handle_skill_introspection(
    runtime: Any,
    query_text: str,
    intent_result: Any,
    action_context: Any,
    session_id: str,
) -> Optional[Tuple[str, Any]]:
    skills = _GLOBAL_REGISTRY.list_skills()
    lines = [f"🧩 JARVIS PLUGGABLE SKILL REGISTRY ({len(skills)} Modular Skills Aktif):"]
    for idx, s in enumerate(skills, 1):
        lines.append(
            f"  {idx}. [{s['domain']}] {s['name']} (priority={s['priority']}, triggers={s['triggers_count']}) — {s['description']}"
        )
    action_context.action_taken = "LIST_JARVIS_SKILLS"
    action_context.execution_status = "SUCCESS"
    return "\n".join(lines), action_context
