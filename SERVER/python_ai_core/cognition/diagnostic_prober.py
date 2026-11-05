"""
Enterprise Autonomous AI OS — Level 5 Sovereign AIOps
Active Read-Only Diagnostic Prober & Topological Episode Deduplicator
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Provides:
  1. EpisodeDeduplicator:
     - Prevents alert-storm ticket duplication by binding repeated telemetry anomalies
       on the same host (within an active 10-minute episode window) to the existing open incident.
     - Performs Topological Upstream Alert Correlation: checks `device_dependencies` to detect
       if an upstream parent device (e.g. Core Switch / Gateway / DB Host) already has an active outage.
  2. ActiveDiagnosticProber:
     - Runs 100% read-only pre-triage diagnostic probes (live telemetry snapshot, device heartbeat
       reachability, and optional fast NATS read-only RPC `agent.diagnostic.<host>`) BEFORE
       LLM hypothesis generation, turning passive symptom guessing into evidence-backed diagnosis.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

try:
    from cognition.temporal_reasoning_engine import evaluate_metric_severity
except ImportError:
    from SERVER.python_ai_core.cognition.temporal_reasoning_engine import evaluate_metric_severity

logger = logging.getLogger("DIAGNOSTIC_PROBER")


class EpisodeDeduplicator:
    """
    Topological Alert Suppression & Episode Deduplication Gate.
    """

    EPISODE_WINDOW_MINUTES = 10
    UPSTREAM_WINDOW_MINUTES = 15

    def __init__(self, db_conn=None):
        self.conn = db_conn

    def find_or_correlate_active_episode(
        self,
        device_name: str,
        symptoms: str = "",
    ) -> Dict[str, Any]:
        """
        Checks before creating a new incident row:
          1. Does `device_name` already have an active (non-RESOLVED/CLOSED) incident within EPISODE_WINDOW_MINUTES?
          2. Does an upstream dependency (`depends_on` in `device_dependencies`) have an active incident?

        Returns:
            {
                "existing_incident_id": Optional[int],
                "is_duplicate_episode": bool,
                "upstream_root_incident": Optional[Dict[str, Any]],
                "suppression_note": Optional[str],
            }
        """
        result: Dict[str, Any] = {
            "existing_incident_id": None,
            "is_duplicate_episode": False,
            "upstream_root_incident": None,
            "suppression_note": None,
        }
        if not self.conn or not device_name:
            return result

        try:
            with self.conn.cursor() as cur:
                # 1. Check same-host active episode within window
                cur.execute(
                    """
                    SELECT incident_id, flag, evidence
                    FROM incidents
                    WHERE device_name = %s
                      AND COALESCE(flag, 'OPEN') NOT IN ('RESOLVED', 'CLOSED')
                      AND created_at >= (NOW() - INTERVAL '%s minutes')
                    ORDER BY incident_id DESC
                    LIMIT 1
                    """,
                    (device_name, self.EPISODE_WINDOW_MINUTES),
                )
                row = cur.fetchone()
                if row:
                    inc_id, flag_val, old_ev = row
                    result["existing_incident_id"] = int(inc_id)
                    result["is_duplicate_episode"] = True
                    result["suppression_note"] = (
                        f"Episode deduplicated into active incident #{inc_id} (state={flag_val}) on {device_name}"
                    )
                    # Append new symptom snippet to evidence if informative
                    if symptoms and symptoms[:80] not in str(old_ev or ""):
                        cur.execute(
                            """
                            UPDATE incidents
                            SET evidence = LEFT(COALESCE(evidence, '') || ' | [CORRELATED]: ' || %s, 1000)
                            WHERE incident_id = %s
                            """,
                            (symptoms[:200], inc_id),
                        )
                        self.conn.commit()

                # 2. Check upstream parent outage in device_dependencies
                cur.execute(
                    """
                    SELECT dd.depends_on, dd.dep_type, i.incident_id, i.flag, i.evidence
                    FROM device_dependencies dd
                    JOIN incidents i ON i.device_name = dd.depends_on
                    WHERE dd.pc_name = %s
                      AND COALESCE(dd.status, 'ACTIVE') != 'ARCHIVED'
                      AND COALESCE(i.flag, 'OPEN') NOT IN ('RESOLVED', 'CLOSED')
                      AND i.created_at >= (NOW() - INTERVAL '%s minutes')
                    ORDER BY i.incident_id DESC
                    LIMIT 1
                    """,
                    (device_name, self.UPSTREAM_WINDOW_MINUTES),
                )
                up_row = cur.fetchone()
                if up_row:
                    parent_dev, dep_type, parent_inc_id, parent_flag, parent_ev = up_row
                    result["upstream_root_incident"] = {
                        "parent_device": parent_dev,
                        "dep_type": dep_type or "UPSTREAM_DEPENDENCY",
                        "parent_incident_id": int(parent_inc_id),
                        "parent_state": parent_flag,
                        "parent_evidence": str(parent_ev or "")[:160],
                    }
                    note = (
                        f"[TOPOLOGICAL CORRELATION]: Upstream parent '{parent_dev}' ({dep_type}) "
                        f"has active Incident #{parent_inc_id} ({parent_flag}). "
                        f"Downstream alert on '{device_name}' is likely a cascading effect."
                    )
                    result["suppression_note"] = (
                        f"{result['suppression_note']} | {note}" if result["suppression_note"] else note
                    )
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception:
                pass
            logger.debug(f"[EPISODE_DEDUP] Query note for {device_name}: {e}")

        return result


class ActiveDiagnosticProber:
    """
    Executes read-only diagnostic probes prior to hypothesis generation.
    Combines:
      1. Live device heartbeat & reachability state (`fleet_devices`)
      2. Latest per-metric telemetry snapshot with domain-aware severity (`telemetry_logs`)
      3. Optional fast NATS read-only agent diagnostic RPC (`agent.diagnostic.<hostname>`)
    """

    def __init__(self, db_conn=None, nc=None):
        self.conn = db_conn
        self.nc = nc

    async def run_pre_triage_probes(
        self,
        hostname: str,
        metadata: Optional[Dict[str, Any]] = None,
        rpc_timeout_sec: float = 1.2,
    ) -> Dict[str, Any]:
        facts: List[str] = []
        anomalies: List[Dict[str, Any]] = []
        host_status = "UNKNOWN"
        ip_addr = (metadata or {}).get("ip_address") or "UNKNOWN"

        # 1. Probe fleet_devices heartbeat & latest telemetry snapshot from DB
        if self.conn and hostname:
            try:
                with self.conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT status, ip_address, EXTRACT(EPOCH FROM (NOW() - last_seen))::int AS age_sec
                        FROM fleet_devices
                        WHERE pc_name = %s
                        LIMIT 1
                        """,
                        (hostname,),
                    )
                    dev_row = cur.fetchone()
                    if dev_row:
                        host_status = str(dev_row[0] or "UNKNOWN")
                        ip_addr = str(dev_row[1] or ip_addr)
                        age_sec = dev_row[2] if dev_row[2] is not None else -1
                        facts.append(
                            f"Host Heartbeat: status={host_status}, ip={ip_addr}, last_seen_age={age_sec}s"
                        )

                    # Latest metric value per metric_type in the last 15 minutes
                    cur.execute(
                        """
                        SELECT DISTINCT ON (metric_type)
                            metric_type, metric_value, "timestamp"
                        FROM telemetry_logs
                        WHERE device_name = %s
                          AND "timestamp" >= (NOW() - INTERVAL '15 minutes')
                        ORDER BY metric_type, "timestamp" DESC
                        LIMIT 10
                        """,
                        (hostname,),
                    )
                    for m_type, m_val, m_ts in cur.fetchall():
                        sev = evaluate_metric_severity(m_type or "", m_val)
                        ts_str = m_ts.strftime("%H:%M:%S") if hasattr(m_ts, "strftime") else str(m_ts)
                        facts.append(f"Metric Probe [{m_type}]: {m_val} (severity={sev} @ {ts_str})")
                        if sev in ("CRITICAL", "HIGH"):
                            anomalies.append({"metric": m_type, "value": m_val, "severity": sev})
            except Exception as db_err:
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                logger.debug(f"[DIAGNOSTIC_PROBER] DB probe note for {hostname}: {db_err}")

        # 2. Optional Fast Read-Only NATS Diagnostic RPC to Agent (`agent.diagnostic.<hostname>`)
        rpc_probe_data = None
        if self.nc and hostname and hostname not in ("UNKNOWN", "SYSTEM"):
            try:
                subject = f"agent.diagnostic.{hostname}"
                payload = json.dumps({"action": "READONLY_SNAPSHOT", "probes": ["top_processes", "net_health", "disk_free"]}).encode()
                resp = await asyncio.wait_for(self.nc.request(subject, payload), timeout=rpc_timeout_sec)
                rpc_probe_data = json.loads(resp.data.decode())
                if isinstance(rpc_probe_data, dict) and rpc_probe_data.get("summary"):
                    facts.append(f"Live Agent RPC Probe: {rpc_probe_data.get('summary')}")
            except Exception:
                # Non-blocking: many agents are passive telemetry emitters
                pass

        prompt_block = ""
        if facts:
            prompt_block = (
                "[ACTIVE DIAGNOSTIC PROBE FACTS (READ-ONLY VERIFIED)]:\n  - "
                + "\n  - ".join(facts)
            )

        return {
            "hostname": hostname,
            "host_status": host_status,
            "ip_address": ip_addr,
            "facts": facts,
            "anomalies_detected": anomalies,
            "rpc_probe": rpc_probe_data,
            "prompt_block": prompt_block,
        }
