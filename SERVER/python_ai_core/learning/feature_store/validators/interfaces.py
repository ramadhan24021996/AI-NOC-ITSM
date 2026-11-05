from abc import ABC, abstractmethod
from typing import Dict, Any

class IFeatureValidator(ABC):
    @abstractmethod
    def validate_schema(self, payload: Dict[str, Any]) -> bool:
        raise NotImplementedError
    @abstractmethod
    def validate_tenant_isolation(self, payload: Dict[str, Any]) -> bool:
        raise NotImplementedError
    @abstractmethod
    def validate_checksum(self, payload: Dict[str, Any]) -> bool:
        raise NotImplementedError
    @abstractmethod
    def validate_quality_range(self, payload: Dict[str, Any]) -> bool:
        raise NotImplementedError


# ══════════════════════════════════════════════════════════════════════════════
# CONCRETE IMPLEMENTATION — Step 6.5
# ══════════════════════════════════════════════════════════════════════════════
import hashlib, json, logging
_fvlog = logging.getLogger("lf2.feature_validator")

REQUIRED_SCHEMA_KEYS = {"feature_id", "name", "value", "data_type", "tenant_id"}

class DefaultFeatureValidator(IFeatureValidator):
    """Validates feature payloads: schema, tenant isolation, checksum, quality range."""

    def validate_schema(self, payload: Dict[str, Any]) -> bool:
        missing = REQUIRED_SCHEMA_KEYS - set(payload.keys())
        if missing:
            _fvlog.warning("[FeatureValidator] Schema validation FAILED — missing keys: %s", missing)
            return False
        return True

    def validate_tenant_isolation(self, payload: Dict[str, Any]) -> bool:
        tenant = payload.get("tenant_id","")
        if not tenant or tenant.strip() == "":
            _fvlog.warning("[FeatureValidator] Tenant isolation FAILED — empty tenant_id")
            return False
        if "shared" in str(tenant).lower() or "global" in str(tenant).lower():
            _fvlog.warning("[FeatureValidator] Tenant isolation FAILED — forbidden tenant_id: %s", tenant)
            return False
        return True

    def validate_checksum(self, payload: Dict[str, Any]) -> bool:
        provided = payload.get("checksum","")
        data_str = json.dumps({k: v for k, v in sorted(payload.items()) if k != "checksum"}, default=str)
        computed = hashlib.md5(data_str.encode()).hexdigest()
        if provided and provided != computed:
            _fvlog.warning("[FeatureValidator] Checksum MISMATCH — provided=%s computed=%s", provided, computed)
            return False
        return True

    def validate_quality_range(self, payload: Dict[str, Any]) -> bool:
        val = payload.get("quality_score", payload.get("value", None))
        if val is None:
            return True
        try:
            fval = float(val)
            if not (0.0 <= fval <= 1.0):
                _fvlog.warning("[FeatureValidator] Quality out of range: %.4f", fval)
                return False
        except (ValueError, TypeError):
            pass
        return True
