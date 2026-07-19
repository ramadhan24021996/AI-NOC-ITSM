import logging
import time
import json
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

logger = logging.getLogger("TRUST_ENGINE")

class TrustEngine:
    """
    Hardened Agent Trust Scoring Engine (Phase 6).
    Performs real-time trust scoring, degradation, recovery, and auditing.
    """

    def __init__(self):
        logger.info("Initializing Agent Trust Scoring Engine.")

    def evaluate_trust_scores(self, conn) -> None:
        """
        Periodically runs to evaluate all agents in agent_trust_scores.
        Applies degradation, recovery, updates scores, and logs security audits.
        """
        if not conn:
            logger.warning("No DB connection for Trust Engine evaluation.")
            return

        try:
            with conn.cursor() as cur:
                # 1. Fetch all agents currently tracked
                cur.execute("SELECT agent_name, trust_score, heartbeat_score, false_positive_penalty, "
                            "execution_success_bonus, rollback_frequency_penalty, telemetry_integrity_score, "
                            "spoof_detection_flag, total_events_processed, total_false_positives, "
                            "total_rollbacks, total_successes, score_version FROM agent_trust_scores")
                agents = cur.fetchall()

                for row in agents:
                    (agent_name, old_trust, old_hb, old_fp_pen, old_exec_bon, old_rb_pen,
                     old_tel, spoof_flag, total_ev, total_fp, total_rb, total_succ, score_ver) = row

                    # A. Evaluate Heartbeat consistency
                    cur.execute("SELECT last_seen FROM agent_heartbeats WHERE agent = %s", (agent_name,))
                    hb_row = cur.fetchone()
                    
                    new_hb = float(old_hb)
                    if hb_row and hb_row[0]:
                        last_seen = hb_row[0]
                        # Calculate lag in seconds
                        if isinstance(last_seen, str):
                            # Parse string timestamp if needed
                            try:
                                last_seen_dt = datetime.strptime(last_seen.split('.')[0], "%Y-%m-%d %H:%M:%S")
                                lag = (datetime.utcnow() - last_seen_dt).total_seconds()
                            except Exception:
                                lag = 0
                        elif isinstance(last_seen, datetime):
                            # Convert last_seen to naive utc datetime if it is timezone aware
                            last_seen_naive = last_seen.replace(tzinfo=None)
                            lag = (datetime.utcnow() - last_seen_naive).total_seconds()
                        else:
                            lag = 0

                        # Heartbeat degradation/recovery logic
                        if lag > 30.0:
                            # Degrade 5 points for every 10 seconds beyond 30s
                            intervals = int((lag - 30.0) / 10.0) + 1
                            new_hb = max(0.0, float(old_hb) - (intervals * 5.0))
                        else:
                            # Consistent heartbeat: recover 2.0 points
                            new_hb = min(100.0, float(old_hb) + 2.0)
                    else:
                        # No heartbeat recorded at all: degrade heartbeat score
                        new_hb = max(0.0, float(old_hb) - 10.0)

                    # B. Fetch False Positive count from incident_feedback
                    cur.execute(
                        "SELECT COUNT(*) FROM incident_feedback f "
                        "JOIN incidents i ON f.incident_id = i.incident_id "
                        "WHERE i.device_name = %s AND (f.review_result = 'False Positive' OR f.review_result = 'Rejected')",
                        (agent_name,)
                    )
                    fp_count = cur.fetchone()[0]
                    # Update local counter if DB has more
                    total_fp = max(total_fp, fp_count)
                    new_fp_pen = min(50.0, total_fp * 15.0)

                    # C. Fetch execution success count
                    cur.execute(
                        "SELECT COUNT(*) FROM verification_logs v "
                        "JOIN fleet_incidents fi ON v.incident_id = fi.incident_id "
                        "WHERE fi.pc_name = %s AND v.rollback_needed = FALSE AND v.verification_status = 'SUCCESS'",
                        (agent_name,)
                    )
                    succ_count = cur.fetchone()[0]
                    total_succ = max(total_succ, succ_count)
                    new_exec_bon = min(10.0, total_succ * 2.0)

                    # D. Fetch rollback frequency
                    cur.execute(
                        "SELECT COUNT(*) FROM rollback_logs r "
                        "JOIN fleet_incidents fi ON r.incident_id = fi.incident_id "
                        "WHERE fi.pc_name = %s",
                        (agent_name,)
                    )
                    rb_count = cur.fetchone()[0]
                    total_rb = max(total_rb, rb_count)
                    new_rb_pen = min(60.0, total_rb * 20.0)

                    # E. Fetch telemetry/trace integrity issues
                    cur.execute(
                        "SELECT COUNT(*) FROM trace_integrity_reports WHERE resolved = FALSE AND (site_id = %s OR trace_id IN "
                        "(SELECT CAST(incident_id AS TEXT) FROM fleet_incidents WHERE pc_name = %s))",
                        (agent_name, agent_name)
                    )
                    tel_anomalies = cur.fetchone()[0]
                    new_tel = max(0.0, 100.0 - (tel_anomalies * 10.0))

                    # F. Aggregate Trust Score formula
                    # TrustScore = HeartbeatScore - FalsePositivePenalty + ExecutionSuccessBonus - RollbackFrequencyPenalty - (100.0 - TelemetryIntegrityScore) - (100.0 if SpoofDetectionFlag else 0.0)
                    spoof_penalty = 100.0 if spoof_flag else 0.0
                    new_trust = new_hb - new_fp_pen + new_exec_bon - new_rb_pen - (100.0 - new_tel) - spoof_penalty
                    new_trust = max(0.0, min(100.0, new_trust))

                    # G. Update database record
                    cur.execute(
                        "UPDATE agent_trust_scores SET "
                        "trust_score = %s, heartbeat_score = %s, false_positive_penalty = %s, "
                        "execution_success_bonus = %s, rollback_frequency_penalty = %s, telemetry_integrity_score = %s, "
                        "total_false_positives = %s, total_rollbacks = %s, total_successes = %s, "
                        "last_seen_at = NOW(), last_scored_at = NOW(), score_version = score_version + 1, "
                        "updated_at = NOW() "
                        "WHERE agent_name = %s",
                        (new_trust, new_hb, new_fp_pen, new_exec_bon, new_rb_pen, new_tel,
                         total_fp, total_rb, total_succ, agent_name)
                    )

                    # H. Log audit trailing if trust score changes significantly or drops below critical threshold
                    if abs(float(old_trust) - new_trust) >= 1.0 or (old_trust >= 70.0 and new_trust < 70.0):
                        event_payload = {
                            "agent": agent_name,
                            "old_trust_score": float(old_trust),
                            "new_trust_score": new_trust,
                            "metrics": {
                                "heartbeat_score": new_hb,
                                "false_positive_penalty": new_fp_pen,
                                "execution_success_bonus": new_exec_bon,
                                "rollback_frequency_penalty": new_rb_pen,
                                "telemetry_integrity_score": new_tel,
                                "spoof_detection_flag": spoof_flag
                            },
                            "timestamp": datetime.utcnow().isoformat()
                        }
                        cur.execute(
                            "INSERT INTO security_events (rule_name, event_type, payload) VALUES (%s, %s, %s)",
                            ("Phase 6: Trust Score Update", "TRUST_DEGRADATION" if new_trust < old_trust else "TRUST_RECOVERY", json.dumps(event_payload))
                        )
                        logger.info(f"Trust update for agent '{agent_name}': {old_trust} -> {new_trust}")

            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Failed to evaluate agent trust scores: {e}", exc_info=True)

    def record_agent_event(self, conn, agent_name: str, event_type: str) -> None:
        """
        Real-time event-driven trust updates (e.g. execution success or rollback).
        """
        if not conn or not agent_name:
            return

        try:
            with conn.cursor() as cur:
                # First ensure agent exists in agent_trust_scores
                cur.execute("SELECT id FROM agent_trust_scores WHERE agent_name = %s", (agent_name,))
                if not cur.fetchone():
                    cur.execute(
                        "INSERT INTO agent_trust_scores (agent_name, trust_score, heartbeat_score) "
                        "VALUES (%s, 100.0, 100.0) ON CONFLICT (agent_name) DO NOTHING",
                        (agent_name,)
                    )

                if event_type == "SUCCESS":
                    # Successful execution: increment successes, decay penalties
                    cur.execute(
                        "UPDATE agent_trust_scores SET "
                        "total_successes = total_successes + 1, "
                        "total_events_processed = total_events_processed + 1, "
                        "rollback_frequency_penalty = max(0.0, rollback_frequency_penalty - 5.0), "
                        "false_positive_penalty = max(0.0, false_positive_penalty - 2.0), "
                        "updated_at = NOW() WHERE agent_name = %s",
                        (agent_name,)
                    )
                elif event_type == "ROLLBACK":
                    # Rollback triggered: increment rollbacks and increase penalty immediately
                    cur.execute(
                        "UPDATE agent_trust_scores SET "
                        "total_rollbacks = total_rollbacks + 1, "
                        "total_events_processed = total_events_processed + 1, "
                        "rollback_frequency_penalty = min(60.0, rollback_frequency_penalty + 20.0), "
                        "updated_at = NOW() WHERE agent_name = %s",
                        (agent_name,)
                    )
                elif event_type == "FALSE_POSITIVE":
                    # User flagged false positive: increment FP count and increase penalty
                    cur.execute(
                        "UPDATE agent_trust_scores SET "
                        "total_false_positives = total_false_positives + 1, "
                        "total_events_processed = total_events_processed + 1, "
                        "false_positive_penalty = min(50.0, false_positive_penalty + 15.0), "
                        "updated_at = NOW() WHERE agent_name = %s",
                        (agent_name,)
                    )
                elif event_type == "SPOOF_DETECTED":
                    # Spoofing detected: trigger flag
                    cur.execute(
                        "UPDATE agent_trust_scores SET "
                        "spoof_detection_flag = TRUE, "
                        "updated_at = NOW() WHERE agent_name = %s",
                        (agent_name,)
                    )
            conn.commit()
            # Immediately re-evaluate trust score for this agent
            self.evaluate_trust_scores(conn)
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Failed to record agent event: {e}", exc_info=True)
