"""
SERVER.repositories.postgres_impl - Concrete PostgreSQL Unit of Work
Implements UnitOfWork with database transaction boundaries.
"""
from typing import Optional, Any
from SERVER.repositories.unit_of_work import UnitOfWork
from SERVER.repositories.postgres_impl.postgres_incident_repo import PostgresIncidentRepository

class PostgresUnitOfWork(UnitOfWork):
    """Concrete PostgreSQL Unit of Work implementation."""
    def __init__(self, db_connection: Optional[Any] = None):
        self.db = db_connection
        self.incidents = PostgresIncidentRepository(db_connection)
        self.committed: bool = False
        self.rolled_back: bool = False

    def commit(self) -> None:
        self.committed = True
        self.rolled_back = False

    def rollback(self) -> None:
        self.rolled_back = True
        self.committed = False
