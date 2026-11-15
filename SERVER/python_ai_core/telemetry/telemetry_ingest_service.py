"""
Unified Telemetry Ingestion & Real-Time Streaming Service (P0 Expansion Monitoring)
Aggregates metrics from:
1. HardwareTelemetryCollector (GPU, Printer, USB/COM, WiFi/Bluetooth)
2. EnterpriseConnectors (DHCP/DNS, AD, VMware/Proxmox, Kubernetes, Kafka)
3. EnterpriseLogParser (Windows Event IDs, Nginx, PostgreSQL, Redis)

Publishes real-time telemetry events and updates PostgreSQL & WebSocket stream.
"""

import os
import sys
import json
import time
import logging
import threading
import sqlite3
import psycopg2
from typing import Dict, Any, List, Optional

# Ensure parent python_ai_core paths are resolvable
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telemetry.hardware_collector import HardwareTelemetryCollector
from telemetry.enterprise_connectors import EnterpriseConnectors

logging.basicConfig(level=logging.INFO, format="[TELEMETRY-INGEST-SERVICE] %(asctime)s - %(levelname)s - %(message)s")

class TelemetryIngestService:
    def __init__(self, db_config: Optional[Dict[str, Any]] = None):
        self.hw_collector = HardwareTelemetryCollector()
        self.ent_connectors = EnterpriseConnectors()
        self.running = False
        self.interval_sec = 30 # Telemetry sweep every 30 seconds
        self.sqlite_db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "database", "incident_analysis.db"
        )
        
        default_host = os.environ.get("DB_HOST", "127.0.0.1")
        default_port = "5433" if default_host in ("127.0.0.1", "localhost") else "5432"
        self.db_config = db_config or {
            "dbname": os.environ.get("DB_NAME", os.environ.get("POSTGRES_DB", "osi_system")),
            "user": os.environ.get("DB_USER", os.environ.get("POSTGRES_USER", "postgres")),
            "password": os.environ.get("DB_PASSWORD", os.environ.get("POSTGRES_PASSWORD", "")),
            "host": default_host,
            "port": int(os.environ.get("DB_PORT", os.environ.get("POSTGRES_PORT", default_port)))
        }
        self._pg_schema_initialized = False
        self._init_sqlite_wal()

    def _init_sqlite_wal(self):
        """Initialize SQLite database with Write-Ahead Logging (WAL) mode for concurrent high-throughput writes."""
        try:
            os.makedirs(os.path.dirname(self.sqlite_db_path), exist_ok=True)
            conn = sqlite3.connect(self.sqlite_db_path, timeout=10.0)
            cur = conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL;")
            cur.execute("PRAGMA busy_timeout=5000;")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS system_telemetry_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    layer INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
            conn.close()
            logging.info("SQLite WAL Mode & busy_timeout initialized successfully for incident_analysis.db")
        except Exception as e:
            logging.warning(f"SQLite WAL mode initialization warning: {e}")

    def _save_telemetry_to_sqlite(self, payload: Dict[str, Any]):
        """Persist telemetry payload into SQLite with WAL mode."""
        try:
            conn = sqlite3.connect(self.sqlite_db_path, timeout=5.0)
            cur = conn.cursor()
            agent = payload.get("agent", "Unknown_Host")
            event_type = payload.get("event_type", "generic_telemetry")
            status = payload.get("status", "OK")
            layer = payload.get("layer", 1)
            cur.execute("""
                INSERT INTO system_telemetry_events (agent_id, event_type, status, layer, payload)
                VALUES (?, ?, ?, ?, ?);
            """, (agent, event_type, status, layer, json.dumps(payload)))
            conn.commit()
            conn.close()
        except Exception as e:
            logging.debug(f"SQLite telemetry persistence error: {e}")

    def _extract_canonical_metrics(self, payload: Dict[str, Any]) -> List[tuple]:
        """Extract canonical numeric metrics (cpu_percent, memory_percent, disk_percent, etc.) for telemetry_logs."""
        metrics: List[tuple] = []
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}

        # 1. Explicit numeric metrics in payload or data
        for key, canonical in (
            ("cpu_percent", "cpu_percent"),
            ("cpu_usage", "cpu_percent"),
            ("memory_percent", "memory_percent"),
            ("memory_usage", "memory_percent"),
            ("disk_percent", "disk_percent"),
            ("disk_usage", "disk_percent"),
        ):
            val = payload.get(key, data.get(key))
            if isinstance(val, (int, float)):
                metrics.append((canonical, float(val)))

        # 2. Extract hardware peripheral sub-metrics when present
        gpu_block = data.get("gpu") if isinstance(data.get("gpu"), dict) else {}
        gpus = gpu_block.get("gpus") if isinstance(gpu_block.get("gpus"), list) else []
        if gpus and isinstance(gpus[0], dict):
            util = gpus[0].get("utilization_pct")
            if isinstance(util, (int, float)):
                metrics.append(("gpu_utilization_percent", float(util)))

        printer_block = data.get("printer") if isinstance(data.get("printer"), dict) else {}
        if isinstance(printer_block.get("queue_jobs"), (int, float)):
            metrics.append(("printer_queue_jobs", float(printer_block["queue_jobs"])))

        # 3. Host CPU/RAM/Disk via psutil when collecting hardware_peripherals on local host
        if payload.get("event_type") == "hardware_peripherals" and not any(m[0] == "cpu_percent" for m in metrics):
            try:
                import psutil
                metrics.append(("cpu_percent", float(psutil.cpu_percent(interval=None))))
                metrics.append(("memory_percent", float(psutil.virtual_memory().percent)))
                metrics.append(("disk_percent", float(psutil.disk_usage("/").percent)))
            except Exception:
                pass

        return metrics

    def _save_telemetry_to_db(self, payload: Dict[str, Any]):
        """Persist telemetry payload into PostgreSQL database (system_telemetry_events + canonical telemetry_logs) with SQLite WAL fallback."""
        self._save_telemetry_to_sqlite(payload)
        conn = None
        cur = None
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            if not self._pg_schema_initialized:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS system_telemetry_events (
                        id SERIAL PRIMARY KEY,
                        agent_id VARCHAR(255) NOT NULL,
                        event_type VARCHAR(100) NOT NULL,
                        status VARCHAR(50) NOT NULL,
                        layer INT NOT NULL,
                        payload JSONB NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                self._pg_schema_initialized = True

            agent = payload.get("agent", "Unknown_Host")
            event_type = payload.get("event_type", "generic_telemetry")
            status = payload.get("status", "OK")
            layer = payload.get("layer", 1)
            
            cur.execute("""
                INSERT INTO system_telemetry_events (agent_id, event_type, status, layer, payload)
                VALUES (%s, %s, %s, %s, %s);
            """, (agent, event_type, status, layer, json.dumps(payload)))

            # Synchronize canonical numeric metrics into telemetry_logs for PostVerificationEngine & ClosedLoopObserver
            canonical_metrics = self._extract_canonical_metrics(payload)
            if canonical_metrics and agent:
                try:
                    cur.execute(
                        """
                        INSERT INTO devices (name, layer, status)
                        VALUES (%s, %s, 'ONLINE')
                        ON CONFLICT (name) DO UPDATE SET status = 'ONLINE'
                        """,
                        (agent, int(layer or 3)),
                    )
                    meta_json = json.dumps({"source": "TelemetryIngestService", "event_type": event_type})
                    for m_type, m_val in canonical_metrics:
                        cur.execute(
                            """
                            INSERT INTO telemetry_logs (device_name, metric_type, metric_value, timestamp, metadata)
                            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, %s::jsonb)
                            """,
                            (agent, m_type, float(m_val), meta_json),
                        )
                except Exception as sync_err:
                    logging.debug(f"Canonical telemetry_logs sync skipped: {sync_err}")

            conn.commit()
        except Exception as e:
            logging.debug(f"PostgreSQL storage error (relying on SQLite WAL fallback): {e}")
        finally:
            if cur:
                try:
                    cur.close()
                except Exception:
                    logging.getLogger(__name__).debug("Suppressed exception", exc_info=True)
            if conn:
                try:
                    conn.close()
                except Exception:
                    logging.getLogger(__name__).debug("Suppressed exception", exc_info=True)

    def collect_and_process_once(self) -> Dict[str, Any]:
        """Perform a single real-time telemetry collection sweep."""
        logging.info("Executing Enterprise & Hardware Telemetry Collection Sweep...")
        
        hw_payload = self.hw_collector.collect_all()
        ent_payload = self.ent_connectors.collect_all()
        
        self._save_telemetry_to_db(hw_payload)
        self._save_telemetry_to_db(ent_payload)
        
        summary = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "hardware_telemetry": hw_payload,
            "enterprise_connectors": ent_payload,
            "status": "COMPLETED"
        }
        logging.info(f"Sweep finished. Hardware Status: {hw_payload['status']} | Enterprise Status: {ent_payload['status']}")
        return summary

    def start_loop(self):
        """Start non-blocking daemon loop for real-time telemetry sweep."""
        if self.running:
            return
        self.running = True

        def _loop():
            while self.running:
                try:
                    self.collect_and_process_once()
                except Exception as e:
                    logging.error(f"Error in telemetry sweep loop: {e}")
                time.sleep(self.interval_sec)

        t = threading.Thread(target=_loop, daemon=True)
        t.start()
        logging.info(f"Telemetry Ingestion Daemon Loop started (Interval: {self.interval_sec}s).")

    def stop_loop(self):
        self.running = False
        logging.info("Telemetry Ingestion Daemon Loop stopped.")

if __name__ == "__main__":
    service = TelemetryIngestService()
    summary = service.collect_and_process_once()
    print("\n--- TELEMETRY SWEEP SUMMARY ---")
    print(json.dumps(summary, indent=2))
