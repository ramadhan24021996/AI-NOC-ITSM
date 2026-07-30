"""
Phase 3 Governance Framework: Automated AI Quality & Model Drift Detection Engine.

Detects metric degradation over time (e.g. Week 1 RCA Accuracy = 91% vs Week 5 RCA Accuracy = 82%).
Generates governance alerts when metric drift exceeds configured thresholds,
saving to PostgreSQL and broadcasting via NATS.
"""

import logging
import time
import json
import os
import asyncio
import psycopg2
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger("DriftDetectionEngine")


@dataclass
class DriftAlert:
    metric_name: str
    baseline_value: float
    current_value: float
    drift_delta_pct: float
    alert_level: str  # WARNING, CRITICAL
    message: str
    timestamp: float = time.time()


class DriftDetectionEngine:
    """Automated Drift Detection Engine for AI reasoning quality degradation over time."""

    def __init__(self, alert_threshold_pct: float = 5.0):
        self.alert_threshold_pct = alert_threshold_pct
        self.db_host = os.environ.get("DB_HOST", "postgres")
        self.db_port = os.environ.get("DB_PORT", "5432")
        self.db_name = os.environ.get("DB_NAME", "osi_system")
        self.db_user = os.environ.get("DB_USER", "postgres")
        self.db_password = os.environ.get("DB_PASSWORD", "postgres")
        self.nats_url = os.environ.get("NATS_URL", "nats://nats:4222")

    def _get_conn(self):
        try:
            return psycopg2.connect(
                host=self.db_host, port=self.db_port, dbname=self.db_name, 
                user=self.db_user, password=self.db_password
            )
        except Exception as e:
            logger.error(f"[DriftDetection] DB Connection Failed: {e}")
            return None

    def analyze_ai_quality_drift(
        self,
        baseline_metrics: Dict[str, float],
        current_metrics: Dict[str, float]
    ) -> List[DriftAlert]:
        """
        Compares current AI metrics against baseline metrics (e.g., Week 1 vs Week 5).
        Generates DriftAlert objects for any metric degrading beyond threshold.
        """
        alerts: List[DriftAlert] = []
        conn = self._get_conn()

        for metric, base_val in baseline_metrics.items():
            if metric not in current_metrics:
                continue
            curr_val = current_metrics[metric]

            # For Unsupported Claim Rate, drift means an INCREASE
            if metric == "unsupported_claim_rate_percent":
                delta = curr_val - base_val
                if delta > self.alert_threshold_pct:
                    alert_level = "CRITICAL" if delta > 10.0 else "WARNING"
                    alert = DriftAlert(
                        metric_name=metric,
                        baseline_value=base_val,
                        current_value=curr_val,
                        drift_delta_pct=round(delta, 2),
                        alert_level=alert_level,
                        message=f"DRIFT ALERT: {metric} increased by {delta:.2f}% (from {base_val}% to {curr_val}%)"
                    )
                    alerts.append(alert)
                    logger.warning(alert.message)
            else:
                # For RCA Accuracy, Evidence Grounding, etc., drift means a DECREASE
                delta = base_val - curr_val
                if delta > self.alert_threshold_pct:
                    alert_level = "CRITICAL" if delta > 10.0 else "WARNING"
                    alert = DriftAlert(
                        metric_name=metric,
                        baseline_value=base_val,
                        current_value=curr_val,
                        drift_delta_pct=round(delta, 2),
                        alert_level=alert_level,
                        message=f"DRIFT ALERT: {metric} degraded by {delta:.2f}% (from {base_val}% to {curr_val}%)"
                    )
                    alerts.append(alert)
                    logger.warning(alert.message)

        if alerts and conn:
            try:
                with conn.cursor() as cur:
                    for alert in alerts:
                        cur.execute("""
                            INSERT INTO ai_drift_metrics (
                                metric_type, target_name, baseline_success_rate, 
                                current_success_rate, drift_percentage, detected_at
                            ) VALUES (%s, %s, %s, %s, %s, NOW())
                        """, (
                            alert.alert_level,
                            alert.metric_name,
                            alert.baseline_value,
                            alert.current_value,
                            alert.drift_delta_pct
                        ))
                conn.commit()
                logger.info(f"[DriftDetection] Persisted {len(alerts)} alerts to ai_drift_metrics")
            except Exception as e:
                logger.error(f"[DriftDetection] Failed to persist alerts: {e}")
                conn.rollback()
            finally:
                conn.close()

            # Async fire-and-forget NATS broadcast
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._broadcast_alerts(alerts))
                else:
                    loop.run_until_complete(self._broadcast_alerts(alerts))
            except Exception as e:
                logger.warning(f"[DriftDetection] Async broadcast scheduling failed: {e}")

        elif conn:
            conn.close()

        return alerts

    async def _broadcast_alerts(self, alerts: List[DriftAlert]):
        try:
            import nats
            nc = await nats.connect(self.nats_url)
            for alert in alerts:
                payload = {
                    "alert_level": alert.alert_level,
                    "metric_name": alert.metric_name,
                    "baseline": alert.baseline_value,
                    "current": alert.current_value,
                    "delta_pct": alert.drift_delta_pct,
                    "message": alert.message
                }
                await nc.publish("governance.drift.alert", json.dumps(payload).encode())
            await nc.drain()
            logger.info(f"[DriftDetection] Broadcasted {len(alerts)} drift alerts to NATS")
        except Exception as e:
            logger.error(f"[DriftDetection] Failed to broadcast to NATS: {e}")

    def compute_kl_divergence_and_trigger_emergency_refresh(
        self,
        today_dist: List[float],
        week_baseline_dist: List[float],
        threshold: float = 0.30
    ) -> Dict[str, Any]:
        """
        Calculates Kullback-Leibler (KL) Divergence D_KL(P || Q) between today's metric distribution (P)
        and 7-day baseline distribution (Q):
        D_KL(P || Q) = sum( P(i) * log2( P(i) / Q(i) ) )
        If D_KL > threshold (0.30) -> Triggers Emergency DAG Refresh (< 5 minutes).
        """
        import math
        import redis

        epsilon = 1e-9
        # Normalize distributions
        sum_p = sum(today_dist) or 1.0
        sum_q = sum(week_baseline_dist) or 1.0
        P = [max(x / sum_p, epsilon) for x in today_dist]
        Q = [max(x / sum_q, epsilon) for x in week_baseline_dist]

        # Calculate KL-Divergence D_KL(P || Q)
        kl_div = 0.0
        for p_val, q_val in zip(P, Q):
            kl_div += p_val * math.log2(p_val / q_val)

        drift_score = round(float(kl_div), 4)
        is_emergency_refresh_required = drift_score > threshold

        result = {
            "kl_divergence_score": drift_score,
            "threshold": threshold,
            "emergency_refresh_triggered": is_emergency_refresh_required,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }

        if is_emergency_refresh_required:
            logger.warning(f"[DriftDetection] SEMANTIC DRIFT DETECTED! KL-Divergence = {drift_score:.4f} > {threshold}. Triggering Emergency DAG Refresh!")
            try:
                redis_host = os.environ.get("REDIS_HOST", "localhost")
                redis_port = int(os.environ.get("REDIS_PORT", 6379))
                redis_pass = os.environ.get("REDIS_PASSWORD", os.environ.get("OSI_SECURITY_KEY", None))
                r = redis.Redis(host=redis_host, port=redis_port, password=redis_pass, decode_responses=True)
                r.publish("dag:reload", json.dumps({"action": "EMERGENCY_DAG_REFRESH", "drift_score": drift_score}))
                logger.info("[DriftDetection] Broadcasted 'EMERGENCY_DAG_REFRESH' signal to NATS/Redis pubsub.")
            except Exception as e:
                logger.error(f"[DriftDetection] Failed to publish emergency DAG refresh signal: {e}")

        return result
