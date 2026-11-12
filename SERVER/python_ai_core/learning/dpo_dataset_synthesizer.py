"""
AUTONOMOUS DPO DATASET SYNTHESIZER (AUTO-LoRA FINE-TUNING PIPELINE)
Compiles NOC operator approval/rejection feedback history from Feedback Collector
into standard JSONL DPO (Direct Preference Optimization) format:
  { "prompt": "<incident context>", "chosen": "<approved AI response>", "rejected": "<rejected AI response>" }

Designed for monthly auto-export to fine-tune local LoRA models (Llama-3 / Qwen)
to eliminate 99% Cloud API costs while improving AI accuracy over time.
"""

import logging
import sqlite3
import psycopg2.extras
import os
import json
import time
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone

UTC = timezone.utc

from SERVER.shared.db_pool import PGConnection

logger = logging.getLogger("DPO_DATASET_SYNTHESIZER")

DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("DB_PORT", "5433" if DB_HOST == "127.0.0.1" else "5432")
DB_NAME = os.environ.get("DB_NAME", "osi_system")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("POSTGRES_PASSWORD", ""))
MIN_DPO_VOLUME_THRESHOLD = 50


class DPODatasetSynthesizer:
    def __init__(self, db_path: Optional[str] = None, output_dir: Optional[str] = None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), "..", "cognitive_memory.db")
        if output_dir is None:
            output_dir = os.path.join(os.path.dirname(__file__), "..", "dpo_datasets")
        self.db_path = db_path
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self._init_sqlite_cache()

    def _get_pg_connection(self):
        """Returns a PostgreSQL connection to the authoritative osi_system database."""
        conn = PGConnection().__enter__()
        return conn

    def _get_sqlite_connection(self):
        """Returns a local SQLite connection for fallback/cache."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _close(self, conn):
        try:
            if conn is not None and hasattr(conn, "close"):
                conn.close()
        except Exception:
            pass

    def _init_sqlite_cache(self):
        """Initializes local SQLite cache table for offline fallback."""
        conn = self._get_sqlite_connection()
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dpo_feedback_records (
                    record_id   TEXT PRIMARY KEY,
                    incident_id TEXT NOT NULL,
                    intent      TEXT NOT NULL,
                    device_id   TEXT NOT NULL,
                    prompt      TEXT NOT NULL,
                    chosen      TEXT NOT NULL,
                    rejected    TEXT NOT NULL,
                    operator_id TEXT DEFAULT 'NOC_OPS',
                    feedback_ts TEXT NOT NULL
                )
            """)
            conn.commit()
            logger.info("[DPO SYNTH] SQLite local cache schema ready.")
        except Exception as e:
            logger.error(f"[DPO SYNTH] Failed to init SQLite cache: {e}")
        finally:
            self._close(conn)

    def record_feedback(
        self,
        incident_id: str,
        intent: str,
        device_id: str,
        prompt: str,
        chosen_response: str,
        rejected_response: str,
        operator_id: str = "NOC_OPS",
        quality_score: float = 0.90,
        source: str = "human_feedback",
        trace_id: Optional[str] = None,
        decision_id: Optional[str] = None,
        hitl_decision_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        outcome_id: Optional[str] = None,
        feedback_id: Optional[int] = None,
        learning_job_id: Optional[str] = None,
        outcome_verified: bool = False
    ) -> bool:
        """
        Records one DPO training pair into PostgreSQL dpo_training_pairs (Authoritative Single Source)
        ONLY IF outcome_verified is True. Rejects DPO pair creation if outcome is unverified or failed.
        """
        if not prompt or not chosen_response or not rejected_response:
            logger.warning(f"[DPO SYNTH] Invalid feedback payload for incident {incident_id}: missing prompt/chosen/rejected")
            return False

        if not outcome_verified:
            logger.warning(f"[DPO REJECTED] Cannot record positive DPO pair for incident {incident_id}: outcome_verified is FALSE (APPROVED != SUCCESS)")
            return False

        record_id = f"DPO-{incident_id}-{int(time.time())}"
        now_ts = datetime.now(UTC)

        # Primary Write Path: PostgreSQL dpo_training_pairs
        pg_conn = None
        dpo_pair_db_id = None
        try:
            pg_conn = self._get_pg_connection()
            with pg_conn.cursor() as cur:
                # 1. Deduplication check
                cur.execute("""
                    SELECT COUNT(*) FROM dpo_training_pairs 
                    WHERE record_id = %s OR (md5(prompt) = md5(%s) AND md5(chosen) = md5(%s) AND md5(rejected) = %s);
                """, (record_id, prompt, chosen_response, rejected_response))
                if cur.fetchone()[0] > 0:
                    logger.info(f"[DPO SYNTH] Duplicate DPO pair rejected (Incident: {incident_id})")
                    return False

                # 2. Insert into PostgreSQL with full provenance fields
                cur.execute("""
                    INSERT INTO dpo_training_pairs (
                        record_id, incident_id, device_name, prompt, chosen, rejected,
                        domain, quality_score, source, exported, created_at,
                        trace_id, decision_id, hitl_decision_id, execution_id, outcome_id, feedback_id, learning_job_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id;
                """, (
                    record_id, incident_id, device_id, prompt, chosen_response, rejected_response,
                    intent, quality_score, source, now_ts,
                    trace_id, decision_id, hitl_decision_id, execution_id, outcome_id, feedback_id, learning_job_id
                ))
                dpo_pair_db_id = cur.fetchone()[0]

            pg_conn.commit()
            logger.info(f"[DPO SYNTH] Recorded DPO pair to PostgreSQL authoritative store (ID: {dpo_pair_db_id}, Trace: {trace_id})")

            # Update canonical provenance chain if trace_id is present
            if trace_id and dpo_pair_db_id:
                try:
                    from provenance.provenance_tracker import ProvenanceTracker
                    ptracker = ProvenanceTracker()
                    ptracker.create_provenance_chain(trace_id=trace_id, incident_id=incident_id)
                    ptracker.update_stage_id(trace_id=trace_id, stage_name="dpo_pair_id", stage_value=dpo_pair_db_id)
                    if feedback_id: ptracker.update_stage_id(trace_id, "feedback_id", feedback_id)
                    if execution_id: ptracker.update_stage_id(trace_id, "execution_id", execution_id)
                    if outcome_id: ptracker.update_stage_id(trace_id, "outcome_id", outcome_id)
                except Exception as p_err:
                    logger.warning(f"[DPO SYNTH] Error updating canonical provenance tracker: {p_err}")

            return True
        except psycopg2.IntegrityError as ie:
            if pg_conn:
                pg_conn.rollback()
            logger.info(f"[DPO SYNTH] Duplicate DPO pair rejected by PostgreSQL constraint: {ie}")
            return False
        except Exception as e:
            if pg_conn:
                try:
                    pg_conn.rollback()
                except Exception:
                    pass
            logger.error(f"[DPO SYNTH] PostgreSQL write error, falling back to SQLite cache: {e}")
            # Fallback to local SQLite cache
            return self._write_sqlite_fallback(record_id, incident_id, intent, device_id, prompt, chosen_response, rejected_response, operator_id)
        finally:
            self._close(pg_conn)

    def _write_sqlite_fallback(self, record_id, incident_id, intent, device_id, prompt, chosen, rejected, operator_id):
        conn = self._get_sqlite_connection()
        try:
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ")
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO dpo_feedback_records
                (record_id, incident_id, intent, device_id, prompt, chosen, rejected, operator_id, feedback_ts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (record_id, incident_id, intent, device_id, prompt, chosen, rejected, operator_id, now))
            conn.commit()
            logger.info(f"[DPO SYNTH] Recorded DPO pair into SQLite fallback cache: {record_id}")
            return True
        except Exception as e:
            logger.error(f"[DPO SYNTH] SQLite fallback write error: {e}")
            return False
        finally:
            self._close(conn)

    def migrate_sqlite_to_postgresql(self) -> Dict[str, Any]:
        """
        Controlled migration of historical SQLite dpo_feedback_records into PostgreSQL dpo_training_pairs.
        Validates records, skips duplicates, preserves historical timestamps, and logs audit summary.
        """
        s_conn = self._get_sqlite_connection()
        try:
            s_cur = s_conn.cursor()
            s_cur.execute("SELECT record_id, incident_id, intent, device_id, prompt, chosen, rejected, operator_id, feedback_ts FROM dpo_feedback_records")
            sqlite_rows = s_cur.fetchall()
        except Exception as e:
            logger.error(f"[DPO SYNTH] Failed to read SQLite records for migration: {e}")
            return {"status": "ERROR", "message": str(e)}
        finally:
            self._close(s_conn)

        if not sqlite_rows:
            return {"status": "NO_DATA", "message": "No historical SQLite records found to migrate.", "migrated_count": 0}

        total_read = len(sqlite_rows)
        valid_count = 0
        migrated_count = 0
        duplicates_skipped = 0
        invalid_skipped = 0

        # Track seen triplet hashes in memory to prevent duplicate inserts during batch
        seen_triplets = set()

        pg_conn = None
        try:
            pg_conn = self._get_pg_connection()
            with pg_conn.cursor() as cur:
                # Pre-populate seen triplets from existing PostgreSQL records
                cur.execute("SELECT md5(prompt), md5(chosen), md5(rejected) FROM dpo_training_pairs;")
                for r in cur.fetchall():
                    seen_triplets.add((r[0], r[1], r[2]))

                for row in sqlite_rows:
                    rec_id = row["record_id"]
                    inc_id = row["incident_id"]
                    intent = row["intent"]
                    device_id = row["device_id"]
                    prompt = row["prompt"]
                    chosen = row["chosen"]
                    rejected = row["rejected"]
                    ts_str = row["feedback_ts"]

                    # 1. Validation
                    if not prompt or not chosen or not rejected:
                        invalid_skipped += 1
                        continue
                    valid_count += 1

                    # 2. Check for duplicate triplets
                    p_hash = hashlib.md5(prompt.encode('utf-8'), usedforsecurity=False).hexdigest()
                    c_hash = hashlib.md5(chosen.encode('utf-8'), usedforsecurity=False).hexdigest()
                    r_hash = hashlib.md5(rejected.encode('utf-8'), usedforsecurity=False).hexdigest()
                    triplet_key = (p_hash, c_hash, r_hash)

                    if triplet_key in seen_triplets:
                        duplicates_skipped += 1
                        continue

                    # 3. Controlled Insert into PostgreSQL
                    try:
                        cur.execute("""
                            INSERT INTO dpo_training_pairs (
                                record_id, incident_id, device_name, prompt, chosen, rejected,
                                domain, quality_score, source, exported, created_at
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 0.85, 'migrated_from_sqlite', FALSE, %s)
                            ON CONFLICT (record_id) DO NOTHING;
                        """, (rec_id, inc_id, device_id, prompt, chosen, rejected, intent, ts_str))
                        seen_triplets.add(triplet_key)
                        migrated_count += 1
                    except Exception as ie:
                        logger.warning(f"[DPO MIGRATION] Row skipped due to constraint: {ie}")
                        duplicates_skipped += 1

            pg_conn.commit()
            logger.info(f"[DPO MIGRATION] Migration complete. Total: {total_read}, Valid: {valid_count}, Migrated: {migrated_count}, Duplicates Skipped: {duplicates_skipped}, Invalid Skipped: {invalid_skipped}")

            return {
                "status": "SUCCESS",
                "total_read": total_read,
                "valid_count": valid_count,
                "migrated_count": migrated_count,
                "duplicates_skipped": duplicates_skipped,
                "invalid_skipped": invalid_skipped
            }
        except Exception as e:
            if pg_conn:
                pg_conn.rollback()
            logger.error(f"[DPO MIGRATION] Migration transaction rolled back due to error: {e}")
            return {"status": "ERROR", "message": str(e)}
        finally:
            self._close(pg_conn)

    def check_and_trigger_auto_export(self, min_records_threshold: int = 50) -> Dict[str, Any]:
        """
        Checks if total verified DPO records in PostgreSQL authoritative store reach min_records_threshold.
        If threshold is not met (e.g. < 50), returns THRESHOLD_NOT_MET status.
        """
        pg_conn = None
        try:
            pg_conn = self._get_pg_connection()
            with pg_conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM dpo_training_pairs WHERE exported = FALSE;")
                total_count = cur.fetchone()[0]
        except Exception as e:
            logger.error(f"[DPO SYNTH] Error checking PostgreSQL DPO count: {e}")
            return {"status": "ERROR", "message": str(e)}
        finally:
            self._close(pg_conn)

        if total_count >= min_records_threshold:
            logger.info(f"[DPO SYNTH] Auto-export triggered! Record count ({total_count}) >= threshold ({min_records_threshold})")
            return self.synthesize_monthly_dataset(months_back=12)

        return {
            "status": "THRESHOLD_NOT_MET",
            "total_records": total_count,
            "min_required": min_records_threshold,
            "auto_export_triggered": False
        }

    def record_operator_decision(
        self,
        incident_id: str,
        action_proposed: str,
        decision: str,
        prompt_context: str,
        operator_id: str = "NOC_OPS",
        intent: str = "INCIDENT_REMEDIATION",
        device_id: str = "UNKNOWN_DEVICE",
        alternative_recommendation: Optional[str] = None
    ) -> bool:
        """
        Records NOC operator approval or rejection decision as a DPO preference pair in PostgreSQL.
        """
        decision_upper = (decision or "").strip().upper()
        if decision_upper in ("APPROVED", "APPROVE"):
            chosen = action_proposed
            rejected = alternative_recommendation or "Abaikan saran AI dan eskalasi manual"
        else:
            chosen = alternative_recommendation or "Verifikasi manual sebelum mengeksekusi perintah berisiko"
            rejected = action_proposed

        return self.record_feedback(
            incident_id=incident_id,
            intent=intent,
            device_id=device_id,
            prompt=prompt_context,
            chosen_response=chosen,
            rejected_response=rejected,
            operator_id=operator_id
        )

    def synthesize_daily_dataset(self) -> Dict[str, Any]:
        """
        Compiles DPO feedback records for today from PostgreSQL into a JSONL dataset file.
        """
        today_str = datetime.now(UTC).strftime("%Y-%m-%d")
        output_file = os.path.join(self.output_dir, f"dpo_dataset_{today_str}.jsonl")

        pg_conn = None
        try:
            pg_conn = self._get_pg_connection()
            with pg_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT prompt, chosen, rejected, domain, device_name, created_at, record_id
                    FROM dpo_training_pairs
                    WHERE created_at >= %s::date
                    ORDER BY created_at ASC;
                """, (today_str,))
                rows = cur.fetchall()
        except Exception as e:
            logger.error(f"[DPO SYNTH] Error reading daily DPO pairs from PostgreSQL: {e}")
            return {"status": "ERROR", "message": str(e)}
        finally:
            self._close(pg_conn)

        if not rows:
            return {
                "status": "NO_DATA",
                "message": f"No DPO feedback records found in PostgreSQL for today ({today_str}).",
                "output_file": None,
                "record_count": 0
            }

        written = 0
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                for row in rows:
                    entry = {
                        "prompt": row["prompt"],
                        "chosen": row["chosen"],
                        "rejected": row["rejected"],
                        "metadata": {
                            "domain": row["domain"],
                            "device_name": row["device_name"],
                            "record_id": row["record_id"],
                            "created_at": str(row["created_at"])
                        }
                    }
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    written += 1

            size_kb = round(os.path.getsize(output_file) / 1024, 2)
            logger.info(f"[DPO SYNTH] Exported {written} daily DPO pairs from PostgreSQL to {output_file} ({size_kb} KB)")

            return {
                "status": "SUCCESS",
                "output_file": output_file,
                "record_count": written,
                "size_kb": size_kb,
                "date": today_str,
                "lora_ready": True
            }
        except Exception as e:
            logger.error(f"[DPO SYNTH] Failed to synthesize daily dataset: {e}")
            return {"status": "ERROR", "message": str(e)}

    def synthesize_monthly_dataset(self, months_back: int = 1) -> Dict[str, Any]:
        """
        Compiles DPO feedback records from the past N months from PostgreSQL into a JSONL dataset file.
        """
        cutoff = datetime.now(UTC) - timedelta(days=30 * months_back)
        month_label = datetime.now(UTC).strftime("%Y-%m")
        output_file = os.path.join(self.output_dir, f"dpo_dataset_{month_label}.jsonl")

        pg_conn = None
        try:
            pg_conn = self._get_pg_connection()
            with pg_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT prompt, chosen, rejected, domain, device_name, created_at, record_id
                    FROM dpo_training_pairs
                    WHERE created_at >= %s
                    ORDER BY created_at ASC;
                """, (cutoff,))
                rows = cur.fetchall()
        except Exception as e:
            logger.error(f"[DPO SYNTH] Error reading monthly DPO pairs from PostgreSQL: {e}")
            return {"status": "ERROR", "message": str(e)}
        finally:
            self._close(pg_conn)

        if len(rows) < MIN_DPO_VOLUME_THRESHOLD:
            logger.warning(f"[DPO EXPORT REJECTED] Total pairs ({len(rows)}) < MIN_DPO_VOLUME_THRESHOLD ({MIN_DPO_VOLUME_THRESHOLD}). Rejecting model optimization claim.")
            return {
                "status": "INSUFFICIENT_VOLUME",
                "message": f"DPO pair count ({len(rows)}) < MIN_DPO_VOLUME_THRESHOLD ({MIN_DPO_VOLUME_THRESHOLD}). Rejecting model optimization claim.",
                "output_file": None,
                "record_count": len(rows),
                "min_required": MIN_DPO_VOLUME_THRESHOLD,
                "lora_ready": False
            }

        written = 0
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                for row in rows:
                    entry = {
                        "prompt": row["prompt"],
                        "chosen": row["chosen"],
                        "rejected": row["rejected"],
                        "metadata": {
                            "domain": row["domain"],
                            "device_name": row["device_name"],
                            "record_id": row["record_id"],
                            "created_at": str(row["created_at"])
                        }
                    }
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    written += 1

            size_kb = round(os.path.getsize(output_file) / 1024, 2)
            logger.info(f"[DPO SYNTH] Exported {written} DPO pairs from PostgreSQL to {output_file} ({size_kb} KB)")

            return {
                "status": "SUCCESS",
                "output_file": output_file,
                "record_count": written,
                "size_kb": size_kb,
                "period": f"Last {months_back * 30} days",
                "lora_ready": True,
                "compatible_trainers": ["HuggingFace TRL DPOTrainer", "Axolotl", "LLaMA-Factory"]
            }
        except Exception as e:
            logger.error(f"[DPO SYNTH] Failed to synthesize dataset: {e}")
            return {"status": "ERROR", "message": str(e)}

    def get_statistics(self) -> Dict[str, Any]:
        """Returns aggregate statistics of all DPO feedback records in PostgreSQL."""
        pg_conn = None
        try:
            pg_conn = self._get_pg_connection()
            with pg_conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM dpo_training_pairs;")
                total = cur.fetchone()[0]

                cur.execute("SELECT domain, COUNT(*) FROM dpo_training_pairs GROUP BY domain ORDER BY count DESC LIMIT 5;")
                top_domains = [{"domain": r[0], "count": r[1]} for r in cur.fetchall()]

                return {
                    "authoritative_store": "PostgreSQL (osi_system.dpo_training_pairs)",
                    "total_feedback_pairs": total,
                    "top_domains": top_domains
                }
        except Exception as e:
            logger.error(f"[DPO SYNTH] Error getting statistics from PostgreSQL: {e}")
            return {"total_feedback_pairs": 0, "error": str(e)}
        finally:
            self._close(pg_conn)
