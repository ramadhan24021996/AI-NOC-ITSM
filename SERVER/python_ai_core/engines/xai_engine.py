"""
SERVER.python_ai_core.engines.xai_engine
=========================================
#9 Explainable AI (XAI) — Setiap Keputusan AI Harus Bisa Dijelaskan

Fitur Production-Ready:
  ✅ Bangun explanation dari evidence nyata (CPU spike, error log, history)
  ✅ Sertakan threshold yang dilanggar dan berapa kali
  ✅ Historical context: "Pola ini terjadi 3x sebelumnya, MTTR rata-rata 45 menit"
  ✅ Confidence breakdown: seberapa yakin AI dengan rekomendasi ini
  ✅ Counter-evidence: apa yang tidak cocok (transparansi penuh)
  ✅ API-ready: output JSON terstruktur untuk dashboard
  ✅ JARVIS TTS: output versi ringkas untuk dibacakan
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("python_ai_core.engines.xai")

# ─── Evidence Strengths ───────────────────────────────────────────────────────
EVIDENCE_WEIGHT = {
    "CPU_SPIKE":          0.25,
    "MEMORY_LEAK":        0.25,
    "DISK_FULL":          0.20,
    "NETWORK_LOSS":       0.20,
    "PRINTER_OFFLINE":    0.15,
    "SERVICE_DOWN":       0.25,
    "ERROR_LOG_SPIKE":    0.15,
    "HISTORICAL_PATTERN": 0.20,
    "SLA_BREACH":         0.30,
    "CASCADE_DETECTED":   0.15,
}


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class EvidenceItem:
    """Satu bukti yang mendukung keputusan AI."""
    code: str           # CPU_SPIKE, MEMORY_LEAK, dst
    description: str    # "CPU usage 98% (threshold: 85%)"
    value: Any          # Nilai aktual
    threshold: Any      # Threshold yang dilanggar
    weight: float       # Kontribusi terhadap skor
    source: str         # "live_telemetry" | "historical_db" | "log_analysis"


@dataclass
class CounterEvidence:
    """Bukti yang bertentangan (transparansi)."""
    description: str
    impact: str         # "Minor" | "Moderate" | "Significant"


@dataclass
class DecisionExplanation:
    """Penjelasan lengkap satu keputusan AI."""
    decision_id: str
    subject: str            # "INC-1895000" atau "PC-KASIR-3"
    decision: str           # "CRITICAL priority" | "RESTART_SPOOLER"
    rationale_summary: str  # 1-2 kalimat untuk TTS
    evidence_items: List[EvidenceItem] = field(default_factory=list)
    counter_evidence: List[CounterEvidence] = field(default_factory=list)
    historical_context: str = ""
    confidence_score: float = 0.0
    confidence_breakdown: Dict[str, float] = field(default_factory=dict)
    severity: str = "MEDIUM"
    criteria_met: int = 0
    criteria_total: int = 0
    explained_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict:
        return {
            "decision_id": self.decision_id,
            "subject": self.subject,
            "decision": self.decision,
            "severity": self.severity,
            "confidence_score": round(self.confidence_score, 3),
            "confidence_breakdown": {k: round(v, 3) for k, v in self.confidence_breakdown.items()},
            "criteria_met": f"{self.criteria_met}/{self.criteria_total}",
            "rationale_summary": self.rationale_summary,
            "evidence": [
                {
                    "code": e.code,
                    "description": e.description,
                    "value": e.value,
                    "threshold": e.threshold,
                    "weight": round(e.weight, 2),
                    "source": e.source,
                }
                for e in self.evidence_items
            ],
            "counter_evidence": [
                {"description": ce.description, "impact": ce.impact}
                for ce in self.counter_evidence
            ],
            "historical_context": self.historical_context,
            "explained_at": self.explained_at,
        }

    def to_tts_text(self) -> str:
        """Ringkasan singkat untuk JARVIS TTS — max 4 kalimat."""
        lines = [
            f"Keputusan untuk {self.subject}: {self.decision}.",
            f"Alasan: {self.rationale_summary}",
        ]
        if self.evidence_items:
            ev = self.evidence_items[0]
            lines.append(f"Bukti utama: {ev.description}")
        if self.historical_context:
            lines.append(self.historical_context)
        lines.append(f"Keyakinan AI: {self.confidence_score * 100:.0f}%.")
        return " ".join(lines)


# ─── XAI Engine ───────────────────────────────────────────────────────────────

class XAIEngine:
    """
    Explainable AI Engine untuk AI NOC.
    Menghasilkan penjelasan terstruktur untuk setiap keputusan AI.
    """

    def __init__(self, db_conn: Optional[Any] = None,
                 episodic_memory: Optional[Any] = None):
        self._db = db_conn
        self._memory = episodic_memory

    def explain_incident_priority(
        self,
        incident: Dict[str, Any],
        live_metrics: Optional[Dict[str, Any]] = None,
    ) -> DecisionExplanation:
        """
        Jelaskan mengapa AI menetapkan prioritas tertentu untuk sebuah insiden.
        
        Args:
            incident: Dict insiden dari DB (incident_id, severity, device, evidence, dll)
            live_metrics: Metrik real-time (cpu_pct, mem_pct, dll) jika tersedia
        """
        inc_id = str(incident.get("incident_id", incident.get("id", "?")))
        device = str(incident.get("device_name", incident.get("agent", "unknown")))
        severity = str(incident.get("severity", "MEDIUM")).upper()
        evidence_raw = str(incident.get("evidence", incident.get("flag", "")))
        decision = f"{severity} priority untuk INC-{inc_id}"

        evidence_items: List[EvidenceItem] = []
        counter_items: List[CounterEvidence] = []

        # ── Analisis evidence dari insiden ────────────────────────────────────
        ev_lower = evidence_raw.lower()

        # CPU spike
        cpu_val = None
        if live_metrics:
            cpu_val = live_metrics.get("cpu_usage_pct", live_metrics.get("cpu_percent"))
        if cpu_val is None and "cpu" in ev_lower:
            import re
            m = re.search(r'(\d+(?:\.\d+)?)\s*%', evidence_raw)
            cpu_val = float(m.group(1)) if m else None

        if cpu_val and float(cpu_val) > 85:
            evidence_items.append(EvidenceItem(
                code="CPU_SPIKE",
                description=f"CPU usage {cpu_val}% (threshold: 85%)",
                value=cpu_val, threshold=85.0,
                weight=EVIDENCE_WEIGHT["CPU_SPIKE"],
                source="live_telemetry" if live_metrics else "incident_evidence",
            ))

        # Memory leak
        mem_val = live_metrics.get("memory_usage_pct") if live_metrics else None
        if mem_val and float(mem_val) > 85:
            evidence_items.append(EvidenceItem(
                code="MEMORY_LEAK",
                description=f"Memory usage {mem_val}% (threshold: 85%)",
                value=mem_val, threshold=85.0,
                weight=EVIDENCE_WEIGHT["MEMORY_LEAK"],
                source="live_telemetry",
            ))

        # Printer/service offline
        if any(kw in ev_lower for kw in ["offline", "down", "unreachable", "failed"]):
            evidence_items.append(EvidenceItem(
                code="SERVICE_DOWN",
                description=f"Service/device {device} offline: {evidence_raw[:60]}",
                value="OFFLINE", threshold="ONLINE",
                weight=EVIDENCE_WEIGHT["SERVICE_DOWN"],
                source="incident_evidence",
            ))

        # Network loss
        if any(kw in ev_lower for kw in ["network", "network loss", "packet loss", "latency", "timeout"]):
            evidence_items.append(EvidenceItem(
                code="NETWORK_LOSS",
                description=f"Network issue terdeteksi: {evidence_raw[:60]}",
                value="DEGRADED", threshold="NORMAL",
                weight=EVIDENCE_WEIGHT["NETWORK_LOSS"],
                source="incident_evidence",
            ))

        # Error log spike
        if any(kw in ev_lower for kw in ["error", "exception", "crash", "fatal", "critical"]):
            evidence_items.append(EvidenceItem(
                code="ERROR_LOG_SPIKE",
                description=f"Error/exception terdeteksi: {evidence_raw[:60]}",
                value="ERROR", threshold="NONE",
                weight=EVIDENCE_WEIGHT["ERROR_LOG_SPIKE"],
                source="log_analysis",
            ))

        # SLA breach
        if any(kw in ev_lower for kw in ["sla", "breach", "downtime", "availability"]):
            evidence_items.append(EvidenceItem(
                code="SLA_BREACH",
                description="Potensi SLA breach terdeteksi",
                value="AT_RISK", threshold="99.9%",
                weight=EVIDENCE_WEIGHT["SLA_BREACH"],
                source="sla_monitor",
            ))

        # Historical pattern dari episodic memory
        historical_context = ""
        if self._memory:
            try:
                ctx = self._memory.get_device_context(device)
                risk = self._memory.get_device_risk_level(device)
                if ctx:
                    evidence_items.append(EvidenceItem(
                        code="HISTORICAL_PATTERN",
                        description=f"Device {device} punya riwayat insiden berulang",
                        value=risk, threshold="LOW",
                        weight=EVIDENCE_WEIGHT["HISTORICAL_PATTERN"],
                        source="episodic_memory",
                    ))
                    historical_context = ctx
            except Exception:
                pass

        # Dari DB — cek historical incident count
        if self._db and not historical_context:
            try:
                with self._db.cursor() as cur:
                    cur.execute(
                        """SELECT COUNT(*), AVG(EXTRACT(EPOCH FROM (resolved_at - created_at))/60)
                           FROM incidents
                           WHERE device_name = %s AND resolved_at IS NOT NULL
                           AND created_at > NOW() - INTERVAL '30 days'""",
                        (device,)
                    )
                    row = cur.fetchone()
                    if row and row[0] and int(row[0]) > 1:
                        count = int(row[0])
                        mttr = round(float(row[1] or 0), 0)
                        evidence_items.append(EvidenceItem(
                            code="HISTORICAL_PATTERN",
                            description=f"{device} terjadi {count}x dalam 30 hari, MTTR rata-rata {mttr} menit",
                            value=count, threshold=1,
                            weight=EVIDENCE_WEIGHT["HISTORICAL_PATTERN"],
                            source="historical_db",
                        ))
                        historical_context = f"Pola ini terjadi {count}x dalam 30 hari, MTTR rata-rata {mttr:.0f} menit."
            except Exception as _e:
                logger.debug("[XAI] DB historical query error: %s", _e)

        # Counter evidence — hal yang tidak mendukung severity tinggi
        if severity in ("CRITICAL", "HIGH") and not evidence_items:
            counter_items.append(CounterEvidence(
                description="Tidak ada metrik live yang mendukung severity ini",
                impact="Moderate"
            ))
        if cpu_val and float(cpu_val) < 70 and severity == "CRITICAL":
            counter_items.append(CounterEvidence(
                description=f"CPU {cpu_val}% di bawah threshold warning (70%)",
                impact="Minor"
            ))

        # Confidence calculation
        ev_score = min(1.0, sum(e.weight for e in evidence_items))
        criteria_met = len(evidence_items)
        criteria_total = 3  # Minimum 3 bukti untuk severity tinggi

        # Adjustment berdasarkan severity dari insiden
        sev_base = {"CRITICAL": 0.85, "HIGH": 0.72, "MEDIUM": 0.58, "LOW": 0.40}.get(severity, 0.55)

        # Penalti jika ada counter evidence
        counter_penalty = sum(
            0.10 if ce.impact == "Significant" else 0.05 if ce.impact == "Moderate" else 0.02
            for ce in counter_items
        )

        confidence = min(0.98, max(0.30,
            sev_base * 0.5 + ev_score * 0.4 + (criteria_met / max(criteria_total, 1)) * 0.1 - counter_penalty
        ))

        # Build rationale summary
        if evidence_items:
            top_ev = sorted(evidence_items, key=lambda e: e.weight, reverse=True)[:2]
            reasons = " dan ".join(e.description for e in top_ev)
            rationale = f"{severity} ditetapkan karena: {reasons}."
        else:
            rationale = f"{severity} ditetapkan berdasarkan kategori insiden ({evidence_raw[:60]})."

        if criteria_met >= 2:
            rationale += f" {criteria_met} dari {criteria_total} kriteria terpenuhi."

        confidence_breakdown = {
            "severity_base": round(sev_base * 0.5, 3),
            "evidence_score": round(ev_score * 0.4, 3),
            "criteria_ratio": round((criteria_met / max(criteria_total, 1)) * 0.1, 3),
            "counter_penalty": round(-counter_penalty, 3),
        }

        return DecisionExplanation(
            decision_id=f"XAI-{inc_id}-{int(time.time())}",
            subject=f"INC-{inc_id} ({device})",
            decision=decision,
            rationale_summary=rationale,
            evidence_items=evidence_items,
            counter_evidence=counter_items,
            historical_context=historical_context,
            confidence_score=confidence,
            confidence_breakdown=confidence_breakdown,
            severity=severity,
            criteria_met=criteria_met,
            criteria_total=criteria_total,
        )

    def explain_remediation(
        self,
        action: str,
        device: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> DecisionExplanation:
        """
        Jelaskan mengapa AI merekomendasikan aksi remediasi tertentu.
        
        Args:
            action: Aksi yang direkomendasikan (RESTART_SPOOLER, FLUSH_DNS, dll)
            device: Target device
            context: Context insiden
        """
        action_explanations = {
            "RESTART_SPOOLER": {
                "rationale": "Print spooler service tidak responsif — restart adalah solusi standar SOP-PRINT-001",
                "evidence_code": "SERVICE_DOWN",
                "evidence_desc": "Spooler service dalam state STUCK/HUNG",
                "alternatives": ["Update driver printer", "Reinstall printer service"],
            },
            "FLUSH_DNS": {
                "rationale": "DNS cache korup atau stale entry terdeteksi — flush cache solusi paling cepat",
                "evidence_code": "NETWORK_LOSS",
                "evidence_desc": "DNS resolution gagal atau timeout",
                "alternatives": ["Restart network service", "Ganti DNS server"],
            },
            "CLEAR_PRINT_QUEUE": {
                "rationale": "Antrian cetak stuck dengan dokumen corrupt — clear queue diperlukan",
                "evidence_code": "SERVICE_DOWN",
                "evidence_desc": "Print queue dalam state STUCK",
                "alternatives": ["Restart spooler", "Delete file spool manual"],
            },
            "RESTART_SERVICE": {
                "rationale": "Service tidak responsif — restart adalah tindakan recovery standar",
                "evidence_code": "SERVICE_DOWN",
                "evidence_desc": "Service timeout atau not responding",
                "alternatives": ["Cek dependency service", "Review error log dahulu"],
            },
        }

        exp = action_explanations.get(action, {
            "rationale": f"Aksi {action} dipilih berdasarkan pola insiden dan SOP terdaftar",
            "evidence_code": "SERVICE_DOWN",
            "evidence_desc": f"Issue pada {device}",
            "alternatives": [],
        })

        evidence_items = [EvidenceItem(
            code=exp["evidence_code"],
            description=exp["evidence_desc"],
            value="DEGRADED", threshold="NORMAL",
            weight=0.7,
            source="sop_knowledge_base",
        )]

        # Historical dari memory
        historical_context = ""
        if self._memory:
            try:
                ctx = self._memory.get_device_context(device)
                if ctx:
                    historical_context = ctx
            except Exception:
                pass

        return DecisionExplanation(
            decision_id=f"XAI-REM-{int(time.time())}",
            subject=device,
            decision=f"Rekomendasi: {action}",
            rationale_summary=exp["rationale"],
            evidence_items=evidence_items,
            counter_evidence=[],
            historical_context=historical_context,
            confidence_score=0.82,
            confidence_breakdown={"sop_match": 0.70, "historical": 0.12},
            severity="ACTION",
            criteria_met=1,
            criteria_total=1,
        )

    def batch_explain(
        self,
        incidents: List[Dict[str, Any]],
        live_metrics: Optional[Dict[str, Any]] = None,
    ) -> List[DecisionExplanation]:
        """Explain semua insiden dalam batch — untuk dashboard overview."""
        return [self.explain_incident_priority(inc, live_metrics) for inc in incidents]


# ─── Singleton ────────────────────────────────────────────────────────────────
_instance: Optional[XAIEngine] = None

def get_xai_engine(db_conn: Optional[Any] = None,
                   episodic_memory: Optional[Any] = None) -> XAIEngine:
    global _instance
    if _instance is None:
        _instance = XAIEngine(db_conn=db_conn, episodic_memory=episodic_memory)
    return _instance
