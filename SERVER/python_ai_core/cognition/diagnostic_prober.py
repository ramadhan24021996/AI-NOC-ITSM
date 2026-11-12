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
    Topological Alert Suppression, Multi-Hop Upstream Correlation & Flapping Gate.
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
        Checks at the ingest gate BEFORE creating a new incident row or running LLM triage:
          1. Direct or 2-Hop Upstream Parent Outage (`device_dependencies`):
             Does an upstream switch/gateway/core service (`depends_on`) already have an active incident?
             If so, binds this downstream host as a child symptom on the parent incident and suppresses
             duplicate child ticket creation (`should_suppress_pipeline = True`).
          2. Implicit Common-Parent Sibling Storm Deduction:
             If `device_name` depends on parent `P` (which hasn't reported its own ticket yet, e.g. unmanaged
             switch), and >= 1 sibling device sharing parent `P` already has an active incident within
             `UPSTREAM_WINDOW_MINUTES`, correlates into that root incident as a common-parent storm and
             suppresses downstream child ticket creation (`should_suppress_pipeline = True`).
          3. Same-Host Cross-Layer Flapping Episode:
             Does `device_name` already have an active (non-RESOLVED/CLOSED) incident within
             `EPISODE_WINDOW_MINUTES`? If so, appends the flapping symptom to the existing incident's
             evidence and suppresses redundant pipeline re-execution (`should_suppress_pipeline = True`).

        Returns:
            {
                "existing_incident_id": Optional[int],
                "is_duplicate_episode": bool,
                "is_upstream_storm_suppressed": bool,
                "should_suppress_pipeline": bool,
                "suppression_reason": Optional[str],
                "upstream_root_incident": Optional[Dict[str, Any]],
                "suppression_note": Optional[str],
            }
        """
        result: Dict[str, Any] = {
            "existing_incident_id": None,
            "is_duplicate_episode": False,
            "is_upstream_storm_suppressed": False,
            "should_suppress_pipeline": False,
            "suppression_reason": None,
            "upstream_root_incident": None,
            "suppression_note": None,
        }
        if not self.conn or not device_name:
            return result

        try:
            with self.conn.cursor() as cur:
                # 1. Check direct (1-hop) or 2-hop upstream parent outage in device_dependencies
                cur.execute(
                    """
                    SELECT parent_dev, dep_type, incident_id, flag, evidence
                    FROM (
                        -- 1-hop direct parent
                        SELECT dd1.depends_on AS parent_dev,
                               dd1.dep_type AS dep_type,
                               i.incident_id,
                               i.flag,
                               i.evidence,
                               1 AS hop_distance
                        FROM device_dependencies dd1
                        JOIN incidents i ON i.device_name = dd1.depends_on
                        WHERE dd1.pc_name = %s
                          AND COALESCE(dd1.status, 'ACTIVE') != 'ARCHIVED'
                          AND COALESCE(i.flag, 'OPEN') NOT IN ('RESOLVED', 'CLOSED')
                          AND i."timestamp" >= (NOW() - INTERVAL '%s minutes')
                        UNION ALL
                        -- 2-hop grandparent (e.g. PC -> Access Switch -> Core Gateway)
                        SELECT dd2.depends_on AS parent_dev,
                               dd2.dep_type AS dep_type,
                               i.incident_id,
                               i.flag,
                               i.evidence,
                               2 AS hop_distance
                        FROM device_dependencies dd1
                        JOIN device_dependencies dd2 ON dd2.pc_name = dd1.depends_on
                        JOIN incidents i ON i.device_name = dd2.depends_on
                        WHERE dd1.pc_name = %s
                          AND COALESCE(dd1.status, 'ACTIVE') != 'ARCHIVED'
                          AND COALESCE(dd2.status, 'ACTIVE') != 'ARCHIVED'
                          AND COALESCE(i.flag, 'OPEN') NOT IN ('RESOLVED', 'CLOSED')
                          AND i."timestamp" >= (NOW() - INTERVAL '%s minutes')
                    ) up_matches
                    ORDER BY hop_distance ASC, incident_id DESC
                    LIMIT 1
                    """,
                    (
                        device_name,
                        self.UPSTREAM_WINDOW_MINUTES,
                        device_name,
                        self.UPSTREAM_WINDOW_MINUTES,
                    ),
                )
                up_row = cur.fetchone()
                if up_row:
                    parent_dev, dep_type, parent_inc_id, parent_flag, parent_ev = up_row
                    parent_inc_id = int(parent_inc_id)
                    result["existing_incident_id"] = parent_inc_id
                    result["is_upstream_storm_suppressed"] = True
                    result["should_suppress_pipeline"] = True
                    result["suppression_reason"] = "UPSTREAM_PARENT_OUTAGE"
                    result["upstream_root_incident"] = {
                        "parent_device": parent_dev,
                        "dep_type": dep_type or "UPSTREAM_DEPENDENCY",
                        "parent_incident_id": parent_inc_id,
                        "parent_state": parent_flag,
                        "parent_evidence": str(parent_ev or "")[:160],
                    }
                    child_tag = f"[CHILD_SYMPTOM:{device_name}]"
                    if child_tag not in str(parent_ev or ""):
                        cur.execute(
                            """
                            UPDATE incidents
                            SET evidence = LEFT(COALESCE(evidence, '') || ' | ' || %s, 1000)
                            WHERE incident_id = %s
                            """,
                            (f"{child_tag} {(symptoms or '')[:80]}".strip(), parent_inc_id),
                        )
                        self.conn.commit()
                    result["suppression_note"] = (
                        f"[TOPOLOGICAL CORRELATION]: Upstream parent '{parent_dev}' ({dep_type}) "
                        f"has active Incident #{parent_inc_id} ({parent_flag}). "
                        f"Downstream alert on '{device_name}' bound as child symptom and suppressed."
                    )
                    return result

                # 2. Implicit Common-Parent Sibling Storm Deduction:
                # Check if another sibling device sharing the same upstream parent in device_dependencies
                # already has an active incident within UPSTREAM_WINDOW_MINUTES (e.g. switch died and 20 PCs report).
                cur.execute(
                    """
                    SELECT dd_self.depends_on AS common_parent,
                           dd_self.dep_type,
                           i_sib.device_name AS sibling_device,
                           i_sib.incident_id AS root_incident_id,
                           i_sib.flag,
                           i_sib.evidence
                    FROM device_dependencies dd_self
                    JOIN device_dependencies dd_sib
                      ON dd_sib.depends_on = dd_self.depends_on
                     AND dd_sib.pc_name != dd_self.pc_name
                    JOIN incidents i_sib
                      ON i_sib.device_name = dd_sib.pc_name
                    WHERE dd_self.pc_name = %s
                      AND COALESCE(dd_self.status, 'ACTIVE') != 'ARCHIVED'
                      AND COALESCE(dd_sib.status, 'ACTIVE') != 'ARCHIVED'
                      AND COALESCE(i_sib.flag, 'OPEN') NOT IN ('RESOLVED', 'CLOSED')
                      AND i_sib."timestamp" >= (NOW() - INTERVAL '%s minutes')
                    ORDER BY i_sib.incident_id ASC
                    LIMIT 1
                    """,
                    (device_name, self.UPSTREAM_WINDOW_MINUTES),
                )
                sib_row = cur.fetchone()
                if sib_row:
                    common_parent, dep_type, sibling_dev, root_inc_id, root_flag, root_ev = sib_row
                    root_inc_id = int(root_inc_id)
                    result["existing_incident_id"] = root_inc_id
                    result["is_upstream_storm_suppressed"] = True
                    result["should_suppress_pipeline"] = True
                    result["suppression_reason"] = "COMMON_PARENT_SIBLING_STORM"
                    result["upstream_root_incident"] = {
                        "parent_device": common_parent,
                        "dep_type": dep_type or "COMMON_UPSTREAM_INFRA",
                        "parent_incident_id": root_inc_id,
                        "leader_sibling_device": sibling_dev,
                        "parent_state": root_flag,
                        "parent_evidence": str(root_ev or "")[:160],
                    }
                    child_tag = f"[STORM_CHILD:{device_name}@via:{common_parent}]"
                    if child_tag not in str(root_ev or ""):
                        cur.execute(
                            """
                            UPDATE incidents
                            SET evidence = LEFT(COALESCE(evidence, '') || ' | ' || %s, 1000)
                            WHERE incident_id = %s
                            """,
                            (child_tag, root_inc_id),
                        )
                        self.conn.commit()
                    result["suppression_note"] = (
                        f"[STORM SUPPRESSION]: '{device_name}' and sibling '{sibling_dev}' share upstream "
                        f"parent '{common_parent}' ({dep_type}). Correlated into Root Incident #{root_inc_id}."
                    )
                    return result

                # 3. Check same-host active flapping episode within EPISODE_WINDOW_MINUTES
                cur.execute(
                    """
                    SELECT incident_id, flag, evidence
                    FROM incidents
                    WHERE device_name = %s
                      AND COALESCE(flag, 'OPEN') NOT IN ('RESOLVED', 'CLOSED')
                      AND "timestamp" >= (NOW() - INTERVAL '%s minutes')
                    ORDER BY incident_id DESC
                    LIMIT 1
                    """,
                    (device_name, self.EPISODE_WINDOW_MINUTES),
                )
                row = cur.fetchone()
                if row:
                    inc_id, flag_val, old_ev = row
                    inc_id = int(inc_id)
                    result["existing_incident_id"] = inc_id
                    result["is_duplicate_episode"] = True
                    result["should_suppress_pipeline"] = True
                    result["suppression_reason"] = "SAME_HOST_FLAPPING_COOLDOWN"
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
                        SELECT status,
                               COALESCE(NULLIF(ip, ''), hardware_info->>'ip', 'UNKNOWN') AS ip_addr,
                               EXTRACT(EPOCH FROM (NOW() - last_seen))::int AS age_sec
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

        # 3. Active Probing Catalog & Sandbox Read-Only Verification (active_probing package integration)
        catalog_probe_results: List[Dict[str, Any]] = []
        try:
            try:
                from active_probing import ProbeCatalog, ActiveProbeExecutor, RiskLevel
            except ImportError:
                from SERVER.python_ai_core.active_probing import ProbeCatalog, ActiveProbeExecutor, RiskLevel
            catalog = ProbeCatalog()
            executor = ActiveProbeExecutor()
            simulated_failures = [str(a.get("metric", "")).lower() for a in anomalies]
            target_ctx = {
                "target_ip": ip_addr if ip_addr != "UNKNOWN" else "127.0.0.1",
                "device_id": hostname or "UNKNOWN",
                "simulated_failures": simulated_failures,
            }
            for probe in list(catalog.probes.values()):
                if probe.read_only and probe.risk_level == RiskLevel.LEVEL_1_READ_ONLY:
                    p_res = executor.execute_probe(probe, target_ctx)
                    catalog_probe_results.append({
                        "probe_id": p_res.probe_id,
                        "name": p_res.probe_name,
                        "osi_layer": p_res.osi_layer,
                        "status": p_res.status,
                        "confidence": p_res.confidence,
                    })
                    if len(catalog_probe_results) >= 4:
                        break
        except Exception as ap_err:
            logger.debug(f"[DIAGNOSTIC_PROBER] Active probing catalog note: {ap_err}")

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
            "catalog_probes": catalog_probe_results,
            "prompt_block": prompt_block,
        }
