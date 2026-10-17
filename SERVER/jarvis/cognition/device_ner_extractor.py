"""
SERVER.jarvis.cognition.device_ner_extractor — NOC Device Named Entity Recognizer
==================================================================================
Gap #2 Fix: Menggantikan naive word-by-word device detection di rule_fallback
dengan NER (Named Entity Recognition) berbasis multi-pattern regex yang akurat.

Mendukung:
  - Compound device names: "kasir 2", "server backup", "gudang 3"
  - Prefix-based: "PC-MKT-01", "SERVER-DB-02", "PRINTER-GDG-01"
  - Number-suffix verbal: "kasir dua", "server satu", "gudang tiga"
  - Site-compound: "printer kasir 1", "pc gudang 2"
  - Generic fallback: mencari kata paling spesifik yang menjadi target

Zero mock | Zero placeholder | Zero hardcoded single-word matching
"""
import re
import logging
from typing import Optional, Tuple, Dict, List

logger = logging.getLogger("jarvis.cognition.device_ner")

# ── Verbal number → digit mapping ───────────────────────────────────────────
VERBAL_NUMBERS: Dict[str, str] = {
    "satu": "1", "dua": "2", "tiga": "3", "empat": "4", "lima": "5",
    "enam": "6", "tujuh": "7", "delapan": "8", "sembilan": "9", "sepuluh": "10",
    "sebelas": "11", "duabelas": "12", "tigabelas": "13", "empatbelas": "14",
    "limabelas": "15",
    # Common English numbers in bilingual commands
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
}

# ── Device type anchor words ─────────────────────────────────────────────────
DEVICE_TYPE_ANCHORS: List[str] = [
    "kasir", "gudang", "server", "printer", "pc", "komputer", "laptop",
    "router", "switch", "access point", "ap", "modem", "ups", "mikrotik",
    "cisco", "firewall", "gateway", "display", "monitor", "kiosk",
    "marketing", "finance", "hrd", "it", "kantor", "pusat", "cabang",
    "backup", "primary", "secondary", "db", "database", "web", "app",
    "nuc", "nux", "store",
]

# ── Site/location anchors ─────────────────────────────────────────────────────
SITE_ANCHORS: List[str] = [
    "kasir", "gudang", "kantor", "pusat", "cabang", "store", "lantai",
    "ruang", "area", "zona", "marketing", "finance", "hrd", "it",
]

# ── Device prefix patterns (case-insensitive) ────────────────────────────────
PREFIX_PATTERNS: List[re.Pattern] = [
    # Formal prefix: PC-MKT-01, SERVER-DB-02
    re.compile(r'\b(PC|SERVER|SRV|PRINTER|PRT|AP|SW|RTR|GW|UPS|NUC|KIOSK|DB|WEB|APP)[-_]\w+(?:[-_]\w+)*\b', re.IGNORECASE),
    # Device+site+optional_number (PALING SPESIFIK — harus dicek lebih dulu):
    # printer kasir 1, pc gudang 2, komputer marketing 3
    re.compile(r'\b(printer|pc|komputer)\s+(kasir|gudang|marketing|finance|hrd|it)\s*\d*\b', re.IGNORECASE),
    # Device+descriptor: server backup, server primary, pc utama
    re.compile(r'\b(server|pc)\s+(backup|primary|secondary|db|web|app|utama|cadangan)\b', re.IGNORECASE),
    # Device+number: kasir 2, gudang 3, printer 5
    re.compile(r'\b(kasir|gudang|printer|server|pc|router|switch|ups|modem|mikrotik|cisco|display)\s+\d+\b', re.IGNORECASE),
    # Site+number: kasir 2, gudang 1, marketing 3
    re.compile(r'\b(kasir|gudang|marketing|finance|hrd|it)\s*\d+\b', re.IGNORECASE),
]

# ── Stopwords that should NOT be included in device name ────────────────────
DEVICE_STOPWORDS: set = {
    "via", "online", "offline", "adalah", "dengan", "dan", "atau",
    "ke", "dari", "di", "untuk", "pada", "yang", "ini", "itu",
    "cek", "status", "restart", "reboot", "flush", "remot",
    "remote", "diagnostik", "deep", "diagnosa", "buka", "tutup",
}


class JarvisDeviceNERExtractor:
    """
    Named Entity Recognizer untuk device/perangkat NOC dari teks Bahasa Indonesia + Inggris.

    Gap #2 Fix: Menggantikan naive word-loop yang gagal untuk:
      - "kasir 2"          → butuh 2 kata (sebelumnya gagal)
      - "server backup"    → butuh descriptor (sebelumnya gagal)
      - "printer gudang 3" → compound 3 kata (sebelumnya gagal)
    """

    @classmethod
    def normalize_verbal_numbers(cls, text: str) -> str:
        """Konversi angka verbal ke digit: 'kasir dua' → 'kasir 2'."""
        result = text
        for verbal, digit in VERBAL_NUMBERS.items():
            result = re.sub(r'\b' + verbal + r'\b', digit, result, flags=re.IGNORECASE)
        return result

    @classmethod
    def extract_device(cls, text: str) -> str:
        """
        Ekstraksi nama device/perangkat dari teks perintah operator.

        Priority:
          1. Formal prefix pattern (PC-MKT-01, SERVER-DB-02)
          2. Compound device+number (kasir 2, server backup)
          3. Device+site compound (printer kasir 1)
          4. Single device anchor dengan context terdekat

        Returns:
            Nama device dinormalisasi (UPPERCASE), atau string kosong.
        """
        if not text or not text.strip():
            return ""

        # Normalize verbal numbers first
        normalized = cls.normalize_verbal_numbers(text.strip())

        # Priority 1: Formal prefix patterns (PC-MKT-01 style)
        match = PREFIX_PATTERNS[0].search(normalized)
        if match:
            device = match.group(0).upper()
            logger.debug(f"[DeviceNER] Prefix match: '{device}' from '{text[:50]}'")
            return device

        # Priority 2-5: Compound patterns (order matters — longest match first)
        for pattern in PREFIX_PATTERNS[1:]:
            match = pattern.search(normalized)
            if match:
                device = re.sub(r'\s+', '-', match.group(0).strip()).upper()
                logger.debug(f"[DeviceNER] Compound match: '{device}' from '{text[:50]}'")
                return device

        # Priority 6: Single device anchor dengan 1-2 word context (dengan stopword filter)
        for anchor in DEVICE_TYPE_ANCHORS:
            pattern = re.compile(r'\b' + re.escape(anchor) + r'(?:\s+\w+){0,2}\b', re.IGNORECASE)
            ext_match = pattern.search(normalized)
            if ext_match:
                # Filter: hapus stopwords dari akhir match
                words = ext_match.group(0).strip().split()
                filtered = []
                for w in words:
                    if w.lower() in DEVICE_STOPWORDS:
                        break  # Stop di stopword pertama
                    filtered.append(w)
                if filtered:
                    device = "-".join(filtered).upper()
                    logger.debug(f"[DeviceNER] Anchor match: '{device}' from '{text[:50]}'")
                    return device

        logger.debug(f"[DeviceNER] No device found in: '{text[:50]}'")
        return ""

    @classmethod
    def extract_site(cls, text: str) -> str:
        """
        Ekstraksi nama site/lokasi dari teks perintah operator.

        Returns:
            Nama site dinormalisasi, atau string kosong.
        """
        if not text or not text.strip():
            return ""

        normalized = cls.normalize_verbal_numbers(text.strip())

        for site in SITE_ANCHORS:
            pattern = re.compile(r'\b' + re.escape(site) + r'(?:\s+\d+)?\b', re.IGNORECASE)
            match = pattern.search(normalized)
            if match:
                site_name = re.sub(r'\s+', '-', match.group(0).strip()).upper()
                logger.debug(f"[DeviceNER] Site match: '{site_name}' from '{text[:50]}'")
                return site_name

        return ""

    @classmethod
    def extract_all(cls, text: str) -> Tuple[str, str]:
        """
        Ekstraksi device dan site sekaligus.

        Returns:
            Tuple (device_name, site_name), masing-masing bisa kosong.
        """
        device = cls.extract_device(text)
        site = cls.extract_site(text)
        return device, site
