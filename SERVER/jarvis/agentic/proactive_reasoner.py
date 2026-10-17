"""
SERVER.jarvis.agentic.proactive_reasoner — JARVIS Proactive Insight Synthesizer
================================================================================
Pilar 3: Setelah setiap tool execution, ProactiveReasoner meminta Gemini untuk:
  1. Menginterpretasi data hasil tool (bukan hanya membacakan data mentah)
  2. Mendeteksi anomali / tren yang perlu diperhatikan
  3. Menyarankan satu langkah selanjutnya yang relevan dan kontekstual

FILOSOFI:
  - Hardcoded handler mengeksekusi dan mengumpulkan data (RELIABLE)
  - Gemini menganalisis data dan memberi insight bernilai tambah (INTELLIGENT)
  - Keduanya SALING MELENGKAPI, bukan saling menggantikan

Output proaktif SELALU:
  - Maksimal 2 kalimat (agar TTS natural dan tidak bertele-tele)
  - Ditulis dalam Bahasa Indonesia santai/humanis
  - Relevan dengan data aktual yang diterima (zero hallucination)
  - Diakhiri dengan satu pertanyaan/saran tindakan (jika ada)

Contoh:
  Data masuk: "CPU 94%, RAM 87%, trend naik 12% dalam 10 menit"
  Output:  "CPU server ini sudah hampir di batas kritis Bosku, tren naiknya
            cukup cepat. Apakah perlu saya periksa proses mana yang paling boros,
            atau langsung aktifkan failover ke node backup?"
"""
from __future__ import annotations

import logging
import os
import json
import time
import urllib.request
import urllib.error
from typing import Any, Dict, Optional

logger = logging.getLogger("jarvis.agentic.proactive_reasoner")

# ── System Prompt ProactiveReasoner ──────────────────────────────────────────
PROACTIVE_SYSTEM_PROMPT = """\
Kamu adalah JARVIS, Senior Site Reliability Engineer AI untuk tim NOC Enterprise.

TUGAS: Setelah handler menjalankan perintah operator dan menghasilkan data,
kamu bertugas memberikan INSIGHT PROAKTIF berupa 1-2 kalimat analisis + saran konkret.

ATURAN KETAT:
1. Tulis HANYA teks plain yang bisa langsung diucapkan TTS (tanpa markdown, simbol, bullet).
2. Maksimal 2 kalimat. Singkat, padat, berisi.
3. Gunakan Bahasa Indonesia santai namun profesional.
4. Jika data menunjukkan kondisi normal/baik → akui dengan singkat dan tawarkan monitoring lanjutan.
5. Jika data menunjukkan anomali/warning → highlight dengan jelas dan sarankan tindakan SPESIFIK.
6. Akhiri dengan satu pertanyaan tindakan jika relevan (contoh: "Apakah perlu saya...?").
7. JANGAN mengulang seluruh data yang sudah dibacakan handler — cukup interpretasinya.
8. Jangan gunakan kata "JARVIS" untuk merujuk dirimu sendiri dalam output.
9. Output HARUS berupa string teks saja — bukan JSON, bukan list, bukan objek.
"""


class ProactiveReasoner:
    """
    Post-action proactive insight synthesizer menggunakan Gemini.

    Dipanggil SETELAH handler mengembalikan answer_text, untuk menambahkan
    satu lapisan analisis cerdas yang membuat JARVIS terasa seperti Senior SRE
    bukan sekadar chatbot yang membacakan data.
    """

    def __init__(self):
        self._gemini_api_key = self._load_gemini_key()
        self._model = "gemini-1.5-flash"
        self._enabled = bool(self._gemini_api_key)
        if self._enabled:
            logger.info("[ProactiveReasoner] ✅ Gemini initialized — proactive insights ACTIVE.")
        else:
            logger.warning("[ProactiveReasoner] ⚠️ Gemini API key not found — proactive insights DISABLED.")

    def _load_gemini_key(self) -> str:
        """Load Gemini API key dari environment atau .env file."""
        key = os.getenv("GEMINI_API_KEY", "")
        if not key or key in ("YOUR_GEMINI_API_KEY_HERE", ""):
            # Coba baca langsung dari .env file
            for env_path in ["/app/.env", ".env", "../.env"]:
                try:
                    with open(env_path) as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("GEMINI_API_KEY="):
                                val = line.split("=", 1)[1].strip().strip('"\'')
                                if val and val != "YOUR_GEMINI_API_KEY_HERE":
                                    return val
                except (FileNotFoundError, PermissionError):
                    continue
        return key if key and key != "YOUR_GEMINI_API_KEY_HERE" else ""

    def generate_insight(
        self,
        tool_name: str,
        tool_result_text: str,
        user_query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate proactive insight berdasarkan hasil tool execution.

        Args:
            tool_name:        Nama tool yang dipanggil (get_live_incidents, get_host_metrics, dll)
            tool_result_text: Teks hasil yang sudah diformat oleh handler
            user_query:       Query asli operator
            context:          Context tambahan (device, session history, dll)

        Returns:
            Teks insight proaktif 1-2 kalimat, atau "" jika tidak relevan/gagal.
        """
        if not self._enabled:
            return ""

        # Beberapa tool tidak perlu insight (jawaban langsung, navigasi UI)
        skip_tools = {"answer_directly", "open_dashboard_panel", "assign_field_engineer"}
        if tool_name in skip_tools:
            return ""

        # Jangan tambah insight jika jawaban terlalu pendek (error/fallback)
        if len(tool_result_text.strip()) < 50:
            return ""

        ctx = context or {}
        context_note = ""
        if ctx.get("last_device"):
            context_note = f"\nDevice yang dibahas: {ctx['last_device']}"
        if ctx.get("last_incident"):
            context_note += f"\nInsiden terkait: {ctx['last_incident']}"

        prompt = (
            f"{PROACTIVE_SYSTEM_PROMPT}\n\n"
            f"Perintah operator: \"{user_query}\"\n"
            f"Tool yang dieksekusi: {tool_name}\n"
            f"{context_note}\n\n"
            f"Data hasil eksekusi:\n{tool_result_text[:1500]}\n\n"
            f"Berikan INSIGHT PROAKTIF 1-2 kalimat:"
        )

        insight = self._call_gemini(prompt)
        if insight:
            logger.info(
                "[ProactiveReasoner] Generated insight for tool '%s': %s chars",
                tool_name, len(insight)
            )
        return insight

    def _call_gemini(self, prompt: str) -> str:
        """Panggil Gemini REST API untuk menghasilkan insight."""
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self._model}:generateContent?key={self._gemini_api_key}"
        )
        data = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 150,
                "stopSequences": ["\n\n"],
            }
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                candidates = resp_data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    text = parts[0].get("text", "").strip() if parts else ""
                    # Bersihkan output dari artefak markdown
                    text = text.replace("**", "").replace("*", "").replace("```", "").strip()
                    return text
        except urllib.error.HTTPError as e:
            logger.warning("[ProactiveReasoner] Gemini HTTP error %s: %s", e.code, e.reason)
        except Exception as e:
            logger.debug("[ProactiveReasoner] Gemini call failed (non-fatal): %s", e)
        return ""

    @property
    def is_enabled(self) -> bool:
        return self._enabled
