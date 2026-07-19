from abc import ABC, abstractmethod
from typing import Dict, Any, List

class IFeatureRegistry(ABC):
    @abstractmethod
    def register_feature_metadata(self, metadata: Dict[str, Any]) -> bool:
        raise NotImplementedError
    @abstractmethod
    def get_feature_metadata(self, feature_id: str) -> Dict[str, Any]:
        raise NotImplementedError
