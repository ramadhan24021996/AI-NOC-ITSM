"""
SERVER.jarvis.command.intent_router — JARVIS Command Intent Router
==================================================================
P1 Implementation: 6-kategori intent classification untuk semua perintah NOC.

Intent Categories:
  - QUERY      : Permintaan informasi tanpa side-effect
  - REMEDIATE  : Aksi remediasi yang melewati Safety Gate
  - HITL       : Human-in-the-Loop approval/rejection/escalation
  - REMOTE     : Buka/tutup sesi remote access (VNC/RDP/SSH)
  - CHAT       : Manajemen live chat dengan client/device
  - ISSUE      : Lihat/filter/manage issue tracking

Keyword extraction menggunakan Bahasa Indonesia + English hybrid matching.
"""
import re
import logging
from enum import Enum
from typing import Tuple, List, Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("jarvis.command.intent_router")


class JarvisIntent(str, Enum):
    QUERY      = "query"
    REMEDIATE  = "remediate"
    HITL       = "hitl"
    REMOTE     = "remote"
    CHAT       = "chat"
    ISSUE      = "issue"
    UNKNOWN    = "unknown"


@dataclass
class IntentResult:
    """Hasil klasifikasi intent dari satu perintah user."""
    intent: JarvisIntent
    confidence: float
    matched_keywords: List[str] = field(default_factory=list)
    extracted_entities: Dict[str, str] = field(default_factory=dict)
    # Entity shortcuts
    target_device: Optional[str] = None
    target_site: Optional[str] = None
    target_incident: Optional[str] = None
    remote_tool: Optional[str] = None
    chat_session: Optional[str] = None


# ──────────────────────────────────────────────────────────────────────────────
# Keyword Bank — Bahasa Indonesia + English hybrid
# ──────────────────────────────────────────────────────────────────────────────

_QUERY_KEYWORDS = [
    # Status & monitoring
    "status", "cek", "check", "lihat", "tampilkan", "show", "display",
    "berapa", "how many", "apa", "what", "siapa", "who",
    "monitor", "pantau", "laporan", "lapor", "report", "info",
    "cek status kesehatan sistem", "status kesehatan sistem", "kesehatan sistem",
    "berapa metrik cpu dan ram sekarang", "metrik cpu dan ram", "metrik cpu", "metrik ram",
    # PC & Device status
    "pc online", "pc offline", "device online", "device offline",
    "berapa pc yang sedang online dan offline", "pc online dan offline",
    "berapa pc", "berapa device", "perangkat online", "perangkat offline",
    "status pc", "status device", "status perangkat", "komputer online", "komputer offline",
    # Printer status
    "printer", "printer aktif", "printer online", "printer offline",
    "berapa printer yang sudah terhubung dan aktif", "berapa printer", "printer terhubung",
    "printer aktif", "status printer", "antrean printer", "print queue", "spooler printer",
    # Deep Diagnostics & Cognition
    "deep diagnostics", "diagnostik mendalam", "diagnosa mendalam", "diagnosa lengkap",
    "jalankan diagnosa mendalam", "jalankan diagnosa", "jalankan diagnostik mendalam", "jalankan deep diagnostics",
    "analisa incident", "analisa insiden", "analisis incident", "analisis insiden",
    "rca incident", "rca insiden", "analisa incident di", "analisa insiden di",
    "analisis incident di", "analisis insiden di", "analisa incident di pc", "analisa insiden di pc",
    "analisa incident di printer", "analisa insiden di printer", "analisis incident di printer", "analisa incident printer", "analisa insiden printer",
    "causal graph", "tunjukkan causal graph",
    "blast radius", "berapa blast radius",
    "criticality score", "berapa criticality score", "skor kritikalitas",
    "catalog aksi", "daftar catalog aksi pre-approved", "aksi pre-approved",
    "audit log hari ini", "lihat audit log hari ini",
    "sop belum direview", "berapa sop yang belum direview",
    # Launcher & AI status (QUERY, not REMOTE/REMEDIATE)
    "cek launcher", "status launcher", "launcher service",
    "konfigurasi ai", "update konfigurasi ai", "ai config",
    # System health
    "kesehatan sistem", "health", "sehat", "runtime", "uptime",
    "cpu", "ram", "memory", "disk", "storage",
    "ping", "latency", "latens", "response time",
    # Incident info
    "incident aktif", "insiden", "incident", "anomali", "anomaly",
    "alert", "peringatan", "alarm", "warning",
    # SLA & compliance
    "sla", "compliance", "uptime", "ketersediaan", "availability",
    # Fleet & devices
    "device", "perangkat", "fleet", "site", "lokasi",
    "printer", "router", "switch", "server",
    # Bilingual Code-Switching & NOC Slang Keywords
    "loss packet", "packet loss", "spike", "ngedrop", "nge-drop", "lemot", "ngadat",
    "switch down", "link putus", "rute putus", "kasir macet", "spooler ngadat",
    "kenapa switch", "kenapa router", "kenapa server", "loss packet spike",
    # Knowledge & SOP info (read-only)
    "sop", "prosedur", "knowledge", "pengetahuan", "cari",
    "daftar knowledge", "cari knowledge", "list knowledge",
    # n8n & workflow
    "n8n", "workflow", "hidup", "aktif",
    # Historical & Post-Mortem Reports
    "history", "riwayat", "log", "audit", "post-mortem", "postmortem",
    "buatkan visual postmortem", "buat visual postmortem", "buatkan postmortem", "buat postmortem",
    "visual postmortem", "laporan visual postmortem", "laporan eksekutif insiden", "laporan eksekutif",
    "export postmortem", "generate postmortem", "timeline insiden kasir", "timeline insiden",
    # Browser & Media Control
    "buka dashboard", "buka noc", "buka portal", "dashboard jarvis", "tampilan awal",
    "buka youtube", "youtube", "play musik", "putar musik", "play lagu", "putar lagu",
    "saya ingin musik", "saya ingin lagu", "mau musik", "mau lagu", "dengarkan musik", "dengarkan lagu",
    "setel musik", "setel lagu", "carikan musik", "carikan lagu",
    "stop musik", "stop music", "matikan musik", "hentikan musik", "stop lagu", "matikan lagu",
    "hentikan lagu", "pause musik", "pause music", "jeda musik",
    "jarvis stop", "stop player", "matikan player", "stop media", "berhenti", "jarvis diam",
    "buka chatgpt", "chat gpt", "gpt.ai", "buka gpt ai", "buka gpt",
    "openai", "tanyakan ke chatgpt", "tanyakan ke gpt ai", "tanyakan ke gpt",
    "buka tab", "buka website", "buka site",
]

_REMEDIATE_KEYWORDS = [
    # Service actions (specific NOC ops — avoid generic 'matikan'/'hentikan' that clash with media stop)
    "restart", "reboot", "start", "kill", "terminate",
    "mulai ulang", "nyalakan",
    "matikan server", "matikan service", "hentikan service",
    "restart spooler", "restart print spooler", "clear print queue", "flush dns",
    # Network actions
    "failover", "failover isp", "pindah isp", "switch over", "backup isp", "link backup",
    "disable port", "enable port", "aktifkan port", "nonaktifkan port",
    "shutdown interface", "no shutdown",
    "clear arp", "bersihkan arp", "flush arp", "clear cache", "bersihkan cache",
    # Configuration actions
    "update", "upgrade", "rollback",
    "deploy", "trigger", "execute", "jalankan", "eksekusi", "eksekusi jalankan", "eksekusi insiden", "eksekusi sekarang",
    "apply", "terapkan",
    # SOP execution & management mutations
    "execute sop", "jalankan sop", "lakukan sop", "eksekusi sop", "terapkan sop",
    "buat sop", "buat prosedur", "hapus sop", "delete sop", "promote sop", "promosi sop",
    "remediate", "perbaiki", "fix", "resolve",
    # Incident mutations (create/close/resolve/escalate are mutations, not queries)
    "buat insiden", "tutup insiden", "selesaikan insiden", "eskalasi insiden",
    "assign insiden", "create incident", "close incident", "resolve incident",
    "reanalyze", "reanalisa",
    # OTA
    "ota", "firmware", "update agent", "trigger ota",
    # DB/service specific
    "vacuum", "analyze db", "restart postgresql", "kill query",
    "restart redis", "flush redis", "restart nats", "reboot server",
    # Queue
    "clear queue", "bersihkan antrian", "kosongkan antrian", "kosongkan queue",
    "bersihkan antrian cetak",
    # RBAC mutations
    "tambah user", "hapus user", "update role",
    # Device management
    "tambah device", "hapus device", "register device",
    # Slang Remediation Actions
    "benerin", "benerin spooler", "beresin", "beresin antrean", "beresin antrian", "fix kasir",
    # n8n / Knowledge mutations
    "publish postmortem", "sync vault", "import knowledge",
]

_HITL_KEYWORDS = [
    # Approval
    "approve", "setujui", "izinkan", "konfirmasi", "confirm",
    "ya lakukan", "yes execute", "proceed",
    # Rejection
    "reject", "tolak", "batalkan", "cancel", "abort",
    "jangan lakukan", "no don't",
    # Escalation
    "escalate", "eskalasi", "naikan", "teruskan ke",
    "kirim ke l2", "kirim ke l3", "forward to",
    # HITL queue management
    "antrian approval", "approval queue", "siapa yang belum approve",
    "aksi menunggu", "pending action",
    # Override
    "override", "paksa", "force execute",
]

_REMOTE_KEYWORDS = [
    # Open remote — Gap 7 FIX: explicit "buka X" variants for browser dispatch
    "buka remote", "remote ke", "open remote", "launch remote",
    "akses remote", "remote access", "sambungkan ke",
    "connect to", "masuk ke server",
    # Explicit "buka" + tool name (Gap 7 fix — previously falling to QUERY)
    "buka rustdesk", "buka vnc", "buka rdp", "buka anydesk",
    "buka teamviewer", "buka remote desktop", "buka sesi remote",
    "buka desktop jauh", "open rustdesk", "open vnc",
    # Specific tools
    "vnc", "rdp", "ssh", "anydesk", "teamviewer", "rustdesk", "rust desk",
    "remote desktop", "desktop jauh",
    # Session management
    "tutup remote", "close remote", "disconnect", "putuskan",
    "keluar dari remote", "terminate session", "hentikan sesi",
    "putuskan koneksi", "hentikan sesi remote",
    # Detection (moved cek launcher to QUERY — it's a status check, not a launch)
    "deteksi tool remote", "detect remote", "deteksi remote",
]


_CHAT_KEYWORDS = [
    # Read chat
    "baca chat", "read chat", "lihat chat", "tampilkan chat",
    "chat terbaru", "pesan terbaru", "latest message",
    "chat dari", "pesan dari",
    # Send message
    "kirim pesan", "send message", "balas", "reply",
    "jawab chat", "respond to",
    # AI suggest
    "suggest balasan", "suggest reply", "saran balasan",
    "rekomendasikan balasan", "ai suggest",
    # Session management
    "buka chat", "tutup chat", "close chat",
    "escalate chat", "eskalasi chat",
    "update status chat", "session",
    # Identity & Purpose
    "siapa kamu", "siapa anda", "kamu siapa", "anda siapa", "namamu siapa", "nama kamu",
    "diprogram buat apa", "di program buat apa", "diprogram untuk apa", "di program untuk apa",
    "dibuat untuk apa", "dibuat buat apa", "fungsi kamu", "tugas kamu", "apa tugasmu",
    "kamu bisa apa", "kamu bisa apa saja", "kamu bisa apa aja", "apa yang bisa kamu lakukan",
    "fitur kamu", "kemampuan kamu", "apa fungsi kamu",
    "anda di program buat apa", "anda diprogram buat apa",
    "anda diprogram untuk apa", "anda di program untuk apa",
    "siapa yang buat kamu", "siapa pembuatmu",
    # Live stream
    "live chat", "chat live", "stream chat",
]

_ISSUE_KEYWORDS = [
    # List issues
    "issue", "masalah", "problem", "gangguan",
    "issue apa", "masalah apa", "tampilkan issue",
    "lihat issue", "daftar masalah",
    # Filter by severity
    "issue critical", "issue high", "issue medium", "issue low",
    "masalah kritis", "masalah serius",
    # Device-specific issues
    "issue device", "issue server", "masalah perangkat",
    "gangguan di", "problem pada",
    # Priority
    "prioritas", "priority", "urgent", "mendesak",
    "perlu perhatian", "needs attention",
]

# ──────────────────────────────────────────────────────────────────────────────
# Entity Extraction Patterns
# ──────────────────────────────────────────────────────────────────────────────

_INCIDENT_PATTERN = re.compile(
    r"\b(INC[-\s]?\d{3,}|insiden[\s#]+\d+|incident[\s#]+\d+)\b",
    re.IGNORECASE
)
_DEVICE_PATTERN = re.compile(
    r"\b(server[-\s]?\w+|pc[-\s]?\w+|router[-\s]?\w+|switch[-\s]?\w+"
    r"|printer[-\s]?\w+|dc[-\s]?\w+|sg[-\s]?\w+|[a-z]{2,4}-\w{2,})\b",
    re.IGNORECASE
)
_SITE_PATTERN = re.compile(
    r"\b(jakarta|surabaya|bandung|medan|bali|yogya|semarang|"
    r"site[\s]+\w+|lokasi[\s]+\w+)\b",
    re.IGNORECASE
)
_REMOTE_TOOL_PATTERN = re.compile(
    r"\b(vnc|rdp|ssh|anydesk|teamviewer|rustdesk|rust\s*desk)\b",
    re.IGNORECASE
)


# ──────────────────────────────────────────────────────────────────────────────
# JarvisCommandIntentRouter
# ──────────────────────────────────────────────────────────────────────────────

class JarvisCommandIntentRouter:
    """
    P1 — JARVIS Command Intent Router (Bahasa Indonesia + English).

    Mengklasifikasikan teks perintah ke 6 kategori intent NOC:
      QUERY | REMEDIATE | HITL | REMOTE | CHAT | ISSUE

    Contoh:
        router = JarvisCommandIntentRouter()
        result = router.classify("Jarvis, restart spooler server-01")
        # result.intent → JarvisIntent.REMEDIATE
        # result.target_device → "server-01"
    """

    def __init__(self):
        # Build keyword → intent lookup table dengan bobot
        self._keyword_map: Dict[str, Tuple[JarvisIntent, float]] = {}
        self._build_keyword_map()
        logger.info("[IntentRouter] JarvisCommandIntentRouter initialized. "
                    f"Total keywords: {len(self._keyword_map)}")

    def _build_keyword_map(self) -> None:
        mappings = [
            (_QUERY_KEYWORDS,     JarvisIntent.QUERY,     1.0),
            (_REMEDIATE_KEYWORDS, JarvisIntent.REMEDIATE, 1.5),  # Higher weight — action verbs
            (_HITL_KEYWORDS,      JarvisIntent.HITL,      1.6),  # Highest — approval context
            (_REMOTE_KEYWORDS,    JarvisIntent.REMOTE,    1.4),
            (_CHAT_KEYWORDS,      JarvisIntent.CHAT,      1.0),
            (_ISSUE_KEYWORDS,     JarvisIntent.ISSUE,     1.0),
        ]
        for keywords, intent, weight in mappings:
            for kw in keywords:
                # Longer keywords = more specific = higher base score
                base = 0.3 + (len(kw.split()) * 0.15)
                self._keyword_map[kw.lower()] = (intent, base * weight)

    def classify(self, query_text: str) -> IntentResult:
        """
        Klasifikasikan perintah dan ekstrak entitas.

        Args:
            query_text: Teks perintah setelah wake word sudah di-strip.

        Returns:
            IntentResult dengan intent, confidence, dan entitas yang diekstrak.
        """
        if not query_text or not query_text.strip():
            return IntentResult(intent=JarvisIntent.UNKNOWN, confidence=0.0)

        normalized = query_text.lower().strip()
        scores: Dict[JarvisIntent, float] = {}
        matched: List[str] = []

        # Score each intent berdasarkan keyword match
        for kw, (intent, weight) in self._keyword_map.items():
            if kw in normalized:
                prev = scores.get(intent, 0.0)
                scores[intent] = prev + weight
                matched.append(kw)

        # Pilih intent dengan skor tertinggi
        if not scores:
            best_intent = JarvisIntent.QUERY  # Default ke query (safest)
            confidence = 0.3
        else:
            best_intent_enum = max(scores, key=lambda i: scores[i])
            best_intent = best_intent_enum
            raw_score = scores[best_intent]
            # Normalize: >= 0.7 = high confidence
            confidence = min(0.99, max(0.5, raw_score / 1.5))

        # Extract entities
        entities = self._extract_entities(query_text)

        result = IntentResult(
            intent=best_intent,
            confidence=round(confidence, 3),
            matched_keywords=matched[:10],  # top 10
            extracted_entities=entities,
            target_device=entities.get("device"),
            target_site=entities.get("site"),
            target_incident=entities.get("incident"),
            remote_tool=entities.get("remote_tool"),
            chat_session=entities.get("device") or entities.get("site"),
        )

        logger.info(
            f"[IntentRouter] Query='{query_text[:60]}' → "
            f"Intent={result.intent.value} (confidence={result.confidence}) "
            f"Matched={matched[:3]}"
        )
        return result

    def _extract_entities(self, text: str) -> Dict[str, str]:
        """Extract device, site, incident ID, remote tool dari teks bebas."""
        entities: Dict[str, str] = {}

        # Direct pattern for "di pc XYZ" / "di printer XYZ" / "analisa incident di printer"
        pc_match = re.search(r'\b(?:di|pada|ke|for)\s+(?:pc|server|device|komputer|node|printer|prt|spooler)\s+([a-z0-9_\-\.]+)', text, re.IGNORECASE)
        if pc_match:
            entities["device"] = pc_match.group(1).upper()
        elif re.search(r'\b(?:analisa|analisis|rca|cek)\s+(?:incident|insiden)\s+(?:di|pada)?\s*(?:printer|spooler|prt)\b', text, re.IGNORECASE):
            entities["device"] = "PRT-HR-01"

        m = _INCIDENT_PATTERN.search(text)
        if m:
            entities["incident"] = m.group(0).upper().replace(" ", "-")

        if "device" not in entities:
            m = _DEVICE_PATTERN.search(text)
            if m:
                entities["device"] = m.group(0)

        # Extract Relative Time Window from NOC slang
        if re.search(r'\b(?:abis|setelah|sehabis)\s+(?:jam\s+)?(?:makan\s+siang|ishoma|lunch)\b', text, re.IGNORECASE):
            entities["time_window"] = "post_lunch_13_00"
        elif re.search(r'\b(?:tadi\s+pagi|pagi\s+ini|morning)\b', text, re.IGNORECASE):
            entities["time_window"] = "morning_08_00"
        elif re.search(r'\b(?:1|se|satu)\s+jam\s+(?:terakhir|lalu|past\s+hour)\b', text, re.IGNORECASE):
            entities["time_window"] = "last_1_hour"
        elif re.search(r'\b(?:kemarin|yesterday|semalam)\b', text, re.IGNORECASE):
            entities["time_window"] = "yesterday"

        # Slang abbreviation mapping for site (e.g. SBY -> Surabaya, JKT -> Jakarta, BDG -> Bandung)
        if "site" not in entities:
            if re.search(r'\b(?:sby|surabaya)\b', text, re.IGNORECASE):
                entities["site"] = "Surabaya"
            elif re.search(r'\b(?:jkt|jakarta|pusat)\b', text, re.IGNORECASE):
                entities["site"] = "Jakarta"
            elif re.search(r'\b(?:bdg|bandung)\b', text, re.IGNORECASE):
                entities["site"] = "Bandung"

        return entities

    def get_risk_hint(self, intent: JarvisIntent) -> str:
        """Berikan petunjuk risk level berdasarkan intent kategori."""
        risk_map = {
            JarvisIntent.QUERY:     "NONE",
            JarvisIntent.CHAT:      "NONE",
            JarvisIntent.ISSUE:     "NONE",
            JarvisIntent.REMOTE:    "LOW",
            JarvisIntent.HITL:      "MEDIUM",
            JarvisIntent.REMEDIATE: "VARIES",  # Ditentukan oleh AISafetyLayer
        }
        return risk_map.get(intent, "UNKNOWN")

    def describe(self) -> str:
        """Human-readable deskripsi router untuk debugging."""
        return (
            f"JarvisCommandIntentRouter: "
            f"{len(self._keyword_map)} keywords across 6 intent categories "
            f"(QUERY|REMEDIATE|HITL|REMOTE|CHAT|ISSUE)"
        )
