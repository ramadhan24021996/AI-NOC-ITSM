from enum import Enum
from abc import ABC, abstractmethod
from typing import Dict, Any

class AuditEvent(Enum):
    LEARNING_STARTED = "Learning Started"
    LEARNING_FINISHED = "Learning Finished"
    EVALUATION_STARTED = "Evaluation Started"
    EVALUATION_FINISHED = "Evaluation Finished"
    FEATURE_CREATED = "Feature Created"
    FEATURE_UPDATED = "Feature Updated"
    MODEL_REGISTERED = "Model Registered"
    MODEL_DEPRECATED = "Model Deprecated"

class IAuditLogger(ABC):
    @abstractmethod
    def log(self, event: AuditEvent, details: Dict[str, Any]) -> None:
        raise NotImplementedError("LF-1 Framework: log not implemented")
