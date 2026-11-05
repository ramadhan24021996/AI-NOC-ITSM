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
