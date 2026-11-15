"""
SERVER.python_ai_core.services.shift_forensic_db_helper
=======================================================
Service-layer PostgreSQL query adapter for JARVIS Shift Handover,
Forensic Rule #6 Drilldown, OSI Layer Breakdown, and Episodic Memory Sync.
Keeps SERVER/jarvis 100% compliant with ADR-005 (zero direct SQL/psycopg2 in presentation layer).
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("python_ai_core.services.shift_forensic_db_helper")


def get_db_conn():
    """Acquire a PostgreSQL connection via shared pool or psycopg2 fallback."""
    try:
        from shared.db_pool import get_db_connection
        return get_db_connection()
    except Exception:
        try:
            from SERVER.shared.db_pool import get_db_connection
            return get_db_connection()
        except Exception:
            try:
                import psycopg2
                host = os.getenv("DB_HOST", "postgres")
                port = int(os.getenv("DB_PORT", "5433" if host == "127.0.0.1" else "5432"))
                return psycopg2.connect(
                    host=host,
                    port=port,
                    database=os.getenv("DB_NAME", "osi_system"),
                    user=os.getenv("DB_USER", "postgres"),
                    password=os.getenv("DB_PASSWORD", ""),
                    connect_timeout=3,
                )
            except Exception as e:
                logger.debug("[ShiftForensicDBHelper] DB connection fallback note: %s", e)
                return None


def sync_episodic_record(db_conn: Optional[Any], table: str, payload: Dict[str, Any]) -> bool:
    """Sync episodic memory or voice feedback to PostgreSQL when db_conn is provided."""
    if db_conn is None:
        return False
    try:
        if hasattr(db_conn, "cursor"):
            with db_conn.cursor() as cur:
                if table == "episodic_memory":
                    cur.execute(
                        "INSERT INTO episodic_memory (incident_id, event_time, description, telemetry_snapshot) "
                        "VALUES (%s, CURRENT_TIMESTAMP, %s, %s)",
                        (
                            str(payload.get("incident_id") or payload.get("device_id") or "INC-VOICE"),
                            str(payload.get("description") or payload.get("last_action") or ""),
                            json.dumps(payload, ensure_ascii=False),
                        ),
                    )
                elif table == "feedback_history":
                    cur.execute(
                        "INSERT INTO feedback_history (incident_id, engineer_id, action, details) "
                        "VALUES (%s, %s, %s, %s)",
                        (
                            str(payload.get("incident_id") or "INC-VOICE"),
                            str(payload.get("operator_id") or "operator"),
                            str(payload.get("action") or "VOICE_FEEDBACK"),
                            json.dumps(payload, ensure_ascii=False),
                        ),
                    )
            if hasattr(db_conn, "commit"):
                db_conn.commit()
            return True
    except Exception as db_err:
        logger.debug("[ShiftForensicDBHelper] Optional DB sync skipped: %s", db_err)
    return False


def query_shift_db_stats(db_conn: Optional[Any] = None, hours: int = 12) -> Dict[str, Any]:
    """Query PostgreSQL for 12-hour shift handover metrics (Rule #6, Pending/HITL, Top 3 Noisy Devices)."""
    stats: Dict[str, Any] = {
        "db_available": False,
        "resolved_total": 0,
        "rule6_verified_count": 0,
        "pending_verification_list": [],
        "awaiting_hitl_list": [],
        "open_active_list": [],
        "top_noisy_devices": [],
        "autonomy_actions_12h": 0,
        "autonomy_budget_max": int(os.getenv("AUTONOMY_BUDGET_PER_SHIFT", "20")),
    }
    conn = db_conn or get_db_conn()
    owns_conn = db_conn is None and conn is not None
    if not conn:
        return stats

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE UPPER(COALESCE(flag, '')) IN ('RESOLVED', 'CLOSED', 'SOLVED')
                    ) AS resolved_total,
                    COUNT(*) FILTER (
                        WHERE UPPER(COALESCE(flag, '')) IN ('RESOLVED', 'CLOSED', 'SOLVED')
                          AND (
                              (execution_time IS NOT NULL AND verification_time IS NOT NULL AND verification_time >= execution_time)
                              OR COALESCE(evidence, '') ILIKE '%%POST%%'
                              OR COALESCE(evidence, '') ILIKE '%%VERIFIED%%'
                          )
                    ) AS rule6_verified
                FROM incidents
                WHERE "timestamp" >= NOW() - INTERVAL '%s hours'
                """,
                (hours,),
            )
            row = cur.fetchone()
            if row:
                stats["resolved_total"] = int(row[0] or 0)
                stats["rule6_verified_count"] = int(row[1] or 0)

            cur.execute(
                """
                SELECT incident_id,
                       COALESCE(device_name, 'UNKNOWN') AS dev,
                       COALESCE(layer, 1) AS osi_layer,
                       UPPER(COALESCE(flag, 'OPEN')) AS state,
                       LEFT(COALESCE(evidence, 'Anomali telemetri'), 120) AS ev
                FROM incidents
                WHERE UPPER(COALESCE(flag, 'OPEN')) NOT IN ('RESOLVED', 'CLOSED', 'SOLVED')
                  AND "timestamp" >= NOW() - INTERVAL '%s hours'
                ORDER BY incident_id DESC
                LIMIT 15
                """,
                (hours * 2,),
            )
            for inc_id, dev, layer, state, ev in cur.fetchall() or []:
                item = {
                    "incident_id": int(inc_id),
                    "device_name": str(dev),
                    "layer": int(layer or 1),
                    "state": str(state),
                    "evidence": str(ev or ""),
                }
                if "PENDING_VERIF" in state or "VERIFY" in state:
                    stats["pending_verification_list"].append(item)
                elif "HITL" in state or "APPROV" in state:
                    stats["awaiting_hitl_list"].append(item)
                else:
                    stats["open_active_list"].append(item)

            cur.execute(
                """
                SELECT device_name, COUNT(*) AS inc_count
                FROM incidents
                WHERE "timestamp" >= NOW() - INTERVAL '%s hours'
                  AND device_name IS NOT NULL
                  AND device_name != ''
                GROUP BY device_name
                ORDER BY inc_count DESC, device_name ASC
                LIMIT 3
                """,
                (hours,),
            )
            stats["top_noisy_devices"] = [
                {"device_name": str(r[0]), "count": int(r[1])}
                for r in (cur.fetchall() or [])
            ]

            cur.execute(
                """
                SELECT COUNT(*)
                FROM incidents
                WHERE "timestamp" >= NOW() - INTERVAL '%s hours'
                  AND execution_time IS NOT NULL
                """,
                (hours,),
            )
            exec_row = cur.fetchone()
            stats["autonomy_actions_12h"] = int(exec_row[0] or 0) if exec_row else 0
            stats["db_available"] = True
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            logger.debug("Suppressed rollback exception", exc_info=True)
        logger.debug("[ShiftForensicDBHelper] Shift DB query note: %s", e)
    finally:
        if owns_conn and conn:
            try:
                conn.close()
            except Exception:
                logger.debug("Suppressed close exception", exc_info=True)

    return stats


def query_forensic_incident_record(
    db_conn: Optional[Any] = None,
    inc_id_num: Optional[int] = None,
    target_device: Optional[str] = None,
) -> Tuple[Optional[Any], Optional[Any], List[Tuple[Any, ...]]]:
    """Fetch incident row, remediation log row, and evidence logs for Rule #6 drilldown."""
    conn = db_conn or get_db_conn()
    owns_conn = db_conn is None and conn is not None

    inc_row = None
    rem_row = None
    ev_rows: List[Tuple[Any, ...]] = []

    if not conn:
        return inc_row, rem_row, ev_rows

    try:
        with conn.cursor() as cur:
            if inc_id_num is not None:
                cur.execute(
                    """
                    SELECT incident_id, device_name, COALESCE(layer, 1), COALESCE(flag, 'OPEN'),
                           COALESCE(evidence, ''), execution_time, verification_time, solved_time, "timestamp"
                    FROM incidents
                    WHERE incident_id = %s
                    LIMIT 1
                    """,
                    (inc_id_num,),
                )
                inc_row = cur.fetchone()
            elif target_device:
                cur.execute(
                    """
                    SELECT incident_id, device_name, COALESCE(layer, 1), COALESCE(flag, 'OPEN'),
                           COALESCE(evidence, ''), execution_time, verification_time, solved_time, "timestamp"
                    FROM incidents
                    WHERE LOWER(device_name) = LOWER(%s)
                    ORDER BY incident_id DESC
                    LIMIT 1
                    """,
                    (target_device,),
                )
                inc_row = cur.fetchone()

            if inc_row is None:
                cur.execute(
                    """
                    SELECT incident_id, device_name, COALESCE(layer, 1), COALESCE(flag, 'OPEN'),
                           COALESCE(evidence, ''), execution_time, verification_time, solved_time, "timestamp"
                    FROM incidents
                    ORDER BY incident_id DESC
                    LIMIT 1
                    """
                )
                inc_row = cur.fetchone()

            if inc_row:
                found_id = int(inc_row[0])
                try:
                    cur.execute(
                        """
                        SELECT action_taken, status, executed_at
                        FROM remediation_logs
                        WHERE incident_id = %s
                        ORDER BY executed_at DESC NULLS LAST
                        LIMIT 1
                        """,
                        (found_id,),
                    )
                    rem_row = cur.fetchone()
                except Exception:
                    conn.rollback()

                try:
                    cur.execute(
                        """
                        SELECT evidence_type, metric_snapshot, created_at
                        FROM ai_evidence_logs
                        WHERE incident_id = %s
                        ORDER BY created_at DESC NULLS LAST
                        LIMIT 3
                        """,
                        (found_id,),
                    )
                    ev_rows = cur.fetchall() or []
                except Exception:
                    conn.rollback()
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            logger.debug("Suppressed rollback exception", exc_info=True)
        logger.debug("[ShiftForensicDBHelper] Forensic query note: %s", e)
    finally:
        if owns_conn and conn:
            try:
                conn.close()
            except Exception:
                logger.debug("Suppressed close exception", exc_info=True)

    return inc_row, rem_row, ev_rows


def query_active_incidents_by_layer(
    db_conn: Optional[Any] = None,
) -> Tuple[Dict[int, List[Dict[str, Any]]], bool]:
    """Query active incidents grouped by OSI Layer (1-7)."""
    conn = db_conn or get_db_conn()
    owns_conn = db_conn is None and conn is not None

    layer_counts: Dict[int, List[Dict[str, Any]]] = {i: [] for i in range(1, 8)}
    db_queried = False

    if not conn:
        return layer_counts, db_queried

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT incident_id,
                       COALESCE(device_name, 'UNKNOWN') AS dev,
                       COALESCE(layer, 1) AS osi_layer,
                       UPPER(COALESCE(flag, 'OPEN')) AS state,
                       LEFT(COALESCE(evidence, 'Anomali telemetri'), 100) AS ev
                FROM incidents
                WHERE UPPER(COALESCE(flag, 'OPEN')) NOT IN ('RESOLVED', 'CLOSED', 'SOLVED')
                ORDER BY incident_id DESC
                LIMIT 50
                """
            )
            rows = cur.fetchall() or []
            for inc_id, dev, l_num, state, ev in rows:
                l = int(l_num or 1)
                if 1 <= l <= 7:
                    layer_counts[l].append(
                        {
                            "id": int(inc_id),
                            "dev": str(dev),
                            "state": str(state),
                            "ev": str(ev),
                        }
                    )
            db_queried = True
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            logger.debug("Suppressed rollback exception", exc_info=True)
        logger.debug("[ShiftForensicDBHelper] Layer breakdown query error: %s", e)
    finally:
        if owns_conn and conn:
            try:
                conn.close()
            except Exception:
                logger.debug("Suppressed close exception", exc_info=True)

    return layer_counts, db_queried
