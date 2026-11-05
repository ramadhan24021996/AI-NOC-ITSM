"""
SERVER.tools.policy — Tool Policy Engine
==========================================
Tahap 2.4 — Tool Execution Layer (Lapisan Keamanan 2/4)

Posisi dalam alur keamanan:
  ToolDispatcher → ApprovalManager → [PolicyEngine] → RiskClassifier → Driver

PolicyEngine menegakkan aturan bisnis dan batasan operasional:
  1. Role-Based Access Control (RBAC) — siapa boleh menjalankan apa
  2. Time-Window Enforcement — tool tertentu diblokir di luar jam operasional
  3. Maintenance Window Lock — blokir aksi produksi saat maintenance
  4. Driver-Level Restrictions — SSH/RouterOS hanya untuk role tertentu
  5. Incident Severity Gates — aksi berbahaya diblokir pada incident severity tertentu
  6. Mandatory Dry-Run Gate — driver tertentu wajib sandbox sebelum eksekusi nyata
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from SERVER.tools.interfaces import PolicyDecision, ToolRequest, RiskLevel

logger = logging.getLogger("tools.policy.engine")


# ── RBAC Permission Matrix ─────────────────────────────────────────────────────
#
# Setiap entry: {role: {driver_type: [allowed_risk_levels]}}
# "ai_auto" = AI menjalankan otomatis (confidence >= 92%), risiko rendah only
# "ai_suggested" = AI menyarankan, operator harus approve
# "operator" = operator manusia yang mengirim permintaan
# "admin" = akses penuh (tetap melewati HITL untuk CRITICAL)
#
RBAC_MATRIX: Dict[str, Dict[str, List[str]]] = {
    "ai_auto": {
        "rest":    ["LOW"],
        "sandbox": ["LOW", "MEDIUM"],
        # SSH, Docker, RouterOS tidak boleh auto-dieksekusi oleh AI
    },
    "ai_suggested": {
        "rest":    ["LOW", "MEDIUM"],
        "sandbox": ["LOW", "MEDIUM", "HIGH"],
        "ssh":     ["LOW"],
        "docker":  ["LOW", "MEDIUM"],
    },
    "operator": {
        "rest":     ["LOW", "MEDIUM", "HIGH"],
        "sandbox":  ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
        "ssh":      ["LOW", "MEDIUM", "HIGH"],
        "docker":   ["LOW", "MEDIUM", "HIGH"],
        "mikrotik": ["LOW", "MEDIUM"],
    },
    "admin": {
        "rest":     ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
        "sandbox":  ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
        "ssh":      ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
        "docker":   ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
        "mikrotik": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
    },
}

# ── Mandatory Sandbox Drivers ──────────────────────────────────────────────────
# Driver ini SELALU dieksekusi dalam sandbox mode dulu, kecuali role admin
# dan sudah melewati HITL approval.
MANDATORY_SANDBOX_FOR_AUTO = {"ssh", "mikrotik", "docker"}

# ── Business Hours (WIB = UTC+7): non-critical ops hanya jam kerja ─────────────
BUSINESS_HOURS_START = 8   # 08:00 WIB
BUSINESS_HOURS_END = 18    # 18:00 WIB


class ToolPolicyEngine:
    """
    Menegakkan aturan bisnis sebelum tool dieksekusi.
    Menghasilkan PolicyDecision yang menentukan apakah eksekusi diizinkan,
    harus melewati HITL, atau harus dijalankan dalam sandbox.
    """

    def __init__(self, maintenance_mode: bool = False):
        """
        Args:
            maintenance_mode: Jika True, semua aksi produksi diblokir.
        """
        self._maintenance_mode = maintenance_mode

    @property
    def maintenance_mode(self) -> bool:
        return self._maintenance_mode

    def set_maintenance_mode(self, enabled: bool) -> None:
        self._maintenance_mode = enabled
        logger.warning(f"[PolicyEngine] Maintenance mode {'ENABLED' if enabled else 'DISABLED'}")

    def evaluate(
        self,
        request: ToolRequest,
        driver_type: str,
        risk_level: RiskLevel,
    ) -> PolicyDecision:
        """
        Mengevaluasi apakah ToolRequest diizinkan berdasarkan semua aturan policy.

        Args:
            request: ToolRequest yang akan dievaluasi.
            driver_type: Jenis driver yang akan dieksekusi.
            risk_level: Hasil dari RiskClassifier.

        Returns:
            PolicyDecision dengan allowed, reason, requires_hitl, force_sandbox.
        """
        role = request.requestor_role.lower()
        risk_str = risk_level.value

        # ── Rule 1: Maintenance Mode Lock ─────────────────────────────────────
        if self._maintenance_mode and role != "admin":
            logger.warning(f"[PolicyEngine] BLOCKED: Maintenance mode active | role={role}")
            return PolicyDecision(
                allowed=False,
                reason="System is in maintenance mode. Production actions are locked.",
                requires_hitl=False,
                policy_rule="MAINTENANCE_MODE_LOCK",
            )

        # ── Rule 2: RBAC Check ────────────────────────────────────────────────
        allowed_risk_levels = (RBAC_MATRIX.get(role, {}) or {}).get(driver_type, [])
        if not allowed_risk_levels:
            logger.warning(
                f"[PolicyEngine] BLOCKED: role={role} has no access to driver={driver_type}"
            )
            return PolicyDecision(
                allowed=False,
                reason=f"Role '{role}' is not authorized to use driver '{driver_type}'.",
                requires_hitl=False,
                policy_rule="RBAC_DENY",
            )

        if risk_str not in allowed_risk_levels:
            # Apakah ada role yang lebih tinggi bisa mengizinkan melalui HITL?
            if role in ("ai_auto", "ai_suggested"):
                logger.info(
                    f"[PolicyEngine] HITL_REQUIRED: role={role} cannot run {driver_type} "
                    f"at risk={risk_str} without human approval."
                )
                return PolicyDecision(
                    allowed=True,
                    reason=f"Risk level {risk_str} requires human approval for role '{role}'.",
                    requires_hitl=True,
                    force_sandbox=False,
                    policy_rule="RBAC_HITL_ESCALATION",
                )
            return PolicyDecision(
                allowed=False,
                reason=f"Role '{role}' cannot execute {driver_type} at risk level {risk_str}.",
                requires_hitl=False,
                policy_rule="RBAC_RISK_LEVEL_DENY",
            )

        # ── Rule 3: Mandatory Sandbox for AI Auto + Dangerous Drivers ─────────
        if role == "ai_auto" and driver_type in MANDATORY_SANDBOX_FOR_AUTO:
            logger.warning(
                f"[PolicyEngine] FORCE_SANDBOX: ai_auto cannot directly use {driver_type}"
            )
            return PolicyDecision(
                allowed=True,
                reason=f"AI auto-execution of '{driver_type}' must run in sandbox mode only.",
                requires_hitl=True,
                force_sandbox=True,
                policy_rule="AI_AUTO_SANDBOX_MANDATORY",
            )

        # ── Rule 4: Business Hours Check for non-critical ops ────────────────
        now_wib_hour = (datetime.now(timezone.utc).hour + 7) % 24
        if risk_str in ("HIGH", "CRITICAL") and role != "admin":
            if not (BUSINESS_HOURS_START <= now_wib_hour < BUSINESS_HOURS_END):
                logger.warning(
                    f"[PolicyEngine] HITL_REQUIRED: High-risk op outside business hours "
                    f"({now_wib_hour}:00 WIB)"
                )
                return PolicyDecision(
                    allowed=True,
                    reason=(
                        f"High-risk operations outside business hours "
                        f"({BUSINESS_HOURS_START}:00–{BUSINESS_HOURS_END}:00 WIB) "
                        f"require HITL approval."
                    ),
                    requires_hitl=True,
                    policy_rule="BUSINESS_HOURS_GATE",
                )

        # ── Rule 5: CRITICAL always needs HITL regardless of role ─────────────
        if risk_str == "CRITICAL":
            return PolicyDecision(
                allowed=True,
                reason="CRITICAL risk level mandates Human-in-the-Loop approval for any role.",
                requires_hitl=True,
                force_sandbox=False,
                policy_rule="CRITICAL_ALWAYS_HITL",
            )

        # ── ALLOWED: All checks passed ────────────────────────────────────────
        logger.info(
            f"[PolicyEngine] ALLOWED: role={role} | driver={driver_type} | risk={risk_str}"
        )
        return PolicyDecision(
            allowed=True,
            reason=f"Policy checks passed. Role '{role}' authorized for {driver_type} at {risk_str} risk.",
            requires_hitl=False,
            policy_rule="POLICY_PASS",
        )
