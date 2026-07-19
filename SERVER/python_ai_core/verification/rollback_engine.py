"""
OSI AI Ops — Rollback & State Recovery Engine (Hardened)
Sprint 1: Gap 1

Alur:
  1. StateMachine memanggil snapshot() SEBELUM eksekusi aksi apapun
  2. Jika verifikasi pasca-eksekusi gagal, trigger_rollback() dipanggil
  3. Snapshot pre-state disimpan ke rollback_snapshots (PostgreSQL)
  4. Rollback event dikirim ke NATS remediation.rollback
  5. rollback_logs diupdate untuk Trust Engine scoring
"""

import json
import logging
import uuid
import time
from typing import Optional

logger = logging.getLogger("ROLLBACK_ENGINE")


class RollbackEngine:
    """
    Hardened Rollback & State Recovery Engine.

    Menyimpan pre-execution snapshot sebelum setiap aksi AI,
    dan mengeksekusi rollback otomatis jika aksi gagal diverifikasi.
    """

    def __init__(self, nc=None, db_conn=None):
        self.nc = nc
        self.db = db_conn

    # ─────────────────────────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────────────────────────

    async def snapshot(
        self,
        incident_id: int,
        action: str,
        device: str,
        pre_state: dict,
    ) -> str:
        """
        Simpan snapshot kondisi sebelum eksekusi aksi ke database.
        Harus dipanggil SEBELUM setiap aksi remediasi.

        Returns: snap_id (UUID string) untuk digunakan saat rollback.
        """
        snap_id = str(uuid.uuid4())
        self._persist_snapshot(snap_id, incident_id, action, device, pre_state)
        logger.info(
            "[ROLLBACK] Snapshot saved | snap_id=%s incident=%s action=%s device=%s",
            snap_id, incident_id, action, device
        )
        return snap_id

    async def trigger_rollback(
        self,
        incident_id: int,
        event_id: str,
        action: str,
        snap_id: Optional[str] = None,
    ) -> bool:
        """
        Ambil snapshot pre-state terakhir dan kirim perintah rollback ke NATS.
        Catat ke rollback_logs untuk keperluan Trust Engine scoring.

        Returns: True jika rollback berhasil dikirim.
        """
        logger.warning(
            "[ROLLBACK] Triggering rollback | incident=%s action=%s snap_id=%s",
            incident_id, action, snap_id
        )

        # Ambil pre-state dari DB
        pre_state = self._load_snapshot(incident_id, action, snap_id)

        # Bangun payload rollback
        payload = {
            "event_id":     event_id,
            "incident_id":  incident_id,
            "action":       "ROLLBACK",
            "target_action": action,
            "restore_state": pre_state,
            "details":      f"Auto-rollback triggered: action '{action}' failed post-execution verification.",
            "timestamp":    time.time(),
        }

        # Kirim ke NATS
        nats_ok = await self._publish_rollback(payload)

        # Catat ke rollback_logs (untuk Trust Engine)
        self._log_rollback(incident_id, action, snap_id, nats_ok)

        return nats_ok

    # ─────────────────────────────────────────────────────────────
    # POST-EXECUTION VERIFIER
    # ─────────────────────────────────────────────────────────────

    async def verify_and_rollback_if_needed(
        self,
        incident_id: int,
        event_id: str,
        action: str,
        snap_id: str,
        post_metrics: dict,
        threshold_key: str = "cpu_percent",
        threshold_max: float = 95.0,
    ) -> dict:
        """
        Verifikasi kondisi pasca-eksekusi.
        Jika kondisi memburuk (metrik melebihi threshold), rollback otomatis.

        Returns: {"rolled_back": bool, "reason": str}
        """
        metric_val = post_metrics.get(threshold_key, 0)
        if metric_val > threshold_max:
            reason = (
                f"Post-execution metric '{threshold_key}'={metric_val} "
                f"exceeds threshold {threshold_max}. Auto-rollback initiated."
            )
            logger.warning("[ROLLBACK] %s", reason)
            await self.trigger_rollback(incident_id, event_id, action, snap_id)
            return {"rolled_back": True, "reason": reason}

        logger.info(
            "[ROLLBACK] Post-execution OK | incident=%s action=%s %s=%.1f",
            incident_id, action, threshold_key, metric_val
        )
        return {"rolled_back": False, "reason": "Post-execution verification passed."}

    # ─────────────────────────────────────────────────────────────
    # INTERNAL HELPERS
    # ─────────────────────────────────────────────────────────────

    def _persist_snapshot(
        self,
        snap_id: str,
        incident_id: int,
        action: str,
        device: str,
        pre_state: dict,
    ) -> None:
        if not self.db:
            logger.warning("[ROLLBACK] No DB connection — snapshot not persisted.")
            return
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO rollback_snapshots
                        (snap_id, incident_id, action, device, pre_state, created_at)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (snap_id) DO NOTHING
                    """,
                    (snap_id, incident_id, action, device, json.dumps(pre_state)),
                )
            self.db.commit()
        except Exception as e:
            logger.error("[ROLLBACK] Failed to persist snapshot: %s", e)
            try:
                self.db.rollback()
            except Exception:
                import logging; logging.getLogger(__name__).debug('_ = None suppressed')

    def _load_snapshot(
        self,
        incident_id: int,
        action: str,
        snap_id: Optional[str],
    ) -> dict:
        """Ambil pre_state dari snapshot terbaru untuk incident + action ini."""
        if not self.db:
            return dict()
        try:
            with self.db.cursor() as cur:
                if snap_id:
                    cur.execute(
                        "SELECT pre_state FROM rollback_snapshots WHERE snap_id = %s",
                        (snap_id,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT pre_state FROM rollback_snapshots
                        WHERE incident_id = %s AND action = %s
                        ORDER BY created_at DESC LIMIT 1
                        """,
                        (incident_id, action),
                    )
                row = cur.fetchone()
                return row[0] if row else {}
        except Exception as e:
            logger.error("[ROLLBACK] Failed to load snapshot: %s", e)
            return dict()

    async def _publish_rollback(self, payload: dict) -> bool:
        """Kirim rollback payload ke NATS."""
        if not self.nc:
            logger.error("[ROLLBACK] No NATS connection — rollback not published.")
            return False
        try:
            await self.nc.publish(
                "remediation.rollback",
                json.dumps(payload).encode(),
            )
            logger.info(
                "[ROLLBACK] Published to NATS remediation.rollback | incident=%s",
                payload.get("incident_id"),
            )
            return True
        except Exception as e:
            logger.error("[ROLLBACK] NATS publish failed: %s", e)
            return False

    def _log_rollback(
        self,
        incident_id: int,
        action: str,
        snap_id: Optional[str],
        success: bool,
    ) -> None:
        """Catat ke rollback_logs untuk Trust Engine scoring."""
        if not self.db:
            return
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO rollback_logs
                        (incident_id, action, snap_id, success, triggered_at)
                    VALUES (%s, %s, %s, %s, NOW())
                    """,
                    (incident_id, action, snap_id, success),
                )
            self.db.commit()
        except Exception as e:
            # rollback_logs mungkin belum punya kolom snap_id/success — fallback
            try:
                with self.db.cursor() as cur:
                    cur.execute(
                        "INSERT INTO rollback_logs (incident_id, action, triggered_at) VALUES (%s, %s, NOW())",
                        (incident_id, action),
                    )
                self.db.commit()
            except Exception as e2:
                logger.warning("[ROLLBACK] Could not write rollback_logs: %s | %s", e, e2)
