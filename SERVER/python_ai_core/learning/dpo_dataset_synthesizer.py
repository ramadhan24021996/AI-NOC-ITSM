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
import os
import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, UTC

logger = logging.getLogger("DPO_DATASET_SYNTHESIZER")


class DPODatasetSynthesizer:
    def __init__(self, db_path: Optional[str] = None, output_dir: Optional[str] = None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), "..", "cognitive_memory.db")
        if output_dir is None:
            output_dir = os.path.join(os.path.dirname(__file__), "..", "dpo_datasets")
        self.db_path = db_path
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _close(self, conn):
        try:
            conn.close()
        except Exception:
            pass

    def _init_db(self):
        """Initializes the DPO feedback table in SQLite if not already created."""
        conn = self._get_connection()
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
            logger.info("[DPO SYNTH] DPO feedback schema initialized.")
        except Exception as e:
            logger.error(f"[DPO SYNTH] Failed to init DB: {e}")
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
        operator_id: str = "NOC_OPS"
    ) -> bool:
        """
        Records one DPO training pair from a single NOC operator feedback event.
        chosen_response  = the AI response approved by the operator.
        rejected_response = the AI response rejected / overridden by the operator.
        """
        conn = self._get_connection()
        try:
            record_id = f"DPO-{incident_id}-{int(time.time())}"
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ")
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO dpo_feedback_records
                (record_id, incident_id, intent, device_id, prompt, chosen, rejected, operator_id, feedback_ts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (record_id, incident_id, intent, device_id, prompt,
                  chosen_response, rejected_response, operator_id, now))
            conn.commit()
            logger.info(f"[DPO SYNTH] Recorded DPO pair for incident {incident_id}.")
            return True
        except Exception as e:
            logger.error(f"[DPO SYNTH] Error recording feedback: {e}")
            return False
        finally:
            self._close(conn)

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
        Records NOC operator approval or rejection decision as a DPO preference pair:
        - If decision is 'APPROVED' or 'APPROVE':
          chosen = action_proposed
          rejected = alternative_recommendation or 'Do nothing / Manual investigation required'
        - If decision is 'REJECTED' or 'REJECT':
          chosen = alternative_recommendation or 'Manual investigation required before execution'
          rejected = action_proposed
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
        Compiles DPO feedback records for today into a JSONL dataset file:
          dpo_dataset_YYYY-MM-DD.jsonl
        Runs in background passively without locking primary database.
        """
        today_str = datetime.now(UTC).strftime("%Y-%m-%d")
        output_file = os.path.join(self.output_dir, f"dpo_dataset_{today_str}.jsonl")

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT prompt, chosen, rejected, intent, device_id, feedback_ts
                FROM dpo_feedback_records
                WHERE feedback_ts LIKE ?
                ORDER BY feedback_ts ASC
            """, (f"{today_str}%",))
            rows = cursor.fetchall()
        finally:
            self._close(conn)

        if not rows:
            return {
                "status": "NO_DATA",
                "message": f"No DPO feedback records found for today ({today_str}).",
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
                            "intent": row["intent"],
                            "device_id": row["device_id"],
                            "feedback_ts": row["feedback_ts"]
                        }
                    }
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    written += 1

            size_kb = round(os.path.getsize(output_file) / 1024, 2)
            logger.info(f"[DPO SYNTH] Exported {written} daily DPO pairs to {output_file} ({size_kb} KB)")

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
        Compiles all DPO feedback records from the past N months into a JSONL dataset file.
        Output format per line:
          { "prompt": "...", "chosen": "...", "rejected": "..." }
        Suitable for HuggingFace TRL DPO Trainer and Axolotl LoRA fine-tuning.
        """
        cutoff = (datetime.now(UTC) - timedelta(days=30 * months_back)).strftime("%Y-%m-%dT%H:%M:%SZ")
        month_label = datetime.now(UTC).strftime("%Y-%m")
        output_file = os.path.join(self.output_dir, f"dpo_dataset_{month_label}.jsonl")

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT prompt, chosen, rejected, intent, device_id, feedback_ts
                FROM dpo_feedback_records
                WHERE feedback_ts >= ?
                ORDER BY feedback_ts ASC
            """, (cutoff,))
            rows = cursor.fetchall()
        finally:
            self._close(conn)

        if not rows:
            return {
                "status": "NO_DATA",
                "message": "No DPO feedback records found for this period.",
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
                            "intent": row["intent"],
                            "device_id": row["device_id"],
                            "feedback_ts": row["feedback_ts"]
                        }
                    }
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    written += 1

            size_kb = round(os.path.getsize(output_file) / 1024, 2)
            logger.info(f"[DPO SYNTH] Exported {written} DPO pairs to {output_file} ({size_kb} KB)")

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
        """Returns aggregate statistics of all DPO feedback records."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as total FROM dpo_feedback_records")
            total = cursor.fetchone()["total"]
            cursor.execute("SELECT intent, COUNT(*) as cnt FROM dpo_feedback_records GROUP BY intent ORDER BY cnt DESC LIMIT 5")
            top_intents = [{"intent": r["intent"], "count": r["cnt"]} for r in cursor.fetchall()]
            return {"total_feedback_pairs": total, "top_intents": top_intents}
        except Exception as e:
            return {"total_feedback_pairs": 0, "error": str(e)}
        finally:
            self._close(conn)



# Demo test run
if __name__ == "__main__":
    synth = DPODatasetSynthesizer()
    print("=== UJI AUTONOMOUS DPO DATASET SYNTHESIZER (AUTO-LoRA PIPELINE) ===\n")

    # Simulate 3 NOC operator feedback events
    sample_pairs = [
        {
            "incident_id": "INC-2026-0811",
            "intent": "PRINTER_SPOOLER_STALLED",
            "device_id": "KASIR-POS-STORE-02",
            "prompt": "[INSIDEN] Print Spooler tidak responsif selama 4 menit pada KASIR-POS-STORE-02. CPU: 98%. Queue: 47 jobs tertunda.",
            "chosen_response": "LANGKAH: 1) Hentikan Spooler service. 2) Bersihkan folder C:\\Windows\\System32\\spool\\PRINTERS. 3) Mulai ulang Spooler service. 4) Verifikasi queue kosong.",
            "rejected_response": "Reboot seluruh mesin kasir untuk membersihkan spooler."
        },
        {
            "incident_id": "INC-2026-0812",
            "intent": "HIGH_CPU_PROCESS",
            "device_id": "SERVER-BACKEND-01",
            "prompt": "[INSIDEN] Proses python3 mengonsumsi 97% CPU selama 8 menit pada SERVER-BACKEND-01. Load average: 12.4.",
            "chosen_response": "LANGKAH: 1) Identifikasi PID dengan 'top -bn1'. 2) Kill proses zombie (kill -9 <PID>). 3) Restart layanan yang bersangkutan. 4) Pantau CPU selama 5 menit.",
            "rejected_response": "Matikan server dan nyalakan kembali untuk mereset CPU load."
        },
        {
            "incident_id": "INC-2026-0813",
            "intent": "DISK_SPACE_CRITICAL",
            "device_id": "SERVER-DB-PRIMARY",
            "prompt": "[INSIDEN] Disk usage mencapai 94% pada /var/lib/postgresql di SERVER-DB-PRIMARY. Risiko crash PostgreSQL.",
            "chosen_response": "LANGKAH: 1) Jalankan VACUUM FULL pada tabel terbesar. 2) Hapus log WAL lama (pg_wal >7 hari). 3) Archive data historis ke cold storage. 4) Alert jika disk >90%.",
            "rejected_response": "Hapus semua file di /tmp dan /var/log untuk membebaskan ruang disk."
        }
    ]

    for pair in sample_pairs:
        synth.record_feedback(**pair)
        print(f"  ✅ Recorded DPO pair: {pair['incident_id']} ({pair['intent']})")

    print("\n[Synthesizing Monthly DPO Dataset...]")
    result = synth.synthesize_monthly_dataset(months_back=1)

    print(f"\n📦 Status       : {result['status']}")
    print(f"📁 Output File  : {result.get('output_file', '-')}")
    print(f"📊 DPO Pairs    : {result.get('record_count', 0)} records")
    print(f"💾 Dataset Size : {result.get('size_kb', 0)} KB")
    print(f"🔗 Compatible   : {', '.join(result.get('compatible_trainers', []))}")

    stats = synth.get_statistics()
    print(f"\n[DPO Statistics]")
    print(f"  Total Feedback Pairs : {stats['total_feedback_pairs']}")
    print(f"  Top Intents:")
    for t in stats.get("top_intents", []):
        print(f"    - {t['intent']}: {t['count']} pairs")
