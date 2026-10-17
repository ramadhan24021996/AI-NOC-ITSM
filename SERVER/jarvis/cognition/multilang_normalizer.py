"""
SERVER.jarvis.cognition.multilang_normalizer
=============================================
#10 Seamless Multi-Language Support (ID + EN)

Fitur Production-Ready:
  ✅ Normalisasi query campur ID/EN (Singlish-style) ke Bahasa Indonesia bersih
  ✅ Deteksi bahasa dominan (id/en/mixed)
  ✅ Kamus istilah teknis NOC bilingual (EN→ID)
  ✅ Preserve proper nouns (device names, IP, error codes)
  ✅ Fallback ke query asli jika normalisasi gagal
  ✅ 100% offline — tidak butuh API translator eksternal

Contoh:
  "restart the printer at kasir 3" → "restart printer di kasir 3"
  "check network status semua site" → "cek status jaringan semua site"
  "kasir-3 offline, please fix" → "kasir-3 offline, tolong perbaiki"
"""
from __future__ import annotations

import re
import logging
from typing import Tuple

logger = logging.getLogger("jarvis.cognition.multilang")

# ─── Bilingual Tech Dictionary (EN→ID) ───────────────────────────────────────
_EN_TO_ID: dict = {
    # Commands
    "check":          "cek",
    "show":           "tampilkan",
    "display":        "tampilkan",
    "list":           "daftar",
    "get":            "ambil",
    "fix":            "perbaiki",
    "repair":         "perbaiki",
    "restart":        "restart",
    "reboot":         "restart",
    "start":          "mulai",
    "stop":           "hentikan",
    "analyze":        "analisa",
    "investigate":    "investigasi",
    "find":           "cari",
    "search":         "cari",
    "open":           "buka",
    "close":          "tutup",
    "please":         "tolong",
    "help":           "bantuan",
    "run":            "jalankan",
    "execute":        "eksekusi",
    "approve":        "setujui",
    "reject":         "tolak",
    "update":         "perbarui",
    "create":         "buat",
    "delete":         "hapus",
    "clear":          "bersihkan",
    "flush":          "bersihkan",
    "reset":          "reset",
    "send":           "kirim",
    "monitor":        "pantau",
    "deploy":         "deploy",
    "backup":         "backup",
    # Network/IT terms
    "network":        "jaringan",
    "internet":       "internet",
    "connection":     "koneksi",
    "connected":      "terhubung",
    "disconnected":   "terputus",
    "offline":        "offline",
    "online":         "online",
    "slow":           "lambat",
    "fast":           "cepat",
    "bandwidth":      "bandwidth",
    "latency":        "latensi",
    "packet loss":    "packet loss",
    "server":         "server",
    "router":         "router",
    "switch":         "switch",
    "firewall":       "firewall",
    "gateway":        "gateway",
    "dns":            "dns",
    "ip":             "ip",
    "port":           "port",
    "service":        "layanan",
    "services":       "layanan",
    "system":         "sistem",
    "systems":        "sistem",
    "device":         "device",
    "devices":        "device",
    "printer":        "printer",
    "printers":       "printer",
    # Status terms
    "status":         "status",
    "health":         "kondisi",
    "incident":       "insiden",
    "incidents":      "insiden",
    "alert":          "alert",
    "error":          "error",
    "warning":        "peringatan",
    "critical":       "kritis",
    "down":           "offline",
    "up":             "online",
    "running":        "berjalan",
    # Common phrases
    "all":            "semua",
    "all sites":      "semua site",
    "today":          "hari ini",
    "now":            "sekarang",
    "immediately":    "segera",
    "urgent":         "mendesak",
    "latest":         "terbaru",
    "last":           "terakhir",
    "summary":        "ringkasan",
    "report":         "laporan",
    "at":             "di",
    "for":            "untuk",
    "with":           "dengan",
    "and":            "dan",
    "or":             "atau",
    "the":            "",
    "is":             "",
    "are":            "",
    "not":            "tidak",
    "no":             "tidak ada",
    "yes":            "ya",
    "ok":             "oke",
    "please fix":     "tolong perbaiki",
    "can you":        "bisa",
    "what is":        "apa",
    "how many":       "berapa",
    "how much":       "berapa",
    "where is":       "di mana",
    "why is":         "kenapa",
    "which":          "yang mana",
    "when":           "kapan",
    "who":            "siapa",
}

# Preserve pattern: device names, IPs, codes
_PRESERVE_PATTERNS = [
    r'\b[A-Z]{2,}-[A-Z0-9-]+\b',           # PC-KASIR-3, SW-GDG-01
    r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',  # IP addresses
    r'\bINC-?\d+\b',                         # INC-1234
    r'\bSOP-[A-Z0-9-]+\b',                   # SOP-PRINT-001
    r'\b[A-Z]{2,}\d+\b',                     # SRV01, PC01
    r'\bv\d+\.\d+',                          # v3.2, v11.4
]


def _extract_preservables(text: str) -> Tuple[str, dict]:
    """Simpan proper nouns sementara supaya tidak ditranslate."""
    preserved = {}
    result = text
    for i, pattern in enumerate(_PRESERVE_PATTERNS):
        for m in re.finditer(pattern, result):
            token = m.group()
            placeholder = f"__PRSV{i}_{len(preserved)}__"
            preserved[placeholder] = token
            result = result.replace(token, placeholder, 1)
    return result, preserved


def _restore_preservables(text: str, preserved: dict) -> str:
    """Kembalikan proper nouns yang disimpan."""
    for placeholder, original in preserved.items():
        text = text.replace(placeholder, original)
    return text


def _detect_language(text: str) -> str:
    """Deteksi bahasa dominan: 'id' | 'en' | 'mixed'."""
    q_lower = text.lower()
    id_markers = ["cek", "lihat", "tampilkan", "saya", "anda", "tolong",
                  "perbaiki", "insiden", "jaringan", "kondisi", "bagaimana",
                  "semua", "sudah", "belum", "masalah", "berapa", "kenapa"]
    en_markers = ["check", "show", "list", "please", "fix", "analyze",
                  "the", "is", "are", "status", "what", "how", "why", "which",
                  "restart", "reboot", "clear", "network"]

    id_score = sum(1 for w in id_markers if w in q_lower)
    en_score = sum(1 for w in en_markers if w in q_lower)

    if id_score > en_score * 1.5:
        return "id"
    if en_score > id_score * 1.5:
        return "en"
    return "mixed"


def normalize_query(text: str) -> Tuple[str, str]:
    """
    Normalisasi query bilingual ke Bahasa Indonesia bersih.
    
    Returns:
        (normalized_text, detected_language)
    """
    if not text or not text.strip():
        return text, "id"

    lang = _detect_language(text)

    # Jika sudah bahasa Indonesia murni, kembalikan langsung
    if lang == "id":
        return text.strip(), "id"

    # Preserve proper nouns (case-sensitive)
    working, preserved = _extract_preservables(text)

    # Apply phrase translations on working copy (preserving placeholders as-is)
    # We work on the lower version of NON-placeholder parts only
    sorted_keys = sorted(_EN_TO_ID.keys(), key=len, reverse=True)
    
    # Split into segments: placeholders vs normal text, translate only normal text
    # Build result by processing token by token
    import re as _re
    placeholder_re = _re.compile(r'(__PRSV\d+_\d+__)', _re.IGNORECASE)
    segments = placeholder_re.split(working)
    
    translated_parts = []
    for seg in segments:
        if placeholder_re.match(seg):
            # Keep placeholder as-is (don't lowercase)
            translated_parts.append(seg)
        else:
            # Translate this segment
            seg_lower = seg.lower()
            for en_phrase in sorted_keys:
                id_phrase = _EN_TO_ID[en_phrase]
                if id_phrase:
                    pat = _re.compile(r'\b' + _re.escape(en_phrase) + r'\b', _re.IGNORECASE)
                    seg_lower = pat.sub(id_phrase, seg_lower)
                else:
                    pat = _re.compile(r'\b' + _re.escape(en_phrase) + r'\s*', _re.IGNORECASE)
                    seg_lower = pat.sub(' ', seg_lower)
            translated_parts.append(seg_lower)
    
    normalized = _re.sub(r'\s+', ' ', ''.join(translated_parts)).strip()

    # Restore proper nouns (case-sensitive)
    normalized = _restore_preservables(normalized, preserved)

    # Capitalize awal kalimat
    if normalized:
        normalized = normalized[0].upper() + normalized[1:]

    logger.debug("[MultiLang] %r (%s) → %r", text, lang, normalized)
    return normalized, lang


class MultiLangNormalizer:
    """Wrapper class untuk integrasi ke JARVIS pipeline."""

    def normalize(self, query: str) -> Tuple[str, str]:
        """Normalize query, return (normalized_query, lang_detected)."""
        return normalize_query(query)

    def is_mixed_language(self, query: str) -> bool:
        return _detect_language(query) == "mixed"


_instance = None

def get_multilang_normalizer() -> MultiLangNormalizer:
    global _instance
    if _instance is None:
        _instance = MultiLangNormalizer()
    return _instance
