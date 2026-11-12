"""
SERVER.python_ai_core.engines.event_correlation_engine
=======================================================
Real-Time Anomaly Correlation Engine — AI NOC Senior Intelligence

Masalah yang diselesaikan:
  5 insiden cascade dari 1 root cause → selama ini diproses 5 tiket terpisah
  Sekarang: dikorrelasikan menjadi 1 root cause + cascade map

Fitur:
  ✅ Temporal correlation window (±5 menit)
  ✅ Topology-aware (device yang satu network → lebih mungkin berkorelasi)
  ✅ Semantic clustering (insiden dengan kata kunci mirip)
  ✅ Root cause ranking (device mana yang paling mungkin sebab pertama)
  ✅ Cascade chain builder (visualisasi sebab-akibat)
  ✅ Dedup suppression (insiden turunan tidak trigger alert terpisah)
"""
from __future__ import annotations

import hashlib
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("python_ai_core.engines.event_correlation")


# ─── Constants ────────────────────────────────────────────────────────────────
TEMPORAL_WINDOW_SECONDS = 300   # 5 menit
TOPOLOGY_BOOST = 0.35           # Boost skor korelasi jika satu subnet
SEMANTIC_BOOST  = 0.25          # Boost skor jika kata kunci mirip
MIN_CORRELATION_SCORE = 0.55    # Threshold untuk dianggap berkorelasi


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class CorrelatedIncidentGroup:
    """Sekelompok insiden yang berkorelasi — satu root cause."""
    group_id: str
    root_cause_incident_id: str
    root_cause_device: str
    root_cause_confidence: float
    cascade_incidents: List[str] = field(default_factory=list)
    cascade_devices: List[str] = field(default_factory=list)
    correlation_method: str = "temporal+semantic"
    total_incidents: int = 1
    estimated_blast_radius: int = 1
    recommended_action: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict:
        return {
            "group_id": self.group_id,
            "root_cause_incident_id": self.root_cause_incident_id,
            "root_cause_device": self.root_cause_device,
            "root_cause_confidence": round(self.root_cause_confidence, 3),
            "cascade_incidents": self.cascade_incidents,
            "cascade_devices": self.cascade_devices,
            "total_incidents": self.total_incidents,
            "estimated_blast_radius": self.estimated_blast_radius,
            "recommended_action": self.recommended_action,
            "correlation_method": self.correlation_method,
            "created_at": self.created_at,
        }


@dataclass
class CorrelationResult:
    """Hasil analisis korelasi untuk batch insiden."""
    groups: List[CorrelatedIncidentGroup] = field(default_factory=list)
    standalone_incidents: List[str] = field(default_factory=list)
    suppressed_count: int = 0          # Insiden yang seharusnya tidak jadi tiket baru
    processing_ms: int = 0
    summary: str = ""


# ─── Semantic Keyword Extractor ───────────────────────────────────────────────

_KEYWORD_GROUPS = {
    "printer":   {"printer", "spooler", "cetak", "print", "kasir", "struk", "antrian"},
    "network":   {"network", "jaringan", "switch", "gateway", "subnet", "vlan", "ping", "dns", "dhcp"},
    "server":    {"server", "cpu", "ram", "memory", "disk", "storage", "process", "load"},
    "database":  {"database", "db", "postgres", "sql", "query", "connection", "lock"},
    "auth":      {"login", "auth", "authentication", "ldap", "ad", "password", "session"},
}


def _extract_semantic_group(text: str) -> Optional[str]:
    """Tentukan kategori semantik dari teks insiden."""
    t = text.lower()
    for group, keywords in _KEYWORD_GROUPS.items():
        if any(kw in t for kw in keywords):
            return group
    return None


def _extract_subnet(ip_or_device: str) -> str:
    """Ekstrak prefix subnet dari IP atau nama device."""
    import re
    # IP address pattern
    m = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3})\.\d{1,3}', ip_or_device)
    if m:
        return m.group(1)
    # Device naming convention: PC-KASIR-*, PC-TMS-*, PC-HQ-*
    m2 = re.match(r'^([A-Z]+-[A-Z]+)-', ip_or_device.upper())
    if m2:
        return m2.group(1)
    return ""


# ─── Event Correlation Engine ─────────────────────────────────────────────────

class EventCorrelationEngine:
    """
    Real-time event correlation engine untuk AI NOC.
    
    Mengidentifikasi insiden yang berasal dari root cause yang sama,
    mencegah alert fatigue dari cascade failure yang menjadi banyak tiket.
    """

    def __init__(self, temporal_window: int = TEMPORAL_WINDOW_SECONDS):
        self._window = temporal_window
        self._correlation_cache: Dict[str, CorrelatedIncidentGroup] = {}
        self._suppressed_ids: Set[str] = set()

    # ─── Scoring ──────────────────────────────────────────────────────────────

    def _temporal_score(self, ts1: float, ts2: float) -> float:
        """Score berdasarkan kedekatan waktu. 1.0 = bersamaan, 0.0 = >5 menit."""
        diff = abs(ts1 - ts2)
        if diff >= self._window:
            return 0.0
        return 1.0 - (diff / self._window)

    def _topology_score(self, dev1: str, dev2: str) -> float:
        """Score berdasarkan kedekatan topologi network."""
        if not dev1 or not dev2:
            return 0.0
        s1 = _extract_subnet(dev1)
        s2 = _extract_subnet(dev2)
        if s1 and s2 and s1 == s2:
            return TOPOLOGY_BOOST
        # Same site prefix (PC-KASIR → PC-KASIR)
        p1 = dev1.split("-")[0] if "-" in dev1 else dev1
        p2 = dev2.split("-")[0] if "-" in dev2 else dev2
        if p1.upper() == p2.upper():
            return TOPOLOGY_BOOST * 0.5
        return 0.0

    def _semantic_score(self, text1: str, text2: str) -> float:
        """Score berdasarkan kemiripan semantik."""
        g1 = _extract_semantic_group(text1)
        g2 = _extract_semantic_group(text2)
        if g1 and g2 and g1 == g2:
            return SEMANTIC_BOOST
        return 0.0

    def _correlation_score(self, inc_a: Dict, inc_b: Dict) -> float:
        """Hitung total korelasi antara dua insiden."""
        ts_a = float(inc_a.get("_ts_epoch", time.time()))
        ts_b = float(inc_b.get("_ts_epoch", time.time()))

        dev_a = str(inc_a.get("device_name") or inc_a.get("agent", ""))
        dev_b = str(inc_b.get("device_name") or inc_b.get("agent", ""))

        text_a = str(inc_a.get("evidence","") or inc_a.get("flag","") or inc_a.get("title",""))
        text_b = str(inc_b.get("evidence","") or inc_b.get("flag","") or inc_b.get("title",""))

        t_score = self._temporal_score(ts_a, ts_b)
        if t_score == 0.0:
            return 0.0  # Jauh dari window → tidak mungkin berkorelasi

        topo_score = self._topology_score(dev_a, dev_b)
        sem_score  = self._semantic_score(text_a + " " + dev_a, text_b + " " + dev_b)

        return min(1.0, t_score * 0.5 + topo_score + sem_score)

    # ─── Root Cause Detection ─────────────────────────────────────────────────

    def _find_root_cause(self, group: List[Dict]) -> Tuple[Dict, float]:
        """
        Temukan insiden yang paling mungkin sebagai root cause.
        
        Heuristik:
        1. Insiden tertua dalam window (paling awal terjadi)
        2. Device dengan severity tertinggi
        3. Device yang memiliki paling banyak koneksi ke device lain
        """
        if not group:
            return {}, 0.0

        # Sort by timestamp (paling awal = paling mungkin root cause)
        sorted_group = sorted(group, key=lambda x: float(x.get("_ts_epoch", time.time())))
        
        # Score setiap kandidat
        scores = {}
        for i, inc in enumerate(sorted_group):
            inc_id = str(inc.get("incident_id") or inc.get("id", "?"))
            score = 0.0

            # Bonus untuk yang paling awal (lebih signifikan)
            score += (len(sorted_group) - i) * 0.15

            # Bonus severity
            sev = str(inc.get("severity","")).upper()
            if sev == "CRITICAL": score += 0.40
            elif sev == "HIGH":   score += 0.25
            elif sev == "MEDIUM": score += 0.10

            # Bonus jika device-nya tipe infrastruktur (switch, server, gateway)
            dev = str(inc.get("device_name") or inc.get("agent","")).lower()
            if any(t in dev for t in ["switch", "gateway", "router", "server", "nuc", "proxmox"]):
                score += 0.20

            scores[inc_id] = score

        # Pilih yang tertinggi
        best_id = max(scores, key=scores.get)
        best_inc = next(i for i in sorted_group if str(i.get("incident_id") or i.get("id","?")) == best_id)
        confidence = min(0.98, scores[best_id] / max(sum(scores.values()), 1) * len(sorted_group))

        return best_inc, confidence

    # ─── Main API ─────────────────────────────────────────────────────────────

    def correlate(self, incidents: List[Dict]) -> CorrelationResult:
        """
        Analisis batch insiden dan temukan grup berkorelasi.
        
        Args:
            incidents: List insiden dari /api/incidents
        
        Returns:
            CorrelationResult dengan groups dan standalone incidents
        """
        t0 = time.time()
        result = CorrelationResult()

        if not incidents:
            result.summary = "Tidak ada insiden untuk dianalisis."
            return result

        # Pre-process: normalisasi timestamp
        now = time.time()
        processed = []
        for inc in incidents:
            ts_raw = inc.get("timestamp") or inc.get("created_at") or ""
            try:
                if isinstance(ts_raw, str) and ts_raw:
                    from dateutil import parser as _dp
                    ts_epoch = _dp.parse(ts_raw).timestamp()
                elif isinstance(ts_raw, (int, float)):
                    ts_epoch = float(ts_raw)
                else:
                    ts_epoch = now - 60  # Anggap 1 menit lalu
            except Exception:
                ts_epoch = now - 60
            inc_copy = dict(inc)
            inc_copy["_ts_epoch"] = ts_epoch
            processed.append(inc_copy)

        # Filter hanya insiden dalam window (lebih dari 5 menit lalu tidak dikorrelasikan)
        in_window = [i for i in processed if now - float(i["_ts_epoch"]) <= self._window * 6]
        old_incidents = [i for i in processed if i not in in_window]

        # Build correlation matrix
        visited: Set[str] = set()
        groups_raw: List[List[Dict]] = []

        def get_id(inc: Dict) -> str:
            return str(inc.get("incident_id") or inc.get("id", id(inc)))

        for i, inc_a in enumerate(in_window):
            id_a = get_id(inc_a)
            if id_a in visited:
                continue

            current_group = [inc_a]
            visited.add(id_a)

            for inc_b in in_window[i+1:]:
                id_b = get_id(inc_b)
                if id_b in visited:
                    continue
                score = self._correlation_score(inc_a, inc_b)
                if score >= MIN_CORRELATION_SCORE:
                    current_group.append(inc_b)
                    visited.add(id_b)

            groups_raw.append(current_group)

        # Build CorrelatedIncidentGroup dari setiap grup
        for raw_group in groups_raw:
            if len(raw_group) == 1:
                # Insiden standalone — tidak berkorelasi
                result.standalone_incidents.append(get_id(raw_group[0]))
                continue

            root_inc, confidence = self._find_root_cause(raw_group)
            root_id = get_id(root_inc)
            root_dev = str(root_inc.get("device_name") or root_inc.get("agent","unknown"))

            cascade = [i for i in raw_group if get_id(i) != root_id]
            cascade_ids = [get_id(i) for i in cascade]
            cascade_devs = [str(i.get("device_name") or i.get("agent","?")) for i in cascade]

            # Recommended action based on root
            sev = str(root_inc.get("severity","")).upper()
            if sev in ["CRITICAL","HIGH"]:
                rec = f"Prioritaskan investigasi {root_dev} — {len(cascade)} insiden lain bergantung padanya"
            else:
                rec = f"Periksa {root_dev} sebagai kemungkinan root cause"

            group_hash = hashlib.md5(f"{root_id}:{len(raw_group)}".encode(), usedforsecurity=False).hexdigest()[:8]
            group = CorrelatedIncidentGroup(
                group_id=f"CG-{group_hash.upper()}",
                root_cause_incident_id=root_id,
                root_cause_device=root_dev,
                root_cause_confidence=confidence,
                cascade_incidents=cascade_ids,
                cascade_devices=cascade_devs,
                total_incidents=len(raw_group),
                estimated_blast_radius=len(raw_group),
                recommended_action=rec,
            )
            result.groups.append(group)
            # Cascade incidents seharusnya disuppress (tidak alert terpisah)
            result.suppressed_count += len(cascade_ids)
            self._suppressed_ids.update(cascade_ids)

        # Old incidents — langsung standalone
        result.standalone_incidents.extend([get_id(i) for i in old_incidents])

        result.processing_ms = int((time.time() - t0) * 1000)
        result.summary = self._build_summary(result)
        return result

    def _build_summary(self, result: CorrelationResult) -> str:
        lines = [f"📊 EVENT CORRELATION ANALYSIS:"]
        if result.groups:
            lines.append(f"  🔗 Grup berkorelasi : {len(result.groups)} grup root cause teridentifikasi")
            for g in result.groups[:3]:
                lines.append(
                    f"    • {g.group_id}: {g.root_cause_device} → "
                    f"{len(g.cascade_devices)} cascade ({', '.join(g.cascade_devices[:3])})"
                )
        lines.append(f"  📌 Standalone       : {len(result.standalone_incidents)} insiden independen")
        lines.append(f"  🔕 Disuppress       : {result.suppressed_count} alert cascade (cegah alert fatigue)")
        lines.append(f"  ⚡ Processing       : {result.processing_ms}ms")
        return "\n".join(lines)

    def is_suppressed(self, incident_id: str) -> bool:
        """Cek apakah insiden ini sudah diidentifikasi sebagai cascade (bukan root cause)."""
        return str(incident_id) in self._suppressed_ids

    def get_correlation_summary_text(self, incidents: List[Dict]) -> str:
        """Shortcut — langsung return summary text untuk JARVIS TTS."""
        result = self.correlate(incidents)
        return result.summary


# ─── Singleton ────────────────────────────────────────────────────────────────
_instance: Optional[EventCorrelationEngine] = None

def get_correlation_engine() -> EventCorrelationEngine:
    global _instance
    if _instance is None:
        _instance = EventCorrelationEngine()
    return _instance
