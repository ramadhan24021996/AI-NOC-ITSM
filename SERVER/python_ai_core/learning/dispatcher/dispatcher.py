import asyncio
from typing import Dict, Any
from .validators import validate_schema
from .adapters import V5ProtocolAdapter
from .routing import route_to_feature_store, route_to_remediation, route_to_infrastructure, route_to_temporal

class LearningDispatcher:
    def __init__(self):
        self.adapter = V5ProtocolAdapter()
        # Initialize NATS subscriber here...

    async def handle_telemetry(self, raw_payload: Dict[str, Any]):
        # 1. Replay Protection & Idempotency check happens here
        
        # 2. Adapt from V5 to V6 format
        v6_payload = self.adapter.adapt(raw_payload)
        
        # 3. Validate Schema
        if not validate_schema(v6_payload):
            return
            
        # 4. Asynchronous fan-out (Shadow listening - does not block main incident engine)
        asyncio.create_task(route_to_feature_store(v6_payload))
        asyncio.create_task(route_to_infrastructure(v6_payload))
        asyncio.create_task(route_to_temporal(v6_payload))
        
    async def handle_feedback(self, raw_payload: Dict[str, Any]):
        v6_payload = self.adapter.adapt(raw_payload)
        asyncio.create_task(route_to_remediation(v6_payload))\n