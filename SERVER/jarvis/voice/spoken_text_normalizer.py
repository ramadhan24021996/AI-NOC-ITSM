"""
SERVER.jarvis.voice.spoken_text_normalizer — LLM-to-Spoken-Text Normalizer
===========================================================================
Mengonversi output LLM mentah menjadi teks yang siap diucapkan TTS secara
natural dalam Bahasa Indonesia. Tanpa modul ini, TTS akan membacakan:
  - "**CPU**" → bintang bintang C P U bintang bintang (robotik)
  - "v1.2.0"  → v satu titik dua titik nol (tidak natural)
  - "SLA"     → S-L-A (tanpa spasi, TTS bisa salah ucapkan)
  - "192.168.1.1" → perlu dieja per oktet
  - "90%"     → sembilan puluh persen

Transformasi urutan:
  1. Strip markdown symbols
  2. Expand URL/domain → fonetik
  3. Expand IP address → verbal
  4. Expand versi software → verbal
  5. Expand percentage → "persen"
  6. Expand angka cardinal → kata Bahasa Indonesia
  7. Expand akronim teknis NOC → dieja per huruf
  8. Normalisasi simbol operator (>, <, -, /)
  9. Normalisasi whitespace + punctuation
 10. Inject natural pause hint (koma) pada kalimat panjang

TIDAK ada external dependency — pure Python stdlib.
"""
import re
import logging
from typing import Dict, List

logger = logging.getLogger("jarvis.voice.spoken_text_normalizer")

# =============================================================================
# AKRONIM TEKNIS NOC — dieja per huruf saat diucapkan
# =============================================================================
ACRONYM_MAP: Dict[str, str] = {
    # Sistem & Infrastruktur
    "CPU":   "C-P-U",
    "RAM":   "R-A-M",
    "GPU":   "G-P-U",
    "HDD":   "H-D-D",
    "SSD":   "S-S-D",
    "UPS":   "U-P-S",
    "NAS":   "N-A-S",
    "SAN":   "S-A-N",
    "PDU":   "P-D-U",
    # Jaringan & Protokol
    "BGP":   "B-G-P",
    "OSPF":  "O-S-P-F",
    "VLAN":  "V-L-A-N",
    "VPN":   "V-P-N",
    "DNS":   "D-N-S",
    "DHCP":  "D-H-C-P",
    "NTP":   "N-T-P",
    "SNMP":  "S-N-M-P",
    "ICMP":  "I-C-M-P",
    "TCP":   "T-C-P",
    "UDP":   "U-D-P",
    "HTTP":  "H-T-T-P",
    "HTTPS": "H-T-T-P-S",
    "FTP":   "F-T-P",
    "SSH":   "S-S-H",
    "RDP":   "R-D-P",
    "VNC":   "V-N-C",
    "API":   "A-P-I",
    "IP":    "I-P",
    # ITSM & SLA
    "SLA":   "S-L-A",
    "SLO":   "S-L-O",
    "SLI":   "S-L-I",
    "ITSM":  "I-T-S-M",
    "CMDB":  "C-M-D-B",
    "ITIL":  "I-T-I-L",
    "OLA":   "O-L-A",
    "NOC":   "N-O-C",
    "SOC":   "S-O-C",
    "HITL":  "H-I-T-L",
    "MTTR":  "M-T-T-R",
    "MTBF":  "M-T-B-F",
    "RTO":   "R-T-O",
    "RPO":   "R-P-O",
    # Platform & Tools
    "RCA":   "R-C-A",
    "OPA":   "O-P-A",
    "MCP":   "M-C-P",
    "LLM":   "L-L-M",
    "AI":    "A-I",
    "ML":    "M-L",
    "CI":    "C-I",
    "CD":    "C-D",
    "DB":    "D-B",
    "SQL":   "S-Q-L",
    "ORM":   "O-R-M",
    "GW":    "Gateway",
    "SBY":   "Surabaya",
    "JKT":   "Jakarta",
    "BDG":   "Bandung",
    "TTF":   "T-T-F",
    "DAG":   "D-A-G",
    "RRF":   "R-R-F",
    "OLS":   "O-L-S",
    "PCM":   "P-C-M",
    "WS":    "Web-Socket",
    "OK":    "O-K",
}

# =============================================================================
# ANGKA KARDINAL → KATA BAHASA INDONESIA
# =============================================================================
_ONES: List[str] = [
    "", "satu", "dua", "tiga", "empat", "lima",
    "enam", "tujuh", "delapan", "sembilan", "sepuluh",
    "sebelas", "dua belas", "tiga belas", "empat belas", "lima belas",
    "enam belas", "tujuh belas", "delapan belas", "sembilan belas",
]
_TENS: List[str] = [
    "", "", "dua puluh", "tiga puluh", "empat puluh", "lima puluh",
    "enam puluh", "tujuh puluh", "delapan puluh", "sembilan puluh",
]


def _number_to_words_id(n: int) -> str:
    """Konversi integer ke kata Bahasa Indonesia (0-999.999)."""
    if n < 0:
        return "minus " + _number_to_words_id(-n)
    if n == 0:
        return "nol"
    if n < 20:
        return _ONES[n]
    if n < 100:
        t, o = divmod(n, 10)
        return _TENS[t] + (" " + _ONES[o] if o else "")
    if n < 1000:
        h, rem = divmod(n, 100)
        prefix = "seratus" if h == 1 else _ONES[h] + " ratus"
        return prefix + (" " + _number_to_words_id(rem) if rem else "")
    if n < 1_000_000:
        th, rem = divmod(n, 1000)
        prefix = "seribu" if th == 1 else _number_to_words_id(th) + " ribu"
        return prefix + (" " + _number_to_words_id(rem) if rem else "")
    return str(n)


# =============================================================================
# MAIN NORMALIZER CLASS
# =============================================================================

class SpokenTextNormalizer:
    """
    Konversi output LLM mentah ke spoken-style text untuk TTS.

    Contoh:
      Input:  "**CPU** di `192.168.1.1` naik 90% — SLA breach! v1.2.0"
      Output: "C-P-U di satu sembilan dua titik satu enam delapan titik satu
               naik sembilan puluh persen, S-L-A breach! versi satu titik dua."
    """

    def normalize(self, text: str) -> str:
        """Pipeline utama normalisasi. Mengembalikan teks siap TTS."""
        if not text or not text.strip():
            return text
        text = self._strip_markdown(text)
        text = self._expand_url(text)
        text = self._expand_ip(text)
        text = self._expand_version(text)
        text = self._expand_percent(text)
        text = self._normalize_symbols(text)   # jalankan SEBELUM expand_numbers
        text = self._expand_numbers(text)
        text = self._expand_acronyms(text)
        text = self._normalize_whitespace(text)
        text = self._inject_natural_pauses(text)
        logger.debug("[SpokenTextNormalizer] normalized: %s", text[:120])
        return text

    # -- Step 1: Strip Markdown -----------------------------------------------

    def _strip_markdown(self, text: str) -> str:
        """Hapus semua markdown syntax yang tidak bisa diucapkan."""
        text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text, flags=re.DOTALL)
        text = re.sub(r'_{1,3}(.*?)_{1,3}', r'\1', text, flags=re.DOTALL)
        text = re.sub(r'`{1,3}(.*?)`{1,3}', r'\1', text, flags=re.DOTALL)
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', r'\1', text)
        text = re.sub(r'^[\-=\*]{3,}\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*[-\*\+]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*>\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'\|[-: ]+\|[-: |]+', '', text)
        text = re.sub(r'\|', ' ', text)
        return text

    # -- Step 2: Expand URL ---------------------------------------------------

    def _expand_url(self, text: str) -> str:
        """https://github.com/user/repo → github titik com"""
        def _expand(m: re.Match) -> str:
            url = re.sub(r'^https?://', '', m.group(0))
            url = re.sub(r'^www\.', '', url)
            domain = url.split('/')[0]
            return ' titik '.join(domain.split('.'))
        return re.sub(r'https?://[^\s\]\)]+|www\.[^\s\]\)]+', _expand, text)

    # -- Step 3: Expand IP Address --------------------------------------------

    def _expand_ip(self, text: str) -> str:
        """192.168.1.1 → satu sembilan dua titik satu enam delapan titik satu titik satu"""
        def _expand(m: re.Match) -> str:
            parts = m.group(0).split('.')
            spoken_octets = []
            for octet in parts:
                digits = ' '.join(
                    _ONES[int(d)] if 0 < int(d) < len(_ONES) else ("nol" if d == "0" else d)
                    for d in octet
                )
                spoken_octets.append(digits)
            return ' titik '.join(spoken_octets)
        return re.sub(r'\b(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\b', _expand, text)

    # -- Step 4: Expand Version String ----------------------------------------

    def _expand_version(self, text: str) -> str:
        """v1.2.0 → versi satu titik dua titik nol"""
        def _expand(m: re.Match) -> str:
            ver_str = m.group(0).lstrip('vV')
            parts = ver_str.split('.')
            spoken = ' titik '.join(
                _number_to_words_id(int(p)) if p.isdigit() else p
                for p in parts
            )
            return 'versi ' + spoken
        return re.sub(r'\b[vV]\d+(?:\.\d+){0,4}\b', _expand, text)

    # -- Step 5: Expand Percentage --------------------------------------------

    def _expand_percent(self, text: str) -> str:
        """90% → sembilan puluh persen  |  90.5% → sembilan puluh koma lima persen"""
        def _expand(m: re.Match) -> str:
            num_str = m.group(1)
            if '.' in num_str:
                int_part, dec_part = num_str.split('.', 1)
                spoken = _number_to_words_id(int(int_part)) + ' koma ' + _number_to_words_id(int(dec_part))
            else:
                spoken = _number_to_words_id(int(num_str))
            return spoken + ' persen'
        return re.sub(r'(\d+(?:\.\d+)?)\s*%', _expand, text)

    # -- Step 6: Expand Cardinal Numbers --------------------------------------

    def _expand_numbers(self, text: str) -> str:
        """Angka cardinal standalone → kata Bahasa Indonesia.
        Tidak memproses angka yang didahului kata 'nomor ' (dari #N expansion).
        """
        def _expand(m: re.Match) -> str:
            # Periksa apakah angka didahului 'nomor ' — jika ya, biarkan
            start = m.start()
            prefix = text[max(0, start - 7):start]
            if prefix.rstrip().endswith('nomor'):
                return m.group(0)
            num = int(m.group(0))
            if 1990 <= num <= 2099:   # tahun — biarkan
                return m.group(0)
            if num > 999_999:
                return m.group(0)
            return _number_to_words_id(num)
        return re.sub(r'(?<![A-Za-z\-])\b(\d{1,6})\b(?![A-Za-z\-])', _expand, text)

    # -- Step 7: Expand Acronyms ----------------------------------------------

    def _expand_acronyms(self, text: str) -> str:
        """CPU → C-P-U  |  SLA → S-L-A (urutan terpanjang dulu)."""
        for acronym in sorted(ACRONYM_MAP.keys(), key=len, reverse=True):
            ejaan = ACRONYM_MAP[acronym]
            text = re.sub(r'\b' + re.escape(acronym) + r'\b', ejaan, text, flags=re.IGNORECASE)
        return text

    # -- Step 8: Normalize Symbols --------------------------------------------

    def _normalize_symbols(self, text: str) -> str:
        """Ganti simbol operator dan tanda baca yang kaku menjadi kata/koma yang natural diucapkan."""
        # Strip parenthetical abbreviations or convert to smooth commas (e.g. "(RCA)" -> "")
        text = re.sub(r'\s*\(([A-Z0-9_\-\s]{2,10})\)', '', text)
        replacements = [
            (r'\s*\u2192\s*',          ', menjadi '),
            (r'\s*\u2190\s*',          ', dari '),
            (r'\s*\u2191\s*',          ' naik '),
            (r'\s*\u2193\s*',          ' turun '),
            (r'\s*\u2265\s*',          ' lebih dari atau sama dengan '),
            (r'\s*\u2264\s*',          ' kurang dari atau sama dengan '),
            (r'\s*[\u2014\u2013]\s*',   ', '),
            (r'\s*--+\s*',             ', '),
            (r'\.{3,}',               ', '),
            (r'&amp;',                ' dan '),
            (r'&',                    ' dan '),
            (r'@',                    ' at '),
            # #42 → "nomor 42" (angka dijaga dari double-expansion oleh _expand_numbers)
            (r'#(\d+)',               r'nomor \1'),
            (r'#(\w+)',               r'\1'),
        ]
        for pattern, replacement in replacements:
            text = re.sub(pattern, replacement, text)
        return text

    # -- Step 9: Normalize Whitespace -----------------------------------------

    def _normalize_whitespace(self, text: str) -> str:
        """Bersihkan whitespace berlebih dan newline."""
        text = re.sub(r'\n+', ', ', text)
        text = re.sub(r'  +', ' ', text)
        text = re.sub(r'[,;]{2,}', ',', text)
        text = re.sub(r'\.{2,}', '.', text)
        text = re.sub(r',\s*\.', '.', text)
        text = re.sub(r'\s+([.,!?:;])', r'\1', text)
        text = re.sub(r'([.,!?:;])(?=[^\s])', r'\1 ', text)
        return text.strip()

    # -- Step 10: Inject Natural Pauses ---------------------------------------

    def _inject_natural_pauses(self, text: str) -> str:
        """
        Tambahkan koma sebelum conjunction pada kalimat panjang (>8 kata)
        untuk memberikan jeda bicara natural.
        """
        conjunctions = (
            r'\b(dan|atau|namun|tetapi|tapi|sehingga|karena|jika|bila|'
            r'apabila|saat|ketika|sedangkan)\b'
        )

        def _inject(m: re.Match) -> str:
            before_conj = m.string[:m.start()]
            # Hitung kata sejak tanda baca terakhir
            last_boundary = max(
                before_conj.rfind('.'),
                before_conj.rfind(','),
                before_conj.rfind('!'),
                before_conj.rfind('?'),
            )
            segment = before_conj[last_boundary + 1:]
            word_count = len(segment.split())
            if word_count > 8:
                return ', ' + m.group(0)
            return ' ' + m.group(0)

        text = re.sub(conjunctions, _inject, text, flags=re.IGNORECASE)
        text = text.strip()
        if text and text[-1] not in '.!?':
            text += '.'
        return text
