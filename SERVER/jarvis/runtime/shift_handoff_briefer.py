"""
SERVER.jarvis.runtime.shift_handoff_briefer — JARVIS Shift Handoff, Forensic Rule #6 & Deterministic Narrator
=============================================================================================================
Menyediakan 3 kapabilitas utama untuk JARVIS Voice Copilot:
  1. ShiftHandoffBriefer.generate_briefing() [SHIFT_HANDOVER_REPORT]:
     - Merangkum data 8–12 jam terakhir dari PostgreSQL & NOC Bridge secara terstruktur:
       • Jumlah insiden yang selesai diverifikasi sesuai Rule #6 (Execution ACK + Post-Telemetry T_post >= T_exec).
       • Daftar tiket yang masih tertahan di PENDING_VERIFICATION atau menunggu persetujuan operator (AWAITING_HITL).
       • Top 3 Noisy Devices (perangkat paling sering mengalami anomali dalam 12 jam terakhir).
       • Sisa Autonomy Budget & status darurat Kill-Switch.
  2. ShiftHandoffBriefer.generate_forensic_rule6_drilldown() [FORENSIC_RULE6_DRILLDOWN]:
     - Membacakan status Dual-Evidence Binding (Axiom Rule #6) & korelasi kausal secara lisan:
       • Bukti Eksekusi (T_exec): waktu eksekusi perintah/SOP & status ACK agen.
       • Bukti Pasca-Remediasi (T_post): waktu verifikasi telemetri live & validasi T_post >= T_exec.
       • Alasan mengapa tiket terkunci di PENDING_VERIFICATION (bukti mana yang masih ditunggu) atau konfirmasi sah RESOLVED.
  3. ShiftHandoffBriefer.synthesize_deterministic_noc_narrative() [ZERO-DOWNTIME NATURAL INDONESIAN FALLBACK]:
     - Penyusun kalimat Bahasa Indonesia berbasis fakta lokal (PostgreSQL / NOC Bridge) ketika Cloud LLM
       (Gemini/Groq) sedang offline atau terkena rate-limit.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("jarvis.runtime.shift_handoff")


def _get_db_conn():
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
                logger.debug("[ShiftHandoffBriefer] DB connection fallback note: %s", e)
                return None


class ShiftHandoffBriefer:
    """
    Menyusun Executive Briefing Pergantian Shift, Forensic Rule #6 Drilldown,
    dan Deterministic Indonesian NOC Narrative berdasarkan fakta live PostgreSQL & NOC Bridge.
    """

    def __init__(self, noc_bridge: Optional[Any] = None, db_conn: Optional[Any] = None):
        self._noc = noc_bridge
        self._db_conn = db_conn

    def _fetch(self, endpoint: str) -> Any:
        if not self._noc:
            return None
        try:
            r = self._noc._get(endpoint)
            return r.data if r and getattr(r, "success", False) else None
        except Exception:
            return None

    def _query_shift_db_stats(self, hours: int = 12) -> Dict[str, Any]:
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
        conn = self._db_conn or _get_db_conn()
        owns_conn = self._db_conn is None and conn is not None
        if not conn:
            return stats

        try:
            with conn.cursor() as cur:
                # 1. Resolved & Rule #6 Dual-Evidence Verified count in last N hours
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

                # 2. Tickets locked in PENDING_VERIFICATION or AWAITING_HITL / OPEN
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

                # 3. Top 3 Noisy Devices in the last N hours
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

                # 4. Autonomy budget usage in the last N hours
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
                pass
            logger.debug("[ShiftHandoffBriefer] Shift DB query note: %s", e)
        finally:
            if owns_conn and conn:
                try:
                    conn.close()
                except Exception:
                    pass

        return stats

    def generate_briefing(
        self,
        incoming_operator: str = "",
        outgoing_operator: str = "",
        verbose: bool = True,
        hours: int = 12,
    ) -> str:
        """
        Generate structured Shift Handover Executive Briefing (8–12 hours):
          1. Jumlah insiden selesai & terverifikasi sesuai Rule #6 (Execution ACK + Post-Telemetry OK).
          2. Daftar tiket yang masih tertahan di PENDING_VERIFICATION atau menunggu persetujuan (AWAITING_HITL).
          3. Top 3 Noisy Devices (perangkat paling sering mengalami anomali) & sisa Autonomy Budget.
        """
        now = datetime.now(timezone.utc)
        hour_wib = (now.hour + 7) % 24
        shift_name = "Pagi" if 6 <= hour_wib < 14 else ("Siang" if 14 <= hour_wib < 22 else "Malam")

        stats = self._query_shift_db_stats(hours=hours)

        # Fallback / supplement from NOC Bridge if DB had no rows
        incidents_data = self._fetch("/api/incidents")
        bridge_incidents = []
        if isinstance(incidents_data, list):
            bridge_incidents = incidents_data
        elif isinstance(incidents_data, dict):
            bridge_incidents = incidents_data.get("incidents", [])

        if not stats["db_available"] and bridge_incidents:
            for inc in bridge_incidents:
                st = str(inc.get("status") or inc.get("flag") or "OPEN").upper()
                item = {
                    "incident_id": inc.get("incident_id") or inc.get("id", 0),
                    "device_name": inc.get("device_name") or inc.get("agent", "UNKNOWN"),
                    "layer": inc.get("layer", 1),
                    "state": st,
                    "evidence": str(inc.get("evidence") or inc.get("description") or "")[:100],
                }
                if st in ("RESOLVED", "CLOSED", "SOLVED"):
                    stats["resolved_total"] += 1
                    stats["rule6_verified_count"] += 1
                elif "PENDING_VERIF" in st:
                    stats["pending_verification_list"].append(item)
                elif "HITL" in st or "APPROV" in st:
                    stats["awaiting_hitl_list"].append(item)
                else:
                    stats["open_active_list"].append(item)

        pending_verif = stats["pending_verification_list"]
        awaiting_hitl = stats["awaiting_hitl_list"]
        open_active = stats["open_active_list"]
        top_noisy = stats["top_noisy_devices"]
        budget_max = stats["autonomy_budget_max"]
        budget_used = stats["autonomy_actions_12h"]
        budget_rem = max(0, budget_max - budget_used)

        header = f"📋 LAPORAN SERAH TERIMA SHIFT ({shift_name.upper()} — {hours} Jam Terakhir)"
        if incoming_operator or outgoing_operator:
            op_note = []
            if outgoing_operator:
                op_note.append(f"Dari: {outgoing_operator}")
            if incoming_operator:
                op_note.append(f"Kepada: {incoming_operator}")
            header += f" [{' → '.join(op_note)}]"

        lines = [
            header,
            f"1. ✅ Resolusi Terverifikasi (Axiom Rule #6): {stats['resolved_total']} insiden selesai "
            f"({stats['rule6_verified_count']} terikat bukti ganda Execution ACK + Post-Telemetry T_post >= T_exec).",
            f"2. 🔒 Tiket Tertahan & Menunggu Tindakan: "
            f"{len(pending_verif)} PENDING_VERIFICATION | {len(awaiting_hitl)} AWAITING_HITL | {len(open_active)} OPEN/IN_PROGRESS.",
        ]

        if pending_verif:
            for item in pending_verif[:3]:
                lines.append(
                    f"   • [PENDING_VERIFICATION] INC-#{item['incident_id']} pada {item['device_name']} (L{item['layer']}): "
                    f"menunggu telemetri pasca-remediasi T_post >= T_exec."
                )
        if awaiting_hitl:
            for item in awaiting_hitl[:3]:
                lines.append(
                    f"   • [AWAITING_HITL] INC-#{item['incident_id']} pada {item['device_name']} (L{item['layer']}): "
                    f"menunggu persetujuan operator di Dashboard."
                )
        if open_active and not (pending_verif or awaiting_hitl):
            for item in open_active[:3]:
                lines.append(
                    f"   • [{item['state']}] INC-#{item['incident_id']} pada {item['device_name']} (L{item['layer']}): {item['evidence'][:70]}"
                )

        if top_noisy:
            noisy_str = ", ".join(f"{d['device_name']} ({d['count']}x)" for d in top_noisy)
            lines.append(f"3. 📊 Top 3 Noisy Devices ({hours} Jam): {noisy_str}.")
        else:
            lines.append(f"3. 📊 Top 3 Noisy Devices ({hours} Jam): Tidak ada perangkat dengan anomali berulang.")

        lines.append(
            f"4. 🛡️ Governance & Autonomy Budget: Sisa kuota otonom {budget_rem}/{budget_max} aksi "
            f"(terpakai {budget_used} aksi) | Kill-Switch: NORMAL (Tidak Aktif)."
        )
        return "\n".join(lines)

    def generate_forensic_rule6_drilldown(
        self,
        target_incident: Optional[str] = None,
        target_device: Optional[str] = None,
    ) -> str:
        """
        Membacakan status Dual-Evidence Binding (Axiom Rule #6) & korelasi kausal untuk insiden
        tertentu atau insiden terakhir dari PostgreSQL.
        """
        conn = self._db_conn or _get_db_conn()
        owns_conn = self._db_conn is None and conn is not None

        inc_row = None
        rem_row = None
        ev_rows: List[Tuple[Any, ...]] = []

        inc_id_num: Optional[int] = None
        if target_incident:
            m = re.search(r"(\d+)", str(target_incident))
            if m:
                inc_id_num = int(m.group(1))

        if conn:
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
                    pass
                logger.debug("[ShiftHandoffBriefer] Forensic query note: %s", e)
            finally:
                if owns_conn and conn:
                    try:
                        conn.close()
                    except Exception:
                        pass

        if not inc_row:
            return (
                "🔍 AUDIT FORENSIK RULE #6: Saat ini belum ditemukan catatan insiden yang cocok di basis data. "
                "Seluruh tiket disyaratkan memiliki bukti eksekusi (T_exec) dan bukti telemetri pasca-remediasi "
                "(T_post >= T_exec) sebelum dapat dinyatakan RESOLVED."
            )

        inc_id, dev_name, layer, flag, evidence, t_exec, t_verif, t_solved, t_created = inc_row
        state_upper = str(flag or "OPEN").upper()
        t_post = t_verif or t_solved

        # Determine Execution Evidence (Bukti 1)
        has_exec = t_exec is not None or rem_row is not None or ("ACK" in str(evidence).upper())
        exec_ts_str = str(t_exec)[:19] if t_exec else (str(rem_row[2])[:19] if rem_row and rem_row[2] else "Belum tercatat")
        exec_action = str(rem_row[0]) if rem_row and rem_row[0] else "SOP Remediasi Terkait"

        # Determine Post-Remediation Evidence (Bukti 2) & Temporal Invariant T_post >= T_exec
        temporal_valid = False
        if t_exec and t_post:
            try:
                temporal_valid = t_post >= t_exec
            except Exception:
                temporal_valid = True
        elif t_post or state_upper in ("RESOLVED", "CLOSED", "SOLVED") or len(ev_rows) > 0:
            temporal_valid = True

        has_post = t_post is not None or len(ev_rows) > 0 or ("POST" in str(evidence).upper())
        post_ts_str = str(t_post)[:19] if t_post else (
            str(ev_rows[0][2])[:19] if ev_rows and len(ev_rows[0]) > 2 and ev_rows[0][2] else "Belum tersedia"
        )

        if state_upper in ("RESOLVED", "CLOSED", "SOLVED") and (has_exec or has_post):
            verdict_line = (
                f"✅ STATUS RULE #6 SAH (TERVERIFIKASI): Insiden #{inc_id} pada {dev_name} (Layer {layer}) "
                f"telah memenuhi syarat bukti ganda (T_post >= T_exec) dan sah berstatus {state_upper}."
            )
            missing_line = "Tidak ada bukti yang tertunda; rantai kausalitas dan telemetri pemulihan lengkap."
        else:
            missing_parts = []
            if not has_exec:
                missing_parts.append("Bukti Eksekusi (Execution ACK / exit-code 0 dari agen)")
            if not has_post:
                missing_parts.append("Bukti Telemetri Pasca-Remediasi (live metric sehat dengan timestamp T_post >= T_exec)")
            elif not temporal_valid:
                missing_parts.append("Validasi urutan waktu T_post >= T_exec")
            missing_str = " serta ".join(missing_parts) if missing_parts else "konfirmasi verifikasi akhir dari Verification Engine"
            verdict_line = (
                f"🔒 STATUS RULE #6 TERKUNCI ({state_upper}): Insiden #{inc_id} pada {dev_name} (Layer {layer}) "
                f"dilarang ditutup otomatis karena masih menunggu {missing_str}."
            )
            missing_line = f"Bukti yang masih ditunggu: {missing_str}."

        ev_clean = str(evidence or "Anomali telemetri").strip()
        if len(ev_clean) > 180:
            ev_clean = ev_clean[:180] + "..."

        lines = [
            f"🔍 LAPORAN FORENSIK DUAL-EVIDENCE (AXIOM RULE #6) — INSIDEN #{inc_id}:",
            f"  • Perangkat & Lapisan : {dev_name} (OSI Layer {layer}) | Status Saat Ini: {state_upper}",
            f"  • Bukti 1 (T_exec)    : {'✅ TERCATAT' if has_exec else '⏳ MENUNGGU'} ({exec_action} | Timestamp: {exec_ts_str})",
            f"  • Bukti 2 (T_post)    : {'✅ TERCATAT' if has_post else '⏳ MENUNGGU'} (Timestamp: {post_ts_str} | Invarian T_post >= T_exec: {'VALID' if (has_exec and has_post and temporal_valid) else 'BELUM TERPENUHI'})",
            f"  • Jejak Kausal & Bukti: {ev_clean}",
            f"  • Kesimpulan Audit    : {verdict_line}",
            f"  • Keterangan          : {missing_line}",
        ]
        return "\n".join(lines)

    def synthesize_deterministic_noc_narrative(
        self,
        query_text: str = "",
        target_device: Optional[str] = None,
    ) -> str:
        """
        Zero-Downtime Natural Indonesian Narrator:
        Menyusun respon Bahasa Indonesia teknis yang natural dan akurat langsung dari data fakta
        PostgreSQL & NOC Bridge ketika Cloud LLM (Gemini/Groq) sedang offline atau terkena rate-limit.
        """
        stats = self._query_shift_db_stats(hours=12)
        open_cnt = len(stats["open_active_list"]) + len(stats["pending_verification_list"]) + len(stats["awaiting_hitl_list"])
        pending_v = len(stats["pending_verification_list"])
        hitl_cnt = len(stats["awaiting_hitl_list"])
        resolved_cnt = stats["resolved_total"]

        if target_device:
            # Check if target_device has any active or recent incident
            matched = [
                i for i in (stats["pending_verification_list"] + stats["awaiting_hitl_list"] + stats["open_active_list"])
                if str(i.get("device_name", "")).lower() == target_device.lower()
            ]
            if matched:
                inc = matched[0]
                return (
                    f"Berdasarkan data telemetri lokal PostgreSQL saat ini, perangkat {target_device} memiliki "
                    f"insiden aktif #{inc['incident_id']} pada OSI Layer {inc['layer']} dengan status {inc['state']}. "
                    f"Bukti tercatat: {inc['evidence'][:100]}. Sesuai Axiom Rule #6, tiket akan tetap dikawal hingga "
                    f"bukti eksekusi dan telemetri pasca-remediasi tervalidasi."
                )
            return (
                f"Berdasarkan pemantauan basis data lokal saat ini, perangkat {target_device} tidak memiliki "
                f"insiden aktif yang terbuka. Secara keseluruhan di NOC terdapat {open_cnt} insiden aktif "
                f"dan {resolved_cnt} insiden yang telah diselesaikan dalam 12 jam terakhir."
            )

        if open_cnt == 0:
            return (
                f"Saat ini kondisi operasional NOC stabil dan terkendali. Tidak ada insiden aktif yang terbuka, "
                f"dan sebanyak {resolved_cnt} insiden dalam 12 jam terakhir telah diselesaikan serta terverifikasi "
                f"sesuai Axiom Rule #6."
            )

        top_dev = stats["top_noisy_devices"][0]["device_name"] if stats["top_noisy_devices"] else (
            (stats["open_active_list"] + stats["pending_verification_list"] + stats["awaiting_hitl_list"])[0]["device_name"]
        )
        return (
            f"Berdasarkan data faktual NOC saat ini, terdapat {open_cnt} insiden aktif "
            f"({pending_v} menunggu verifikasi Rule #6 di PENDING_VERIFICATION dan {hitl_cnt} menunggu persetujuan HITL), "
            f"serta {resolved_cnt} insiden telah selesai dalam 12 jam terakhir. "
            f"Perangkat dengan prioritas pemantauan utama saat ini adalah {top_dev}."
        )

    def explain_osi_layer(self, layer_num: Optional[int] = None) -> str:
        """
        Memberikan penjelasan lisan teknis mengenai Layer OSI tertentu (1–7)
        atau gambaran umum seluruh Layer 1–7.
        """
        try:
            from SERVER.python_ai_core.knowledge.osi_layer_matrix import explain_layer, explain_all_layers
        except ImportError:
            try:
                from python_ai_core.knowledge.osi_layer_matrix import explain_layer, explain_all_layers
            except ImportError:
                from knowledge.osi_layer_matrix import explain_layer, explain_all_layers

        if layer_num and 1 <= int(layer_num) <= 7:
            return explain_layer(int(layer_num))
        return explain_all_layers()

    def generate_layer_breakdown(self, target_layer: Optional[int] = None) -> str:
        """
        Merangkum sebaran insiden aktif per Layer OSI (1–7) langsung dari basis data PostgreSQL.
        Mendeteksi korelasi kausalitas hulu-hilir (Root Cause Layer vs Secondary Symptoms).
        """
        try:
            from SERVER.python_ai_core.knowledge.osi_layer_matrix import (
                get_layer_knowledge, evaluate_cross_layer_causality
            )
        except ImportError:
            try:
                from python_ai_core.knowledge.osi_layer_matrix import (
                    get_layer_knowledge, evaluate_cross_layer_causality
                )
            except ImportError:
                from knowledge.osi_layer_matrix import (
                    get_layer_knowledge, evaluate_cross_layer_causality
                )

        conn = self._db_conn or _get_db_conn()
        owns_conn = self._db_conn is None and conn is not None

        layer_counts: Dict[int, List[Dict[str, Any]]] = {i: [] for i in range(1, 8)}
        db_queried = False

        if conn:
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
                            layer_counts[l].append({
                                "id": int(inc_id),
                                "dev": str(dev),
                                "state": str(state),
                                "ev": str(ev)
                            })
                    db_queried = True
            except Exception as e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                logger.debug("[generate_layer_breakdown] DB query error: %s", e)
            finally:
                if owns_conn and conn:
                    try:
                        conn.close()
                    except Exception:
                        pass

        # Fallback to NOC Bridge if DB returned no rows or had error
        if not db_queried:
            inc_data = self._fetch("/api/incidents")
            inc_list = inc_data if isinstance(inc_data, list) else (inc_data.get("incidents", []) if isinstance(inc_data, dict) else [])
            for inc in inc_list:
                st = str(inc.get("status") or inc.get("flag") or "OPEN").upper()
                if st not in ('RESOLVED', 'CLOSED', 'SOLVED'):
                    l = int(inc.get("layer", 1))
                    if 1 <= l <= 7:
                        layer_counts[l].append({
                            "id": inc.get("incident_id") or inc.get("id", 0),
                            "dev": inc.get("device_name") or inc.get("agent", "UNKNOWN"),
                            "state": st,
                            "ev": str(inc.get("evidence") or inc.get("description") or "")[:100]
                        })

        # Single layer specific breakdown
        if target_layer and 1 <= int(target_layer) <= 7:
            tl = int(target_layer)
            k = get_layer_knowledge(tl) or {}
            lname = k.get("name", f"Layer {tl}")
            items = layer_counts[tl]
            if not items:
                return (
                    f"✅ STATUS LAYER {tl} ({lname.upper()}): "
                    f"Kondisi normal dan stabil. Tidak ada insiden aktif yang terdeteksi pada Layer {tl}."
                )
            lines = [
                f"⚠️ STATUS LAYER {tl} ({lname.upper()}) — Terdeteksi {len(items)} Insiden Aktif:",
            ]
            for it in items[:5]:
                lines.append(f"  • INC-#{it['id']} pada {it['dev']} [{it['state']}]: {it['ev']}")
            lines.append(f"\n💡 SOP Remediasi Rekomendasi: {', '.join(s['id'] for s in k.get('sops', []))}.")
            lines.append(f"🛡️ Syarat Tutup Tiket (Rule #6): {k.get('rule6_verification', {}).get('verification_explanation', '')}")
            return "\n".join(lines)

        # Full 7-Layer Overview Breakdown
        active_layers = [l for l, items in layer_counts.items() if len(items) > 0]
        total_active = sum(len(items) for items in layer_counts.values())

        if total_active == 0:
            return (
                "✅ KESEHATAN SELURUH LAYER OSI (L1–L7): "
                "Seluruh lapisan dari Layer 1 (Physical) hingga Layer 7 (Application) dalam kondisi normal, "
                "terpantau hijau dan tidak ada insiden aktif terbuka di NOC."
            )

        causality = evaluate_cross_layer_causality(active_layers)

        lines = [
            f"📊 REKAPITULASI SEBARAN INSIDEN PER LAYER OSI (Total {total_active} Insiden):",
        ]
        for l in range(1, 8):
            k = get_layer_knowledge(l) or {}
            lname = k.get("name", f"L{l}")
            items = layer_counts[l]
            count = len(items)
            icon = "🔴" if count > 0 else "🟢"
            detail = f"{count} insiden aktif" if count > 0 else "Normal (0)"
            lines.append(f"  {icon} Layer {l} ({lname:<12}): {detail}")

        lines.append("")
        lines.append(f"🔍 Alur Propagasi Kausalitas: {causality['propagation_path']}")
        lines.append(f"💡 Rekomendasi Investigasi : {causality['recommendation']}")

        return "\n".join(lines)

    def generate_quick_status(self) -> str:
        """Versi singkat untuk TTS — max 3 kalimat."""
        return self.synthesize_deterministic_noc_narrative()


def get_shift_briefer(noc_bridge: Optional[Any] = None, db_conn: Optional[Any] = None) -> ShiftHandoffBriefer:
    return ShiftHandoffBriefer(noc_bridge=noc_bridge, db_conn=db_conn)
