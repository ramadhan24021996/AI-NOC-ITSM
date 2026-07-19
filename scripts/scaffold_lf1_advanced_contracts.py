#!/usr/bin/env python3
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../SERVER/python_ai_core/learning'))

FILES = {
    "registry/interfaces.py": '''from abc import ABC, abstractmethod
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
''',
    "evaluator/interfaces.py": '''from abc import ABC, abstractmethod
from typing import Dict, Any

class IEvaluationContract(ABC):
    @abstractmethod
    def evaluate(self, payload: Dict[str, Any]) -> Dict[str, float]:
        raise NotImplementedError

    @abstractmethod
    def validate(self, payload: Dict[str, Any]) -> bool:
        raise NotImplementedError

    @abstractmethod
    def score(self, output: Dict[str, Any]) -> float:
        raise NotImplementedError
        
    @abstractmethod
    def benchmark(self) -> Dict[str, float]:
        raise NotImplementedError
        
    @abstractmethod
    def approve(self) -> bool:
        raise NotImplementedError
        
    @abstractmethod
    def reject(self) -> bool:
        raise NotImplementedError
''',
    "audit/schemas.py": '''from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class AuditLogSchema(BaseModel):
    correlation_id: str
    learning_id: str
    tenant_id: str
    engine: str
    evidence: str
    ground_truth: str
    decision: str
    confidence: float
    duration_ms: int
    timestamp: datetime
    version: str
'''
}

def build_advanced_scaffold():
    for rel_path, content in FILES.items():
        full_path = os.path.join(BASE_DIR, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w') as f:
            f.write(content)
        print(f"[+] Advanced Contract Injected: {rel_path}")

if __name__ == "__main__":
    build_advanced_scaffold()
