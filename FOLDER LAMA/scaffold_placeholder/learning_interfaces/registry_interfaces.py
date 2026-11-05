from abc import ABC, abstractmethod
from typing import Dict, Any, List
from enum import Enum
from pydantic import BaseModel

class CapabilityState(Enum):
    REGISTERED = "REGISTERED"
    INSTALLED = "INSTALLED"
    VALIDATED = "VALIDATED"
    READY = "READY"
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    ARCHIVED = "ARCHIVED"

class CapabilityManifest(BaseModel):
    engine: str
    version: str
    status: str
    dependencies: List[str]
    requires: List[str]
    provides: List[str]
    owner: str
    api_version: str
    schema_version: int

class IHealthContract(ABC):
    @abstractmethod
    def health(self) -> bool:
        raise NotImplementedError
    @abstractmethod
    def ready(self) -> bool:
        raise NotImplementedError
    @abstractmethod
    def version(self) -> str:
        raise NotImplementedError
    @abstractmethod
    def dependency_status(self) -> Dict[str, bool]:
        raise NotImplementedError
    @abstractmethod
    def metrics(self) -> Dict[str, Any]:
        raise NotImplementedError

class IPluginLoader(ABC):
    @abstractmethod
    def discover(self) -> List[CapabilityManifest]:
        raise NotImplementedError
    @abstractmethod
    def load(self, engine_name: str) -> bool:
        raise NotImplementedError
    @abstractmethod
    def validate(self, manifest: CapabilityManifest) -> bool:
        raise NotImplementedError
    @abstractmethod
    def activate(self, engine_name: str) -> bool:
        raise NotImplementedError

class IRegistry(IPluginLoader, ABC):
    @abstractmethod
    def check_compatibility(self, manifest: CapabilityManifest) -> bool:
        raise NotImplementedError
