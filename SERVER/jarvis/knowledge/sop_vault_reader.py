"""
SERVER.jarvis.knowledge.sop_vault_reader — JARVIS SOP Vault Reader
====================================================================
Production module untuk JARVIS membaca dan mencari Canonical SOP via suara.

Fitur:
  ✅ READ_SOP     — Bacakan isi SOP canonical untuk intent tertentu
  ✅ SEARCH_SOP   — Cari SOP berdasarkan kata kunci bebas
  ✅ GET_SOPS     — Daftar semua canonical SOP yang aktif
  ✅ Voice-optimized summary — Output singkat ≤120 kata untuk TTS
  ✅ Vault Sync   — Sinkronisasi antara canonical dir, obsidian_vault, docs/SOP_VAULT

Contoh perintah yang didukung:
  "Jarvis, bacakan SOP restart spooler"
  "Jarvis, cari SOP untuk DNS flush"
  "Jarvis, daftar semua SOP aktif"
  "Jarvis, tampilkan SOP printer"
  "Jarvis, cara penanganan spooler"
"""
from __future__ import annotations

import glob
import logging
import os
import re
import shutil
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("jarvis.knowledge.sop_vault_reader")

# ─── Lokasi Vault (resolved dari lokasi file ini) ─────────────────────────────
_THIS_DIR       = os.path.dirname(os.path.abspath(__file__))          # SERVER/jarvis/knowledge/
_SERVER_DIR     = os.path.abspath(os.path.join(_THIS_DIR, "..", ".."))  # SERVER/
_PROJECT_ROOT   = os.path.abspath(os.path.join(_SERVER_DIR, ".."))     # incident-analysis/

_CANONICAL_DIR  = os.path.join(_SERVER_DIR, "python_ai_core", "auto_generated_sops", "sop_canonical")
_OBSIDIAN_DIR   = os.path.join(_PROJECT_ROOT, "DOCUMENTATION", "obsidian_vault", "sops")
_DOCS_VAULT_DIR = os.path.join(_PROJECT_ROOT, "docs", "SOP_VAULT")

# Intent → nama aksi yang mudah diucapkan (untuk TTS)
_INTENT_FRIENDLY_NAME: Dict[str, str] = {
    "ACT_RESTART_SPOOLER":          "Restart Windows Print Spooler",
    "ACT_RESTART_PRINTER_SERVICE":  "Restart Printer Service",
    "ACT_CLEAR_PRINT_QUEUE":        "Bersihkan Antrian Cetak",
    "ACT_CLEAR_QUEUE":              "Bersihkan Antrian",
    "ACT_CLEAR_CACHE":              "Bersihkan Cache",
    "ACT_FLUSH_DNS":                "Flush DNS Cache",
    "ACT_ENABLE_PORT":              "Aktifkan Port Jaringan",
    "ACT_RESTART_SERVICE":          "Restart Service",
    "ACT_TRIGGER_OTA":              "Trigger OTA Update",
    "ACT_RUN_SANDBOX_TEST":         "Jalankan Sandbox Test",
    "ACT_TRIGGER_N8N_WORKFLOW":     "Trigger n8n Workflow",
    "ACT_N8N_VAULT_SYNC":           "Sinkronisasi Vault via n8n",
    "ACT_N8N_PUBLISH_POSTMORTEM":   "Publish Postmortem via n8n",
    "ACT_IMPORT_KNOWLEDGE":         "Import Knowledge Base",
    "ACT_REGISTER_DEVICE":          "Daftarkan Device Baru",
    "ACT_REANALYZE_RCA":            "Analisa Ulang Root Cause",
    "ACT_CREATE_SOP":               "Buat SOP Baru",
    "ACT_EXECUTE_SOP":              "Eksekusi SOP",
    "PRINTER_SPOOLER_STALLED":      "Printer Spooler Macet",
    "PRINT_SPOOLER_STALL":          "Print Spooler Stall",
}

# Keyword ke intent mapping untuk pencarian bebas
_KEYWORD_INTENT_MAP: Dict[str, str] = {
    "spooler":        "ACT_RESTART_SPOOLER",
    "print spooler":  "ACT_RESTART_SPOOLER",
    "restart spooler":"ACT_RESTART_SPOOLER",
    "printer service":"ACT_RESTART_PRINTER_SERVICE",
    "antrian cetak":  "ACT_CLEAR_PRINT_QUEUE",
    "print queue":    "ACT_CLEAR_PRINT_QUEUE",
    "queue":          "ACT_CLEAR_QUEUE",
    "antrian":        "ACT_CLEAR_QUEUE",
    "cache":          "ACT_CLEAR_CACHE",
    "dns":            "ACT_FLUSH_DNS",
    "flush dns":      "ACT_FLUSH_DNS",
    "port":           "ACT_ENABLE_PORT",
    "service":        "ACT_RESTART_SERVICE",
    "ota":            "ACT_TRIGGER_OTA",
    "firmware":       "ACT_TRIGGER_OTA",
    "sandbox":        "ACT_RUN_SANDBOX_TEST",
    "n8n":            "ACT_TRIGGER_N8N_WORKFLOW",
    "vault sync":     "ACT_N8N_VAULT_SYNC",
    "postmortem":     "ACT_N8N_PUBLISH_POSTMORTEM",
    "knowledge":      "ACT_IMPORT_KNOWLEDGE",
    "device":         "ACT_REGISTER_DEVICE",
    "rca":            "ACT_REANALYZE_RCA",
}


class SOPVaultReader:
    """
    Production SOP Vault Reader untuk JARVIS Voice Commands.
    Membaca dari canonical SOP directory dan menghasilkan respons voice-friendly.
    """

    def __init__(self) -> None:
        os.makedirs(_CANONICAL_DIR, exist_ok=True)
        os.makedirs(_OBSIDIAN_DIR, exist_ok=True)

    # ─── Helper: baca canonical SOP file ──────────────────────────────────────
    def _read_canonical(self, intent: str) -> Optional[str]:
        """Baca isi file canonical SOP untuk intent tertentu."""
        safe = re.sub(r"[^A-Z0-9_]", "_", intent.upper())
        path = os.path.join(_CANONICAL_DIR, f"SOP_CANONICAL_{safe}.md")
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.warning("[SOPVaultReader] Cannot read %s: %s", path, e)
            return None

    def _extract_voice_summary(self, content: str, intent: str) -> str:
        """
        Ekstrak ringkasan SOP yang optimal untuk TTS (≤ 120 kata).
        Mengambil Root Cause, Resolution Strategy, dan Bash Command.
        """
        lines = content.splitlines()
        root_cause = ""
        solution = ""
        bash_cmd = ""
        version = "?"
        in_bash = False

        for line in lines:
            line_s = line.strip()
            if line_s.startswith("sop_version:"):
                version = line_s.split(":", 1)[-1].strip()
            elif "Root Cause Analysis:" in line_s:
                root_cause = re.sub(r"\*+", "", line_s.split(":", 1)[-1]).strip()
            elif "Resolution Strategy:" in line_s:
                solution = re.sub(r"\*+", "", line_s.split(":", 1)[-1]).strip()
            elif line_s.startswith("```bash") or line_s == "```bash":
                in_bash = True
            elif in_bash and line_s.startswith("```"):
                in_bash = False
            elif in_bash and line_s and not line_s.startswith("#"):
                bash_cmd = line_s
                in_bash = False

        friendly_name = _INTENT_FRIENDLY_NAME.get(intent, intent.replace("_", " ").title())
        cmd_str = f"\n\nPerintah eksekusi: {bash_cmd}" if bash_cmd else ""

        summary = (
            f"📋 SOP {friendly_name} versi {version}.\n\n"
            f"Penyebab: {root_cause or 'Dianalisa otomatis oleh AI NOC.'}\n\n"
            f"Solusi: {solution or 'Ikuti prosedur remediasi standar.'}"
            f"{cmd_str}"
        )
        return summary

    # ─── Fuzzy intent match dari teks bebas ───────────────────────────────────
    def _resolve_intent_from_query(self, query: str) -> Optional[str]:
        """
        Cari intent yang paling relevan dari query teks bebas.
        Contoh: "restart printer spooler" → "ACT_RESTART_SPOOLER"
        """
        query_lower = query.lower()

        # 1. Langsung match dari keyword map (longest match first)
        for kw in sorted(_KEYWORD_INTENT_MAP.keys(), key=len, reverse=True):
            if kw in query_lower:
                return _KEYWORD_INTENT_MAP[kw]

        # 2. Cari dari nama file canonical yang tersedia
        if os.path.isdir(_CANONICAL_DIR):
            for fname in os.listdir(_CANONICAL_DIR):
                if not fname.endswith(".md") or not fname.startswith("SOP_CANONICAL_"):
                    continue
                intent = fname.replace("SOP_CANONICAL_", "").replace(".md", "")
                intent_words = intent.lower().replace("_", " ")
                if any(word in query_lower for word in intent_words.split() if len(word) > 3):
                    return intent

        return None

    # ─── PUBLIC APIs ──────────────────────────────────────────────────────────

    def read_sop(self, query: str) -> str:
        """
        READ_SOP: Bacakan isi SOP canonical berdasarkan query.

        Contoh: "bacakan SOP restart spooler"
        """
        intent = self._resolve_intent_from_query(query)
        if not intent:
            available = self.list_sops_brief()
            return (
                f"❌ Tidak menemukan SOP untuk '{query}'.\n\n"
                f"SOP yang tersedia:\n{available}\n\n"
                "Coba: 'Jarvis, cari SOP DNS' atau 'Jarvis, daftar SOP aktif'"
            )

        content = self._read_canonical(intent)
        if not content:
            return (
                f"⚠️ SOP untuk '{intent}' ditemukan di index tapi file belum ada.\n"
                "Sistem akan membuat SOP saat insiden berikutnya diselesaikan."
            )

        summary = self._extract_voice_summary(content, intent)
        logger.info("[SOPVaultReader] READ_SOP: %s", intent)
        return summary

    def search_sop(self, query: str) -> str:
        """
        SEARCH_SOP: Cari SOP berdasarkan kata kunci, tampilkan daftar yang relevan.

        Contoh: "cari SOP untuk printer"
        """
        query_lower = query.lower()
        results: List[Tuple[str, str, str]] = []  # (intent, friendly_name, version)

        if os.path.isdir(_CANONICAL_DIR):
            for fname in sorted(os.listdir(_CANONICAL_DIR)):
                if not fname.endswith(".md") or not fname.startswith("SOP_CANONICAL_"):
                    continue
                intent = fname.replace("SOP_CANONICAL_", "").replace(".md", "")
                intent_words = intent.lower().replace("_", " ")

                # Match jika query ada di intent words atau friendly name
                friendly = _INTENT_FRIENDLY_NAME.get(intent, intent_words.title())
                if (query_lower in intent_words or
                    query_lower in friendly.lower() or
                    any(w in intent_words for w in query_lower.split() if len(w) > 3)):

                    # Extract version dari content
                    content = self._read_canonical(intent) or ""
                    version = "?"
                    for line in content.splitlines():
                        if line.strip().startswith("sop_version:"):
                            version = line.strip().split(":", 1)[-1].strip()
                            break

                    results.append((intent, friendly, version))

        if not results:
            return (
                f"🔍 Tidak ada SOP yang cocok untuk '{query}'.\n\n"
                f"Gunakan: 'Jarvis, daftar SOP aktif' untuk melihat semua SOP."
            )

        lines = [f"🔍 Hasil pencarian SOP untuk '{query}' ({len(results)} ditemukan):\n"]
        for intent, friendly, version in results[:5]:
            lines.append(f"  • {friendly} (v{version}) — '{intent}'")

        if len(results) > 5:
            lines.append(f"  ... dan {len(results) - 5} SOP lainnya.")

        lines.append("\n💡 Tip: 'Jarvis, bacakan SOP [nama]' untuk detail lengkap.")
        logger.info("[SOPVaultReader] SEARCH_SOP: '%s' → %d results", query, len(results))
        return "\n".join(lines)

    def get_all_sops(self) -> str:
        """
        GET_SOPS: Daftar semua canonical SOP aktif dengan versi.
        """
        sops: List[Tuple[str, str, str, int]] = []  # (intent, friendly, version, size)

        if os.path.isdir(_CANONICAL_DIR):
            for fname in sorted(os.listdir(_CANONICAL_DIR)):
                if not fname.endswith(".md") or not fname.startswith("SOP_CANONICAL_"):
                    continue
                intent = fname.replace("SOP_CANONICAL_", "").replace(".md", "")
                fpath = os.path.join(_CANONICAL_DIR, fname)
                fsize = os.path.getsize(fpath)
                friendly = _INTENT_FRIENDLY_NAME.get(intent, intent.replace("_", " ").title())

                content = self._read_canonical(intent) or ""
                version = "?"
                for line in content.splitlines():
                    if line.strip().startswith("sop_version:"):
                        version = line.strip().split(":", 1)[-1].strip()
                        break
                sops.append((intent, friendly, version, fsize))

        if not sops:
            return (
                "📭 Belum ada canonical SOP tersimpan.\n"
                "SOP akan dibuat otomatis saat incident pertama diselesaikan."
            )

        lines = [f"📚 Canonical SOP Vault — {len(sops)} SOP aktif:\n"]
        for i, (intent, friendly, version, size) in enumerate(sops, 1):
            lines.append(f"  {i:2}. [{version}] {friendly}")

        lines.append(f"\n✅ Total: {len(sops)} SOP | Lokasi: sop_canonical/")
        lines.append("💡 'Jarvis, bacakan SOP [nama]' untuk detail prosedur.")
        logger.info("[SOPVaultReader] GET_SOPS: %d SOPs listed", len(sops))
        return "\n".join(lines)

    def get_handling_procedure(self, query: str) -> str:
        """
        GET_HANDLING_PROCEDURE: Cara penanganan untuk insiden tertentu.
        Alias untuk read_sop dengan framing berbeda.
        """
        intent = self._resolve_intent_from_query(query)
        if not intent:
            return self.search_sop(query)

        content = self._read_canonical(intent)
        if not content:
            return f"⚠️ Belum ada prosedur tercatat untuk '{query}'."

        summary = self._extract_voice_summary(content, intent)
        friendly = _INTENT_FRIENDLY_NAME.get(intent, intent)
        return f"🔧 Prosedur penanganan untuk {friendly}:\n\n{summary}"

    # ─── Vault Sync ───────────────────────────────────────────────────────────
    def sync_vault_locations(self) -> Dict[str, Any]:
        """
        VAULT SYNC: Sinkronisasi canonical SOPs ke:
          1. DOCUMENTATION/obsidian_vault/sops/
          2. docs/SOP_VAULT/{INTENT}/SOP.md

        Memastikan single source of truth (canonical) menjadi master.
        """
        synced = 0
        errors = 0
        synced_files: List[str] = []

        if not os.path.isdir(_CANONICAL_DIR):
            return {"status": "ERROR", "message": "Canonical dir tidak ditemukan"}

        for fname in os.listdir(_CANONICAL_DIR):
            if not fname.endswith(".md") or not fname.startswith("SOP_CANONICAL_"):
                continue
            if fname == ".sop_versions.json":
                continue

            src = os.path.join(_CANONICAL_DIR, fname)
            intent = fname.replace("SOP_CANONICAL_", "").replace(".md", "")
            friendly_fname = f"SOP_{intent}.md"

            try:
                # Sync ke obsidian_vault/sops/
                os.makedirs(_OBSIDIAN_DIR, exist_ok=True)
                dst_obsidian = os.path.join(_OBSIDIAN_DIR, friendly_fname)
                shutil.copy2(src, dst_obsidian)

                # Sync ke docs/SOP_VAULT/{INTENT}/SOP.md
                vault_intent_dir = os.path.join(_DOCS_VAULT_DIR, intent)
                os.makedirs(vault_intent_dir, exist_ok=True)
                dst_vault = os.path.join(vault_intent_dir, "SOP.md")
                shutil.copy2(src, dst_vault)

                synced += 1
                synced_files.append(intent)
            except Exception as e:
                logger.warning("[SOPVaultReader] Sync error for %s: %s", intent, e)
                errors += 1

        logger.info("[SOPVaultReader] Vault sync: %d synced, %d errors", synced, errors)
        return {
            "status": "SUCCESS",
            "synced": synced,
            "errors": errors,
            "synced_intents": synced_files,
            "locations": [_CANONICAL_DIR, _OBSIDIAN_DIR, _DOCS_VAULT_DIR],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_vault_status(self) -> str:
        """Ringkasan status vault untuk semua 3 lokasi."""
        canonical_count = len([
            f for f in os.listdir(_CANONICAL_DIR)
            if f.endswith(".md") and f.startswith("SOP_CANONICAL_")
        ]) if os.path.isdir(_CANONICAL_DIR) else 0

        obsidian_count = len([
            f for f in os.listdir(_OBSIDIAN_DIR)
            if f.endswith(".md")
        ]) if os.path.isdir(_OBSIDIAN_DIR) else 0

        vault_count = len([
            d for d in os.listdir(_DOCS_VAULT_DIR)
            if os.path.isdir(os.path.join(_DOCS_VAULT_DIR, d))
        ]) if os.path.isdir(_DOCS_VAULT_DIR) else 0

        in_sync = (canonical_count == obsidian_count == vault_count)
        status_emoji = "✅" if in_sync else "⚠️"

        return (
            f"{status_emoji} SOP Vault Status:\n"
            f"  Canonical  : {canonical_count} SOPs (source of truth)\n"
            f"  Obsidian   : {obsidian_count} SOPs\n"
            f"  docs/VAULT : {vault_count} SOPs\n"
            f"{'  ✅ Semua tersinkronisasi' if in_sync else '  ⚠️ Perlu sync — jalankan: sync vault'}"
        )
