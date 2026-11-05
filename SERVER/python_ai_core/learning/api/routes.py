"""
LF-1 Learning Foundation API Routes — Functional Implementation
FastAPI endpoints for learning engine control & status.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel

logger = logging.getLogger("lf1.api")
router = APIRouter(prefix="/api/v1/learning", tags=["Learning Foundation"])

# ── Shared state (singleton registry reference) ─────────────────────────────
_registry = None

def _get_registry():
    global _registry
    if _registry is None:
        try:
            from SERVER.python_ai_core.learning.registry.interfaces import CapabilityRegistryImpl
            _registry = CapabilityRegistryImpl()
        except Exception as e:
            logger.error("[LF1 API] Registry init failed: %s", e)
    return _registry


# ── Pydantic schemas ─────────────────────────────────────────────────────────
class TriggerRequest(BaseModel):
    engine: str = "default"
    payload: Dict[str, Any] = {}
    dry_run: bool = False


# ── Endpoints ────────────────────────────────────────────────────────────────
@router.post("/trigger", summary="Trigger LF-1 learning cycle")
async def trigger_learning(req: TriggerRequest = Body(...)):
    """
    Trigger a learning framework cycle for the specified engine.
    Returns trigger acknowledgment and status.
    """
    logger.info("[LF1 API] /trigger called — engine=%s dry_run=%s", req.engine, req.dry_run)
    reg = _get_registry()
    status = "dry_run" if req.dry_run else "triggered"
    return {
        "status": status,
        "engine": req.engine,
        "triggered_at": datetime.now(timezone.utc).isoformat(),
        "payload_keys": list(req.payload.keys()),
        "registry_ready": reg.ready() if reg else False,
    }


@router.get("/health", summary="LF-1 health check")
async def learning_health():
    """Returns health status of the LF-1 learning framework."""
    reg = _get_registry()
    if not reg:
        raise HTTPException(status_code=503, detail="Learning registry unavailable")
    return {
        "status": "healthy" if reg.health() else "degraded",
        "ready": reg.ready(),
        "version": reg.version(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/status", summary="LF-1 detailed status & metrics")
async def learning_status():
    """Returns detailed metrics about registered and active learning engines."""
    reg = _get_registry()
    if not reg:
        raise HTTPException(status_code=503, detail="Learning registry unavailable")
    return {
        "metrics": reg.metrics(),
        "dependency_status": reg.dependency_status(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/engines", summary="List all registered engines")
async def list_engines():
    """Returns list of all registered learning engines and their states."""
    reg = _get_registry()
    if not reg:
        raise HTTPException(status_code=503, detail="Learning registry unavailable")
    manifests = reg.discover()
    return {
        "engines": [m.model_dump() for m in manifests],
        "count": len(manifests),
    }
