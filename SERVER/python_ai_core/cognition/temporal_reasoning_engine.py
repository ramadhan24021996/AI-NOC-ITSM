"""
Enterprise AI OS — Temporal Reasoning Engine
Sprint: Gap Closure 1B

Tujuan:
Membangun urutan kausal berdasarkan timestamp event NYATA dari database.
AI tidak boleh melihat snapshot sesaat — harus memahami KRONOLOGI kejadian.

Contoh output:
  08:00 CPU naik (PC-01)
  08:02 Disk latency naik (PC-01)
  08:03 Database timeout (DB-Server)
  08:04 API timeout (App-Server)
  08:05 NOC Alert dipicu

ZERO-MOCK: Semua data dari telemetry_logs, incident_events, fleet_incidents.
"""

import logging
import math
import os
import statistics
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

try:
    from shared.db_pool import PGConnection
except ImportError:
    try:
        from SERVER.shared.db_pool import PGConnection
    except ImportError:
        PGConnection = None

logger = logging.getLogger("TEMPORAL_REASONING")


# Domain-aware thresholds: (medium_threshold, high_threshold, critical_threshold)
DOMAIN_METRIC_THRESHOLDS = {
    "packet_loss": (0.2, 1.0, 5.0),
    "loss": (0.2, 1.0, 5.0),
    "error_rate": (0.5, 1.0, 5.0),
    "http_5xx": (0.5, 1.0, 5.0),
    "crc_error": (1.0, 5.0, 20.0),
    "drop": (1.0, 5.0, 25.0),
    "latency": (50.0, 100.0, 300.0),
    "rtt": (50.0, 100.0, 300.0),
    "ping": (50.0, 100.0, 300.0),
    "response_time": (200.0, 500.0, 1500.0),
    "temp": (65.0, 75.0, 85.0),
    "temperature": (65.0, 75.0, 85.0),
    "cpu": (70.0, 80.0, 92.0),
    "ram": (75.0, 85.0, 94.0),
    "mem": (75.0, 85.0, 94.0),
    "disk": (75.0, 85.0, 95.0),
    "queue": (10.0, 25.0, 100.0),
    "backlog": (10.0, 25.0, 100.0),
}

# Metrics where large numbers are normal (throughput/IOPS/bytes) and should only trigger via statistical Z-score
VOLUME_METRICS = ("throughput", "iops", "bps", "kbps", "mbps", "bytes", "packets_sec", "uptime")


def get_diurnal_multiplier(metric_name: str, hour: int, is_weekend: bool = False) -> float:
    """
    Calculates seasonal diurnal threshold calibration multiplier based on hour of day (0-23)
    and business days vs weekend.
    Peak business hours (08:00 - 20:00 on weekdays):
      Threshold relaxes slightly (1.05 - 1.10x) to accommodate expected transactional load.
    Off-peak / Night hours (22:00 - 06:00):
      Threshold tightens (0.80 - 0.88x) to catch stealth anomalies (e.g. runaway backup,
      cryptomining, slow thread leak) that should NOT be occurring at night.
    """
    m_lower = (metric_name or "").lower()
    is_work_hour = (8 <= hour <= 20) and not is_weekend

    # Volume/Utilization metrics fluctuate heavily with business hours
    if any(k in m_lower for k in ("cpu", "ram", "mem", "throughput", "iops", "queue", "backlog")):
        if is_work_hour:
            return 1.08  # Relax threshold during normal business rush
        elif 22 <= hour or hour <= 6:
            return 0.82  # Tighten threshold during quiet hours
    return 1.0


def evaluate_multivariate_anomaly(
    metrics_snapshot: Dict[str, Any],
    historical_window: Optional[List[Dict[str, float]]] = None
) -> Dict[str, Any]:
    """
    Multi-Variate Composite Anomaly Scorer.
    Detects composite systemic failures across correlated metric vectors:
      1. SILENT_DEADLOCK: Low/normal CPU (< 35%) with rising queue depth (>= 15) or stalled I/O.
      2. MEMORY_THRASHING: High RAM (>= 85%) correlated with high disk utilization or swap latency.
      3. NETWORK_BLACKHOLE: High packet loss (>= 5%) paired with severe latency (>= 150ms).
      4. RESOURCE_STARVATION: Concurrently high CPU (>= 88%) and high Memory (>= 88%).
    """
    if not metrics_snapshot or not isinstance(metrics_snapshot, dict):
        return {
            "is_multivariate_anomaly": False,
            "pattern_detected": "NONE",
            "composite_severity": "INFO",
            "confidence": 0.0,
            "correlated_metrics": [],
            "explanation": "No metrics available for composite evaluation"
        }

    # Normalize metrics to float
    def _get_val(*keys) -> Optional[float]:
        for k in keys:
            for mk, mv in metrics_snapshot.items():
                if k in mk.lower():
                    try:
                        return float(str(mv).replace("%", "").replace("ms", "").strip())
                    except (ValueError, TypeError):
                        pass
        return None

    cpu = _get_val("cpu")
    ram = _get_val("ram", "mem")
    disk = _get_val("disk", "iops")
    queue = _get_val("queue", "backlog")
    loss = _get_val("packet_loss", "loss", "drop")
    latency = _get_val("latency", "rtt", "ping")

    # Pattern 1: SILENT DEADLOCK (Thread lock / app hang while CPU looks idle)
    if cpu is not None and queue is not None:
        if cpu < 35.0 and queue >= 15.0:
            return {
                "is_multivariate_anomaly": True,
                "pattern_detected": "SILENT_DEADLOCK",
                "composite_severity": "CRITICAL",
                "confidence": 0.94,
                "correlated_metrics": ["cpu", "queue_depth"],
                "explanation": f"Silent Deadlock: CPU is idle ({cpu:.1f}%) but Queue Depth is high ({queue:.1f}), indicating process hang or lock contention."
            }

    # Pattern 2: MEMORY THRASHING & SWAPPING
    if ram is not None and (disk is not None or queue is not None):
        if ram >= 85.0 and ((disk and disk >= 85.0) or (queue and queue >= 15.0)):
            return {
                "is_multivariate_anomaly": True,
                "pattern_detected": "MEMORY_THRASHING",
                "composite_severity": "CRITICAL",
                "confidence": 0.92,
                "correlated_metrics": ["ram", "disk"],
                "explanation": f"Memory Thrashing: High RAM usage ({ram:.1f}%) with severe I/O pressure ({disk or queue:.1f}), causing swap thrashing."
            }

    # Pattern 3: NETWORK BLACKHOLE
    if loss is not None and latency is not None:
        if loss >= 5.0 and latency >= 150.0:
            return {
                "is_multivariate_anomaly": True,
                "pattern_detected": "NETWORK_BLACKHOLE",
                "composite_severity": "CRITICAL",
                "confidence": 0.95,
                "correlated_metrics": ["packet_loss", "latency"],
                "explanation": f"Network Blackhole: High packet loss ({loss:.1f}%) combined with high RTT latency ({latency:.1f}ms)."
            }

    # Pattern 4: FULL RESOURCE STARVATION
    if cpu is not None and ram is not None:
        if cpu >= 88.0 and ram >= 88.0:
            return {
                "is_multivariate_anomaly": True,
                "pattern_detected": "RESOURCE_STARVATION",
                "composite_severity": "CRITICAL",
                "confidence": 0.96,
                "correlated_metrics": ["cpu", "ram"],
                "explanation": f"Resource Starvation: Dual CPU ({cpu:.1f}%) and RAM ({ram:.1f}%) exhaustion."
            }

    return {
        "is_multivariate_anomaly": False,
        "pattern_detected": "NORMAL",
        "composite_severity": "INFO",
        "confidence": 0.0,
        "correlated_metrics": [],
        "explanation": "No multi-variate anomaly detected"
    }


def evaluate_metric_severity(
    metric_name: str,
    value: Any,
    series_values: Optional[List[float]] = None,
    hour: Optional[int] = None,
    is_weekend: bool = False,
) -> str:
    """
    Domain-Aware + Statistical Z-Score/MAD + Diurnal Seasonal Metric Severity Evaluator.
    Prevents false-negatives on low-numeric critical metrics (e.g. packet_loss=3%)
    and false-positives on high-numeric normal metrics (e.g. throughput=500).
    """
    if value is None:
        return "INFO"
    try:
        num_val = float(str(value).replace("%", "").replace("ms", "").strip())
    except (ValueError, TypeError):
        val_str = str(value).upper()
        if any(w in val_str for w in ("DOWN", "CRITICAL", "FAIL", "TIMEOUT", "ERR", "LOS", "UNREACHABLE")):
            return "CRITICAL"
        if any(w in val_str for w in ("WARN", "DEGRADED", "HIGH", "RETRY")):
            return "HIGH"
        return "INFO"

    m_lower = (metric_name or "").lower()

    # 1. Statistical Z-Score / MAD Spike Detection across the window series
    z_severity = "INFO"
    if series_values and len(series_values) >= 3:
        try:
            mean_val = statistics.mean(series_values)
            stdev_val = statistics.stdev(series_values) if len(series_values) > 1 else 0.0
            if stdev_val > 1e-6:
                z_score = (num_val - mean_val) / stdev_val
                if z_score >= 3.0 and num_val > 0:
                    z_severity = "CRITICAL"
                elif z_score >= 2.0 and num_val > 0:
                    z_severity = "HIGH"
            else:
                median_val = statistics.median(series_values)
                if median_val > 0 and num_val >= median_val * 2.5:
                    z_severity = "HIGH"
        except Exception:
            pass

    # If it is a pure volume metric (throughput/IOPS), rely on statistical spike detection
    if any(vm in m_lower for vm in VOLUME_METRICS):
        return z_severity

    # 2. Check Domain-Specific Thresholds with Diurnal Multiplier Calibration
    matched_thresholds = None
    for key, thresholds in DOMAIN_METRIC_THRESHOLDS.items():
        if key in m_lower:
            matched_thresholds = thresholds
            break

    if matched_thresholds is None:
        matched_thresholds = (70.0, 80.0, 92.0)

    med_th, high_th, crit_th = matched_thresholds

    # Apply seasonal diurnal multiplier if hour is provided
    if hour is not None:
        multiplier = get_diurnal_multiplier(m_lower, hour, is_weekend)
        med_th *= multiplier
        high_th *= multiplier
        crit_th *= multiplier

    domain_sev = "INFO"
    if num_val >= crit_th:
        domain_sev = "CRITICAL"
    elif num_val >= high_th:
        domain_sev = "HIGH"
    elif num_val >= med_th:
        domain_sev = "MEDIUM"

    rank = {"INFO": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
    return domain_sev if rank[domain_sev] >= rank[z_severity] else z_severity


class TemporalEvent:
    """Representasi satu event dalam timeline."""
    def __init__(self, ts: datetime, host: str, metric: str, value: Any, severity: str = "INFO"):
        self.timestamp = ts
        self.host = host
        self.metric = metric
        self.value = value
        self.severity = severity

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "host": self.host,
            "metric": self.metric,
            "value": self.value,
            "severity": self.severity,
        }


class TemporalReasoningEngine:
    """
    Membangun kronologi kausal dari telemetri nyata dalam window waktu.
    Digunakan sebelum Consensus Engine untuk memperkaya konteks hipotesis.
    """

    WINDOW_MINUTES = 10  # Window waktu analisis (menit)

    def __init__(self, db_conn=None):
        self.conn = db_conn

    def _get_conn(self):
        if self.conn and not getattr(self.conn, "closed", 0):
            return self.conn
        if PGConnection is not None:
            return PGConnection().__enter__()
        import psycopg2
        return psycopg2.connect(
            host=os.getenv("DB_HOST", "postgres"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "osi_system"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "")
        )

    def correlate_recent_changes(self, conn, hostname: str, anchor_time: datetime, change_window_minutes: int = 30) -> List[Dict[str, Any]]:
        """
        Change-Event Correlation Engine:
        Detects any recent configuration changes, remediation executions, or policy updates
        on or affecting `hostname` within `change_window_minutes` before `anchor_time`.
        """
        recent_changes: List[Dict[str, Any]] = []
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT ie.created_at, ie.event_type, ie.payload
                    FROM incident_events ie
                    LEFT JOIN fleet_incidents fi ON ie.incident_id = fi.incident_id::text
                    WHERE (fi.pc_name = %s OR ie.payload::text ILIKE %s)
                      AND ie.event_type IN ('APPROVED', 'EXECUTING', 'MITIGATION_APPLIED', 'CONFIG_CHANGE', 'DEPLOY', 'POLICY_UPDATE', 'MANUAL_EXECUTION')
                      AND ie.created_at BETWEEN (%s - INTERVAL '%s minutes') AND %s
                    ORDER BY ie.created_at DESC
                    LIMIT 5
                """, (hostname, f"%{hostname}%", anchor_time, change_window_minutes, anchor_time))
                for ts, ev_type, payload in cur.fetchall():
                    recent_changes.append({
                        "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                        "change_type": ev_type,
                        "summary": str(payload)[:160] if payload else "",
                    })
        except Exception as chg_err:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.debug(f"[TEMPORAL] Change correlation query note for '{hostname}': {chg_err}")
        return recent_changes

    def build_timeline(self, hostname: str, anchor_time: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Ambil semua event dalam window WINDOW_MINUTES dari anchor_time.
        Jika anchor_time None, gunakan NOW().

        Returns:
            {
                "host": hostname,
                "window_minutes": N,
                "anchor_time": ISO string,
                "events": [sorted list of TemporalEvent dicts],
                "causal_chain": narrative string,
                "first_event": dict,
                "root_signal": str — metrik pertama yang melonjak,
                "recent_changes": list of correlated change events,
                "change_correlation_hypothesis": optional str
            }
        """
        if anchor_time is None:
            anchor_time = datetime.now(timezone.utc)

        events: List[TemporalEvent] = []
        recent_changes: List[Dict[str, Any]] = []
        conn = None
        owns_conn = False
        try:
            if self.conn and not getattr(self.conn, "closed", 0):
                conn = self.conn
            else:
                conn = self._get_conn()
                owns_conn = True

            with conn.cursor() as cur:
                # 1. Ambil telemetry log di window waktu
                cur.execute("""
                    SELECT "timestamp", device_name, metric_type, metric_value
                    FROM telemetry_logs
                    WHERE device_name = %s
                      AND "timestamp" BETWEEN (%s - INTERVAL '%s minutes') AND %s
                    ORDER BY "timestamp" ASC
                """, (hostname, anchor_time, self.WINDOW_MINUTES, anchor_time))
                t_logs = cur.fetchall()

                # Group numeric series per metric for statistical Z-score / MAD evaluation
                series_by_metric: Dict[str, List[float]] = {}
                for _, _, m_type, m_val in t_logs:
                    m_key = (m_type or "unknown_metric").lower()
                    try:
                        series_by_metric.setdefault(m_key, []).append(
                            float(str(m_val).replace("%", "").replace("ms", "").strip())
                        )
                    except (ValueError, TypeError):
                        pass

                for r in t_logs:
                    ts, agent, metric, value = r
                    m_name = metric or "unknown_metric"
                    sev = evaluate_metric_severity(
                        m_name,
                        value,
                        series_by_metric.get(m_name.lower()),
                    )
                    events.append(TemporalEvent(
                        ts=ts,
                        host=agent,
                        metric=m_name,
                        value=value,
                        severity=sev
                    ))

                # 2. Ambil event dari incident (state transitions, dll) yang terkait dengan hostname yang sama
                cur.execute("""
                    SELECT ie.created_at, fi.pc_name, ie.event_type, ie.payload
                    FROM incident_events ie
                    JOIN fleet_incidents fi ON ie.incident_id = fi.incident_id::text
                    WHERE fi.pc_name = %s
                      AND ie.created_at BETWEEN (%s - INTERVAL '%s minutes') AND %s
                    ORDER BY ie.created_at ASC
                """, (hostname, anchor_time, self.WINDOW_MINUTES, anchor_time))
                i_logs = cur.fetchall()
                for r in i_logs:
                    ts, pc, event_type, payload = r
                    events.append(TemporalEvent(
                        ts=ts,
                        host=pc or hostname,
                        metric=event_type or "INCIDENT_EVENT",
                        value=str(payload)[:80] if payload else "",
                        severity="HIGH"
                    ))

            # 3. Correlate recent changes within 30 minutes before anchor_time
            recent_changes = self.correlate_recent_changes(conn, hostname, anchor_time, change_window_minutes=30)

        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            logger.error(f"[TEMPORAL] Query gagal untuk host '{hostname}': {e}")
        finally:
            if owns_conn and conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

        # Sort semua events berdasarkan timestamp
        events.sort(key=lambda x: x.timestamp if x.timestamp else datetime.min.replace(tzinfo=timezone.utc))

        change_hypothesis = None
        if recent_changes:
            latest_chg = recent_changes[0]
            change_hypothesis = (
                f"Terdeteksi aktivitas perubahan/eksekusi ({latest_chg['change_type']}) pada {hostname} "
                f"sebelum/dekat waktu insiden ({latest_chg['timestamp']}): {latest_chg['summary']}"
            )

        if not events:
            return {
                "host": hostname,
                "window_minutes": self.WINDOW_MINUTES,
                "anchor_time": anchor_time.isoformat(),
                "events": [],
                "causal_chain": f"Tidak ada event historis ditemukan untuk {hostname} dalam {self.WINDOW_MINUTES} menit terakhir.",
                "first_event": None,
                "root_signal": "UNKNOWN",
                "recent_changes": recent_changes,
                "change_correlation_hypothesis": change_hypothesis,
            }

        # Bangun narasi kausal
        causal_lines = []
        for ev in events:
            ts_str = ev.timestamp.strftime("%H:%M:%S") if ev.timestamp else "??"
            causal_lines.append(
                f"  {ts_str} | {ev.host} | {ev.metric} = {ev.value} [{ev.severity}]"
            )

        # Identifikasi sinyal pertama yang melonjak sebagai root signal kandidat menggunakan Domain-Aware Severity
        root_signal = "UNKNOWN"
        for target_sev in ("CRITICAL", "HIGH", "MEDIUM"):
            for ev in events:
                if ev.severity == target_sev:
                    root_signal = ev.metric
                    break
            if root_signal != "UNKNOWN":
                break

        causal_chain = (
            f"KRONOLOGI EVENT ({hostname}, window {self.WINDOW_MINUTES} menit):\n"
            + "\n".join(causal_lines)
            + f"\n\nSINYAL PERTAMA TERDETEKSI: {root_signal}"
        )
        if change_hypothesis:
            causal_chain += f"\n[KORELASI PERUBAHAN TERBARU]: {change_hypothesis}"

        return {
            "host": hostname,
            "window_minutes": self.WINDOW_MINUTES,
            "anchor_time": anchor_time.isoformat(),
            "events": [e.to_dict() for e in events],
            "causal_chain": causal_chain,
            "first_event": events[0].to_dict() if events else None,
            "root_signal": root_signal,
            "recent_changes": recent_changes,
            "change_correlation_hypothesis": change_hypothesis,
        }

    def multi_host_timeline(self, hostnames: List[str], anchor_time: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Bangun timeline gabungan dari beberapa host.
        Digunakan oleh Multi-host Correlation untuk mencari common parent.
        """
        all_events: List[TemporalEvent] = []
        if anchor_time is None:
            anchor_time = datetime.now(timezone.utc)

        for host in hostnames:
            result = self.build_timeline(host, anchor_time)
            for ev_dict in result.get("events", []):
                ts = ev_dict.get("timestamp")
                if ts:
                    try:
                        ts_parsed = datetime.fromisoformat(ts)
                    except Exception:
                        ts_parsed = anchor_time
                else:
                    ts_parsed = anchor_time
                all_events.append(TemporalEvent(
                    ts=ts_parsed,
                    host=ev_dict["host"],
                    metric=ev_dict["metric"],
                    value=ev_dict["value"],
                    severity=ev_dict["severity"]
                ))

        all_events.sort(key=lambda x: x.timestamp if x.timestamp else datetime.min.replace(tzinfo=timezone.utc))

        lines = []
        for ev in all_events:
            ts_str = ev.timestamp.strftime("%H:%M:%S") if ev.timestamp else "??"
            lines.append(f"  {ts_str} | {ev.host} | {ev.metric} = {ev.value}")

        return {
            "hosts": hostnames,
            "total_events": len(all_events),
            "combined_timeline": "\n".join(lines),
            "events": [e.to_dict() for e in all_events]
        }

    def build_prompt_snippet(self, timeline_result: Dict[str, Any]) -> str:
        """Kembalikan string yang siap disuntikkan ke prompt LLM."""
        chain = timeline_result.get("causal_chain", "Tidak ada data timeline.")
        root = timeline_result.get("root_signal", "UNKNOWN")
        chg = timeline_result.get("change_correlation_hypothesis")
        chg_block = f"\nKORELASI PERUBAHAN (CHANGE EVENT): {chg}\n" if chg else ""
        return (
            f"ANALISIS TEMPORAL (Urutan Waktu Kejadian):\n"
            f"{chain}\n"
            f"{chg_block}\n"
            f"Berdasarkan kronologi di atas, sinyal pertama yang teramati adalah: {root}.\n"
            f"Gunakan urutan ini untuk menetapkan ROOT CAUSE yang paling awal dalam rantai kausal, "
            f"bukan gejala yang muncul belakangan."
        )


_instance: Optional[TemporalReasoningEngine] = None


def get_temporal_engine(db_conn=None) -> TemporalReasoningEngine:
    global _instance
    if _instance is None:
        _instance = TemporalReasoningEngine(db_conn=db_conn)
    elif db_conn and _instance.conn != db_conn:
        _instance.conn = db_conn
    return _instance
