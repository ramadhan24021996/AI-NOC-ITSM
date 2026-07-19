"""
Enterprise AI OS — Hypothesis Engine
Sprint: Gap Closure 1C + 1D

Tujuan:
Menghasilkan N hipotesis kandidat root cause dari evidence, kemudian
memvalidasi setiap hipotesis dengan Counter Evidence dari database nyata.

Alur:
  Evidence → [Hipotesis A, B, C, D, E]
  → Scoring per hipotesis
  → Counter Evidence validation (turunkan score jika ada bukti bantahan)
  → Ranking → Best Root Cause

ZERO-MOCK: Scoring berdasarkan real data dari telemetry_logs, osi_taxonomy,
dan evidence_fabric. Counter evidence diambil dari telemetry nyata.
"""

import logging
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("HYPOTHESIS_ENGINE")


@dataclass
class Hypothesis:
    """Representasi satu hipotesis root cause."""
    id: str
    text: str
    osi_layer: int
    osi_label: str
    base_score: float = 50.0          # Skor awal sebelum validasi
    evidence_score: float = 0.0       # +skor dari evidence yang mendukung
    counter_score: float = 0.0        # -penalty dari bukti bantahan
    historical_score: float = 0.0     # +skor dari insiden historis serupa
    final_score: float = 0.0          # Skor akhir setelah semua komponen
    supporting_evidence: List[str] = field(default_factory=list)
    counter_evidence: List[str] = field(default_factory=list)
    accepted: bool = True             # False jika di-discard

    def calculate_final(self):
        self.final_score = max(
            0.0,
            self.base_score + self.evidence_score - self.counter_score + self.historical_score
        )
        self.final_score = min(100.0, self.final_score)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "osi_layer": self.osi_layer,
            "osi_label": self.osi_label,
            "base_score": self.base_score,
            "evidence_score": self.evidence_score,
            "counter_score": self.counter_score,
            "historical_score": self.historical_score,
            "final_score": round(self.final_score, 2),
            "supporting_evidence": self.supporting_evidence,
            "counter_evidence": self.counter_evidence,
            "accepted": self.accepted
        }


class HypothesisEngine:
    """
    Menghasilkan N hipotesis berdasarkan evidence dan OSI classification,
    kemudian memvalidasi setiap hipotesis dengan Counter Evidence.
    """

    # Peta layer OSI ke hipotesis umum
    LAYER_HYPOTHESIS_MAP = {
        1: [
            ("Hardware failure atau power issue", 1, "Physical Layer"),
            ("Cable atau fiber disconnect", 1, "Physical Layer"),
            ("Temperature overload perangkat", 1, "Physical Layer"),
        ],
        2: [
            ("VLAN misconfiguration atau STP loop", 2, "Data Link Layer"),
            ("MAC table overflow atau broadcast storm", 2, "Data Link Layer"),
            ("Duplex mismatch pada interface", 2, "Data Link Layer"),
        ],
        3: [
            ("IP conflict atau routing failure", 3, "Network Layer"),
            ("Gateway unreachable atau ARP failure", 3, "Network Layer"),
            ("BGP/OSPF route flap", 3, "Network Layer"),
        ],
        4: [
            ("TCP connection timeout atau SYN flood", 4, "Transport Layer"),
            ("Port unreachable atau firewall drop", 4, "Transport Layer"),
            ("Retransmission storm karena packet loss", 4, "Transport Layer"),
        ],
        5: [
            ("Session expired atau authentication failure", 5, "Session Layer"),
            ("SMB session disconnect", 5, "Session Layer"),
        ],
        6: [
            ("TLS/SSL certificate expired atau invalid", 6, "Presentation Layer"),
            ("Encryption handshake failure", 6, "Presentation Layer"),
        ],
        7: [
            ("Application crash atau OOM (Out of Memory)", 7, "Application Layer"),
            ("Database connection pool exhausted", 7, "Application Layer"),
            ("DNS resolution failure", 7, "Application Layer"),
            ("API endpoint down atau rate limited", 7, "Application Layer"),
        ],
    }

    def __init__(self, db_conn=None):
        self.conn = db_conn

    def _get_conn(self):
        if self.conn and not self.conn.closed:
            return self.conn
        import psycopg2
        return psycopg2.connect(
            host=os.getenv("DB_HOST", "postgres"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "osi_system"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "")
        )

    def generate(
        self,
        osi_layer: int,
        symptoms_text: str,
        evidence_pkg: Optional[Dict] = None,
        hostname: str = "UNKNOWN",
        max_hypotheses: int = 5
    ) -> List[Hypothesis]:
        """
        Hasilkan N hipotesis kandidat berdasarkan OSI layer + symptoms.
        Returns sorted list (highest score first).
        """
        candidates = []

        # Ambil template dari peta layer yang terdeteksi + layer ±1 (cascading)
        layers_to_check = {osi_layer}
        if osi_layer > 1:
            layers_to_check.add(osi_layer - 1)
        if osi_layer < 7:
            layers_to_check.add(osi_layer + 1)

        idx = 0
        for layer in sorted(layers_to_check):
            templates = self.LAYER_HYPOTHESIS_MAP.get(layer, [])
            for text, lnum, llabel in templates:
                h = Hypothesis(
                    id=f"H{idx+1:02d}",
                    text=text,
                    osi_layer=lnum,
                    osi_label=llabel,
                    base_score=60.0 if lnum == osi_layer else 35.0  # Layer utama lebih tinggi
                )

                # Score berdasarkan keyword match di symptoms
                keywords = text.lower().split()
                symptoms_lower = symptoms_text.lower()
                keyword_hits = sum(1 for kw in keywords if len(kw) > 3 and kw in symptoms_lower)
                h.evidence_score = min(30.0, keyword_hits * 10.0)
                if keyword_hits > 0:
                    h.supporting_evidence.append(f"Keyword match ({keyword_hits} hits): '{text}'")

                candidates.append(h)
                idx += 1

        # Score dari evidence fabric quality
        if evidence_pkg:
            quality = evidence_pkg.get("quality", {})
            completeness = float(quality.get("completeness_score", 0.5))
            for h in candidates:
                h.evidence_score += completeness * 10.0

        # Historical score dari database
        self._enrich_historical_score(candidates, hostname)

        # Counter Evidence validation
        self._validate_counter_evidence(candidates, hostname)

        # Hitung final score
        for h in candidates:
            h.calculate_final()

        # Sort dan ambil top N
        candidates.sort(key=lambda x: x.final_score, reverse=True)
        top = candidates[:max_hypotheses]

        logger.info(
            f"[HYPOTHESIS] Generated {len(top)} hypotheses for layer {osi_layer} "
            f"on host '{hostname}'. Best: '{top[0].text}' (score={top[0].final_score:.1f})"
            if top else f"[HYPOTHESIS] No hypotheses generated for layer {osi_layer}"
        )
        return top

    def _enrich_historical_score(self, hypotheses: List[Hypothesis], hostname: str):
        """Tambah skor berdasarkan insiden historis serupa dari database."""
        try:
            conn = self._get_conn()
            with conn.cursor() as cur:
                for h in hypotheses:
                    # Cari insiden historis yang cocok dengan teks hipotesis
                    search_term = h.text.split()[:3]
                    if not search_term:
                        continue
                    kw = " ".join(search_term)
                    cur.execute("""
                        SELECT COUNT(*) FROM fleet_incidents
                        WHERE description ILIKE %s
                          AND status = 'RESOLVED'
                        LIMIT 1
                    """, (f"%{kw}%",))
                    row = cur.fetchone()
                    if row and row[0] > 0:
                        historical_boost = min(20.0, float(row[0]) * 5.0)
                        h.historical_score = historical_boost
                        h.supporting_evidence.append(
                            f"Historis: {row[0]} insiden serupa pernah terjadi sebelumnya."
                        )
        except Exception as e:
            if self.conn:
                try:
                    self.conn.rollback()
                except:
                    pass
            logger.warning(f"[HYPOTHESIS] Gagal query historical score: {e}")

    def _validate_counter_evidence(self, hypotheses: List[Hypothesis], hostname: str):
        """
        Cari bukti yang membantah setiap hipotesis dari telemetry nyata.
        Jika bukti bantahan ada → turunkan skor hipotesis.
        """
        try:
            conn = self._get_conn()
            with conn.cursor() as cur:
                # Ambil telemetri terakhir dari host
                cur.execute("""
                    SELECT metric_type, metric_value
                    FROM telemetry_logs
                    WHERE device_name = %s
                    ORDER BY "timestamp" DESC
                    LIMIT 20
                """, (hostname,))
                rows = cur.fetchall()
                recent_metrics = {r[0]: r[1] for r in rows if r[0]}

                for h in hypotheses:
                    # Counter evidence logic per layer
                    layer = h.osi_layer
                    penalty = 0.0

                    if layer == 1:  # Physical Layer Fusion
                        # Jika Switch Port UP dan Endpoint Link UP, kabel tidak mungkin terputus
                        link_status = str(recent_metrics.get("link_status", "")).upper()
                        port_status = str(recent_metrics.get("switch_port_status", "")).upper()
                        if link_status == "UP" and port_status == "UP":
                            if "Cable atau fiber disconnect" in h.text or "Hardware failure" in h.text:
                                penalty += 30.0
                                h.counter_evidence.append("Counter: Link Klien dan Switch Port KEDUANYA dilaporkan UP (L1 Normal).")
                        # Jika ada optical loss / CRC error dari Switch, perkuat hipotesis (reduce penalty, add supporting)
                        crc_errors = float(recent_metrics.get("crc_error", 0))
                        if crc_errors > 10 and "Cable" in h.text:
                            h.evidence_score += 20.0
                            h.supporting_evidence.append(f"Infrastructure: Switch melaporkan {crc_errors} CRC Errors (Physical Degradation).")

                    elif layer == 2:  # Data Link Layer Fusion
                        mac_changes = float(recent_metrics.get("mac_flapping_count", 0))
                        if mac_changes > 5 and "VLAN misconfiguration" in h.text:
                            h.evidence_score += 15.0
                            h.supporting_evidence.append(f"Infrastructure: Terdeteksi MAC Flapping {mac_changes}x di Switch (L2 Loop/Spoofing).")
                        
                        arp_ok = str(recent_metrics.get("arp_status", "")).upper() == "OK"
                        if arp_ok and "broadcast storm" in h.text:
                            penalty += 15.0
                            h.counter_evidence.append("Counter: ARP dan Broadcast rate normal menurut Network Controller.")

                    elif layer == 3:  # IP/Routing
                        # Jika gateway OK (tidak ada gateway timeout), hipotesis routing berkurang
                        if "gateway_rtt_ms" in recent_metrics:
                            gw_rtt = float(recent_metrics["gateway_rtt_ms"] or 0)
                            if gw_rtt < 50:
                                penalty += 20.0
                                h.counter_evidence.append(
                                    f"Counter: Gateway RTT normal ({gw_rtt}ms < 50ms) — routing mungkin bukan penyebab."
                                )

                    elif layer == 7:  # Application
                        # Jika CPU normal dan memory normal, app crash mungkin bukan OOM
                        cpu = recent_metrics.get("cpu_usage")
                        mem = recent_metrics.get("memory_usage")
                        if cpu and float(cpu) < 50 and mem and float(mem) < 70:
                            if "OOM" in h.text or "Out of Memory" in h.text:
                                penalty += 25.0
                                h.counter_evidence.append(
                                    f"Counter: CPU {cpu}% dan Memory {mem}% — tidak ada tanda OOM."
                                )

                    elif layer == 4:  # Transport
                        # Jika port check OK
                        port_status = recent_metrics.get("port_status")
                        if port_status and str(port_status).upper() == "OPEN":
                            if "Port unreachable" in h.text:
                                penalty += 20.0
                                h.counter_evidence.append(
                                    "Counter: Port status OPEN — port bukan yang menjadi masalah."
                                )

                    elif layer == 6:  # TLS/SSL
                        cert_valid = recent_metrics.get("cert_valid")
                        if cert_valid and str(cert_valid).lower() == "true":
                            penalty += 15.0
                            h.counter_evidence.append(
                                "Counter: Sertifikat TLS terverifikasi valid."
                            )

                    h.counter_score = penalty

        except Exception as e:
            if self.conn:
                try:
                    self.conn.rollback()
                except:
                    pass
            logger.warning(f"[HYPOTHESIS] Gagal validate counter evidence: {e}")

    def build_ranked_summary(self, hypotheses: List[Hypothesis]) -> str:
        """Kembalikan string ringkasan ranking untuk disuntikkan ke prompt LLM."""
        if not hypotheses:
            return "Tidak ada hipotesis yang dapat dihasilkan dari evidence yang tersedia."

        lines = ["HIPOTESIS ROOT CAUSE (Diranking berdasarkan skor):"]
        for i, h in enumerate(hypotheses, 1):
            status = "✅ DITERIMA" if h.accepted else "❌ DITOLAK"
            lines.append(
                f"\n  [{i}] {status} (Score: {h.final_score:.1f}/100)\n"
                f"      Hipotesis: {h.text}\n"
                f"      Layer: L{h.osi_layer} — {h.osi_label}\n"
                f"      Pendukung: {'; '.join(h.supporting_evidence) or 'Tidak ada'}\n"
                f"      Bantahan: {'; '.join(h.counter_evidence) or 'Tidak ada'}"
            )
        lines.append(
            f"\n→ HIPOTESIS TERBAIK: [{hypotheses[0].text}] "
            f"(Score: {hypotheses[0].final_score:.1f}/100)"
        )
        return "\n".join(lines)


_instance: Optional[HypothesisEngine] = None


def get_hypothesis_engine(db_conn=None) -> HypothesisEngine:
    global _instance
    if _instance is None:
        _instance = HypothesisEngine(db_conn=db_conn)
    elif db_conn and _instance.conn != db_conn:
        _instance.conn = db_conn
    return _instance
