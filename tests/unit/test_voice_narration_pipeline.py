"""
tests/unit/test_voice_narration_pipeline.py
============================================
Unit Tests — JARVIS Natural Voice Narration Pipeline (v3.0)

Coverage:
  - TestSpokenTextNormalizer  : semua transformasi normalizer
  - TestSSMLBuilder           : output SSML wellformed + sesuai persona/severity
  - TestPersonaVoiceConfig    : semua persona terdaftar dengan voice name valid

Run:
  cd /home/it-itsm/AI/incident-analysis
  python3 -m pytest tests/unit/test_voice_narration_pipeline.py -v
"""
import re
import sys
import os
import unittest

# Tambahkan workspace root ke sys.path agar import SERVER.jarvis.voice berfungsi
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))


# ============================================================================
# TEST: SpokenTextNormalizer
# ============================================================================

class TestSpokenTextNormalizer(unittest.TestCase):
    """Unit tests untuk SpokenTextNormalizer — transformasi LLM output → spoken text."""

    def setUp(self):
        from SERVER.jarvis.voice.spoken_text_normalizer import SpokenTextNormalizer
        self.normalizer = SpokenTextNormalizer()

    # -- Markdown stripping ---------------------------------------------------

    def test_strip_bold_asterisks(self):
        result = self.normalizer.normalize("**CPU** naik drastis.")
        self.assertNotIn("**", result)
        self.assertIn("C-P-U", result)  # akronim sudah di-expand

    def test_strip_inline_code(self):
        result = self.normalizer.normalize("cek `status` server sekarang.")
        self.assertNotIn("`", result)
        self.assertIn("status", result)

    def test_strip_heading(self):
        result = self.normalizer.normalize("# Status Insiden\nCPU tinggi.")
        self.assertNotIn("#", result)
        self.assertIn("Status Insiden", result)

    def test_strip_bullet_list(self):
        result = self.normalizer.normalize("- item satu\n- item dua")
        self.assertNotIn("- item", result)
        self.assertIn("item satu", result)

    def test_strip_link_markdown(self):
        result = self.normalizer.normalize("[link ke dokumen](https://example.com)")
        self.assertNotIn("[", result)
        self.assertNotIn("]", result)
        self.assertIn("link ke dokumen", result)

    # -- IP Address expansion -------------------------------------------------

    def test_expand_ip_address(self):
        result = self.normalizer.normalize("server di 192.168.1.1 down.")
        self.assertNotIn("192.168.1.1", result)
        self.assertIn("titik", result)

    def test_expand_ip_does_not_affect_version(self):
        """IP dan versi harus diproses dengan aturan berbeda."""
        result_ip = self.normalizer.normalize("192.168.1.10")
        result_ver = self.normalizer.normalize("v1.2.0")
        self.assertIn("titik", result_ip)
        self.assertIn("versi", result_ver)

    # -- Version string expansion ---------------------------------------------

    def test_expand_version_simple(self):
        result = self.normalizer.normalize("update ke v2.0 selesai.")
        self.assertIn("versi dua", result)
        self.assertNotIn("v2.0", result)

    def test_expand_version_three_part(self):
        result = self.normalizer.normalize("v1.2.3 deployed.")
        self.assertIn("versi", result)
        self.assertIn("satu", result)

    # -- Percentage expansion -------------------------------------------------

    def test_expand_percent_integer(self):
        result = self.normalizer.normalize("CPU naik 90%.")
        self.assertIn("sembilan puluh persen", result)
        self.assertNotIn("90%", result)

    def test_expand_percent_zero(self):
        result = self.normalizer.normalize("0% packet loss.")
        self.assertIn("nol persen", result)

    def test_expand_percent_100(self):
        result = self.normalizer.normalize("disk penuh 100%.")
        self.assertIn("seratus persen", result)

    # -- Number to words conversion -------------------------------------------

    def test_expand_single_digit(self):
        result = self.normalizer.normalize("ada 3 insiden kritis.")
        self.assertIn("tiga", result)

    def test_expand_two_digit(self):
        result = self.normalizer.normalize("CPU 45 proses aktif.")
        self.assertIn("empat puluh lima", result)

    def test_expand_hundred(self):
        result = self.normalizer.normalize("ada 150 request pending.")
        self.assertIn("seratus lima puluh", result)

    def test_year_not_expanded(self):
        """Tahun 1990-2099 tidak boleh dikonversi ke kata."""
        result = self.normalizer.normalize("insiden tahun 2024.")
        self.assertIn("2024", result)  # tahun dipertahankan

    # -- Acronym expansion ----------------------------------------------------

    def test_expand_cpu_acronym(self):
        result = self.normalizer.normalize("CPU load tinggi.")
        self.assertIn("C-P-U", result)

    def test_expand_sla_acronym(self):
        result = self.normalizer.normalize("SLA breach terdeteksi.")
        self.assertIn("S-L-A", result)

    def test_expand_bgp_acronym(self):
        result = self.normalizer.normalize("BGP peer down.")
        self.assertIn("B-G-P", result)

    def test_expand_hitl_acronym(self):
        result = self.normalizer.normalize("butuh HITL approval.")
        self.assertIn("H-I-T-L", result)

    def test_expand_rdp_acronym(self):
        result = self.normalizer.normalize("koneksi RDP terputus.")
        self.assertIn("R-D-P", result)

    def test_acronym_case_insensitive(self):
        result = self.normalizer.normalize("cpu dan ram normal.")
        self.assertIn("C-P-U", result)
        self.assertIn("R-A-M", result)

    # -- Symbol normalization -------------------------------------------------

    def test_normalize_em_dash(self):
        result = self.normalizer.normalize("status — down.")
        self.assertNotIn("—", result)

    def test_normalize_hash_number(self):
        result = self.normalizer.normalize("insiden #42 kritis.")
        # #42 harus menghasilkan "nomor" diikuti angka (digits atau kata)
        self.assertIn("nomor", result)

    # -- Natural pause injection ----------------------------------------------

    def test_ends_with_punctuation(self):
        result = self.normalizer.normalize("server sedang dimonitor")
        self.assertIn(result[-1], '.!?')

    def test_long_sentence_gets_comma_before_conjunction(self):
        """Kalimat panjang (>8 kata) sebelum 'dan' harus mendapat koma."""
        long_text = (
            "Sistem mendeteksi lonjakan penggunaan memori yang sangat signifikan pada server utama dan "
            "kami merekomendasikan tindakan segera."
        )
        result = self.normalizer.normalize(long_text)
        # Ada koma sebelum 'dan' atau conjunction lainnya
        self.assertIn(",", result)

    # -- URL expansion --------------------------------------------------------

    def test_expand_url(self):
        result = self.normalizer.normalize("lihat https://github.com/user untuk detail.")
        self.assertNotIn("https://", result)
        self.assertIn("github", result)
        self.assertIn("titik", result)

    # -- End-to-end complex case ----------------------------------------------

    def test_complex_llm_output(self):
        """Simulasi output LLM yang mengandung berbagai elemen."""
        llm_output = (
            "**CPU** di `192.168.1.5` naik 90% — **SLA** breach! "
            "Update ke v1.2.0 sudah diterapkan."
        )
        result = self.normalizer.normalize(llm_output)
        # Tidak ada markdown
        self.assertNotIn("**", result)
        self.assertNotIn("`", result)
        # Akronim di-expand
        self.assertIn("C-P-U", result)
        self.assertIn("S-L-A", result)
        # Persentase di-expand
        self.assertIn("sembilan puluh persen", result)
        # Versi di-expand
        self.assertIn("versi", result)
        # IP di-expand (ada 'titik')
        self.assertIn("titik", result)


# ============================================================================
# TEST: SSMLBuilder
# ============================================================================

class TestSSMLBuilder(unittest.TestCase):
    """Unit tests untuk SSMLBuilder — output SSML wellformed."""

    def setUp(self):
        from SERVER.jarvis.voice.ssml_builder import SSMLBuilder
        self.builder = SSMLBuilder()

    def _is_valid_ssml(self, ssml: str) -> bool:
        """Cek apakah string adalah SSML yang wellformed (minimal struktur)."""
        return (
            ssml.strip().startswith('<speak') and
            '</speak>' in ssml and
            '<voice' in ssml and
            '<prosody' in ssml
        )

    def test_produces_valid_ssml_structure(self):
        ssml = self.builder.build_ssml("Sistem normal.", persona_id="noc_engineer", severity="INFO")
        self.assertTrue(self._is_valid_ssml(ssml), f"Invalid SSML: {ssml[:200]}")

    def test_ssml_contains_voice_name(self):
        """v4.0 Voice Policy: semua persona menggunakan GadisNeural (suara wanita) sebagai primary."""
        ssml = self.builder.build_ssml("Test.", persona_id="noc_engineer", severity="INFO")
        # v4.0: noc_engineer primary voice = id-ID-GadisNeural (wanita)
        self.assertIn("GadisNeural", ssml)
        # Pastikan bukan ArdiNeural (pria) yang digunakan sebagai primary
        self.assertNotIn("ArdiNeural", ssml)

    def test_ssml_executive_uses_gadis_voice(self):
        ssml = self.builder.build_ssml("Test executive.", persona_id="executive", severity="INFO")
        self.assertIn("GadisNeural", ssml)

    def test_critical_severity_has_loud_volume(self):
        ssml = self.builder.build_ssml("Darurat sistem!", persona_id="noc_engineer", severity="CRITICAL")
        self.assertIn("loud", ssml)

    def test_critical_severity_rate_faster(self):
        ssml = self.builder.build_ssml("Darurat!", persona_id="noc_engineer", severity="CRITICAL")
        # Rate CRITICAL untuk noc_engineer = +10%
        self.assertIn("+10%", ssml)

    def test_low_severity_rate_slower(self):
        ssml = self.builder.build_ssml("Info.", persona_id="noc_engineer", severity="LOW")
        # Rate LOW untuk noc_engineer = -8%
        self.assertIn("-8%", ssml)

    def test_ssml_contains_xml_lang(self):
        ssml = self.builder.build_ssml("Test.", persona_id="noc_engineer", locale="id-ID")
        self.assertIn('xml:lang="id-ID"', ssml)

    def test_ssml_contains_break_tags(self):
        ssml = self.builder.build_ssml(
            "Sistem down. Perlu penanganan segera.",
            persona_id="noc_engineer",
            severity="HIGH"
        )
        self.assertIn("<break", ssml)

    def test_is_ssml_detection(self):
        ssml = self.builder.build_ssml("Test.")
        self.assertTrue(self.builder.is_ssml(ssml))
        self.assertFalse(self.builder.is_ssml("plain text"))

    def test_extract_plain_text_from_ssml(self):
        ssml = self.builder.build_ssml("Server down sekarang.")
        plain = self.builder.extract_plain_text_from_ssml(ssml)
        self.assertNotIn("<", plain)
        self.assertNotIn(">", plain)
        self.assertIn("Server", plain)

    def test_empty_text_returns_empty(self):
        result = self.builder.build_ssml("", persona_id="noc_engineer", severity="INFO")
        self.assertEqual(result, "")

    def test_plain_prosody_text_passthrough(self):
        result = self.builder.build_plain_prosody_text(
            "Test plain.", persona_id="noc_engineer", severity="INFO"
        )
        self.assertEqual(result, "Test plain.")

    def test_html_escape_in_ssml(self):
        """Karakter < dan > harus di-escape dalam SSML body."""
        text = "nilai lebih dari 90."
        ssml = self.builder.build_ssml(text, persona_id="noc_engineer", severity="INFO")
        # Tidak ada unescaped < atau > di dalam content (hanya dalam tags)
        # Strip tags, lalu cek
        body_only = re.sub(r'<[^>]+>', '', ssml)
        self.assertNotIn(" < ", body_only)
        self.assertNotIn(" > ", body_only)


# ============================================================================
# TEST: PersonaVoiceConfig
# ============================================================================

class TestPersonaVoiceConfig(unittest.TestCase):
    """Unit tests untuk persona_voice_config — registry suara per persona."""

    def setUp(self):
        from SERVER.jarvis.voice.persona_voice_config import (
            PERSONA_VOICE_REGISTRY,
            get_voice_profile,
            get_voice_name,
            get_prosody_for_severity,
            list_all_personas,
        )
        self.registry = PERSONA_VOICE_REGISTRY
        self.get_voice_profile = get_voice_profile
        self.get_voice_name = get_voice_name
        self.get_prosody_for_severity = get_prosody_for_severity
        self.list_all_personas = list_all_personas

    def test_all_required_personas_registered(self):
        """Semua persona wajib harus terdaftar."""
        required = {"noc_engineer", "incident_manager", "executive", "alert_mode"}
        registered = set(self.registry.keys())
        missing = required - registered
        self.assertEqual(missing, set(), f"Missing personas: {missing}")

    def test_all_personas_have_primary_voice(self):
        """Setiap persona harus memiliki primary_voice yang tidak kosong."""
        for persona_id, profile in self.registry.items():
            self.assertTrue(
                profile.primary_voice,
                f"Persona '{persona_id}' has empty primary_voice"
            )
            # Voice harus format valid Microsoft Azure Neural TTS
            self.assertIn("Neural", profile.primary_voice,
                f"Voice '{profile.primary_voice}' for persona '{persona_id}' is not a Neural voice")

    def test_all_personas_have_indonesian_voice(self):
        """Semua voice harus berformat Bahasa Indonesia (id-ID)."""
        for persona_id, profile in self.registry.items():
            self.assertTrue(
                profile.primary_voice.startswith("id-ID"),
                f"Persona '{persona_id}' primary_voice '{profile.primary_voice}' is not id-ID"
            )

    def test_all_severities_have_overrides(self):
        """Setiap persona harus memiliki severity overrides untuk semua level."""
        required_severities = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}
        for persona_id, profile in self.registry.items():
            present = set(profile.severity_overrides.keys())
            missing = required_severities - present
            self.assertEqual(missing, set(),
                f"Persona '{persona_id}' missing severity overrides: {missing}")

    def test_get_voice_name_known_persona(self):
        voice = self.get_voice_name("noc_engineer")
        self.assertIn("Neural", voice)
        self.assertTrue(voice.startswith("id-ID"))

    def test_get_voice_name_unknown_persona_fallback(self):
        """Unknown persona harus fallback ke noc_engineer, bukan raise error."""
        voice = self.get_voice_name("unknown_persona_xyz")
        self.assertIn("Neural", voice)

    def test_get_prosody_critical_severity(self):
        prosody = self.get_prosody_for_severity("noc_engineer", "CRITICAL")
        self.assertIn("rate", prosody)
        self.assertIn("pitch", prosody)
        self.assertIn("volume", prosody)
        # CRITICAL harus lebih cepat dari default
        self.assertIn("+", prosody["rate"])

    def test_get_prosody_low_severity_slower(self):
        prosody_critical = self.get_prosody_for_severity("noc_engineer", "CRITICAL")
        prosody_low = self.get_prosody_for_severity("noc_engineer", "LOW")
        # Tidak bisa langsung compare string, tapi LOW harus punya minus rate
        self.assertIn("-", prosody_low["rate"])

    def test_list_all_personas_returns_dict(self):
        personas = self.list_all_personas()
        self.assertIsInstance(personas, dict)
        self.assertGreaterEqual(len(personas), 4)

    def test_get_voice_profile_returns_profile_object(self):
        from SERVER.jarvis.voice.persona_voice_config import PersonaVoiceProfile
        profile = self.get_voice_profile("noc_engineer")
        self.assertIsInstance(profile, PersonaVoiceProfile)

    def test_alert_mode_louder_than_info(self):
        """alert_mode harus menghasilkan volume yang lebih keras."""
        prosody_alert = self.get_prosody_for_severity("alert_mode", "CRITICAL")
        self.assertEqual(prosody_alert["volume"], "x-loud")


# ============================================================================
# TEST: Integration — SpokenTextNormalizer + SSMLBuilder pipeline
# ============================================================================

class TestNarrativePipeline(unittest.TestCase):
    """Integration test: full normalize → SSML pipeline."""

    def setUp(self):
        from SERVER.jarvis.voice.spoken_text_normalizer import SpokenTextNormalizer
        from SERVER.jarvis.voice.ssml_builder import SSMLBuilder
        self.normalizer = SpokenTextNormalizer()
        self.builder = SSMLBuilder()

    def test_full_pipeline_produces_ssml_without_markdown(self):
        """LLM output → normalize → SSML tidak mengandung markdown symbols."""
        llm_output = "**CPU** naik 90% — **SLA** breach! Server `192.168.1.1` down."
        normalized = self.normalizer.normalize(llm_output)
        ssml = self.builder.build_ssml(normalized, persona_id="noc_engineer", severity="CRITICAL")

        # SSML valid
        self.assertIn("<speak", ssml)
        # Tidak ada markdown dalam SSML body
        plain = self.builder.extract_plain_text_from_ssml(ssml)
        self.assertNotIn("**", plain)
        self.assertNotIn("`", plain)
        # Akronim di-expand
        self.assertIn("C-P-U", plain)
        self.assertIn("S-L-A", plain)

    def test_full_pipeline_critical_uses_loud_volume(self):
        normalized = self.normalizer.normalize("CPU 90% down SLA breach.")
        ssml = self.builder.build_ssml(normalized, persona_id="noc_engineer", severity="CRITICAL")
        self.assertIn("loud", ssml)

    def test_full_pipeline_info_uses_soft_volume(self):
        normalized = self.normalizer.normalize("Status sistem normal.")
        ssml = self.builder.build_ssml(normalized, persona_id="noc_engineer", severity="INFO")
        self.assertIn("soft", ssml)

    def test_pipeline_empty_text(self):
        normalized = self.normalizer.normalize("")
        # Empty normalization — should handle gracefully
        ssml = self.builder.build_ssml(normalized, persona_id="noc_engineer", severity="INFO")
        self.assertEqual(ssml, "")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
