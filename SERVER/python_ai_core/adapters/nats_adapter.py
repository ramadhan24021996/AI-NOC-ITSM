import asyncio
import logging
import nats
from nats.js.api import ConsumerConfig, AckPolicy, DeliverPolicy

logger = logging.getLogger("NATS_ADAPTER")

class JetStreamAdapter:
    def __init__(self, js):
        self.js = js
        self.active_subscriptions = {}
        
    async def add_stream(self, name, subjects):
        return await self.js.add_stream(name=name, subjects=subjects)
        
    async def update_stream(self, name, subjects):
        return await self.js.update_stream(name=name, subjects=subjects)
        
    async def subscribe(self, subject, durable=None, config=None, cb=None):
        if durable in self.active_subscriptions:
            return self.active_subscriptions[durable]
        sub = await self.js.subscribe(subject, durable=durable, config=config, cb=cb)
        if durable:
            self.active_subscriptions[durable] = sub
        return sub

class NATSAdapter:
    def __init__(self, nats_url: str):
        self.nats_url = nats_url
        self.nc = None
        self._js_adapter = None
    
    async def connect(self):
        try:
            from core.ha_manager import get_nats_ha_servers
            try:
                nats_servers = get_nats_ha_servers(self.nats_url)
            except Exception:
                nats_servers = [self.nats_url]
            
            self.nc = await nats.connect(
                servers=nats_servers, 
                max_reconnect_attempts=10, 
                reconnect_time_wait=3
            )
            self._js_adapter = JetStreamAdapter(self.nc.jetstream())
            logger.info(f"[NATS_ADAPTER] Connected successfully to {self.nats_url}")
            return self
        except Exception as e:
            logger.error(f"[NATS_ADAPTER] Connection failed: {e}")
            raise e

    def jetstream(self):
        if not self._js_adapter:
            raise RuntimeError("NATSAdapter not connected.")
        return self._js_adapter

    async def publish(self, subject: str, payload: bytes):
        if not self.nc:
            raise RuntimeError("NATSAdapter not connected.")
        return await self.nc.publish(subject, payload)
        
    async def request(self, subject: str, payload: bytes, timeout: float = 2.0):
        if not self.nc:
            raise RuntimeError("NATSAdapter not connected.")
        return await self.nc.request(subject, payload, timeout=timeout)
        
    async def subscribe(self, subject: str, queue: str = "", cb=None):
        if not self.nc:
            raise RuntimeError("NATSAdapter not connected.")
        return await self.nc.subscribe(subject, queue=queue, cb=cb)

    async def close(self):
        if self.nc and not self.nc.is_closed:
            await self.nc.drain()
            await self.nc.close()
            logger.info("[NATS_ADAPTER] NATS connection closed.")
