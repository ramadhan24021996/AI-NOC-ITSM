"""
SERVER.jarvis.planning.action_catalog_validator — JARVIS Action Catalog Validator
==================================================================================
P15 Implementation: Safety wrapper di atas PreApprovedActionCatalog.
Sebelum JARVIS mengeksekusi aksi REMEDIATE apapun, harus melewati validator ini.

Rules yang di-enforce:
  1. LLM/Operator TIDAK BISA eksekusi shell command mentah
  2. Semua aksi HARUS ada di catalog (ACT_RESTART_SPOOLER, ACT_FLUSH_DNS, dll.)
  3. Aksi di luar catalog → REJECTED, masuk HITL queue
  4. Aksi dengan risk HIGH/CRITICAL → ALWAYS HITL (meski ada di catalog)

Catalog diperluas dari PreApprovedActionCatalog yang ada di python_ai_core.
"""
import logging
import os
import sys
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("jarvis.planning.action_catalog_validator")

# ── Extended Action Catalog (JARVIS-layer) ─────────────────────────────────────
# Memperluas catalog dari PreApprovedActionCatalog di python_ai_core
JARVIS_EXTENDED_CATALOG: Dict[str, Dict[str, Any]] = {
    # === PRINT SERVICES ===
    "ACT_RESTART_SPOOLER": {
        "name": "Restart Windows Print Spooler",
        "category": "PRINT_SPOOLER",
        "risk_level": "LOW",
        "requires_hitl": False,
        "noc_keywords": ["restart spooler", "restart printer service"],
        "blast_radius_estimate": 1,
        "rollback": "net start spooler",
    },
    "ACT_CLEAR_PRINT_QUEUE": {
        "name": "Clear Print Queue",
        "category": "PRINT_SPOOLER",
        "risk_level": "LOW",
        "requires_hitl": False,
        "noc_keywords": ["clear print queue", "bersihkan antrian cetak", "kosongkan queue cetak"],
        "blast_radius_estimate": 1,
        "rollback": None,
    },
    "ACT_RUN_SANDBOX_TEST": {
        "name": "Execute Sandbox Remediation Test",
        "category": "SANDBOX_SIMULATION",
        "risk_level": "LOW",
        "requires_hitl": False,
        "noc_keywords": ["uji sandbox", "jalankan sandbox", "paksa pengujian", "uji di sandbox"],
        "blast_radius_estimate": 1,
        "rollback": None,
    },
    "ACT_RESET_PRINTER_DRIVER": {
        "name": "Auto-Reset Corrupted Printer Driver",
        "category": "PRINT_SPOOLER",
        "risk_level": "LOW",
        "requires_hitl": False,
        "noc_keywords": ["reset printer driver", "fix driver printer", "reset driver"],
        "blast_radius_estimate": 1,
        "rollback": None,
    },
    "ACT_RECOVER_POS_LOCK": {
        "name": "Recover POS Transaction Database Lock",
        "category": "POS_TERMINAL",
        "risk_level": "LOW",
        "requires_hitl": False,
        "noc_keywords": ["pos db lock", "unlock kasir", "fix pos database lock"],
        "blast_radius_estimate": 1,
        "rollback": None,
    },
    "ACT_VPN_RECONNECT": {
        "name": "Reconnect Site VPN Tunnel",
        "category": "NETWORK",
        "risk_level": "LOW",
        "requires_hitl": False,
        "noc_keywords": ["reconnect vpn", "reset vpn tunnel", "vpn reconnect"],
        "blast_radius_estimate": 5,
        "rollback": None,
    },
    # === NETWORK ===
    "ACT_FLUSH_DNS": {
        "name": "Flush Local DNS Resolver Cache",
        "category": "NETWORK",
        "risk_level": "LOW",
        "requires_hitl": False,
        "noc_keywords": ["flush dns", "bersihkan dns", "clear arp", "bersihkan arp"],
        "blast_radius_estimate": 1,
        "rollback": None,
    },
    "ACT_FAILOVER_ISP": {
        "name": "ISP Failover to Backup Link",
        "category": "NETWORK",
        "risk_level": "MEDIUM",
        "requires_hitl": True,
        "noc_keywords": ["failover", "pindah isp", "backup isp", "switch over"],
        "blast_radius_estimate": 50,
        "rollback": "Restore ke primary ISP",
    },
    "ACT_ENABLE_PORT": {
        "name": "Enable Network Port",
        "category": "NETWORK",
        "risk_level": "MEDIUM",
        "requires_hitl": False,
        "noc_keywords": ["aktifkan port", "enable port"],
        "blast_radius_estimate": 5,
        "rollback": "Disable port",
    },
    "ACT_DISABLE_PORT": {
        "name": "Disable Network Port",
        "category": "NETWORK",
        "risk_level": "MEDIUM",
        "requires_hitl": True,
        "noc_keywords": ["disable port", "shutdown interface", "nonaktifkan port"],
        "blast_radius_estimate": 10,
        "rollback": "Enable port",
    },
    # === DATABASE ===
    "ACT_DRAIN_REPLICA": {
        "name": "Graceful Read Replica Drain",
        "category": "DATABASE",
        "risk_level": "MEDIUM",
        "requires_hitl": True,
        "noc_keywords": ["drain replica", "kill query", "terminate backend"],
        "blast_radius_estimate": 20,
        "rollback": "Restore replica connections",
    },
    "ACT_RESTART_POSTGRESQL": {
        "name": "Restart PostgreSQL Service",
        "category": "DATABASE",
        "risk_level": "HIGH",
        "requires_hitl": True,
        "noc_keywords": ["restart postgresql", "restart database", "restart postgres", "restart db"],
        "blast_radius_estimate": 100,
        "rollback": "Start PostgreSQL service",
    },
    "ACT_RESTART_REDIS": {
        "name": "Restart Redis Cache Service",
        "category": "CACHE",
        "risk_level": "MEDIUM",
        "requires_hitl": True,
        "noc_keywords": ["restart redis", "flush redis", "clear cache redis"],
        "blast_radius_estimate": 30,
        "rollback": "Start Redis service",
    },
    # === SERVICES ===
    "ACT_RESTART_SERVICE": {
        "name": "Restart Application Service",
        "category": "SERVICE",
        "risk_level": "MEDIUM",
        "requires_hitl": False,
        "noc_keywords": ["restart service", "restart aplikasi"],
        "blast_radius_estimate": 5,
        "rollback": "Start service",
    },
    "ACT_RESTART_NATS": {
        "name": "Restart NATS Message Broker",
        "category": "MESSAGING",
        "risk_level": "HIGH",
        "requires_hitl": True,
        "noc_keywords": ["restart nats", "restart messaging"],
        "blast_radius_estimate": 200,
        "rollback": "Start NATS service",
    },
    # === SERVER OPERATIONS ===
    "ACT_REBOOT_SERVER": {
        "name": "Reboot Server",
        "category": "SERVER",
        "risk_level": "HIGH",
        "requires_hitl": True,
        "noc_keywords": ["reboot server", "restart server", "reboot"],
        "blast_radius_estimate": 50,
        "rollback": None,  # Tidak bisa di-rollback
    },
    "ACT_ROLLBACK_CONFIG": {
        "name": "Rollback Configuration to Previous Version",
        "category": "CONFIG",
        "risk_level": "MEDIUM",
        "requires_hitl": True,
        "noc_keywords": ["rollback", "kembalikan konfigurasi", "revert config"],
        "blast_radius_estimate": 10,
        "rollback": "Apply current config",
    },
    # === OTA & UPDATES ===
    "ACT_TRIGGER_OTA": {
        "name": "Trigger OTA Agent Update",
        "category": "FLEET",
        "risk_level": "MEDIUM",
        "requires_hitl": False,
        "noc_keywords": ["trigger ota", "update agent", "update firmware"],
        "blast_radius_estimate": 1,
        "rollback": "Rollback agent version",
    },
    # === CONTAINER ===
    "ACT_SCALE_POD": {
        "name": "Scale Out Microservice Pod Replicas",
        "category": "CONTAINER",
        "risk_level": "LOW",
        "requires_hitl": False,
        "noc_keywords": ["scale pod", "scale container", "kubectl scale"],
        "blast_radius_estimate": 0,
        "rollback": "Scale back to original",
    },
    # === SOP EXECUTION ===
    "ACT_EXECUTE_SOP": {
        "name": "Execute Standard Operating Procedure",
        "category": "SOP",
        "risk_level": "VARIES",  # Ditentukan per SOP
        "requires_hitl": False,
        "noc_keywords": ["execute sop", "jalankan sop", "eksekusi sop", "terapkan sop"],
        "blast_radius_estimate": 5,
        "rollback": "Revert SOP changes",
    },
    # === ADDITIONAL ACTIONS FROM CATALOG ===
    "ACT_RESTART_PRINTER_SERVICE": {
        "name": "Restart Printer Service",
        "category": "PRINT_SPOOLER",
        "risk_level": "LOW",
        "requires_hitl": False,
        "noc_keywords": ["restart printer", "restart printer service", "printer service"],
        "blast_radius_estimate": 1,
        "rollback": None,
    },
    "ACT_RESTART_NETWORK_SERVICE": {
        "name": "Restart Network Service",
        "category": "NETWORK",
        "risk_level": "MEDIUM",
        "requires_hitl": True,
        "noc_keywords": ["restart jaringan", "restart network"],
        "blast_radius_estimate": 10,
        "rollback": None,
    },
    "ACT_CLEAR_CACHE": {
        "name": "Clear Cache",
        "category": "SYSTEM",
        "risk_level": "LOW",
        "requires_hitl": False,
        "noc_keywords": ["bersihkan cache", "clear cache"],
        "blast_radius_estimate": 1,
        "rollback": None,
    },
    "ACT_CLEAR_QUEUE": {
        "name": "Clear Queue",
        "category": "SYSTEM",
        "risk_level": "LOW",
        "requires_hitl": False,
        "noc_keywords": ["clear queue", "kosongkan antrian"],
        "blast_radius_estimate": 1,
        "rollback": None,
    },
    "ACT_TRIGGER_N8N_WORKFLOW": {
        "name": "Trigger n8n Workflow",
        "category": "AUTOMATION",
        "risk_level": "LOW",
        "requires_hitl": False,
        "noc_keywords": ["trigger workflow", "jalankan workflow"],
        "blast_radius_estimate": 1,
        "rollback": None,
    },
    "ACT_N8N_PUBLISH_POSTMORTEM": {
        "name": "Publish Postmortem to n8n",
        "category": "AUTOMATION",
        "risk_level": "LOW",
        "requires_hitl": False,
        "noc_keywords": ["publish postmortem", "kirim postmortem"],
        "blast_radius_estimate": 1,
        "rollback": None,
    },
    "ACT_N8N_VAULT_SYNC": {
        "name": "Sync Vault via n8n",
        "category": "AUTOMATION",
        "risk_level": "LOW",
        "requires_hitl": False,
        "noc_keywords": ["sync vault", "sinkronisasi vault"],
        "blast_radius_estimate": 1,
        "rollback": None,
    },
    "ACT_REGISTER_DEVICE": {
        "name": "Register New Device",
        "category": "FLEET",
        "risk_level": "LOW",
        "requires_hitl": False,
        "noc_keywords": ["tambah device", "daftarkan device"],
        "blast_radius_estimate": 1,
        "rollback": None,
    },
    "ACT_DELETE_DEVICE": {
        "name": "Delete Device",
        "category": "FLEET",
        "risk_level": "MEDIUM",
        "requires_hitl": True,
        "noc_keywords": ["hapus device", "delete device"],
        "blast_radius_estimate": 1,
        "rollback": None,
    },
    "ACT_IMPORT_KNOWLEDGE": {
        "name": "Import Knowledge Base",
        "category": "KNOWLEDGE",
        "risk_level": "LOW",
        "requires_hitl": False,
        "noc_keywords": ["import knowledge", "masukkan pengetahuan"],
        "blast_radius_estimate": 1,
        "rollback": None,
    },
    "ACT_CREATE_SOP": {
        "name": "Create SOP",
        "category": "SOP",
        "risk_level": "LOW",
        "requires_hitl": False,
        "noc_keywords": ["buat prosedur", "buat sop"],
        "blast_radius_estimate": 1,
        "rollback": None,
    },
    "ACT_DELETE_SOP": {
        "name": "Delete SOP",
        "category": "SOP",
        "risk_level": "MEDIUM",
        "requires_hitl": True,
        "noc_keywords": ["hapus sop", "hapus prosedur"],
        "blast_radius_estimate": 1,
        "rollback": None,
    },
    "ACT_CREATE_RBAC_USER": {
        "name": "Create RBAC User",
        "category": "SECURITY",
        "risk_level": "MEDIUM",
        "requires_hitl": True,
        "noc_keywords": ["tambah user", "buat user"],
        "blast_radius_estimate": 1,
        "rollback": None,
    },
    "ACT_DELETE_RBAC_USER": {
        "name": "Delete RBAC User",
        "category": "SECURITY",
        "risk_level": "MEDIUM",
        "requires_hitl": True,
        "noc_keywords": ["hapus user", "delete user"],
        "blast_radius_estimate": 1,
        "rollback": None,
    },
    "ACT_UPDATE_RBAC_ROLE": {
        "name": "Update RBAC Role",
        "category": "SECURITY",
        "risk_level": "MEDIUM",
        "requires_hitl": True,
        "noc_keywords": ["update role", "ubah role"],
        "blast_radius_estimate": 1,
        "rollback": None,
    },
    "ACT_REANALYZE_RCA": {
        "name": "Reanalyze Root Cause",
        "category": "RCA",
        "risk_level": "LOW",
        "requires_hitl": False,
        "noc_keywords": ["reanalisa", "reanalisis"],
        "blast_radius_estimate": 1,
        "rollback": None,
    },
}

# ── Risk Level Ordering ───────────────────────────────────────────────────────
_RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3, "VARIES": 1}


class JarvisActionCatalogValidator:
    """
    P15 — JARVIS Action Catalog Validator.
    Safety gate layer yang memvalidasi semua aksi REMEDIATE sebelum eksekusi.

    Alur:
      REMEDIATE command
        → validate(action_name)
        → APPROVED: eksekusi langsung (LOW/MEDIUM no-hitl)
        → HITL_REQUIRED: masuk HITL queue
        → REJECTED: aksi tidak dikenal, BLOCKED

    Contoh:
        validator = JarvisActionCatalogValidator()
        result = validator.validate("restart spooler")
        if result["verdict"] == "APPROVED":
            execute(result["action_id"])
        elif result["verdict"] == "HITL_REQUIRED":
            hitl.enqueue(...)
        else:
            print(result["reason"])
    """

    def __init__(self):
        self._catalog = JARVIS_EXTENDED_CATALOG.copy()
        self._extended_with_core_catalog()
        logger.info(
            f"[ActionCatalogValidator] Initialized with {len(self._catalog)} actions."
        )

    def _extended_with_core_catalog(self) -> None:
        """Extend dengan PreApprovedActionCatalog dari python_ai_core jika tersedia."""
        try:
            from SERVER.python_ai_core.planning.preapproved_action_catalog import PreApprovedActionCatalog  # type: ignore
            for action_id, action_data in PreApprovedActionCatalog.CATALOG.items():
                if action_id not in self._catalog:
                    # Wrap existing catalog entry
                    self._catalog[action_id] = {
                        "name": action_data.get("name", action_id),
                        "category": action_data.get("category", "GENERAL"),
                        "risk_level": "LOW",
                        "requires_hitl": not action_data.get("is_preapproved", False),
                        "noc_keywords": [],
                        "blast_radius_estimate": 1,
                        "rollback": None,
                    }
            logger.info(
                f"[ActionCatalogValidator] Extended with core catalog: "
                f"{len(self._catalog)} total actions."
            )
        except Exception:
            pass  # Graceful — JARVIS catalog saja sudah cukup

    def validate(self, action_text: str) -> Dict[str, Any]:
        """
        Validasi apakah aksi diizinkan dan tentukan approval requirement.

        Args:
            action_text: Teks aksi dalam Bahasa Indonesia atau English,
                         atau ACT_ID langsung.

        Returns:
            Dict berisi:
              - verdict: APPROVED | HITL_REQUIRED | REJECTED
              - action_id: ID catalog jika ditemukan
              - action_name: Nama aksi
              - risk_level: LOW | MEDIUM | HIGH | CRITICAL
              - blast_radius_estimate: int
              - reason: Penjelasan keputusan
              - rollback: Rollback procedure
        """
        # Try direct ACT_ID match
        action_id, action_data = self._find_by_id(action_text)

        # Try keyword match jika tidak match langsung
        if not action_data:
            action_id, action_data = self._find_by_keyword(action_text)

        # REJECTED: tidak ada di catalog
        if not action_data:
            return {
                "verdict": "REJECTED",
                "action_id": None,
                "action_name": action_text,
                "risk_level": "UNKNOWN",
                "blast_radius_estimate": -1,
                "reason": (
                    f"🚫 Aksi '{action_text}' TIDAK DIKENAL dalam Pre-Approved Catalog.\n"
                    f"Jarvis tidak mengeksekusi aksi di luar catalog. "
                    f"Gunakan aksi yang sudah tersedia:\n"
                    + "\n".join(f"  • {a['name']}" for a in list(self._catalog.values())[:5])
                    + f"\n  ... dan {max(0, len(self._catalog)-5)} lainnya."
                ),
                "rollback": None,
            }

        risk_level = action_data.get("risk_level", "LOW")
        requires_hitl = action_data.get("requires_hitl", False)
        blast_radius = action_data.get("blast_radius_estimate", 0)

        # HITL jika risk HIGH/CRITICAL atau action memang requires_hitl
        if requires_hitl or _RISK_ORDER.get(risk_level, 0) >= 2:
            return {
                "verdict": "HITL_REQUIRED",
                "action_id": action_id,
                "action_name": action_data["name"],
                "risk_level": risk_level,
                "blast_radius_estimate": blast_radius,
                "reason": (
                    f"⚠️ Aksi '{action_data['name']}' memerlukan HITL approval.\n"
                    f"Risk Level: {risk_level} | Blast Radius: ~{blast_radius} node."
                ),
                "rollback": action_data.get("rollback"),
            }

        return {
            "verdict": "APPROVED",
            "action_id": action_id,
            "action_name": action_data["name"],
            "risk_level": risk_level,
            "blast_radius_estimate": blast_radius,
            "reason": f"✅ Aksi '{action_data['name']}' diizinkan. Risk: {risk_level}.",
            "rollback": action_data.get("rollback"),
        }

    def _find_by_id(self, action_id: str) -> Tuple[str, Optional[Dict]]:
        """Find action by exact ACT_ID."""
        action_id_upper = action_id.upper().replace(" ", "_")
        if action_id_upper in self._catalog:
            return action_id_upper, self._catalog[action_id_upper]
        return "", None

    def _find_by_keyword(self, text: str) -> Tuple[str, Optional[Dict]]:
        """Find action by keyword match (longest match first)."""
        text_lower = text.lower()
        best_match: Optional[str] = None
        best_len = 0
        for action_id, data in self._catalog.items():
            for kw in data.get("noc_keywords", []):
                if kw in text_lower and len(kw) > best_len:
                    best_match = action_id
                    best_len = len(kw)
        if best_match:
            return best_match, self._catalog[best_match]
        return "", None

    def list_catalog(self, category: str = "", risk_filter: str = "") -> str:
        """Format daftar catalog untuk ditampilkan oleh JARVIS."""
        filtered = {
            aid: data for aid, data in self._catalog.items()
            if (not category or data.get("category") == category.upper())
            and (not risk_filter or data.get("risk_level") == risk_filter.upper())
        }

        lines = [
            f"📋 Pre-Approved Action Catalog "
            f"({'semua' if not category else category} | "
            f"{len(filtered)} aksi):\n"
        ]
        for aid, data in sorted(filtered.items()):
            hitl = "🔒 HITL" if data.get("requires_hitl") else "✅ AUTO"
            risk = data.get("risk_level", "?")
            lines.append(f"  [{hitl}] {data['name']} ({risk})")
        return "\n".join(lines)

    def catalog_size(self) -> int:
        return len(self._catalog)

    def get_categories(self) -> List[str]:
        return sorted(set(d.get("category", "?") for d in self._catalog.values()))
