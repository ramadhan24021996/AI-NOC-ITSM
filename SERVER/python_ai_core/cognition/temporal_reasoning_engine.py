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
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger("TEMPORAL_REASONING")


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
                "root_signal": str — metrik pertama yang melonjak
            }
        """
        if anchor_time is None:
            anchor_time = datetime.now(timezone.utc)

        events: List[TemporalEvent] = []
        try:
            conn = self._get_conn()
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
                for r in t_logs:
                    ts, agent, metric, value = r
                    events.append(TemporalEvent(
                        ts=ts,
                        host=agent,
                        metric=metric or "unknown_metric",
                        value=value,
                        severity="HIGH" if (value and float(value) > 80) else "INFO"
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

        except Exception as e:
            if self.conn:
                try:
                    self.conn.rollback()
                except:
                    pass
            logger.error(f"[TEMPORAL] Query gagal untuk host '{hostname}': {e}")

        # Sort semua events berdasarkan timestamp
        events.sort(key=lambda x: x.timestamp if x.timestamp else datetime.min.replace(tzinfo=timezone.utc))

        if not events:
            return {
                "host": hostname,
                "window_minutes": self.WINDOW_MINUTES,
                "anchor_time": anchor_time.isoformat(),
                "events": [],
                "causal_chain": f"Tidak ada event historis ditemukan untuk {hostname} dalam {self.WINDOW_MINUTES} menit terakhir.",
                "first_event": None,
                "root_signal": "UNKNOWN"
            }

        # Bangun narasi kausal
        causal_lines = []
        for ev in events:
            ts_str = ev.timestamp.strftime("%H:%M:%S") if ev.timestamp else "??"
            causal_lines.append(
                f"  {ts_str} | {ev.host} | {ev.metric} = {ev.value} [{ev.severity}]"
            )

        # Identifikasi sinyal pertama yang melonjak sebagai root signal kandidat
        root_signal = "UNKNOWN"
        for ev in events:
            try:
                if ev.value and float(str(ev.value)) > 70:
                    root_signal = ev.metric
                    break
            except (ValueError, TypeError):
                if ev.severity == "HIGH":
                    root_signal = ev.metric
                    break

        causal_chain = (
            f"KRONOLOGI EVENT ({hostname}, window {self.WINDOW_MINUTES} menit):\n"
            + "\n".join(causal_lines)
            + f"\n\nSINYAL PERTAMA TERDETEKSI: {root_signal}"
        )

        return {
            "host": hostname,
            "window_minutes": self.WINDOW_MINUTES,
            "anchor_time": anchor_time.isoformat(),
            "events": [e.to_dict() for e in events],
            "causal_chain": causal_chain,
            "first_event": events[0].to_dict() if events else None,
            "root_signal": root_signal
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
        return (
            f"ANALISIS TEMPORAL (Urutan Waktu Kejadian):\n"
            f"{chain}\n\n"
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
