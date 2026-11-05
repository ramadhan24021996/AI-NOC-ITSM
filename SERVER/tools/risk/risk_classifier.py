"""
SERVER.tools.risk — Risk Classifier
====================================
Tahap 2.4 — Tool Execution Layer (Lapisan Keamanan 1/4)

Posisi dalam alur keamanan:
  ToolDispatcher → ApprovalManager → PolicyEngine → [RiskClassifier] → Driver

RiskClassifier menilai setiap ToolRequest berdasarkan:
  1. Action keywords dalam params (delete, format, kill, stop, reboot, ...)
  2. Blast radius (target: single host vs fleet vs datacenter)
  3. Reversibility (apakah aksi dapat di-rollback)
  4. Driver type risk baseline (SSH > REST > Docker > Sandbox)
  5. Confidence score dari LLM (confidence rendah = risk lebih tinggi)
  6. Severity incident (HIGH/CRITICAL meningkatkan risk)
"""
import logging
from typing import List
from SERVER.tools.interfaces import RiskAssessment, RiskLevel, ToolRequest

logger = logging.getLogger("tools.risk.classifier")


# ── Risk Baseline Per Driver Type ─────────────────────────────────────────────
DRIVER_RISK_BASELINE = {
    "ssh":      50,  # Shell commands — direct OS impact
    "docker":   40,  # Container ops — service-level impact
    "mikrotik": 60,  # Network changes — can isolate entire site
    "rest":     25,  # API calls — usually reversible
    "sandbox":  5,   # Dry-run simulation — no real effect
}

# ── Destructive Action Keywords ────────────────────────────────────────────────
DESTRUCTIVE_KEYWORDS = {
    "critical": ["rm -rf", "format", "mkfs", "drop database", "truncate table",
                 "delete all", "wipe", "dd if=/dev/zero", ":(){ :|:"],
    "high":     ["delete", "remove", "purge", "reboot", "shutdown", "kill",
                 "disable interface", "ip route del", "iptables -F", "ufw disable"],
    "medium":   ["stop", "restart", "reload", "flush", "reset", "clear cache",
                 "rollback", "deprovision"],
    "low":      ["start", "enable", "check", "ping", "get", "list", "show",
                 "status", "inspect", "describe"],
}

# ── Blast Radius Mapping ───────────────────────────────────────────────────────
def _classify_blast_radius(params: dict) -> str:
    targets = str(params.get("target", "") or params.get("host", "") or "").lower()
    if any(kw in targets for kw in ["all", "fleet", "broadcast", "*", "0.0.0.0"]):
        return "FLEET"
    if any(kw in targets for kw in ["gateway", "router", "switch", "firewall", "core"]):
        return "DATACENTER"
    if any(kw in targets for kw in ["service", "cluster", "group"]):
        return "SERVICE"
    if targets:
        return "LOCAL"
    return "NONE"


class RiskClassifier:
    """
    Menilai risiko setiap ToolRequest sebelum eksekusi driver.
    Menghasilkan RiskAssessment yang digunakan ToolDispatcher dan ApprovalManager.
    """

    def classify(self, request: ToolRequest, driver_type: str) -> RiskAssessment:
        """
        Menghitung risk score (0–100) dan risk level berdasarkan
        kombinasi action keyword, blast radius, reversibility, dan confidence.

        Returns:
            RiskAssessment dengan risk_level, risk_score, risk_reasons, dan
            requires_hitl yang diderivasi dari semua faktor.
        """
        score = DRIVER_RISK_BASELINE.get(driver_type, 30)
        reasons: List[str] = []
        is_reversible = True

        # 1. Action Keyword Scoring
        action_text = " ".join(str(v) for v in request.params.values()).lower()
        action_text += f" {request.context.get('action', '')}".lower()

        for keyword in DESTRUCTIVE_KEYWORDS["critical"]:
            if keyword in action_text:
                score = max(score, 90)
                is_reversible = False
                reasons.append(f"Destructive critical pattern detected: '{keyword}'")

        for keyword in DESTRUCTIVE_KEYWORDS["high"]:
            if keyword in action_text:
                score = max(score, 70)
                is_reversible = False
                reasons.append(f"High-risk action keyword: '{keyword}'")

        for keyword in DESTRUCTIVE_KEYWORDS["medium"]:
            if keyword in action_text:
                score = max(score, max(score, score + 15))
                reasons.append(f"Medium-risk action: '{keyword}'")

        # 2. Blast Radius Adjustment
        blast = _classify_blast_radius(request.params)
        blast_bonus = {"NONE": 0, "LOCAL": 5, "SERVICE": 15, "FLEET": 30, "DATACENTER": 40}
        score = min(100, score + blast_bonus.get(blast, 0))
        if blast in ("FLEET", "DATACENTER"):
            reasons.append(f"Blast radius: {blast} — affects multiple nodes")

        # 3. Confidence Penalty (rendah = tidak yakin = risiko lebih besar)
        confidence = float(request.confidence or 0.0)
        if confidence > 1.0:
            confidence /= 100.0
        if confidence < 0.70:
            score = min(100, score + 20)
            reasons.append(f"Low AI confidence: {confidence * 100:.0f}% (<70%)")
        elif confidence < 0.85:
            score = min(100, score + 10)
            reasons.append(f"Moderate AI confidence: {confidence * 100:.0f}%")

        # 4. Severity Amplification
        severity = request.severity.upper()
        if severity in ("HIGH", "CRITICAL"):
            score = min(100, score + 10)
            reasons.append(f"Incident severity amplification: {severity}")

        # 5. Derive Risk Level
        if score >= 80:
            risk_level = RiskLevel.CRITICAL
        elif score >= 60:
            risk_level = RiskLevel.HIGH
        elif score >= 35:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        requires_hitl = risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

        if not reasons:
            reasons.append(f"Standard {driver_type} operation — baseline risk assessment")

        logger.info(
            f"[RiskClassifier] tool={request.tool_id} | driver={driver_type} | "
            f"score={score} | level={risk_level.value} | hitl={requires_hitl} | "
            f"blast={blast}"
        )

        return RiskAssessment(
            risk_level=risk_level,
            risk_score=score,
            risk_reasons=reasons,
            requires_hitl=requires_hitl,
            is_reversible=is_reversible,
            blast_radius=blast,
        )
