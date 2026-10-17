from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jarvis.memory.episodic")


# ─── File-based Episodic Memory (Production-safe tanpa DB dependency) ─────────
# Persistent ke JSON file di disk — sinkron dengan PostgreSQL jika tersedia

_MEMORY_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..", "auto_generated_sops", ".episodic_memory"
)


def _safe_json_key(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", str(s))[:80]


@dataclass
class MemoryEntry:
    key: str
    value: str
    confidence: float = 0.8
    access_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: Optional[str] = None


@dataclass
class DeviceHistory:
    device_id: str
    incident_count: int = 0
    last_incident: str = ""
    last_action: str = ""
    common_issue: str = ""
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class OperatorProfile:
    operator_id: str
    preferred_brevity: str = "NORMAL"  # SHORT | NORMAL | DETAILED
    preferred_language: str = "ID"     # ID | EN | MIXED
    last_device: str = ""
    last_incident: str = ""
    session_count: int = 0
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())




class EpisodicMemory:
    """
    JARVIS Cross-Session Episodic Memory.
    Persisten ke JSON file + optional PostgreSQL sync.
    """

    def __init__(self, db_conn: Optional[Any] = None):
        import os as _os
        import re as _re
        self._re = _re
        self._db = db_conn
        self._memory_dir = os.path.abspath(_MEMORY_DIR)
        os.makedirs(self._memory_dir, exist_ok=True)
        self._devices_file = os.path.join(self._memory_dir, "device_history.json")
        self._operators_file = os.path.join(self._memory_dir, "operator_profiles.json")
        self._facts_file = os.path.join(self._memory_dir, "facts.json")

        self._devices: Dict[str, Dict] = self._load(self._devices_file)
        self._operators: Dict[str, Dict] = self._load(self._operators_file)
        self._facts: Dict[str, Dict] = self._load(self._facts_file)

        logger.info("[EpisodicMemory] Loaded: %d devices, %d operators, %d facts",
                    len(self._devices), len(self._operators), len(self._facts))

    def _load(self, path: str) -> Dict:
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self, path: str, data: Dict) -> None:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning("[EpisodicMemory] Save error: %s", e)

    # ─── Device History ────────────────────────────────────────────────────────

    def record_device_incident(self, device_id: str, action: str, issue_type: str = "") -> None:
        """Catat insiden device. Akumulasi dari semua session."""
        key = str(device_id).upper().strip()
        now = datetime.now(timezone.utc).isoformat()
        if key not in self._devices:
            self._devices[key] = {
                "device_id": key, "incident_count": 0,
                "last_action": "", "last_incident": now, "common_issue": issue_type
            }
        self._devices[key]["incident_count"] = self._devices[key].get("incident_count", 0) + 1
        self._devices[key]["last_action"] = action
        self._devices[key]["last_incident"] = now
        if issue_type:
            self._devices[key]["common_issue"] = issue_type
        self._save(self._devices_file, self._devices)
        logger.debug("[EpisodicMemory] Device %s: incident_count=%d", key, self._devices[key]["incident_count"])

    def get_device_context(self, device_id: str) -> Optional[str]:
        """
        Recall: Apa yang JARVIS ingat tentang device ini.
        Return: Ringkasan kontekstual untuk diinjeksi ke respons.
        """
        key = str(device_id).upper().strip()
        if key not in self._devices:
            return None
        d = self._devices[key]
        count = d.get("incident_count", 0)
        last_action = d.get("last_action", "")
        common_issue = d.get("common_issue", "")

        if count == 0:
            return None

        from random import choice
        templates = [
            f"(Catatan: {key} sudah {count}x insiden. Terakhir: {last_action})",
            f"(FYI: saya ingat {key} pernah {count}x ada masalah.)",
            f"({key} sudah {count}x insiden terdaftar dalam memori saya.)",
        ]
        base = choice(templates)
        if common_issue and count >= 3:
            base += f" Pola utama: {common_issue}."
        return base

    def get_device_risk_level(self, device_id: str) -> str:
        """Return HIGH/MEDIUM/LOW berdasarkan history insiden."""
        key = str(device_id).upper().strip()
        if key not in self._devices:
            return "LOW"
        count = self._devices[key].get("incident_count", 0)
        if count >= 5:
            return "HIGH"
        elif count >= 2:
            return "MEDIUM"
        return "LOW"

    # ─── Operator Profiles ────────────────────────────────────────────────────

    def update_operator_preference(self, operator_id: str, preference_key: str, value: str) -> None:
        """
        Simpan preferensi operator berdasarkan pola interaksi.
        Contoh: brevity=SHORT jika operator sering menginterupsi respons panjang.
        """
        key = str(operator_id).lower().strip()
        if key not in self._operators:
            self._operators[key] = {
                "operator_id": key,
                "preferred_brevity": "NORMAL",
                "preferred_language": "ID",
                "last_device": "",
                "last_incident": "",
                "session_count": 0,
            }
        self._operators[key][preference_key] = value
        self._operators[key]["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save(self._operators_file, self._operators)

    def get_operator_context(self, operator_id: str) -> Dict[str, str]:
        """Recall operator context untuk adaptive communication."""
        key = str(operator_id).lower().strip()
        default = {
            "preferred_brevity": "NORMAL",
            "preferred_language": "ID",
            "last_device": "",
            "last_incident": "",
        }
        if key not in self._operators:
            return default
        return {**default, **self._operators[key]}

    def record_session_interaction(self, operator_id: str, device: str = "", incident: str = "") -> None:
        """Update last known context untuk operator."""
        key = str(operator_id).lower().strip()
        if key not in self._operators:
            self._operators[key] = {"operator_id": key, "session_count": 0}
        if device:
            self._operators[key]["last_device"] = device
        if incident:
            self._operators[key]["last_incident"] = incident
        self._operators[key]["session_count"] = self._operators[key].get("session_count", 0) + 1
        self._operators[key]["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save(self._operators_file, self._operators)

    # ─── General Facts ────────────────────────────────────────────────────────

    def remember(self, fact_key: str, fact_value: str, confidence: float = 0.8,
                 ttl_hours: int = 168) -> None:
        """
        Simpan fakta umum dengan TTL.
        Contoh: remember("site_a_pattern", "network flap tiap Senin pagi", 0.92)
        """
        key = hashlib.md5(fact_key.encode()).hexdigest()[:16]
        now = datetime.now(timezone.utc)
        expires = None
        if ttl_hours > 0:
            from datetime import timedelta
            exp = now + timedelta(hours=ttl_hours)
            expires = exp.isoformat()

        self._facts[key] = {
            "fact_key": fact_key,
            "fact_value": fact_value,
            "confidence": confidence,
            "created_at": now.isoformat(),
            "expires_at": expires,
            "access_count": 0,
        }
        self._save(self._facts_file, self._facts)

    def recall(self, query: str, top_k: int = 3) -> List[Dict]:
        """
        Cari fakta relevan dari memori.
        Simple keyword matching — bisa diupgrade ke embedding search.
        """
        query_words = set(query.lower().split())
        results = []
        now = datetime.now(timezone.utc)

        for key, fact in self._facts.items():
            # Cek TTL
            if fact.get("expires_at"):
                try:
                    exp = datetime.fromisoformat(fact["expires_at"])
                    if exp < now:
                        continue
                except Exception:
                    pass

            # Simple relevance score
            fact_words = set((fact.get("fact_key","") + " " + fact.get("fact_value","")).lower().split())
            overlap = len(query_words & fact_words)
            if overlap > 0:
                results.append({
                    "fact": fact.get("fact_value", ""),
                    "confidence": fact.get("confidence", 0.5),
                    "relevance": overlap / max(len(query_words), 1),
                })

        results.sort(key=lambda x: x["relevance"] * x["confidence"], reverse=True)
        return results[:top_k]

    def forget_stale(self, days: int = 30) -> int:
        """Hapus fakta yang sudah kedaluwarsa atau lama tidak diakses."""
        now = datetime.now(timezone.utc)
        to_delete = []
        for key, fact in self._facts.items():
            if fact.get("expires_at"):
                try:
                    if datetime.fromisoformat(fact["expires_at"]) < now:
                        to_delete.append(key)
                except Exception:
                    pass
        for key in to_delete:
            del self._facts[key]
        if to_delete:
            self._save(self._facts_file, self._facts)
        return len(to_delete)

    def get_summary(self) -> str:
        """Ringkasan status episodic memory."""
        high_risk = [dev for dev, data in self._devices.items()
                     if data.get("incident_count", 0) >= 5]
        medium_risk = [dev for dev, data in self._devices.items()
                       if 2 <= data.get("incident_count", 0) < 5]
        return (
            f"🧠 Episodic Memory:\n"
            f"  Devices terpantau: {len(self._devices)}\n"
            f"    🔴 High risk (≥5 incident): {len(high_risk)} — {', '.join(high_risk[:3]) or 'tidak ada'}\n"
            f"    🟡 Medium risk (2-4 incident): {len(medium_risk)} — {', '.join(medium_risk[:3]) or 'tidak ada'}\n"
            f"  Operator profiles: {len(self._operators)}\n"
            f"  Fakta tersimpan: {len(self._facts)}"
        )


# ─── Singleton ────────────────────────────────────────────────────────────────
_instance: Optional[EpisodicMemory] = None

def get_episodic_memory() -> EpisodicMemory:
    global _instance
    if _instance is None:
        _instance = EpisodicMemory()
    return _instance
