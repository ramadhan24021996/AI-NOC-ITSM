import os
import asyncio
import json
import logging
import psycopg2
from typing import Dict, Any

logger = logging.getLogger("FeedbackEngine")

class FeedbackEngine:
    def __init__(self):
        self.db_host     = os.environ.get("DB_HOST", "postgres")
        self.db_port     = os.environ.get("DB_PORT", "5432")
        self.db_name     = os.environ.get("DB_NAME", "osi_system")
        self.db_user     = os.environ.get("DB_USER", "postgres")
        self.db_password = os.environ.get("DB_PASSWORD", "postgres")
        self.nats_url    = os.environ.get("NATS_URL", "nats://nats:4222")

    def _get_conn(self):
        try:
            return psycopg2.connect(
                host=self.db_host, port=int(self.db_port),
                dbname=self.db_name,
                user=self.db_user, password=self.db_password
            )
        except Exception as e:
            logger.error(f"[FeedbackEngine] DB connection failed: {e}")
            return None

    def _compute_rlof_delta(self, action: str) -> float:
        """
        Returns RLOF multiplicative-decay delta for playbook confidence.
        Positive for good outcomes, negative for bad ones.
        """
        positive_actions = {"APPROVED", "CORRECT", "RESOLVED", "AUTO_EXECUTED", "VERIFIED"}
        negative_actions = {"REJECTED", "INCORRECT", "OVERRIDE", "ROLLBACK", "ESCALATED"}
        if action.upper() in positive_actions:
            return +0.02   # +2% confidence boost
        if action.upper() in negative_actions:
            return -0.05   # -5% decay
        return 0.0

    def process_feedback(self, engineer_id: str, action: str, incident_id: str, details: Dict[str, Any]):
        """
        Synchronous feedback processing:
          1. Persist to incident_feedback table.
          2. Update ai_playbooks.confidence_score via RLOF delta.
          3. Fire-and-forget NATS broadcast (best-effort).
        """
        conn = self._get_conn()
        if not conn:
            logger.warning("[FeedbackEngine] No DB connection — feedback dropped.")
            return

        try:
            # ── 1. Persist feedback record ─────────────────────────────────────
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO incident_feedback
                        (incident_id, engineer_id, feedback_action, feedback_details, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                """, (incident_id, engineer_id, action, json.dumps(details)))
            conn.commit()
            logger.info(f"[FeedbackEngine] Feedback saved: incident={incident_id} action={action}")

            # ── 2. RLOF Confidence Update ──────────────────────────────────────
            flag = details.get("flag", "")
            delta = self._compute_rlof_delta(action)
            if delta != 0.0 and flag:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE ai_playbooks
                        SET confidence_score = GREATEST(0.0, LEAST(1.0, confidence_score + %s)),
                            last_updated = NOW()
                        WHERE trigger_flag = %s
                    """, (delta, flag))
                conn.commit()
                logger.info(
                    f"[FeedbackEngine] RLOF update: flag={flag} delta={delta:+.2f}"
                )

            # ── 3. Best-effort NATS Broadcast ─────────────────────────────────
            try:
                asyncio.get_event_loop().run_until_complete(
                    self._publish_nats(incident_id, engineer_id, action, flag, delta)
                )
            except RuntimeError:
                # Already inside an event loop (async context) — schedule safely
                asyncio.ensure_future(
                    self._publish_nats(incident_id, engineer_id, action, flag, delta)
                )
            except Exception as nats_err:
                logger.warning(f"[FeedbackEngine] NATS publish skipped: {nats_err}")

        except Exception as e:
            logger.error(f"[FeedbackEngine] process_feedback error: {e}")
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            conn.close()

    async def _publish_nats(self, incident_id, engineer_id, action, flag, delta):
        """Async NATS publish helper — fire-and-forget telemetry event."""
        try:
            import nats as nats_lib
            nc = await nats_lib.connect(self.nats_url)
            payload = json.dumps({
                "incident_id": incident_id,
                "engineer_id": engineer_id,
                "action":      action,
                "flag":        flag,
                "rlof_delta":  delta,
            }).encode()
            await nc.publish("rlof.confidence.update", payload)
            await nc.drain()
            logger.debug("[FeedbackEngine] NATS rlof.confidence.update published.")
        except Exception as e:
            logger.warning(f"[FeedbackEngine] NATS error: {e}")