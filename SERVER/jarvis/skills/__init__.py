"""
SERVER.jarvis.skills — Pluggable Domain Skill Registry (Pilar 1)
================================================================
Memungkinkan penambahan kemampuan baru pada JARVIS secara modular (@jarvis_skill)
tanpa harus memodifikasi blok kondisional monolitik.
"""
from SERVER.jarvis.skills.skill_registry import (
    JarvisSkillRegistry,
    JarvisSkillSpec,
    get_skill_registry,
    jarvis_skill,
)

__all__ = [
    "JarvisSkillRegistry",
    "JarvisSkillSpec",
    "get_skill_registry",
    "jarvis_skill",
]
