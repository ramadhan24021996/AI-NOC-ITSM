"""
SERVER.compatibility - Legacy Repositories Adapter Bridge
Provides fallback wrapper so legacy python_ai_core modules can execute queries via clean SERVER.repositories interfaces.
"""
from typing import Dict, Any, List, Optional
from SERVER.repositories import IncidentRepository, KnowledgeEntityRepository, MemoryEntityRepository

class LegacyRepositoryBridge:
    """Temporary bridge mapping legacy query dictionaries to clean Repository interfaces."""

    def __init__(
        self,
        incident_repo: Optional[IncidentRepository] = None,
        knowledge_repo: Optional[KnowledgeEntityRepository] = None,
        memory_repo: Optional[MemoryEntityRepository] = None,
    ):
        self.incident_repo = incident_repo
        self.knowledge_repo = knowledge_repo
        self.memory_repo = memory_repo

    def legacy_search_incidents(self, filter_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
        site = filter_dict.get("site", filter_dict.get("site_name", ""))
        severity = filter_dict.get("severity", "")
        if self.incident_repo:
            if site:
                return self.incident_repo.find_by_site(site)
            if severity:
                return self.incident_repo.find_by_severity(severity)
            return self.incident_repo.get_all()
        return []
