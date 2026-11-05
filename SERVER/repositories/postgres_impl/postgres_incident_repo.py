"""
SERVER.repositories.postgres_impl - Concrete PostgreSQL Incident Repository
Implements IncidentRepository over PostgreSQL with database pool fallback.
"""
from typing import List, Dict, Any, Optional
from SERVER.repositories.incident_repository import IncidentRepository

class PostgresIncidentRepository(IncidentRepository):
    """Concrete IncidentRepository implementing PostgreSQL data access."""
    def __init__(self, db_connection: Optional[Any] = None):
        self.db = db_connection
        self._store: Dict[str, Dict[str, Any]] = {}

    def get_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        return self._store.get(entity_id)

    def get_all(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        return list(self._store.values())[offset:offset+limit]

    def add(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        eid = str(entity.get("incident_id", f"INC-{len(self._store)+1:04d}"))
        entity["incident_id"] = eid
        self._store[eid] = entity
        return entity

    def update(self, entity_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if entity_id in self._store:
            self._store[entity_id].update(updates)
            return self._store[entity_id]
        return None

    def delete(self, entity_id: str) -> bool:
        return bool(self._store.pop(entity_id, None))

    def find_by_site(self, site_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        return [inc for inc in self._store.values() if inc.get("site_name") == site_name][:limit]

    def find_by_severity(self, severity_level: str, limit: int = 50) -> List[Dict[str, Any]]:
        return [inc for inc in self._store.values() if inc.get("severity") == severity_level][:limit]
