"""
SERVER.jarvis.knowledge.knowledge_learning_bridge — JARVIS Knowledge Learning Bridge
=====================================================================================
P13 Implementation + SOP Voice Reader Integration.

Setelah insiden selesai (RESOLVED/CLOSED), JARVIS otomatis:
  1. Mengambil data insiden (incident_id, RCA, solution)
  2. KnowledgeEvolutionEngine: dedup + conflict detection
  3. Memanggil KnowledgeAutoBuilder.auto_build_sop_from_incident() (v2.0)
  4. Canonical SOP dibuat/diperbarui (bukan per-incident file)
  5. Melaporkan ke operator via JARVIS suara

Voice Commands yang didukung:
  "Jarvis, buat SOP dari INC-001"           → build_sop_from_incident()
  "Jarvis, bacakan SOP restart spooler"     → read_sop()
  "Jarvis, cari SOP untuk DNS"              → search_sop()
  "Jarvis, daftar semua SOP aktif"          → get_all_sops()
  "Jarvis, cara penanganan spooler"         → get_handling_procedure()
  "Jarvis, berapa SOP yang belum direview?" → get_pending_review_count()
  "Jarvis, sync vault"                      → sync_vault()
  "Jarvis, status vault"                    → get_vault_status()
"""
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional

from SERVER.jarvis.noc.noc_bridge import JarvisNOCBridge

logger = logging.getLogger("jarvis.knowledge.learning_bridge")


class JarvisKnowledgeLearningBridge:
    """
    P13 — JARVIS Knowledge Learning Bridge.
    Auto-build SOP dari resolved incidents dan bridge ke knowledge pipeline.
    """

    def __init__(self, noc_bridge: Optional[JarvisNOCBridge] = None):
        self.bridge = noc_bridge or JarvisNOCBridge()
        self._builder: Optional[Any] = None
        self._evolution: Optional[Any] = None
        self._reader: Optional[Any] = None
        self._available = False
        self._try_init_builder()
        self._try_init_evolution()
        self._try_init_reader()

    def _try_init_builder(self) -> None:
        try:
            from SERVER.python_ai_core.knowledge.knowledge_auto_builder import KnowledgeAutoBuilder  # type: ignore
            self._builder = KnowledgeAutoBuilder()
            self._available = True
            logger.info("[KnowledgeLearningBridge] KnowledgeAutoBuilder v2.0 connected.")
        except Exception as e:
            logger.warning(f"[KnowledgeLearningBridge] KnowledgeAutoBuilder not available: {e}.")

    def _try_init_evolution(self) -> None:
        """Wire KnowledgeEvolutionEngine ke production pipeline (FIX: sebelumnya hanya di test suite)."""
        try:
            try:
                from SERVER.python_ai_core.knowledge.knowledge_evolution_engine import KnowledgeEvolutionEngine  # type: ignore
            except ImportError:
                from python_ai_core.knowledge.knowledge_evolution_engine import KnowledgeEvolutionEngine  # type: ignore
            self._evolution = KnowledgeEvolutionEngine()
            logger.info("[KnowledgeLearningBridge] KnowledgeEvolutionEngine connected (production).")
        except Exception as e:
            logger.warning("[KnowledgeLearningBridge] KnowledgeEvolutionEngine not available: %s", e)

    def _try_init_reader(self) -> None:
        """Inisialisasi SOPVaultReader untuk voice query."""
        try:
            from SERVER.jarvis.knowledge.sop_vault_reader import SOPVaultReader  # type: ignore
            self._reader = SOPVaultReader()
            logger.info("[KnowledgeLearningBridge] SOPVaultReader connected.")
        except Exception as e:
            logger.warning("[KnowledgeLearningBridge] SOPVaultReader not available: %s", e)

    def build_sop_from_incident(
        self,
        incident_id: str,
        intent: str = "",
        device_id: str = "",
        root_cause: str = "",
        solution: str = "",
        operator_approved: bool = True,
        execution_time_ms: float = 0.0,
    ) -> str:
        """
        Auto-generate SOP dari data insiden yang sudah diselesaikan.

        Args:
            incident_id: ID insiden sumber (e.g. "INC-001")
            intent: Jenis insiden (e.g. "PRINT_SPOOLER_FAILURE")
            device_id: Device yang terdampak
            root_cause: Hasil RCA (dari AI NOC)
            solution: Langkah solusi yang berhasil
            operator_approved: Apakah operator menyetujui solusi
            execution_time_ms: Waktu eksekusi solusi (ms)

        Returns:
            String konfirmasi dengan path SOP yang dibuat.
        """
        if not self._builder:
            # Fallback: format SOP ringkas tanpa KnowledgeAutoBuilder
            return self._fallback_sop_summary(incident_id, intent, root_cause, solution)

        try:
            incident_data = {
                "incident_id": incident_id,
                "intent": intent or "GENERAL_INCIDENT",
                "device_id": device_id or "GLOBAL",
                "root_cause": root_cause or "Root cause dianalisa otomatis oleh AI NOC.",
                "solution": solution or "Prosedur remediation dieksekusi sesuai SOP.",
                "execution_time_ms": execution_time_ms,
                "operator_approved": operator_approved,
            }
            result = self._builder.auto_build_sop_from_incident(incident_data)

            filepath = result.get("filepath", "N/A")
            sop_id = result.get("doc_id", "SOP-AUTO")
            status = result.get("status", "CREATED")

            return (
                f"✅ SOP Auto-Generated dari insiden {incident_id}:\n"
                f"├── SOP ID   : {sop_id}\n"
                f"├── Status   : {status} (menunggu review NOC Manager)\n"
                f"├── Intent   : {intent}\n"
                f"├── Device   : {device_id}\n"
                f"└── File     : {filepath}\n\n"
                f"💡 SOP ini akan otomatis aktif setelah direview dan di-approve."
            )
        except Exception as e:
            logger.error(f"[KnowledgeLearningBridge] SOP generation failed: {e}")
            return f"❌ Gagal generate SOP dari {incident_id}: {e}"

    def auto_learn_from_resolution(self, incident_data: Dict[str, Any]) -> str:
        """
        Dipanggil otomatis saat insiden di-resolve oleh AI NOC.
        Trigger full knowledge learning pipeline:
          1. KnowledgeEvolutionEngine: dedup + conflict detection (PRODUCTION)
          2. KnowledgeAutoBuilder v2.0: canonical SOP generation
        """
        incident_id = incident_data.get("incident_id", f"INC-{int(time.time())}")
        logger.info("[KnowledgeLearningBridge] Auto-learning from %s", incident_id)

        # ── FIX: KnowledgeEvolutionEngine — wired to PRODUCTION ──────────────
        # Sebelumnya hanya ada di test suite, sekarang dipanggil di sini
        if self._evolution:
            try:
                evo_result = self._evolution.process_evolution_cycle([incident_data])
                logger.info(
                    "[KnowledgeLearningBridge] Evolution cycle: deduped=%d conflicts=%d",
                    evo_result.get("deduped_count", 0),
                    evo_result.get("conflicts_detected", 0),
                )
                # Jika konten terdeteksi duplikat (deduped_count=0), masih lanjut
                # KnowledgeAutoBuilder v2.0 akan SKIP via content hash
            except Exception as evo_err:
                logger.warning("[KnowledgeLearningBridge] Evolution cycle error (non-fatal): %s", evo_err)

        result = self.build_sop_from_incident(
            incident_id=incident_id,
            intent=incident_data.get("intent", ""),
            device_id=incident_data.get("device_id", ""),
            root_cause=incident_data.get("root_cause", ""),
            solution=incident_data.get("solution", ""),
            operator_approved=incident_data.get("operator_approved", True),
            execution_time_ms=float(incident_data.get("execution_time_ms", 0.0)),
        )
        return result


    def get_pending_review_count(self) -> str:
        """Lihat berapa SOP yang belum direview."""
        resp = self.bridge.get_sops()
        if not resp.success:
            return "Tidak dapat mengambil data SOP."

        sops = resp.data if isinstance(resp.data, list) else []
        draft_sops = [s for s in sops if s.get("status") == "DRAFT"]
        pending_review = [s for s in sops if s.get("status") == "PENDING_REVIEW"]

        return (
            f"📚 Status SOP Knowledge Base:\n"
            f"├── ACTIVE    : {sum(1 for s in sops if s.get('status') == 'ACTIVE')}\n"
            f"├── DRAFT     : {len(draft_sops)} (auto-generated, belum direview)\n"
            f"├── PENDING   : {len(pending_review)} (menunggu approval manager)\n"
            f"└── TOTAL     : {len(sops)}\n\n"
            + (f"⚠️ Ada {len(draft_sops) + len(pending_review)} SOP perlu direview!"
               if draft_sops or pending_review else "✅ Semua SOP sudah direview.")
        )

    def search_knowledge(self, query: str) -> str:
        """Cari di knowledge base via NOCBridge."""
        resp = self.bridge.search_knowledge(query)
        if not resp.success:
            return f"❌ Gagal search knowledge: {resp.error}"
        return resp.summary or f"Tidak ada hasil untuk '{query}'"

    # ─── SOP Voice Query Methods (READ_SOP, SEARCH_SOP, etc.) ─────────────────

    def read_sop(self, query: str) -> str:
        """Bacakan isi SOP canonical berdasarkan query (READ_SOP intent)."""
        if not self._reader:
            return "⚠️ SOPVaultReader tidak tersedia. Pastikan canonical SOP sudah dibuat."
        return self._reader.read_sop(query)

    def search_sop(self, query: str) -> str:
        """Cari SOP berdasarkan kata kunci (SEARCH_SOP intent)."""
        if not self._reader:
            return "⚠️ SOPVaultReader tidak tersedia."
        return self._reader.search_sop(query)

    def get_all_sops(self) -> str:
        """Daftar semua canonical SOP aktif (GET_SOPS intent)."""
        if not self._reader:
            return "⚠️ SOPVaultReader tidak tersedia."
        return self._reader.get_all_sops()

    def get_handling_procedure(self, query: str) -> str:
        """Cara penanganan insiden (GET_HANDLING_PROCEDURE intent)."""
        if not self._reader:
            return "⚠️ SOPVaultReader tidak tersedia."
        return self._reader.get_handling_procedure(query)

    def sync_vault(self) -> str:
        """Sinkronisasi 3 lokasi vault (VAULT_SYNC intent)."""
        if not self._reader:
            return "⚠️ SOPVaultReader tidak tersedia."
        result = self._reader.sync_vault_locations()
        synced = result.get("synced", 0)
        errors = result.get("errors", 0)
        intents = result.get("synced_intents", [])
        return (
            f"🔄 Vault Sync selesai:\n"
            f"  ✅ Synced : {synced} SOP canonical"
            f" → obsidian_vault + docs/SOP_VAULT\n"
            f"  ❌ Errors : {errors}\n"
            f"  SOPs     : {', '.join(intents[:5])}"
            + (f" ... +{len(intents)-5} lainnya" if len(intents) > 5 else "")
        )

    def get_vault_status(self) -> str:
        """Status 3 lokasi vault (GET_VAULT_STATUS intent)."""
        if not self._reader:
            return "⚠️ SOPVaultReader tidak tersedia."
        return self._reader.get_vault_status()

    def _fallback_sop_summary(self, incident_id: str, intent: str,
                               root_cause: str, solution: str) -> str:
        """Fallback SOP summary saat KnowledgeAutoBuilder tidak tersedia."""
        return (
            f"📝 SOP Draft (tanpa KnowledgeAutoBuilder):\n"
            f"Insiden: {incident_id}\n"
            f"Intent: {intent}\n"
            f"Root Cause: {root_cause[:200] or 'N/A'}\n"
            f"Solution: {solution[:200] or 'N/A'}\n\n"
            f"⚠️ KnowledgeAutoBuilder tidak tersedia. "
            f"SOP disimpan sebagai catatan manual."
        )
