"""
Enterprise Autonomous AI OS — Phase 8: Learning Plane
Simulation Engine

Tugas: Mengeksekusi Playbook atau skrip remediasi AI pada environment 
sebenarnya (via Agent) atau sandbox, tanpa menggunakan data mock atau dummy.
Engine terhubung langsung ke NATS dan PostgreSQL.
"""

import asyncio
import json
import logging
import os
import uuid
import datetime

logger = logging.getLogger("SIMULATION_ENGINE")

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

class SimulationEngine:
    def __init__(self, nc):
        self.nc = nc
        self._conn = _get_db()

    async def execute_simulation(self, task_payload: dict):
        """
        Menjalankan simulasi playbook secara live di sistem.
        DILARANG MENGGUNAKAN MOCK/DUMMY. Harus mengirim payload eksekusi ke agent target
        dan menunggu hasilnya.
        """
        target_device = task_payload.get("target_device", "sandbox_node")
        playbook_commands = task_payload.get("commands", [])
        simulation_id = str(uuid.uuid4())
        
        logger.info(f"[SIMULATION_ENGINE] Memulai simulasi {simulation_id} pada {target_device}")
        
        results = []
        is_success = True

        for cmd in playbook_commands:
            logger.info(f"[SIMULATION_ENGINE] Executing LIVE command: {cmd}")
            # Request eksekusi asinkron ke agent via NATS
            req_payload = {
                "device_id": target_device,
                "command": cmd,
                "simulation_id": simulation_id
            }
            try:
                # Menunggu respon riil dari agent
                msg = await self.nc.request(
                    f"agent.execute.{target_device}", 
                    json.dumps(req_payload).encode(), 
                    timeout=15.0
                )
                resp = json.loads(msg.data.decode())
                
                output = resp.get("output", "")
                error = resp.get("error", "")
                
                if error:
                    is_success = False
                    results.append({"command": cmd, "status": "FAILED", "output": error})
                    logger.error(f"[SIMULATION_ENGINE] Execution FAILED: {error}")
                    break
                else:
                    results.append({"command": cmd, "status": "SUCCESS", "output": output})
            except asyncio.TimeoutError:
                is_success = False
                results.append({"command": cmd, "status": "TIMEOUT", "output": "Agent did not respond"})
                logger.error(f"[SIMULATION_ENGINE] Execution TIMEOUT on command: {cmd}")
                break
        
        # Simpan bukti simulasi ke database untuk dianalisis oleh Knowledge Engine
        self.save_simulation_evidence(simulation_id, target_device, playbook_commands, results, is_success)
        return is_success, results

    def save_simulation_evidence(self, sim_id, target, commands, results, is_success):
        """Menyimpan hasil simulasi riil ke dalam sistem sebagai bukti otentik."""
        try:
            with self._conn.cursor() as cur:
                # Membuat tabel sementara jika tidak ada (Fase 8 Setup)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS learning_simulation_evidence (
                        simulation_id UUID PRIMARY KEY,
                        target_device TEXT,
                        commands JSONB,
                        results JSONB,
                        is_success BOOLEAN,
                        executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cur.execute("""
                    INSERT INTO learning_simulation_evidence 
                    (simulation_id, target_device, commands, results, is_success) 
                    VALUES (%s, %s, %s, %s, %s)
                """, (sim_id, target, json.dumps(commands), json.dumps(results), is_success))
            self._conn.commit()
            logger.info(f"[SIMULATION_ENGINE] Evidence disimpan. Sim ID: {sim_id}")
        except Exception as e:
            logger.error(f"[SIMULATION_ENGINE] Gagal menyimpan evidence: {e}")
            self._conn.rollback()

async def daemon():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    import nats as nats_lib
    nc = await nats_lib.connect(NATS_URL)
    engine = SimulationEngine(nc)
    
    async def message_handler(msg):
        try:
            payload = json.loads(msg.data.decode())
            logger.info(f"[SIMULATION_ENGINE] Menerima request simulasi: {payload}")
            success, results = await engine.execute_simulation(payload)
            
            # Balas respon
            await nc.publish(msg.reply, json.dumps({"success": success, "results": results}).encode())
        except Exception as e:
            logger.error(f"[SIMULATION_ENGINE] Error memproses pesan: {e}")

    await nc.subscribe("learning.simulation.request", cb=message_handler)
    logger.info("[SIMULATION_ENGINE] Tersambung ke NATS. Menunggu request simulasi (No-Mock Mode)...")
    
    while True:
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(daemon())
