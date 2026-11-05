"""
LF-2 Feature Store API Routes — Functional Implementation
FastAPI CRUD endpoints for feature management.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Body, Path
from pydantic import BaseModel

logger = logging.getLogger("lf2.feature_api")
router = APIRouter(prefix="/api/v1/features", tags=["Feature Store"])

# ── Shared registry ──────────────────────────────────────────────────────────
_registry = None
_validator = None

def _get_registry():
    global _registry
    if _registry is None:
        from SERVER.python_ai_core.learning.feature_store.registry.interfaces import InMemoryFeatureRegistry
        _registry = InMemoryFeatureRegistry()
    return _registry

def _get_validator():
    global _validator
    if _validator is None:
        from SERVER.python_ai_core.learning.feature_store.validators.interfaces import DefaultFeatureValidator
        _validator = DefaultFeatureValidator()
    return _validator


# ── Pydantic schemas ─────────────────────────────────────────────────────────
class FeatureCreate(BaseModel):
    feature_id: str
    name: str
    value: Any
    data_type: str = "float"
    tenant_id: str = "default"
    quality_score: Optional[float] = None
    metadata: Dict[str, Any] = {}


# ── Endpoints ────────────────────────────────────────────────────────────────
@router.post("", summary="Register a new feature")
async def create_feature(req: FeatureCreate = Body(...)):
    payload = req.model_dump()
    validator = _get_validator()
    if not validator.validate_schema(payload):
        raise HTTPException(status_code=422, detail="Feature schema validation failed")
    if not validator.validate_tenant_isolation(payload):
        raise HTTPException(status_code=403, detail="Tenant isolation validation failed")
    registry = _get_registry()
    metadata = {**req.metadata, "feature_id": req.feature_id, "name": req.name,
                "data_type": req.data_type, "tenant_id": req.tenant_id}
    success = registry.register_feature_metadata(metadata)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to register feature")
    return {"status": "created", "feature_id": req.feature_id,
            "registered_at": datetime.now(timezone.utc).isoformat()}


@router.get("", summary="List all registered features")
async def list_features(tenant_id: Optional[str] = None):
    registry = _get_registry()
    # InMemoryFeatureRegistry — expose internal store filtered by tenant
    store = getattr(registry, "_store", {})
    features = list(store.values())
    if tenant_id:
        features = [f for f in features if f.get("tenant_id") == tenant_id]
    return {"features": features, "count": len(features)}


@router.get("/search", summary="Search features by name or type")
async def search_features(q: str = "", data_type: Optional[str] = None):
    """Search features by name or type. MUST be registered before /{feature_id} route."""
    registry = _get_registry()
    store = getattr(registry, "_store", {})
    results = []
    for meta in store.values():
        if meta.get("archived"):
            continue
        name_match = q.lower() in meta.get("name", "").lower() or q.lower() in meta.get("feature_id", "").lower()
        type_match = not data_type or meta.get("data_type") == data_type
        if name_match and type_match:
            results.append(meta)
    return {"results": results, "count": len(results)}


@router.get("/{feature_id}", summary="Get feature by ID")
async def get_feature(feature_id: str = Path(...)):
    registry = _get_registry()
    meta = registry.get_feature_metadata(feature_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Feature '{feature_id}' not found")
    return meta


@router.put("/{feature_id}", summary="Update feature metadata")
async def update_feature(feature_id: str = Path(...), updates: Dict[str, Any] = Body(...)):
    registry = _get_registry()
    meta = registry.get_feature_metadata(feature_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Feature '{feature_id}' not found")
    meta.update(updates)
    meta["updated_at"] = datetime.now(timezone.utc).isoformat()
    registry.register_feature_metadata(meta)
    return {"status": "updated", "feature_id": feature_id}


@router.delete("/{feature_id}", summary="Soft-archive a feature")
async def archive_feature(feature_id: str = Path(...)):
    registry = _get_registry()
    meta = registry.get_feature_metadata(feature_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Feature '{feature_id}' not found")
    meta["archived"] = True
    meta["archived_at"] = datetime.now(timezone.utc).isoformat()
    registry.register_feature_metadata(meta)
    return {"status": "archived", "feature_id": feature_id}

