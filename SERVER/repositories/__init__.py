"""
SERVER.repositories Domain Package
Repository Pattern + Unit of Work + Concrete Persistence Implementations (PostgreSQL, pgvector, Redis).
ZERO SQL in business logic — all data access passes strictly through these interfaces.
"""
from SERVER.repositories.base_repository import BaseRepository
from SERVER.repositories.unit_of_work import UnitOfWork
from SERVER.repositories.incident_repository import IncidentRepository
from SERVER.repositories.knowledge_repository import KnowledgeEntityRepository
from SERVER.repositories.memory_repository import MemoryEntityRepository
from SERVER.repositories.audit_repository import AuditRepository
from SERVER.repositories.vector_repository import VectorRepository
from SERVER.repositories.postgres_impl.postgres_incident_repo import PostgresIncidentRepository
from SERVER.repositories.postgres_impl.pgvector_knowledge_repo import PgVectorRepository
from SERVER.repositories.postgres_impl.redis_state_repo import RedisStateManager
from SERVER.repositories.postgres_impl.postgres_unit_of_work import PostgresUnitOfWork

__all__ = [
    "BaseRepository", "UnitOfWork",
    "IncidentRepository", "KnowledgeEntityRepository",
    "MemoryEntityRepository", "AuditRepository", "VectorRepository",
    "PostgresIncidentRepository", "PgVectorRepository",
    "RedisStateManager", "PostgresUnitOfWork",
]
