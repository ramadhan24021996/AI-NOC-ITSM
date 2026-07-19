"""
Enterprise Autonomous AI OS — Remediation & Escalation
Rollback & Snapshot Engine

Tugas: Mengambil snapshot state riil (Windows Registry, Linux iptables, dll)
dari agent sebelum AI mengeksekusi aksi remediasi, dan melakukan rollback 
ke state tersebut jika remediasi gagal.

TIDAK MENGGUNAKAN MOCK/STUB. Semua command dieksekusi secara live 
pada production runtime via NATS "agent.execute.<target>".
"""

import asyncio
import json
import logging
import os
import uuid
import datetime

logger = logging.getLogger("SNAPSHOT_ENGINE")

DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "osi_system")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASSWORD", "postgres")
NATS_URL = os.getenv("NATS_URL", "nats://nats:4222")

def _get_db():
    import psycopg2
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, database=DB_NAME,
        user=DB_USER, password=DB_PASS
    )

class RollbackSnapshotEngine:
    def __init__(self, nc):
        self.nc = nc
        self._conn = _get_db()

    async def take_snapshot(self, payload: dict) -> dict:
        """
        Mengambil snapshot dari node produksi tanpa mock.
        Payload: {"device_id": "PC-01", "os_type": "linux", "target_components": ["iptables", "network"]}
        """
        device_id = payload.get("device_id")
        os_type = payload.get("os_type", "linux").lower()
        components = payload.get("target_components", [])
        snapshot_id = str(uuid.uuid4())
        
        logger.info(f"[SNAPSHOT] Memulai live snapshot {snapshot_id} pada perangkat {device_id}...")
        
        snapshot_data = {}
        is_success = True

        for comp in components:
            command = self._build_snapshot_command(os_type, comp)
            if not command:
                continue
                
            logger.info(f"[SNAPSHOT] Executing live command for {comp}: {command}")
            req = {
                "device_id": device_id,
                "command": command,
                "snapshot_id": snapshot_id
            }
            
            try:
                # Meminta agen untuk menjalankan perintah snapshot asinkron (Time to Live: 15s)
                msg = await self.nc.request(
                    f"agent.execute.{device_id}",
                    json.dumps(req).encode(),
                    timeout=15.0
                )
                resp = json.loads(msg.data.decode())
                
                if resp.get("error"):
                    logger.error(f"[SNAPSHOT] Error mengambil snapshot {comp}: {resp.get('error')}")
                    snapshot_data[comp] = {"status": "ERROR", "data": resp.get('error')}
                    is_success = False
                else:
                    # Menyimpan dump riil dari agent
                    snapshot_data[comp] = {"status": "SUCCESS", "data": resp.get("output", "")}
            except asyncio.TimeoutError:
                logger.error(f"[SNAPSHOT] Timeout dari perangkat {device_id} untuk komponen {comp}")
                snapshot_data[comp] = {"status": "TIMEOUT", "data": ""}
                is_success = False

        self._save_to_db(snapshot_id, device_id, os_type, snapshot_data)
        
        return {
            "snapshot_id": snapshot_id,
            "device_id": device_id,
            "success": is_success,
            "data_keys": list(snapshot_data.keys())
        }

    def _build_snapshot_command(self, os_type: str, component: str) -> str:
        """Menghasilkan command native OS untuk menarik state (Zero-Mock)"""
        if os_type == "linux":
            if component == "iptables":
                return "iptables-save"
            elif component == "network":
                return "ip route show && ip addr show"
            elif component == "services":
                return "systemctl list-units --type=service --state=running"
        elif os_type == "windows":
            if component == "registry_network":
                return "reg query HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters /s"
            elif component == "firewall":
                return "netsh advfirewall export firewall_backup.wfw"
        return ""

    def _save_to_db(self, snap_id, device_id, os_type, data):
        try:
            with self._conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS state_snapshots (
                        snapshot_id UUID PRIMARY KEY,
                        device_id TEXT,
                        os_type TEXT,
                        snapshot_data JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cur.execute("""
                    INSERT INTO state_snapshots (snapshot_id, device_id, os_type, snapshot_data)
                    VALUES (%s, %s, %s, %s)
                """, (snap_id, device_id, os_type, json.dumps(data)))
            self._conn.commit()
            logger.info(f"[SNAPSHOT] Real state berhasil disimpan di DB: {snap_id}")
        except Exception as e:
            logger.error(f"[SNAPSHOT] Gagal menyimpan ke database: {e}")
            self._conn.rollback()

async def daemon():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    import nats as nats_lib
    nc = await nats_lib.connect(NATS_URL)
    engine = RollbackSnapshotEngine(nc)
    
    async def handle_snapshot_request(msg):
        try:
            payload = json.loads(msg.data.decode())
            logger.info(f"[SNAPSHOT] Menerima request: {payload}")
            result = await engine.take_snapshot(payload)
            await nc.publish(msg.reply, json.dumps(result).encode())
        except Exception as e:
            logger.error(f"[SNAPSHOT] Handler error: {e}")

    await nc.subscribe("remediation.snapshot.request", cb=handle_snapshot_request)
    logger.info("[SNAPSHOT] Tersambung ke NATS. Engine siap (No-Mock Mode)...")
    
    while True:
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(daemon())
