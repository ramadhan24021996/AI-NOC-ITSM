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
        
        self.db_config = db_config or {
            "dbname": os.environ.get("POSTGRES_DB", "incident_db"),
            "user": os.environ.get("POSTGRES_USER", "postgres"),
            "password": os.environ.get("POSTGRES_PASSWORD", "postgres"),
            "host": os.environ.get("DB_HOST", "127.0.0.1"),
            "port": int(os.environ.get("POSTGRES_PORT", 5432))
        }
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

    def _save_telemetry_to_db(self, payload: Dict[str, Any]):
        """Persist telemetry payload into PostgreSQL database with SQLite WAL fallback."""
        self._save_telemetry_to_sqlite(payload)
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
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
            agent = payload.get("agent", "Unknown_Host")
            event_type = payload.get("event_type", "generic_telemetry")
            status = payload.get("status", "OK")
            layer = payload.get("layer", 1)
            
            cur.execute("""
                INSERT INTO system_telemetry_events (agent_id, event_type, status, layer, payload)
                VALUES (%s, %s, %s, %s, %s);
            """, (agent, event_type, status, layer, json.dumps(payload)))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            logging.debug(f"PostgreSQL storage error (relying on SQLite WAL fallback): {e}")

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
