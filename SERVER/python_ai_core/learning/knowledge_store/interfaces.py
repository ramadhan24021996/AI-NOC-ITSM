from abc import ABC, abstractmethod
from typing import Dict, Any, List

class IKnowledgeStore(ABC):
    @abstractmethod
    def add_document(self, doc_id: str, content: str, metadata: Dict[str, Any]) -> bool:
        raise NotImplementedError("LF-1 Framework: add_document not implemented")

    @abstractmethod
    def update_document(self, doc_id: str, content: str) -> bool:
        raise NotImplementedError("LF-1 Framework: update_document not implemented")

    @abstractmethod
    def archive_document(self, doc_id: str) -> bool:
        raise NotImplementedError("LF-1 Framework: archive_document not implemented")

    @abstractmethod
    def search(self, query: str) -> List[Dict[str, Any]]:
        raise NotImplementedError("LF-1 Framework: search not implemented")

    @abstractmethod
    def version(self, doc_id: str) -> str:
        raise NotImplementedError("LF-1 Framework: version not implemented")
