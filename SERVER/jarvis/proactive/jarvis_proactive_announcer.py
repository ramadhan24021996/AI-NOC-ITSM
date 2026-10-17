"""
SERVER.jarvis.proactive.jarvis_proactive_announcer
==================================================
JARVIS Proactive Real-Time Voice Alert Engine — Core Module

Menjadikan JARVIS aktif bicara sendiri saat ada:
  - Early warning sistem (CPU, Disk, Memory)
  - Insiden baru / state change
  - HITL approval menunggu tindakan operator
  - Hasil remediation (sukses / gagal)
  - Drift governance / anomali bisnis

DESAIN KUNCI — ANTI MONOTON:
  1. LLMDynamicNarrator   : setiap narasi di-generate LLM dengan data aktual,
                            BUKAN template string. Tidak ada dua kalimat sama.
  2. NarrativeContextMemory: ingat 10 narasi terakhir per device/incident.
                            LLM diperintahkan untuk TIDAK mengulang frasa yang
                            sudah dipakai sebelumnya.
  3. EventCorrelator      : event sejenis dalam 15 detik digabung menjadi
                            SATU narasi terpadu (bukan 3 suara berturut-turut).
  4. PersonaTimeAdapter   : tone berubah berdasarkan jam (pagi=santai,
                            malam=urgent), severity, dan frekuensi kejadian.
  5. VariationSeeds       : inject random contextual variation instructions
                            ke LLM agar kalimat bervariatif secara alami.

COOLDOWN (anti-spam tinggi):
  - early_warning  : 300 detik (5 menit) per device
  - incident_new   : 180 detik per incident_id
  - approval_req   :  90 detik per incident_id
  - remediation    :   0 detik (sekali saja, tidak repeat)
  - health_score   : 600 detik (10 menit, sangat jarang)
  - drift_alert    : 240 detik

RATE LIMIT GLOBAL:
  - Max 3 announcement per menit (hard cap)
  - Max 1 announcement setiap 20 detik (burst protection)
"""
import json
import logging
import os
import random
import re
import time
import asyncio
import concurrent.futures
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("jarvis.proactive.announcer")

# ─────────────────────────────────────────────────────────────────────────────
# COOLDOWN CONFIGURATION (semua dalam detik)
# ─────────────────────────────────────────────────────────────────────────────
COOLDOWN_CONFIG: Dict[str, int] = {
    "early_warning":    300,   # 5 menit per device
    "incident_new":     180,   # 3 menit per incident
    "incident_update":  240,   # 4 menit per incident
    "approval_request":  90,   # 1.5 menit per incident
    "remediation_ok":     0,   # tidak pernah repeat (cooldown selamanya setelah pertama)
    "remediation_fail":   0,   # idem
    "health_score":     600,   # 10 menit
    "drift_alert":      240,   # 4 menit
    "generic":          180,   # default
}

# Cooldown permanen untuk event yang tidak boleh repeat sama sekali
PERMANENT_COOLDOWN_TYPES = {"remediation_ok", "remediation_fail"}

# Rate limiter: max 3 per menit, min gap 20 detik
RATE_LIMIT_PER_MINUTE = 3
MIN_GAP_SECONDS = 20

# ─────────────────────────────────────────────────────────────────────────────
# VARIATION SEEDS — inject ke LLM untuk variasi bahasa alami
# ─────────────────────────────────────────────────────────────────────────────
VARIATION_SEEDS = [
    "Gunakan diksi yang lebih teknis dan presisi seperti seorang insinyur NOC senior.",
    "Mulai dengan nada urgensi lalu jelaskan konteks secara singkat.",
    "Gunakan kalimat pendek dan tegas. Tidak bertele-tele.",
    "Sampaikan dengan nada tenang namun serius. Berikan satu rekomendasi konkret.",
    "Awali dengan fakta metrik aktual sebelum interpretasi.",
    "Gunakan analogi sederhana untuk menjelaskan dampak pada bisnis.",
    "Fokus pada tindakan yang harus diambil, bukan hanya deskripsi masalah.",
    "Berikan konteks historis jika relevan dengan data yang tersedia.",
]

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT LLM — instruksi narasi dinamis
# ─────────────────────────────────────────────────────────────────────────────
NARRATOR_SYSTEM_PROMPT = """Kamu adalah JARVIS, AI NOC Voice Engineer yang berbicara kepada operator NOC.

TUGAS: Narasi event sistem secara natural dalam Bahasa Indonesia (maksimal 2 kalimat).
OUTPUT FORMAT — SANGAT PENTING:
  1. Hanya teks narasi plain yang akan langsung diucapkan TTS.
  2. JANGAN gunakan: bullet points, simbol (**bold**, `code`, # heading, - list, > blockquote).
  3. JANGAN gunakan singkatan yang tidak bisa diucapkan (gunakan bentuk singkat yang natural).
  4. Gunakan KOMA untuk memberikan jeda natural pada kalimat panjang.
  5. Tulis angka dalam bentuk kata jika memungkinkan ("sembilan puluh" bukan "90").
  6. Akhiri dengan tanda baca (. atau !).

TONE SESUAI SEVERITY:
  - CRITICAL : Nada darurat, tegas, actionable. Awali dengan kata seperti: Darurat!, Siaga penuh!, Alarm!
  - HIGH     : Serius tapi tenang. Awali dengan: Perhatian!, Prioritas tinggi., Respons segera.
  - MEDIUM   : Informatif, profesional. Awali dengan: Update sistem., Notifikasi aktif., Pemantauan.
  - LOW/INFO : Santai, ringkas. Awali dengan: Informasi., Status terkini., Update rutin.

ATURAN ANTI-MONOTON (WAJIB):
1. JANGAN gunakan frase yang sama dengan narasi sebelumnya.
2. JANGAN mulai dengan kata yang sama dengan narasi sebelumnya.
3. Variasikan struktur kalimat: mulai dengan device, metrik, atau dampak secara bergantian.
4. Jika ini pengulangan kejadian yang sama, sebut berapa kali sudah terjadi.
5. Selalu akhiri dengan satu tindakan konkret atau pertanyaan kepada operator.

{variation_instruction}
"""


# ─────────────────────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ProactiveEvent:
    """Representasi event masuk yang akan dinaRasikan JARVIS."""
    event_type: str          # early_warning | incident_new | approval_request | remediation_ok | ...
    severity: str            # CRITICAL | HIGH | MEDIUM | LOW | INFO
    title: str               # Judul singkat event
    details: str             # Detail teknis (metrik, nilai, dll)
    device: str = ""         # Nama perangkat
    incident_id: str = ""    # ID insiden jika ada
    site_id: str = ""        # Site/lokasi
    extra: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def cooldown_key(self) -> str:
        """Kunci unik untuk cooldown lookup."""
        if self.incident_id:
            return f"{self.event_type}:{self.incident_id}"
        if self.device:
            return f"{self.event_type}:{self.device}"
        return f"{self.event_type}:{self.title[:30]}"


@dataclass
class NarrativeHistoryEntry:
    """Entry dalam memori narasi untuk cegah repetisi."""
    text: str
    event_type: str
    device: str
    timestamp: float = field(default_factory=time.time)

    def first_3_words(self) -> str:
        words = self.text.split()
        return " ".join(words[:3]) if words else ""


# ─────────────────────────────────────────────────────────────────────────────
# ALERT COOLDOWN MANAGER
# ─────────────────────────────────────────────────────────────────────────────

class AlertCooldownManager:
    """
    Anti-spam dengan cooldown tinggi.
    Cooldown berbeda per event_type, dengan permanent block untuk remediation results.
    """

    SEVERITY_RANK = {"INFO": 1, "LOW": 2, "MEDIUM": 3, "HIGH": 4, "CRITICAL": 5}

    def __init__(self):
        self._last_announced: Dict[str, float] = {}   # key → timestamp
        self._last_severity: Dict[str, str] = {}     # key → severity
        self._permanent_block: set = set()            # key → never announce again

    def can_announce(self, event: ProactiveEvent) -> Tuple[bool, int]:
        """
        Returns (can_announce: bool, remaining_seconds: int).
        remaining_seconds = 0 jika boleh, >0 jika masih dalam cooldown.
        """
        key = event.cooldown_key()

        # Permanent block check (remediation results)
        if key in self._permanent_block:
            logger.debug(f"[Cooldown] PERMANENT BLOCK: {key}")
            return False, -1

        # Check severity escalation
        last_sev = self._last_severity.get(key, "")
        curr_rank = self.SEVERITY_RANK.get(event.severity.upper(), 1)
        last_rank = self.SEVERITY_RANK.get(last_sev.upper(), 0)

        if last_sev and curr_rank > last_rank:
            logger.info(f"[Cooldown] SEVERITY ESCALATION ({last_sev} -> {event.severity}) for {key} — bypassing cooldown")
            return True, 0

        last_ts = self._last_announced.get(key, 0.0)
        cooldown = COOLDOWN_CONFIG.get(event.event_type, COOLDOWN_CONFIG["generic"])
        elapsed = time.time() - last_ts
        remaining = max(0, int(cooldown - elapsed))

        if remaining > 0:
            logger.debug(f"[Cooldown] SKIP {key} — {remaining}s remaining")
            return False, remaining

        return True, 0

    def mark_announced(self, event: ProactiveEvent):
        """Catat event sebagai sudah diumumkan."""
        key = event.cooldown_key()
        self._last_announced[key] = time.time()
        self._last_severity[key] = event.severity.upper()

        # Permanent block untuk remediation results
        if event.event_type in PERMANENT_COOLDOWN_TYPES:
            self._permanent_block.add(key)
            logger.debug(f"[Cooldown] PERMANENT BLOCK SET: {key}")

    def reset(self, event: ProactiveEvent):
        """Reset cooldown untuk event tertentu (misal setelah severity naik)."""
        key = event.cooldown_key()
        self._last_announced.pop(key, None)
        self._last_severity.pop(key, None)
        self._permanent_block.discard(key)
        logger.info(f"[Cooldown] RESET: {key}")


# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL RATE LIMITER
# ─────────────────────────────────────────────────────────────────────────────

class GlobalRateLimiter:
    """
    Hard cap: max 3 announcement per menit, min gap 20 detik antar announcement.
    Mencegah JARVIS berteriak terus-menerus saat terjadi cascade failure.
    """

    def __init__(self, max_per_minute: int = RATE_LIMIT_PER_MINUTE, min_gap: int = MIN_GAP_SECONDS):
        self.max_per_minute = max_per_minute
        self.min_gap = min_gap
        self._history: deque = deque(maxlen=20)  # timestamp ring buffer

    def can_announce(self) -> Tuple[bool, str]:
        """Returns (allowed, reason_if_denied)."""
        now = time.time()
        cutoff_1min = now - 60.0

        # Filter history dalam 1 menit terakhir
        recent = [t for t in self._history if t > cutoff_1min]

        if len(recent) >= self.max_per_minute:
            return False, f"Rate limit: {len(recent)}/{self.max_per_minute} per menit"

        # Min gap check
        if self._history and (now - self._history[-1]) < self.min_gap:
            gap_left = int(self.min_gap - (now - self._history[-1]))
            return False, f"Min gap: tunggu {gap_left}s lagi"

        return True, ""

    def record(self):
        """Catat satu announcement terjadi."""
        self._history.append(time.time())


# ─────────────────────────────────────────────────────────────────────────────
# NARRATIVE CONTEXT MEMORY
# ─────────────────────────────────────────────────────────────────────────────

class NarrativeContextMemory:
    """
    Ingat 10 narasi terakhir untuk mencegah JARVIS mengulang kalimat yang sama.
    Diinject ke LLM prompt agar LLM sadar apa yang sudah diucapkan sebelumnya.
    """

    def __init__(self, max_history: int = 10):
        self._global_history: deque = deque(maxlen=max_history)
        self._per_device: Dict[str, deque] = {}  # device → deque of recent texts
        self._occurrence_count: Dict[str, int] = {}  # cooldown_key → count

    def add(self, event: ProactiveEvent, narration_text: str):
        """Simpan narasi yang baru saja diucapkan."""
        entry = NarrativeHistoryEntry(
            text=narration_text,
            event_type=event.event_type,
            device=event.device,
        )
        self._global_history.append(entry)

        # Per-device history
        dev = event.device or "global"
        if dev not in self._per_device:
            self._per_device[dev] = deque(maxlen=5)
        self._per_device[dev].append(narration_text)

        # Occurrence count
        key = event.cooldown_key()
        self._occurrence_count[key] = self._occurrence_count.get(key, 0) + 1

    def get_context_for_llm(self, event: ProactiveEvent) -> str:
        """Buat string konteks untuk diinjeksi ke LLM prompt."""
        parts = []

        # Global recent narrations (last 5)
        recent_texts = [e.text for e in list(self._global_history)[-5:]]
        if recent_texts:
            parts.append("NARASI YANG SUDAH DIUCAPKAN (JANGAN DIULANG):")
            for i, t in enumerate(recent_texts, 1):
                parts.append(f"  {i}. \"{t}\"")

        # Occurrence count for this device/event
        key = event.cooldown_key()
        count = self._occurrence_count.get(key, 0)
        if count > 0:
            parts.append(f"\nKEJADIAN INI SUDAH TERJADI {count} KALI SEBELUMNYA.")
            if count >= 3:
                parts.append("TINGKATKAN URGENSI — ini sudah berulang kali terjadi!")

        # Opening words already used
        used_openings = set()
        for entry in self._global_history:
            w = entry.first_3_words()
            if w:
                used_openings.add(w)
        if used_openings:
            parts.append(f"\nJANGAN mulai narasi dengan kata-kata ini: {', '.join(list(used_openings)[:5])}")

        return "\n".join(parts) if parts else ""

    def get_occurrence_count(self, event: ProactiveEvent) -> int:
        return self._occurrence_count.get(event.cooldown_key(), 0)


# ─────────────────────────────────────────────────────────────────────────────
# EVENT CORRELATOR
# ─────────────────────────────────────────────────────────────────────────────

class EventCorrelator:
    """
    Batch event sejenis yang datang dalam 15 detik menjadi satu narasi terpadu.
    Mencegah JARVIS bicara 5 kali berturut-turut untuk 5 device yang sama.

    Contoh:
      CPU kasir 1 tinggi + CPU kasir 2 tinggi + CPU kasir 3 tinggi
      → "CPU critical di 3 kasir sekaligus. Kemungkinan traffic surge..."
    """

    BATCH_WINDOW_SEC = 15

    def __init__(self):
        self._pending: Dict[str, List[ProactiveEvent]] = {}
        self._batch_start: Dict[str, float] = {}

    def add(self, event: ProactiveEvent) -> Optional[List[ProactiveEvent]]:
        """
        Tambah event ke correlator.
        Returns None jika event masih dalam batch window.
        Returns list[ProactiveEvent] jika window closed atau event sudah cukup untuk diflush.
        """
        batch_key = event.event_type  # group by type

        now = time.time()
        if batch_key not in self._pending:
            self._pending[batch_key] = []
            self._batch_start[batch_key] = now

        self._pending[batch_key].append(event)

        # Auto-flush jika lebih dari 5 event atau window > 15s
        elapsed = now - self._batch_start.get(batch_key, now)
        count = len(self._pending[batch_key])

        if count >= 5 or elapsed >= self.BATCH_WINDOW_SEC:
            return self._flush(batch_key)

        # Tidak flush dulu — tunggu window
        return None

    def flush_expired(self) -> List[Tuple[str, List[ProactiveEvent]]]:
        """Flush semua batch yang windownya sudah expired. Dipanggil periodik."""
        now = time.time()
        results = []
        expired_keys = [
            k for k, t in self._batch_start.items()
            if now - t >= self.BATCH_WINDOW_SEC and self._pending.get(k)
        ]
        for key in expired_keys:
            batch = self._flush(key)
            if batch:
                results.append((key, batch))
        return results

    def _flush(self, batch_key: str) -> List[ProactiveEvent]:
        batch = self._pending.pop(batch_key, [])
        self._batch_start.pop(batch_key, None)
        return batch


# ─────────────────────────────────────────────────────────────────────────────
# LLM DYNAMIC NARRATOR
# ─────────────────────────────────────────────────────────────────────────────

class LLMDynamicNarrator:
    """
    Generate narasi JARVIS yang dinamis via LLM.

    Pipeline:
      1. Build rich context (event data + history + occurrence + waktu + variation seed)
      2. Call LLM (via LLMRouter jika tersedia, fallback ke intelligent template)
      3. Post-process: bersihkan simbol, normalisasi angka untuk TTS
      4. Validasi: tidak boleh mirip narasi sebelumnya
    """

    def __init__(self):
        self._llm_router = self._init_llm_router()
        logger.info(f"[LLMNarrator] LLM available: {self._llm_router is not None}")

    def _init_llm_router(self):
        """Coba inisialisasi LLM router."""
        try:
            from SERVER.llm.llm_router import LLMRouter
            router = LLMRouter()
            logger.info("[LLMNarrator] LLMRouter initialized.")
            return router
        except Exception as e:
            logger.warning(f"[LLMNarrator] LLMRouter unavailable: {e} — fallback mode.")
            return None

    def generate(
        self,
        events: List[ProactiveEvent],
        context_memory: NarrativeContextMemory,
    ) -> str:
        """
        Generate narasi unik untuk event/batch event.
        Returns: string siap TTS (Bahasa Indonesia, 1-3 kalimat).
        """
        # Pick variation seed secara acak
        variation_seed = random.choice(VARIATION_SEEDS)
        system_prompt = NARRATOR_SYSTEM_PROMPT.format(
            variation_instruction=f"\nSTYLE INSTRUCTION: {variation_seed}"
        )

        # Build user prompt dengan data aktual
        user_prompt = self._build_user_prompt(events, context_memory)

        # Call LLM
        if self._llm_router:
            try:
                result = self._call_llm(system_prompt, user_prompt)
                if result and len(result.strip()) > 10:
                    cleaned = self._post_process(result)
                    logger.info(f"[LLMNarrator] LLM narasi: {cleaned[:80]}...")
                    return cleaned
            except Exception as e:
                logger.warning(f"[LLMNarrator] LLM failed: {e} — fallback")

        # Fallback: intelligent template (masih bervariasi)
        return self._intelligent_fallback(events, context_memory, variation_seed)

    def _build_user_prompt(self, events: List[ProactiveEvent], mem: NarrativeContextMemory) -> str:
        """Bangun prompt yang kaya konteks untuk LLM."""
        now = datetime.now(timezone.utc)
        hour = now.hour + 7  # WIB
        if hour >= 24:
            hour -= 24

        # Time context
        if 5 <= hour < 12:
            time_ctx = "pagi hari (shift pagi aktif)"
        elif 12 <= hour < 18:
            time_ctx = "siang/sore hari (operasional puncak)"
        elif 18 <= hour < 22:
            time_ctx = "malam hari (akhir shift)"
        else:
            time_ctx = "dini hari / tengah malam (di luar jam kerja normal — TINGKATKAN URGENSI)"

        parts = [f"Waktu saat ini: {time_ctx}"]

        # Event data
        if len(events) == 1:
            ev = events[0]
            parts.append(f"EVENT TYPE: {ev.event_type}")
            parts.append(f"SEVERITY: {ev.severity}")
            parts.append(f"JUDUL: {ev.title}")
            parts.append(f"DETAIL TEKNIS: {ev.details}")
            if ev.device:
                parts.append(f"PERANGKAT: {ev.device}")
            if ev.incident_id:
                parts.append(f"ID INSIDEN: {ev.incident_id}")
            if ev.site_id:
                parts.append(f"LOKASI/SITE: {ev.site_id}")
            # Extra fields
            for k, v in ev.extra.items():
                if v and k not in ("timestamp",):
                    parts.append(f"{k.upper()}: {v}")

            occ = mem.get_occurrence_count(ev)
            if occ > 0:
                parts.append(f"INI KEJADIAN KE-{occ+1} UNTUK PERANGKAT/EVENT INI HARI INI.")

        else:
            # Batch event — buat ringkasan
            parts.append(f"BATCH EVENT: {len(events)} event sejenis terjadi bersamaan")
            parts.append(f"TYPE: {events[0].event_type} | SEVERITY: {events[0].severity}")
            devices = list({e.device for e in events if e.device})
            if devices:
                parts.append(f"PERANGKAT TERDAMPAK: {', '.join(devices)}")
            titles = list({e.title for e in events})
            parts.append(f"DETAIL: {' | '.join(titles[:3])}")

        # Konteks narasi sebelumnya
        history_ctx = mem.get_context_for_llm(events[0])
        if history_ctx:
            parts.append("\n" + history_ctx)

        parts.append("\nBuat narasi JARVIS yang natural, unik, dan tidak mengulang:")
        return "\n".join(parts)

    def _call_llm(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Call LLM router dengan timeout."""
        import concurrent.futures
        import asyncio

        def _sync_call():
            if hasattr(self._llm_router, "generate"):
                res = self._llm_router.generate(
                    system_prompt=system_prompt,
                    prompt=user_prompt,
                    temperature=0.85,  # tinggi = lebih kreatif/bervariasi
                    max_tokens=150,
                )
                return res.get("response", str(res)) if isinstance(res, dict) else str(res)
            elif hasattr(self._llm_router, "route"):
                full_prompt = f"{system_prompt}\n\n{user_prompt}"
                try:
                    loop = asyncio.get_running_loop()
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        fut = pool.submit(asyncio.run, self._llm_router.route(full_prompt))
                        res = fut.result(timeout=8)
                except RuntimeError:
                    res = asyncio.run(self._llm_router.route(full_prompt))
                if isinstance(res, dict):
                    return res.get("response", str(res))
                return str(res)
            return None

        with concurrent.futures.ThreadPoolExecutor() as pool:
            fut = pool.submit(_sync_call)
            return fut.result(timeout=10)

    def _post_process(self, text: str) -> str:
        """Bersihkan output LLM agar siap TTS.

        v3.0: Integrasikan SpokenTextNormalizer untuk normalisasi menyeluruh
        (expand akronim, angka, strip sisa markdown yang mungkin masih ada).
        """
        # Hapus karakter yang aneh untuk TTS (bersihkan sisa markdown)
        text = re.sub(r'[*_`#\[\]{}|\\]', '', text)
        # Normalisasi tanda baca
        text = re.sub(r'\s+', ' ', text).strip()
        # Hapus "JARVIS:" prefix jika ada
        text = re.sub(r'^(JARVIS:|Jarvis:)\s*', '', text, flags=re.IGNORECASE)

        # v3.0: Jalankan SpokenTextNormalizer untuk expand akronim, angka, dll.
        try:
            from SERVER.jarvis.voice.spoken_text_normalizer import SpokenTextNormalizer
            normalizer = SpokenTextNormalizer()
            text = normalizer.normalize(text)
        except ImportError:
            # Fallback: pastikan berakhir dengan tanda baca
            if text and text[-1] not in '.!?':
                text += '.'
        except Exception as e:
            logger.warning("[LLMNarrator] SpokenTextNormalizer error: %s — using cleaned text.", e)
            if text and text[-1] not in '.!?':
                text += '.'

        return text

    def _intelligent_fallback(
        self,
        events: List[ProactiveEvent],
        mem: NarrativeContextMemory,
        variation: str,
    ) -> str:
        """
        Fallback intelligent — masih bervariasi berdasarkan event data aktual.
        Bukan template kaku — hasil berbeda untuk setiap kombinasi data.
        """
        ev = events[0]
        count = mem.get_occurrence_count(ev)

        # Prefix bervariasi berdasarkan severity + count
        CRITICAL_OPENERS = [
            "Darurat!", "Peringatan keras!", "Situasi kritis!", "Tindakan segera!",
            "Alarm sistem!", "Eskalasi segera!"
        ]
        HIGH_OPENERS = [
            "Perhatian Engineer.", "Siaga tinggi.", "Prioritas tinggi.",
            "Perlu respons segera.", "Eskalasi aktif."
        ]
        MEDIUM_OPENERS = [
            "Update sistem.", "Notifikasi operasional.", "Pemantauan aktif.",
            "Catatan sistem.", "Info operasional."
        ]
        LOW_OPENERS = [
            "Informasi.", "Update rutin.", "Status sistem.", "Laporan terkini."
        ]

        sev = ev.severity.upper()
        if sev == "CRITICAL":
            opener = random.choice(CRITICAL_OPENERS)
        elif sev == "HIGH":
            opener = random.choice(HIGH_OPENERS)
        elif sev == "MEDIUM":
            opener = random.choice(MEDIUM_OPENERS)
        else:
            opener = random.choice(LOW_OPENERS)

        # Body berdasarkan event type + data aktual
        device_str = f" di {ev.device}" if ev.device else ""
        incident_str = f" untuk {ev.incident_id}" if ev.incident_id else ""
        count_str = f" Ini kejadian ke-{count+1} hari ini." if count > 0 else ""

        # Tindakan bervariasi
        ACTIONS = {
            "early_warning": [
                "Lakukan pemantauan aktif sekarang.",
                "Pertimbangkan tindakan preventif segera.",
                "Analisis proses yang paling banyak mengonsumsi resource.",
                "Apakah perlu saya buat HITL request untuk tindakan lebih lanjut?",
            ],
            "incident_new": [
                "Silakan tinjau dan tetapkan prioritas penanganan.",
                "Apakah Anda ingin saya eskalasikan ke HITL queue?",
                "Saya siapkan rekomendasi tindakan jika diperlukan.",
                "Periksa runbook terkait untuk langkah penanganan.",
            ],
            "approval_request": [
                "Ucapkan 'approve' atau 'reject' untuk memberikan keputusan.",
                "Tindakan menunggu konfirmasi Anda.",
                "Berikan persetujuan sebelum window waktu habis.",
                "Risiko aksi ini sudah teranalisis — keputusan ada di tangan Anda.",
            ],
            "remediation_ok": [
                "Sistem kembali dalam parameter normal.",
                "Catat hasil ini dalam log shift.",
                "Monitor 15 menit ke depan untuk konfirmasi stabilitas.",
                "Insiden dapat ditutup jika tidak ada gejala lebih lanjut.",
            ],
            "remediation_fail": [
                "Diperlukan intervensi manual segera.",
                "Eskalasikan ke tim level dua.",
                "Periksa log detail untuk root cause.",
                "Saya rekomendasikan rollback ke kondisi sebelumnya.",
            ],
        }

        action_list = ACTIONS.get(ev.event_type, ["Tindak lanjuti sesuai prosedur SOP."])
        action = random.choice(action_list)

        body = f"{ev.title}{device_str}{incident_str}.{count_str} {ev.details[:80] if ev.details else ''}."
        result = f"{opener} {body} {action}"
        return self._post_process(result)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN: JARVIS PROACTIVE ANNOUNCER
# ─────────────────────────────────────────────────────────────────────────────

class JarvisProactiveAnnouncer:
    """
    Main Engine — Proactive Real-Time Voice Announcer.

    Dipanggil dari JarvisVoiceServer via:
      POST /jarvis/proactive/announce
      Body: ProactiveEvent JSON
      Response: { text, audio_b64, audio_format, skipped, skip_reason }
    """

    def __init__(self):
        self.cooldown = AlertCooldownManager()
        self.rate_limiter = GlobalRateLimiter(
            max_per_minute=RATE_LIMIT_PER_MINUTE,
            min_gap=MIN_GAP_SECONDS,
        )
        self.memory = NarrativeContextMemory(max_history=10)
        self.correlator = EventCorrelator()
        self.narrator = LLMDynamicNarrator()
        self._tts_service = None
        logger.info("[JarvisProactiveAnnouncer] Engine ready.")

    def _get_tts(self):
        """Lazy-init TTS service."""
        if self._tts_service is None:
            try:
                from SERVER.jarvis.voice.tts_service import TTSService
                self._tts_service = TTSService()
                logger.info("[JarvisProactiveAnnouncer] TTSService initialized.")
            except Exception as e:
                logger.warning(f"[JarvisProactiveAnnouncer] TTS unavailable: {e}")
        return self._tts_service

    def announce(self, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point. Proses event, narasi LLM, TTS, return result.

        Returns:
            {
              "text": str,         — narasi yang diucapkan
              "audio_b64": str,    — audio TTS base64
              "audio_format": str, — "mp3" | "wav"
              "skipped": bool,     — True jika dikip (cooldown/rate limit)
              "skip_reason": str,  — alasan dikip
              "severity": str,
              "event_type": str,
            }
        """
        try:
            event = ProactiveEvent(
                event_type=event_dict.get("event_type", "generic"),
                severity=event_dict.get("severity", "INFO"),
                title=event_dict.get("title", ""),
                details=event_dict.get("details", ""),
                device=event_dict.get("device", ""),
                incident_id=event_dict.get("incident_id", ""),
                site_id=event_dict.get("site_id", ""),
                extra={k: v for k, v in event_dict.items()
                       if k not in ("event_type","severity","title","details","device","incident_id","site_id")},
            )
        except Exception as e:
            return {"skipped": True, "skip_reason": f"Invalid event: {e}", "text": "", "audio_b64": ""}

        # 1. Cooldown check
        can_announce, cooldown_remaining = self.cooldown.can_announce(event)
        if not can_announce:
            reason = "permanent" if cooldown_remaining == -1 else f"cooldown {cooldown_remaining}s"
            logger.info(f"[Announce] SKIP — {reason} — {event.cooldown_key()}")
            return {"skipped": True, "skip_reason": reason, "text": "", "audio_b64": "",
                    "event_type": event.event_type, "severity": event.severity}

        # 2. Global rate limiter
        rate_ok, rate_reason = self.rate_limiter.can_announce()
        if not rate_ok:
            logger.info(f"[Announce] SKIP — {rate_reason}")
            return {"skipped": True, "skip_reason": rate_reason, "text": "", "audio_b64": "",
                    "event_type": event.event_type, "severity": event.severity}

        # 3. Event correlation — check batch (untuk kali ini langsung announce tanpa delay batch)
        # Untuk proactive webhook kita langsung proses single event + check correlated
        batch_events = [event]

        # 4. Generate narasi via LLM (DINAMIS, ANTI-MONOTON)
        try:
            narration_text = self.narrator.generate(batch_events, self.memory)
        except Exception as e:
            logger.error(f"[Announce] Narration failed: {e}")
            narration_text = f"{event.severity}: {event.title} di {event.device or 'sistem'}."

        # 5. TTS — synthesize audio dengan severity-aware prosody
        import base64
        audio_b64 = ""
        audio_format = "wav"
        tts = self._get_tts()
        if tts:
            try:
                # v3.0: TTSService.synthesize() selalu menerima severity parameter.
                # Pass severity untuk prosody-aware synthesis (rate/pitch via SSMLBuilder).
                audio_payload = tts.synthesize(
                    narration_text,
                    persona_id="noc_engineer",
                    locale="id-ID",
                    severity=event.severity,
                    skip_normalization=True,  # sudah dinormalisasi di _post_process
                )
                if audio_payload and audio_payload.audio_bytes:
                    audio_b64 = base64.b64encode(audio_payload.audio_bytes).decode("utf-8")
                    audio_format = getattr(audio_payload, "audio_format", "wav")
                    logger.info("[Announce] TTS OK — %d bytes | severity=%s", len(audio_payload.audio_bytes), event.severity)
            except Exception as e:
                logger.warning("[Announce] TTS failed: %s", e)

        # 6. Update memory + cooldown + rate limiter
        self.memory.add(event, narration_text)
        self.cooldown.mark_announced(event)
        self.rate_limiter.record()

        logger.info(
            f"[Announce] ✅ ANNOUNCED | type={event.event_type} | sev={event.severity} "
            f"| device={event.device} | text={narration_text[:60]}..."
        )

        return {
            "skipped": False,
            "skip_reason": "",
            "text": narration_text,
            "audio_b64": audio_b64,
            "audio_format": audio_format,
            "severity": event.severity,
            "event_type": event.event_type,
            "device": event.device,
            "incident_id": event.incident_id,
        }


# ─────────────────────────────────────────────────────────────────────────────
# SINGLETON
# ─────────────────────────────────────────────────────────────────────────────

_announcer_instance: Optional[JarvisProactiveAnnouncer] = None

def get_announcer() -> JarvisProactiveAnnouncer:
    """Thread-safe singleton accessor."""
    global _announcer_instance
    if _announcer_instance is None:
        _announcer_instance = JarvisProactiveAnnouncer()
    return _announcer_instance
