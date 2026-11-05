from abc import ABC, abstractmethod
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
