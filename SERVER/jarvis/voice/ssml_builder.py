"""
SERVER.jarvis.voice.ssml_builder — SSML Prosody Engine for EdgeTTS
===================================================================
Membungkus teks yang sudah dinormalisasi dalam tag SSML (Speech Synthesis
Markup Language) sesuai persona dan severity untuk EdgeTTS.

SSML memungkinkan kontrol penuh atas:
  - rate   : Kecepatan bicara (pitch, tempo)
  - pitch  : Nada dasar suara
  - volume : Keras/pelan suara
  - break  : Jeda eksplisit antar kalimat/frasa
  - emphasis: Penekanan kata kritis
  - say-as : Cara ucap khusus (spell-out, date, number)

Referensi SSML EdgeTTS:
  https://learn.microsoft.com/azure/cognitive-services/speech-service/speech-synthesis-markup

CATATAN: SSML hanya efektif via EdgeTTS (cloud). Jika fallback ke KokoroTTS/
parametric WAV, plain text digunakan (tanpa SSML tags).
"""
import re
import logging
import html
from typing import Optional

from SERVER.jarvis.voice.persona_voice_config import get_voice_profile, get_prosody_for_severity

logger = logging.getLogger("jarvis.voice.ssml_builder")

# =============================================================================
# SEVERITY → EMPHASIS LEVEL MAPPING
# =============================================================================
SEVERITY_EMPHASIS: dict = {
    "CRITICAL": "strong",
    "HIGH":     "moderate",
    "MEDIUM":   "none",
    "LOW":      "none",
    "INFO":     "none",
}

# Kata-kata kunci yang diberi emphasis saat severity CRITICAL/HIGH
CRITICAL_KEYWORDS = [
    "kritis", "darurat", "gagal", "error", "crash", "down", "breach",
    "serangan", "eskalasi", "peringatan keras", "alarm", "padam",
    "tidak tersedia", "melebihi", "terlampaui",
]

HIGH_KEYWORDS = [
    "tinggi", "bermasalah", "lambat", "overload", "penuh", "habis",
    "mendekat", "hampir", "segera", "perlu perhatian",
]

# =============================================================================
# SSML BUILDER CLASS
# =============================================================================

class SSMLBuilder:
    """
    Membangun SSML document untuk EdgeTTS berdasarkan:
      - teks (sudah dinormalisasi via SpokenTextNormalizer)
      - persona_id (noc_engineer | incident_manager | executive | alert_mode)
      - severity (CRITICAL | HIGH | MEDIUM | LOW | INFO)

    Contoh output SSML:
    <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="id-ID">
      <voice name="id-ID-GadisNeural">
        <prosody rate="+10%" pitch="+1Hz" volume="loud">
          <emphasis level="strong">Darurat!</emphasis>
          <break time="200ms"/>
          C-P-U di server kasir naik
          <emphasis level="strong">sembilan puluh persen</emphasis>,
          S-L-A breach.
          <break time="300ms"/>
          Lakukan pemantauan aktif sekarang.
        </prosody>
      </voice>
    </speak>
    """

    SSML_NS = 'xmlns="http://www.w3.org/2001/10/synthesis"'
    SSML_MSTTS_NS = 'xmlns:mstts="https://www.w3.org/2001/mstts"'

    def build_ssml(
        self,
        text: str,
        persona_id: str = "noc_engineer",
        severity: str = "INFO",
        locale: str = "id-ID",
    ) -> str:
        """
        Bangun SSML document lengkap untuk EdgeTTS.

        Args:
            text:       Teks sudah dinormalisasi (output SpokenTextNormalizer)
            persona_id: ID persona aktif
            severity:   Tingkat keparahan (CRITICAL|HIGH|MEDIUM|LOW|INFO)
            locale:     Locale bahasa (default: id-ID)

        Returns:
            String SSML siap dikirim ke EdgeTTS Communicate()
        """
        if not text or not text.strip():
            return text

        profile = get_voice_profile(persona_id)
        prosody = get_prosody_for_severity(persona_id, severity)
        voice_name = profile.primary_voice

        # Escape HTML special chars dalam teks
        escaped_text = html.escape(text)

        # Restore ejaan akronim (C-P-U → dipertahankan, tanda - tidak perlu di-escape)
        escaped_text = escaped_text.replace('-', '\u2011')  # non-breaking hyphen untuk akronim

        # Inject emphasis pada kata kunci sesuai severity
        escaped_text = self._inject_emphasis(escaped_text, severity)

        # Inject break pada akhir setiap kalimat untuk ritme natural
        escaped_text = self._inject_sentence_breaks(escaped_text, severity)

        # Handle ejaan per huruf (say-as spell-out) — akronim sudah di-expand
        # oleh SpokenTextNormalizer, tapi tanda - non-breaking perlu dikembalikan
        escaped_text = escaped_text.replace('\u2011', '-')

        # Bangun SSML
        ssml = (
            f'<speak version="1.0" {self.SSML_NS} {self.SSML_MSTTS_NS} xml:lang="{locale}">'
            f'<voice name="{voice_name}">'
            f'<prosody rate="{prosody["rate"]}" pitch="{prosody["pitch"]}" volume="{prosody["volume"]}">'
            f'{escaped_text}'
            f'</prosody>'
            f'</voice>'
            f'</speak>'
        )

        logger.debug(
            "[SSMLBuilder] Built SSML for persona='%s' severity='%s' voice='%s' len=%d",
            persona_id, severity, voice_name, len(ssml)
        )
        return ssml

    def build_plain_prosody_text(
        self,
        text: str,
        persona_id: str = "noc_engineer",
        severity: str = "INFO",
    ) -> str:
        """
        Versi tanpa SSML — hanya teks plain tapi dengan sentence breaks via koma.
        Digunakan sebagai fallback jika SSML tidak didukung provider.

        Args:
            text:       Teks yang sudah dinormalisasi
            persona_id: ID persona (tidak digunakan, untuk API consistency)
            severity:   Severity (tidak digunakan, untuk API consistency)

        Returns:
            Plain text dengan koma jeda yang lebih rapi.
        """
        return text.strip()

    # ── Internal Helpers ────────────────────────────────────────────────────

    def _inject_emphasis(self, text: str, severity: str) -> str:
        """
        Tambahkan tag <emphasis> pada kata kunci kritis sesuai severity.
        Hanya CRITICAL dan HIGH yang mendapat emphasis.
        """
        emphasis_level = SEVERITY_EMPHASIS.get(severity.upper(), "none")
        if emphasis_level == "none":
            return text

        keywords = []
        if severity.upper() == "CRITICAL":
            keywords = CRITICAL_KEYWORDS + HIGH_KEYWORDS
        elif severity.upper() == "HIGH":
            keywords = HIGH_KEYWORDS

        for kw in keywords:
            pattern = re.compile(r'\b(' + re.escape(html.escape(kw)) + r')\b', re.IGNORECASE)
            text = pattern.sub(
                lambda m: f'<emphasis level="{emphasis_level}">{m.group(1)}</emphasis>',
                text,
                count=1,  # hanya emphasize pertama kali muncul
            )

        return text

    def _inject_sentence_breaks(self, text: str, severity: str) -> str:
        """
        Tambahkan <break> tag setelah setiap kalimat untuk ritme bicara natural.
        Durasi break disesuaikan dengan severity.
        """
        break_durations = {
            "CRITICAL": "150ms",
            "HIGH":     "200ms",
            "MEDIUM":   "300ms",
            "LOW":      "350ms",
            "INFO":     "350ms",
        }
        break_time = break_durations.get(severity.upper(), "250ms")
        break_tag = f'<break time="{break_time}"/>'

        # Inject break setelah tanda baca kalimat (. ! ?) tapi bukan di akhir
        text = re.sub(r'([.!?])(\s+)(?=[A-Za-z\u00C0-\u024F])', rf'\1{break_tag}\2', text)

        # Inject break setelah koma pada kalimat panjang
        # Hanya koma yang diikuti >= 4 kata sebelum tanda baca berikutnya
        text = re.sub(r'(,)(\s+)', rf'\1<break time="100ms"/>\2', text)

        return text

    def extract_plain_text_from_ssml(self, ssml: str) -> str:
        """
        Strip semua SSML tags dan kembalikan plain text.
        Berguna untuk logging dan fallback display.
        """
        # Hapus semua XML tags
        plain = re.sub(r'<[^>]+>', ' ', ssml)
        # Normalisasi whitespace
        plain = re.sub(r'  +', ' ', plain).strip()
        return plain

    def is_ssml(self, text: str) -> bool:
        """Periksa apakah string adalah SSML document."""
        return text.strip().startswith('<speak')
