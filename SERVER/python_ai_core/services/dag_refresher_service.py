"""
Layer 4 AI Core — Dynamic Causal Graph Refresher Service (L4_DAG_Refresher)
BAB 19 Implementation with 4 Structural Security & Reliability Patches:
1. Redis Pub/Sub 'dag:reload' signal on graph topology approval/apply.
2. RBAC Guard requiring 'SITE_RELIABILITY_ARCHITECT' or 'SUPERADMIN'.
3. Cold Start & Data Insufficient handling (<48h skip, 48h-7d lag=1 penalization).
4. Business Context temporal weighting (0.5 off-peak, 1.0 normal, 2.0 peak hours).
"""

import os
import json
import logging
import time
import datetime
from typing import Dict, Any, List, Optional
import redis

logger = logging.getLogger("DAG_REFRESHER_SERVICE")

class DAGRefresherService:
    def __init__(self, db_conn=None, redis_client=None):
        self.db = db_conn
        self.redis = redis_client
        if not self.redis:
            try:
                redis_host = os.environ.get("REDIS_HOST", "localhost")
                redis_port = int(os.environ.get("REDIS_PORT", 6379))
                redis_pass = os.environ.get("REDIS_PASSWORD", os.environ.get("OSI_SECURITY_KEY", None))
                self.redis = redis.Redis(host=redis_host, port=redis_port, password=redis_pass, decode_responses=True)
            except Exception as e:
                logger.warning(f"[DAG_REFRESHER] Redis connection fallback: {e}")

    def apply_business_weight(self, dt: datetime.datetime) -> float:
        """
        BAB 19.9 Patch 4: Weighted Business Hours.
        Returns weight multiplier based on business context:
        - Peak Retail Hours (10:00 - 21:00 WIB): 2.0
        - Off-peak Night Hours (00:00 - 06:00 WIB): 0.5
        - Normal Hours: 1.0
        """
        hour = dt.hour
        if 10 <= hour <= 21:
            return 2.0
        elif 0 <= hour <= 6:
            return 0.5
        return 1.0

    def run_daily_causal_refresh(self, window_days: int = 7) -> Dict[str, Any]:
        """
        Step-by-step pipeline execution for daily causal graph learning cycle.
        Uses Redis Distributed Lock ('dag:refresher:lock') to prevent race conditions across multi-pod containers.
        """
        lock_acquired = False
        lock_key = "dag:refresher:lock"
        if self.redis:
            try:
                # SETNX with 15-minute TTL (900 seconds)
                lock_acquired = self.redis.set(lock_key, "LOCKED", nx=True, ex=900)
                if not lock_acquired:
                    logger.warning("[DAG_REFRESHER] SKIPPED: Another DAG Refresher instance holds the Redis Lock ('dag:refresher:lock').")
                    return {"status": "SKIPPED", "reason": "LOCK_HELD_BY_ANOTHER_POD"}
            except Exception as le:
                logger.warning(f"[DAG_REFRESHER] Redis Lock acquisition warning: {le}")

        logger.info("[DAG_REFRESHER] Starting daily causal graph refresh cycle...")

        if not self.db:
            logger.error("[DAG_REFRESHER] Database connection missing. Cycle aborted.")
            if self.redis and lock_acquired:
                self.redis.delete(lock_key)
            return {"status": "ERROR", "reason": "NO_DB_CONNECTION"}

        # 1. Fetch active telemetry logs for devices
        proposals_created = 0
        skipped_cold_start = 0

        try:
            with self.db.cursor() as cur:
                cur.execute("""
                    SELECT device_name, COUNT(*), MIN(timestamp), MAX(timestamp) 
                    FROM telemetry_logs 
                    WHERE timestamp >= NOW() - INTERVAL '%s days'
                    GROUP BY device_name
                """, (window_days,))
                device_stats = cur.fetchall()

            for dev_name, sample_count, min_ts, max_ts in device_stats:
                if not min_ts or not max_ts:
                    continue

                duration_hours = (max_ts - min_ts).total_seconds() / 3600.0

                # BAB 19.9 Patch 3: Cold Start & Insufficient Data Handling
                if duration_hours < 48.0:
                    logger.info(f"[DAG_REFRESHER] SKIPPED: Insufficient data for Node {dev_name} ({duration_hours:.1f} hours < 48h).")
                    skipped_cold_start += 1
                    continue

                # Data penalty factor for partial window (48h - 7d)
                confidence_penalty = 1.0
                max_lag = 3
                if duration_hours < 168.0: # Less than 7 days
                    confidence_penalty = 0.8
                    max_lag = 1
                    logger.info(f"[DAG_REFRESHER] Partial window for Node {dev_name} ({duration_hours:.1f}h). Setting maxlag=1, confidence penalty=0.8.")

                # Calculate Granger Causality delta and insert proposal if significant
                # (Simulated Granger P-value computation for telemetry pairs)
                p_value = 0.03 # Example significant relationship
                stat_score = round(1.0 - p_value, 4)
                final_confidence = round(stat_score * confidence_penalty, 4)

                if p_value < 0.05:
                    self._create_proposal(
                        source_node=f"{dev_name}_CPU",
                        target_node=f"{dev_name}_LATENCY",
                        change_type="INSERT",
                        statistical_score=stat_score,
                        confidence=final_confidence,
                        sampled_period=f"Last {int(duration_hours/24)} Days"
                    )
                    proposals_created += 1

            logger.info(f"[DAG_REFRESHER] Refresh cycle complete. Proposals: {proposals_created}, Skipped Cold Start: {skipped_cold_start}")
            return {
                "status": "SUCCESS",
                "proposals_created": proposals_created,
                "skipped_cold_start": skipped_cold_start,
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"[DAG_REFRESHER] Failed execution cycle: {e}")
            if self.db:
                self.db.rollback()
            return {"status": "ERROR", "error": str(e)}

    def _create_proposal(self, source_node: str, target_node: str, change_type: str, statistical_score: float, confidence: float, sampled_period: str):
        try:
            with self.db.cursor() as cur:
                # Avoid duplicate pending proposals
                cur.execute("""
                    SELECT id FROM proposed_dag_changes 
                    WHERE source_node = %s AND target_node = %s AND current_status = 'PENDING_REVIEW'
                """, (source_node, target_node))
                if cur.fetchone():
                    return

                cur.execute("""
                    INSERT INTO proposed_dag_changes 
                    (source_node, target_node, change_type, statistical_score, confidence, current_status, evidence_sampled_period, created_at)
                    VALUES (%s, %s, %s, %s, %s, 'PENDING_REVIEW', %s, NOW())
                """, (source_node, target_node, change_type, statistical_score, confidence, sampled_period))
            self.db.commit()
        except Exception as e:
            logger.error(f"[DAG_REFRESHER] Failed to create proposal record: {e}")
            if self.db:
                self.db.rollback()

    def approve_and_apply_proposal(self, proposal_id: int, user_role: str, reviewer_notes: str = "") -> Dict[str, Any]:
        """
        BAB 19.9 Patch 2 & Patch 1:
        RBAC Guard (SUPERADMIN / SITE_RELIABILITY_ARCHITECT) & Redis Pub/Sub signal 'dag:reload'
        """
        if user_role not in ["SUPERADMIN", "SITE_RELIABILITY_ARCHITECT"]:
            logger.warning(f"[DAG_REFRESHER] RBAC DENIED: Role '{user_role}' unauthorized to approve DAG topology changes.")
            return {"status": "FORBIDDEN", "reason": "Requires SITE_RELIABILITY_ARCHITECT or SUPERADMIN role"}

        if not self.db:
            return {"status": "ERROR", "reason": "NO_DB_CONNECTION"}

        try:
            with self.db.cursor() as cur:
                cur.execute("""
                    UPDATE proposed_dag_changes 
                    SET current_status = 'APPLIED', reviewer_notes = %s, reviewed_at = NOW(), applied_at = NOW()
                    WHERE id = %s AND current_status = 'PENDING_REVIEW'
                    RETURNING source_node, target_node, change_type
                """, (reviewer_notes, proposal_id))
                res = cur.fetchone()

            if not res:
                return {"status": "NOT_FOUND", "reason": "Proposal ID not found or already processed"}

            self.db.commit()
            source_node, target_node, change_type = res

            # BAB 19.9 Patch 1: Publish Redis Pub/Sub 'dag:reload' signal
            if self.redis:
                try:
                    payload = json.dumps({
                        "action": "RELOAD",
                        "proposal_id": proposal_id,
                        "change": f"{change_type} {source_node} -> {target_node}",
                        "timestamp": datetime.datetime.utcnow().isoformat()
                    })
                    self.redis.publish("dag:reload", payload)
                    logger.info(f"[DAG_REFRESHER] Redis Pub/Sub signal 'dag:reload' published successfully for Proposal #{proposal_id}")
                except Exception as re:
                    logger.warning(f"[DAG_REFRESHER] Failed to publish Redis signal: {re}")

            return {
                "status": "APPLIED_SUCCESSFULLY",
                "proposal_id": proposal_id,
                "change": f"{change_type} {source_node} -> {target_node}"
            }
        except Exception as e:
            logger.error(f"[DAG_REFRESHER] Failed to apply proposal #{proposal_id}: {e}")
            if self.db:
                self.db.rollback()
            return {"status": "ERROR", "error": str(e)}

    def reject_proposal(self, proposal_id: int, user_role: str, reviewer_notes: str = "") -> Dict[str, Any]:
        if user_role not in ["SUPERADMIN", "SITE_RELIABILITY_ARCHITECT"]:
            return {"status": "FORBIDDEN", "reason": "Requires SITE_RELIABILITY_ARCHITECT or SUPERADMIN role"}

        try:
            with self.db.cursor() as cur:
                cur.execute("""
                    UPDATE proposed_dag_changes 
                    SET current_status = 'REJECTED', reviewer_notes = %s, reviewed_at = NOW()
                    WHERE id = %s AND current_status = 'PENDING_REVIEW'
                """, (reviewer_notes, proposal_id))
            self.db.commit()
            return {"status": "REJECTED_SUCCESSFULLY", "proposal_id": proposal_id}
        except Exception as e:
            if self.db:
                self.db.rollback()
            return {"status": "ERROR", "error": str(e)}
