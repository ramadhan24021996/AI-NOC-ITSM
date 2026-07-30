"""
supervisor/nats_bridge.py
--------------------------
AI Supervisor NATS Bridge — Connection, Subscribe, Publish.
Terisolasi dari logika bisnis agar jika NATS disconnect, hanya bridge ini
yang perlu direstart, bukan seluruh supervisor.
"""
import logging
import json
import os
from typing import Callable, Optional

logger = logging.getLogger("AI_SUPERVISOR.nats_bridge")

NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")


class NATSBridge:
    """
    Wrapper terisolasi untuk koneksi NATS.
    - Menangani connect / disconnect / reconnect
    - Menyediakan metode subscribe dan publish dengan error handling
    """

    def __init__(self):
        self.nc = None
        self.js = None

    async def connect(self):
        """Buat koneksi ke NATS server via NATSAdapter."""
        from adapters.nats_adapter import NATSAdapter
        adapter = NATSAdapter(NATS_URL)
        self.nc = await adapter.connect()
        self.js = self.nc.jetstream()
        logger.info(f"[NATS_BRIDGE] Terhubung ke {NATS_URL}")
        return self.nc

    async def ensure_stream(self, name: str, subjects: list):
        """Buat atau update JetStream stream dengan subjects yang diberikan."""
        try:
            await self.js.add_stream(name=name, subjects=subjects)
            logger.info(f"[NATS_BRIDGE] Stream '{name}' berhasil dibuat.")
        except Exception:
            try:
                await self.js.update_stream(name=name, subjects=subjects)
                logger.info(f"[NATS_BRIDGE] Stream '{name}' diperbarui.")
            except Exception as upd_err:
                logger.error(f"[NATS_BRIDGE] Gagal buat/update stream '{name}': {upd_err}")

    async def subscribe(self, subject: str, handler: Callable, queue: Optional[str] = None):
        """Subscribe ke NATS subject dengan handler function."""
        try:
            if queue:
                await self.nc.subscribe(subject, queue=queue, cb=handler)
            else:
                await self.nc.subscribe(subject, cb=handler)
            logger.info(f"[NATS_BRIDGE] Subscribed ke subject: {subject}")
        except Exception as e:
            logger.error(f"[NATS_BRIDGE] Gagal subscribe ke '{subject}': {e}")

    async def publish(self, subject: str, data: dict):
        """Publish pesan JSON ke NATS subject dengan error boundary."""
        try:
            payload = json.dumps(data).encode()
            await self.nc.publish(subject, payload)
        except Exception as e:
            logger.error(f"[NATS_BRIDGE] Gagal publish ke '{subject}': {e}")

    async def disconnect(self):
        """Tutup koneksi NATS dengan graceful drain."""
        if self.nc:
            try:
                await self.nc.drain()
                logger.info("[NATS_BRIDGE] Koneksi NATS ditutup (drain).")
            except Exception as e:
                logger.warning(f"[NATS_BRIDGE] Error saat drain NATS: {e}")
