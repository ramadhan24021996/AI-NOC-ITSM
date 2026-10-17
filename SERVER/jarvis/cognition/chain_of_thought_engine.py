"""
SERVER.jarvis.cognition.chain_of_thought_engine — JARVIS Senior AI: Chain-of-Thought
======================================================================================
Membuat JARVIS berpikir SEBELUM menjawab, bukan langsung reaktif.

Pipeline:
  INPUT → [OBSERVE] → [ANALYZE] → [HYPOTHESIZE] → [VALIDATE] → [RESPOND]

Fitur:
  ✅ Real-time data integration (dari NOC Bridge)
  ✅ Confidence scoring (tahu kapan tidak yakin)
  ✅ Incident pattern correlation (lihat pola tersembunyi)
  ✅ Non-monotone response — variasi kata, gaya, dan nada
  ✅ Context-aware (waktu hari, severity, role operator)
"""
from __future__ import annotations

import hashlib
import logging
import random
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("jarvis.cognition.chain_of_thought")


# ─── Response Variator: Hindari jawaban monoton ───────────────────────────────
# Pool frasa pembuka/penutup per situasi — dipilih acak tiap respons

_OPENER_OK = [
    "Siap, saya sudah analisa datanya.",
    "Oke, ini yang saya temukan:",
    "Data sudah masuk, ini hasilnya:",
    "Berikut kondisi terkini:",
    "Sudah saya cek, ini situasinya:",
    "Real-time data sudah terbaca:",
    "Laporan masuk, Pak.",
    "Ini yang bisa saya sampaikan:",
]

_OPENER_WARNING = [
    "⚠️ Ada yang perlu diperhatikan:",
    "⚠️ Perhatian! Saya deteksi anomali:",
    "Hati-hati, ada indikator yang tidak normal:",
    "Perlu tindakan segera — ini temuannya:",
    "Ada hal yang mengkhawatirkan, Pak:",
    "Sistem mendeteksi kondisi tidak ideal:",
]

_OPENER_CRITICAL = [
    "🔴 ALERT! Situasi kritis terdeteksi:",
    "🚨 Butuh perhatian segera, Pak!",
    "🔴 Eskalasi diperlukan — ini kondisinya:",
    "Prioritas tinggi! Ini yang terjadi:",
    "Peringatan kritis! Saya temukan:",
]

_OPENER_UNKNOWN = [
    "Saya tidak punya cukup data untuk jawab ini dengan yakin.",
    "Hmm, untuk pertanyaan ini saya butuh informasi lebih:",
    "Data yang saya miliki belum cukup untuk jawab ini secara akurat.",
    "Jujur saja, saya tidak 100% yakin — ini yang saya tahu:",
    "Untuk jawaban pasti, saya perlu cek lebih lanjut. Tapi ini perkiraan saya:",
]

_CLOSER_OK = [
    "Ada yang perlu ditindaklanjuti lebih lanjut?",
    "Perlu saya bantu sesuatu lagi?",
    "Ada pertanyaan lebih lanjut?",
    "Kalau ada yang perlu saya cek lagi, silakan.",
    "",  # Kadang tidak perlu penutup
    "",
    "",
]

_CLOSER_RECOMMEND = [
    "\n💡 Rekomendasi: {}",
    "\n🔧 Saran tindakan: {}",
    "\n➡️  Yang perlu dilakukan: {}",
    "\n📋 Langkah selanjutnya: {}",
]

_CONFIDENCE_PHRASES = {
    "very_high": ["Keyakinan saya sangat tinggi ({:.0%}).", "Data sangat konsisten, confidence {:.0%}.", "Ini hampir pasti ({:.0%})."],
    "high":      ["Analisis menunjukkan confidence {:.0%}.", "Saya cukup yakin ({:.0%}).", "Ini kemungkinan besar benar ({:.0%})."],
    "medium":    ["Confidence {:.0%} — ada ketidakpastian kecil.", "Sekitar {:.0%} kemungkinan, tapi perlu validasi.", "Ini estimasi terbaik saya ({:.0%})."],
    "low":       ["Hanya {:.0%} confidence — perlu data lebih banyak.", "Saya kurang yakin ({:.0%}), ada gap data.", "Ini perlu dikonfirmasi manual ({:.0%} confidence)."],
}


def _pick(pool: List[str]) -> str:
    """Pilih acak dari pool respons."""
    return random.choice(pool)


def _confidence_phrase(score: float) -> str:
    if score >= 0.90:
        pool = _CONFIDENCE_PHRASES["very_high"]
    elif score >= 0.75:
        pool = _CONFIDENCE_PHRASES["high"]
    elif score >= 0.55:
        pool = _CONFIDENCE_PHRASES["medium"]
    else:
        pool = _CONFIDENCE_PHRASES["low"]
    return _pick(pool).format(score)


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class ObservationLayer:
    """OBSERVE: Apa yang JARVIS lihat dari data."""
    raw_query: str = ""
    real_data: Dict[str, Any] = field(default_factory=dict)
    data_sources: List[str] = field(default_factory=list)
    data_freshness_ms: int = 0
    observed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class AnalysisLayer:
    """ANALYZE: Apa artinya data tersebut."""
    key_findings: List[str] = field(default_factory=list)
    anomalies: List[str] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)
    severity: str = "LOW"  # LOW | MEDIUM | HIGH | CRITICAL | UNKNOWN


@dataclass
class HypothesisLayer:
    """HYPOTHESIZE: Apa yang mungkin terjadi."""
    primary_hypothesis: str = ""
    alternative_hypothesis: str = ""
    confidence: float = 0.5
    supporting_evidence: List[str] = field(default_factory=list)
    knowledge_gaps: List[str] = field(default_factory=list)


@dataclass
class ValidateLayer:
    """VALIDATE: Apakah hipotesis konsisten."""
    is_validated: bool = False
    validation_notes: str = ""
    recommended_action: str = ""
    requires_human: bool = False


@dataclass
class ChainOfThoughtResult:
    """Hasil lengkap chain-of-thought reasoning."""
    observe: ObservationLayer = field(default_factory=ObservationLayer)
    analyze: AnalysisLayer = field(default_factory=AnalysisLayer)
    hypothesize: HypothesisLayer = field(default_factory=HypothesisLayer)
    validate: ValidateLayer = field(default_factory=ValidateLayer)
    final_response: str = ""
    reasoning_ms: int = 0
    showed_reasoning: bool = False  # Apakah reasoning ditampilkan ke user


# ─── Chain-of-Thought Engine ──────────────────────────────────────────────────

class ChainOfThoughtEngine:
    """
    Senior AI reasoning engine untuk JARVIS.
    
    Setiap respons JARVIS melewati pipeline:
    OBSERVE → ANALYZE → HYPOTHESIZE → VALIDATE → RESPOND
    """

    def __init__(self, noc_bridge: Optional[Any] = None):
        self._noc = noc_bridge
        self._incident_cache: List[Dict] = []
        self._cache_age: float = 0.0
        self._cache_ttl: float = 30.0  # 30 detik cache

    def _get_live_incidents(self) -> List[Dict]:
        """Fetch incident data dengan caching 30 detik."""
        now = time.time()
        if self._noc and (now - self._cache_age > self._cache_ttl):
            try:
                r = self._noc._get("/api/incidents")
                if r and r.success and r.data:
                    data = r.data
                    if isinstance(data, list):
                        self._incident_cache = data
                    elif isinstance(data, dict):
                        self._incident_cache = data.get("incidents", [])
                    self._cache_age = now
            except Exception as e:
                logger.debug("[CoT] Incident fetch error: %s", e)
        return self._incident_cache

    # ─── PHASE 1: OBSERVE ─────────────────────────────────────────────────────

    def _observe(self, query: str, live_data: Dict[str, Any]) -> ObservationLayer:
        """Kumpulkan dan kategorikan semua data yang relevan."""
        t0 = time.time()
        obs = ObservationLayer(raw_query=query, real_data=live_data)

        # Tambahkan data incident live jika relevan
        incident_keywords = ["printer", "insiden", "incident", "spooler", "dns", "jaringan",
                              "network", "offline", "error", "gagal", "masalah", "crash",
                              "cpu", "ram", "disk", "latency"]
        if any(kw in query.lower() for kw in incident_keywords):
            incidents = self._get_live_incidents()
            if incidents:
                obs.real_data["live_incidents"] = incidents[:10]
                obs.data_sources.append("live_incident_feed")

        if live_data:
            obs.data_sources.extend(live_data.get("_sources", []))

        obs.data_freshness_ms = int((time.time() - t0) * 1000)
        return obs

    # ─── PHASE 2: ANALYZE ─────────────────────────────────────────────────────

    def _analyze(self, obs: ObservationLayer) -> AnalysisLayer:
        """Temukan pola, anomali, dan insight dari data observasi."""
        a = AnalysisLayer()
        incidents = obs.real_data.get("live_incidents", [])
        q = obs.raw_query.lower()

        if not incidents and not obs.real_data:
            a.severity = "UNKNOWN"
            a.key_findings.append("Data terbatas — analisis berdasarkan pengetahuan tersimpan")
            return a

        # Analisis insiden
        if incidents:
            open_inc = [i for i in incidents if str(i.get("status","")).upper() in ["OPEN","ACTIVE","NEW","PENDING"]]
            crit_inc = [i for i in open_inc if str(i.get("severity","")).upper() in ["CRITICAL","HIGH"]]

            a.key_findings.append(f"{len(open_inc)} insiden aktif dari {len(incidents)} total")

            if crit_inc:
                a.severity = "CRITICAL" if any(str(i.get("severity","")).upper() == "CRITICAL" for i in crit_inc) else "HIGH"
                a.anomalies.append(f"{len(crit_inc)} insiden CRITICAL/HIGH membutuhkan perhatian segera")
                for inc in crit_inc[:2]:
                    dev = inc.get("device_name") or inc.get("agent", "?")
                    evid = str(inc.get("evidence","") or inc.get("flag","") or "")[:60]
                    a.key_findings.append(f"  → {dev}: {evid}")
            elif open_inc:
                a.severity = "MEDIUM"
            else:
                a.severity = "LOW"
                a.key_findings.append("Tidak ada insiden aktif — sistem berjalan normal")

            # Pattern detection: insiden berulang pada device yang sama
            device_counts: Dict[str, int] = {}
            for inc in incidents:
                dev = str(inc.get("device_name") or inc.get("agent", ""))
                if dev:
                    device_counts[dev] = device_counts.get(dev, 0) + 1
            repeat_offenders = [(dev, cnt) for dev, cnt in device_counts.items() if cnt >= 3]
            if repeat_offenders:
                for dev, cnt in repeat_offenders[:2]:
                    a.patterns.append(f"Device {dev} tercatat {cnt}x insiden — indikasi masalah sistemik")

        # Analisis metrics jika ada
        metrics = obs.real_data.get("metrics", {})
        if metrics:
            cpu = float(metrics.get("cpu_pct", 0))
            ram = float(metrics.get("ram_pct", 0))
            if cpu > 85:
                a.anomalies.append(f"CPU tinggi: {cpu:.1f}%")
                a.severity = "HIGH" if a.severity not in ["CRITICAL"] else a.severity
            if ram > 90:
                a.anomalies.append(f"RAM kritis: {ram:.1f}%")

        return a

    # ─── PHASE 3: HYPOTHESIZE ─────────────────────────────────────────────────

    def _hypothesize(self, obs: ObservationLayer, analysis: AnalysisLayer) -> HypothesisLayer:
        """Formulasikan hipotesis berdasarkan observasi dan analisis."""
        h = HypothesisLayer()
        q = obs.raw_query.lower()

        # Pola keyword → hipotesis umum
        if "spooler" in q or "printer" in q:
            h.primary_hypothesis = "Print spooler crash akibat corrupted job atau driver incompatible"
            h.alternative_hypothesis = "Network share printer tidak dapat dijangkau (timeout)"
            h.confidence = 0.82
            h.supporting_evidence.append("Pola insiden spooler umumnya driver atau corrupted queue")
            if analysis.patterns:
                h.confidence = min(0.95, h.confidence + 0.08)
                h.supporting_evidence.extend(analysis.patterns)

        elif "dns" in q or "jaringan" in q or "network" in q:
            h.primary_hypothesis = "DNS cache stale atau routing mismatch akibat perubahan IP"
            h.alternative_hypothesis = "Firewall rule blocking port DNS (53/UDP)"
            h.confidence = 0.75
            h.supporting_evidence.append("DNS flush biasanya efektif untuk resolusi cepat")

        elif "cpu" in q or "ram" in q:
            h.primary_hypothesis = "Resource leak atau proses zombie yang mengonsumsi resource berlebihan"
            h.alternative_hypothesis = "Beban kerja puncak yang tidak proporsional dengan kapasitas"
            h.confidence = 0.70

        elif analysis.severity == "UNKNOWN":
            h.primary_hypothesis = "Tidak cukup data untuk formulasikan hipotesis yang kuat"
            h.knowledge_gaps.append(f"Tidak ada data spesifik untuk query: '{obs.raw_query}'")
            h.confidence = 0.35

        else:
            h.primary_hypothesis = "Kondisi normal atau gangguan ringan yang tidak kritis"
            h.confidence = 0.65

        # Tambah knowledge gaps jika data terbatas
        if not obs.data_sources:
            h.knowledge_gaps.append("Data real-time tidak tersedia — gunakan pengetahuan tersimpan")

        return h

    # ─── PHASE 4: VALIDATE ────────────────────────────────────────────────────

    def _validate(self, analysis: AnalysisLayer, hypothesis: HypothesisLayer) -> ValidateLayer:
        """Validasi konsistensi hipotesis dengan data."""
        v = ValidateLayer()

        if hypothesis.confidence >= 0.80 and hypothesis.supporting_evidence:
            v.is_validated = True
            v.validation_notes = "Hipotesis konsisten dengan data observasi"
        elif hypothesis.confidence >= 0.55:
            v.is_validated = True
            v.validation_notes = "Hipotesis plausible tapi butuh verifikasi tambahan"
            if hypothesis.knowledge_gaps:
                v.validation_notes += f" — Gap: {hypothesis.knowledge_gaps[0]}"
        else:
            v.is_validated = False
            v.validation_notes = "Data tidak cukup — diperlukan investigasi manual"
            v.requires_human = True

        # Rekomendasikan aksi berdasarkan severity
        severity_actions = {
            "CRITICAL": "Eskalasi segera ke L2/L3 dan aktifkan incident response protocol",
            "HIGH":     "Eksekusi SOP terkait dan monitor resolusi dalam 15 menit",
            "MEDIUM":   "Jadwalkan investigasi dalam 1 jam dan pantau perkembangan",
            "LOW":      "Catat dan monitor, tidak perlu tindakan segera",
            "UNKNOWN":  "Kumpulkan data lebih banyak sebelum mengambil tindakan",
        }
        v.recommended_action = severity_actions.get(analysis.severity, "Monitor situasi")

        return v

    # ─── PHASE 5: COMPOSE RESPONSE ────────────────────────────────────────────

    def _compose_response(
        self,
        base_response: str,
        obs: ObservationLayer,
        analysis: AnalysisLayer,
        hypo: HypothesisLayer,
        validate: ValidateLayer,
        show_reasoning: bool = False,
    ) -> str:
        """
        Compose respons final yang:
        1. Berdasarkan data real (bukan template statis)
        2. Tidak monoton (variasi frasa dari pool acak)
        3. Menyertakan confidence jika relevan
        4. Memberikan rekomendasi konkret
        """
        # Pilih opener berdasarkan severity
        if analysis.severity in ["CRITICAL", "HIGH"]:
            opener = _pick(_OPENER_CRITICAL if analysis.severity == "CRITICAL" else _OPENER_WARNING)
        elif analysis.severity == "UNKNOWN" and hypo.knowledge_gaps:
            opener = _pick(_OPENER_UNKNOWN)
        else:
            opener = _pick(_OPENER_OK)

        parts = []

        # Sentinel emojis that indicate a real handler already provided a structured answer.
        # Expanding this list prevents CoT from prefixing real responses with openers.
        _HANDLER_EMOJIS = (
            "✅", "🔴", "⚠️", "🚨", "📊", "📋", "🌐", "⚡", "💾",
            "🖨️", "🔔", "🤖", "🛡️", "🧪", "📡", "🔧", "🚀", "⚙️",
            "🔑", "🗂️", "💡", "🧠", "🔍", "📈", "📉", "🔗", "🌡️",
        )
        # Only prepend opener when:
        # - base_response doesn't already start with a handler emoji, AND
        # - It's not an UNKNOWN severity with a substantial existing answer
        #   (UNKNOWN means CoT found no data, but handler may have already answered)
        _response_has_real_content = len(base_response) >= 80
        _starts_with_handler_emoji = base_response and any(base_response.startswith(e) for e in _HANDLER_EMOJIS)
        _should_prepend_opener = (
            base_response and
            not _starts_with_handler_emoji and
            not (analysis.severity == "UNKNOWN" and _response_has_real_content)
        )
        if _should_prepend_opener:
            parts.append(opener + "\n")

        # Base response (dari handler yang sudah ada)
        parts.append(base_response)

        # Tambah chain-of-thought insights jika ada anomali atau pola
        cot_insights = []

        if analysis.anomalies and show_reasoning:
            cot_insights.append(f"\n📊 Analisis AI:\n" + "\n".join(f"  • {a}" for a in analysis.anomalies[:2]))

        if analysis.patterns:
            cot_insights.append(f"\n🔍 Pola Terdeteksi:\n" + "\n".join(f"  • {p}" for p in analysis.patterns[:2]))

        if hypo.knowledge_gaps and analysis.severity == "UNKNOWN" and not _response_has_real_content:
            cot_insights.append(f"\n❓ Data Tidak Tersedia:\n" + "\n".join(f"  • {g}" for g in hypo.knowledge_gaps[:2]))
            cot_insights.append(f"\nMau saya coba cara lain untuk mendapatkan informasi ini?")

        if cot_insights:
            parts.extend(cot_insights)

        # Confidence statement (hanya jika tidak terlalu obvious)
        if 0.40 <= hypo.confidence <= 0.80 and analysis.severity not in ["UNKNOWN"]:
            conf_stmt = _confidence_phrase(hypo.confidence)
            parts.append(f"\n\n💭 {conf_stmt}")

        # Recommended action (hanya jika ada sesuatu yang perlu dilakukan)
        if validate.recommended_action and analysis.severity in ["HIGH", "CRITICAL", "MEDIUM"]:
            closer_template = _pick(_CLOSER_RECOMMEND)
            parts.append(closer_template.format(validate.recommended_action))

        # Closer (random, kadang kosong untuk variasi)
        closer = _pick(_CLOSER_OK)
        if closer:
            parts.append(f"\n{closer}")

        return "".join(parts)

    # ─── PUBLIC API ────────────────────────────────────────────────────────────

    def enhance_response(
        self,
        raw_response: str,
        query: str,
        live_data: Optional[Dict[str, Any]] = None,
        show_reasoning: bool = False,
    ) -> ChainOfThoughtResult:
        """
        Entry point utama: enhance respons yang sudah ada dengan CoT reasoning.
        
        Args:
            raw_response: Respons dasar dari handler (sudah berisi data real)
            query: Query text operator
            live_data: Data live yang sudah diambil handler (opsional)
            show_reasoning: Tampilkan chain-of-thought ke user (untuk debug/verbose mode)
        
        Returns:
            ChainOfThoughtResult dengan final_response yang enhanced
        """
        t0 = time.time()
        result = ChainOfThoughtResult()

        try:
            # Pipeline: OBSERVE → ANALYZE → HYPOTHESIZE → VALIDATE
            result.observe = self._observe(query, live_data or {})
            result.analyze = self._analyze(result.observe)
            result.hypothesize = self._hypothesize(result.observe, result.analyze)
            result.validate = self._validate(result.analyze, result.hypothesize)

            # Compose final response
            result.final_response = self._compose_response(
                base_response=raw_response,
                obs=result.observe,
                analysis=result.analyze,
                hypo=result.hypothesize,
                validate=result.validate,
                show_reasoning=show_reasoning,
            )
            result.showed_reasoning = show_reasoning

        except Exception as e:
            logger.warning("[CoT] Error in chain-of-thought (returning base response): %s", e)
            result.final_response = raw_response  # Graceful fallback

        result.reasoning_ms = int((time.time() - t0) * 1000)
        logger.debug("[CoT] Reasoning complete: severity=%s confidence=%.2f time=%dms",
                     result.analyze.severity, result.hypothesize.confidence, result.reasoning_ms)
        return result

    def generate_proactive_insight(self, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Hasilkan insight proaktif berdasarkan data terkini.
        Dipanggil periodik oleh proactive alert engine.
        """
        incidents = self._get_live_incidents()
        if not incidents:
            return None

        open_inc = [i for i in incidents if str(i.get("status","")).upper() in ["OPEN","ACTIVE","NEW"]]
        crit_inc = [i for i in open_inc if str(i.get("severity","")).upper() in ["CRITICAL","HIGH"]]

        # Hanya generate insight jika ada kondisi menarik
        if not crit_inc and len(open_inc) <= 1:
            return None

        # Pattern analysis
        device_counts: Dict[str, int] = {}
        for inc in incidents[-20:]:  # Cek 20 insiden terbaru
            dev = str(inc.get("device_name") or inc.get("agent", ""))
            if dev and dev != "Global":
                device_counts[dev] = device_counts.get(dev, 0) + 1

        repeat = [(dev, cnt) for dev, cnt in device_counts.items() if cnt >= 3]

        if repeat:
            dev, cnt = repeat[0]
            insights = [
                f"Pak, saya perhatikan {dev} sudah {cnt}x incident dalam periode terakhir. Ini bisa indikasi masalah hardware atau driver. Perlu saya analisa lebih dalam?",
                f"Ada pola menarik: {dev} tercatat {cnt} insiden berulang. Kemungkinan ada root cause yang belum tuntas. Mau saya cek?",
                f"Perhatian: {dev} masuk radar {cnt}x. Ini perlu investigasi lebih mendalam daripada hanya restart berulang.",
            ]
            return _pick(insights)

        if crit_inc:
            inc = crit_inc[0]
            dev = inc.get("device_name") or inc.get("agent", "sistem")
            sev = inc.get("severity", "HIGH")
            return _pick([
                f"🔴 Pak, ada insiden {sev} aktif di {dev} yang belum ditangani. Perlu saya bantu analisa atau eksekusi SOP?",
                f"Masih ada insiden {sev} yang open di {dev}. Butuh tindakan segera?",
                f"Reminder: {dev} masih punya insiden {sev} yang belum resolved. Mau saya bantu?",
            ])

        return None
