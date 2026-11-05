"""
Enterprise AI OS — OSI Cognitive Framework: Framework 7
Sprint G1: Correlation Engine + Multi-Host Correlation (Gap 1E)

ZERO-MOCK: Semua korelasi berdasarkan event nyata dari database dan telemetri.
"""

import logging
import time
import uuid
import os
from typing import Dict, List, Any, Optional

logger = logging.getLogger("CORRELATION")

class CorrelatedIncident:
    def __init__(self):
        self.correlation_id = f"CORR-{time.strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
        self.events: List[Dict[str, Any]] = []
        self.primary_host: str = "Unknown"
        self.involved_services: set = set()
        self.first_seen: float = time.time()
        self.last_seen: float = time.time()
        self.status: str = "OPEN"

    def add_event(self, event: Dict[str, Any]):
        self.events.append(event)
        self.last_seen = time.time()
        agent = event.get("agent", "")
        if self.primary_host == "Unknown" and agent:
            self.primary_host = agent
        metadata = event.get("metadata", {})
        component = metadata.get("component", "")
        if component:
            self.involved_services.add(component)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "primary_host": self.primary_host,
            "involved_services": list(self.involved_services),
            "event_count": len(self.events),
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "events_summary": [
                f"{e.get('timestamp')} - {e.get('agent')} - {e.get('status')} - {e.get('metadata', {}).get('component', 'Unknown')}" 
                for e in self.events
            ]
        }


class CorrelationEngine:
    def __init__(self, time_window_seconds: int = 60):
        self.time_window = time_window_seconds
        self.active_correlations: List[CorrelatedIncident] = []

    def process_telemetry(self, telemetry_event: Dict[str, Any]) -> Optional[CorrelatedIncident]:
        now = time.time()
        mature_correlations = []
        active_correlations_new = []
        for corr in self.active_correlations:
            if now - corr.last_seen > self.time_window:
                corr.status = "MATURE"
                mature_correlations.append(corr)
            else:
                active_correlations_new.append(corr)
        self.active_correlations = active_correlations_new

        agent = telemetry_event.get("agent", "")
        metadata = telemetry_event.get("metadata", {})
        component = metadata.get("component", "")

        matched_corr = None
        for corr in self.active_correlations:
            if agent == corr.primary_host or component in corr.involved_services:
                matched_corr = corr
                break

        if matched_corr:
            matched_corr.add_event(telemetry_event)
            logger.info("[CORRELATION] Event correlated to %s (Total events: %d)",
                        matched_corr.correlation_id, len(matched_corr.events))
            return None

        new_corr = CorrelatedIncident()
        new_corr.add_event(telemetry_event)
        self.active_correlations.append(new_corr)
        logger.info("[CORRELATION] New correlation created: %s for %s", new_corr.correlation_id, agent)

        if mature_correlations:
            return mature_correlations[0]
        return None

    def flush_all(self) -> List[CorrelatedIncident]:
        all_corr = self.active_correlations
        self.active_correlations = []
        return all_corr


class MultiHostCorrelator:
    """
    Gap 1E: Deteksi pola multi-host dari database nyata.
    Jika N host error dalam window waktu yang sama → deduksi common parent.

    Contoh:
      PC-A (error) + PC-B (error) + PC-C (error) → semua via Switch-01
      → Root cause hipotesis: Switch-01 (infrastruktur bersama)
    """
    WINDOW_MINUTES = 5
    MIN_HOSTS_THRESHOLD = 2

    def __init__(self, db_conn=None):
        self.conn = db_conn

    def _get_conn(self):
        if self.conn and not getattr(self.conn, "closed", 0):
            return self.conn
        try:
            from shared.db_pool import PGConnection
            return PGConnection().__enter__()
        except ImportError:
            try:
                from SERVER.shared.db_pool import PGConnection
                return PGConnection().__enter__()
            except ImportError:
                import psycopg2
                return psycopg2.connect(
                    host=os.getenv("DB_HOST", "postgres"),
                    port=int(os.getenv("DB_PORT", "5432")),
                    database=os.getenv("DB_NAME", "osi_system"),
                    user=os.getenv("DB_USER", "postgres"),
                    password=os.getenv("DB_PASSWORD", "")
                )

    def analyze(self, current_hostname: str) -> Dict[str, Any]:
        """
        Cek apakah ada host lain yang mengalami insiden dalam window waktu yang sama.
        Returns dict dengan multi_host_detected, affected_hosts, common_parent_hypothesis.
        """
        result = {
            "multi_host_detected": False,
            "affected_hosts": [current_hostname],
            "common_parent_hypothesis": None,
            "confidence_boost": 0.0,
            "summary": "Tidak ada korelasi multi-host terdeteksi."
        }

        conn = None
        owns_conn = False
        try:
            if self.conn and not getattr(self.conn, "closed", 0):
                conn = self.conn
            else:
                conn = self._get_conn()
                owns_conn = True

            with conn.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT host_name FROM (
                        SELECT pc_name AS host_name
                        FROM fleet_incidents
                        WHERE created_at >= NOW() - INTERVAL '%s minutes'
                          AND COALESCE(status, 'OPEN') NOT IN ('RESOLVED', 'CLOSED')
                          AND pc_name IS NOT NULL
                        UNION
                        SELECT device_name AS host_name
                        FROM incidents
                        WHERE created_at >= NOW() - INTERVAL '%s minutes'
                          AND COALESCE(flag, 'OPEN') NOT IN ('RESOLVED', 'CLOSED')
                          AND device_name IS NOT NULL
                    ) active_hosts
                    WHERE LOWER(host_name) != LOWER(%s)
                    LIMIT 20
                """, (self.WINDOW_MINUTES, self.WINDOW_MINUTES, current_hostname))
                rows = cur.fetchall()
                other_hosts = [r[0] for r in rows if r[0]]

                all_hosts = [current_hostname] + other_hosts
                if len(all_hosts) < self.MIN_HOSTS_THRESHOLD:
                    return result

                result["affected_hosts"] = all_hosts
                result["multi_host_detected"] = True

                common_parent = None
                lower_hosts = [h.lower() for h in all_hosts]

                # 1. Cek Common Upstream Parent langsung dari tabel topologi `device_dependencies`
                cur.execute("""
                    SELECT depends_on, dep_type, COUNT(DISTINCT LOWER(pc_name)) AS cnt
                    FROM device_dependencies
                    WHERE LOWER(pc_name) = ANY(%s)
                      AND COALESCE(status, 'ACTIVE') != 'ARCHIVED'
                    GROUP BY depends_on, dep_type
                    ORDER BY cnt DESC
                    LIMIT 1
                """, (lower_hosts,))
                dep_row = cur.fetchone()
                if dep_row and dep_row[0]:
                    common_parent = f"Upstream {dep_row[1] or 'DEPENDENCY'} '{dep_row[0]}' (terhubung ke {dep_row[2]} host terdampak)"

                # 2. Fallback: Cari common parent device jaringan di site yang sama dari `assets`
                if not common_parent:
                    cur.execute("""
                        SELECT a.site_id, COUNT(*) as cnt
                        FROM assets a
                        WHERE LOWER(a.hostname) = ANY(%s)
                        GROUP BY a.site_id
                        ORDER BY cnt DESC
                        LIMIT 1
                    """, (lower_hosts,))
                    site_row = cur.fetchone()

                    if site_row and site_row[0]:
                        site_id = site_row[0]
                        cur.execute("""
                            SELECT hostname, device_type FROM assets
                            WHERE site_id = %s
                              AND (
                                  LOWER(device_type) LIKE '%%switch%%'
                                  OR LOWER(device_type) LIKE '%%router%%'
                                  OR LOWER(device_type) LIKE '%%gateway%%'
                                  OR LOWER(device_type) LIKE '%%firewall%%'
                              )
                            LIMIT 1
                        """, (site_id,))
                        net_row = cur.fetchone()
                        common_parent = (
                            f"{net_row[1]} '{net_row[0]}' (Site ID: {site_id})"
                            if net_row else f"Infrastruktur bersama Site ID: {site_id}"
                        )
                    else:
                        common_parent = f"Infrastruktur bersama ({len(all_hosts)} host terdampak)"

                result["common_parent_hypothesis"] = common_parent
                result["confidence_boost"] = min(20.0, len(all_hosts) * 5.0)
                result["summary"] = (
                    f"MULTI-HOST ALERT: {len(all_hosts)} host error dalam {self.WINDOW_MINUTES} menit: "
                    f"{', '.join(all_hosts[:5])}. "
                    f"Common parent: {common_parent}. "
                    f"Confidence boost: +{result['confidence_boost']:.0f}%."
                )
                logger.warning(f"[MULTI-HOST] {len(all_hosts)} hosts affected. Parent: {common_parent}")

        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            logger.error(f"[MULTI-HOST] Gagal analisis: {e}")
        finally:
            if owns_conn and conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

        return result


_multi_host_instance: Optional[MultiHostCorrelator] = None


def get_multi_host_correlator(db_conn=None) -> MultiHostCorrelator:
    global _multi_host_instance
    if _multi_host_instance is None:
        _multi_host_instance = MultiHostCorrelator(db_conn=db_conn)
    elif db_conn and _multi_host_instance.conn != db_conn:
        _multi_host_instance.conn = db_conn
    return _multi_host_instance
