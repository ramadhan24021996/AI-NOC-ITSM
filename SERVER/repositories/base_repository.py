"""
SERVER.repositories - Base Repository & Unit of Work Interface
Abstract base repository for data access abstraction.
"""
import os
import json
import logging
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, List, Optional, Any, Dict

import psycopg2
from SERVER.shared.db_pool import PGConnection, get_redis
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)
T = TypeVar("T")


class BaseRepository(ABC, Generic[T]):
    """Abstract generic repository interface for data access abstraction."""

    @abstractmethod
    def get_by_id(self, entity_id: str) -> Optional[T]:
        pass

    @abstractmethod
    def get_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        pass

    @abstractmethod
    def add(self, entity: T) -> T:
        pass

    @abstractmethod
    def update(self, entity_id: str, updates: Dict[str, Any]) -> Optional[T]:
        pass

    @abstractmethod
    def delete(self, entity_id: str) -> bool:
        pass


# ── Concrete PostgreSQL Base Implementation ────────────────────────────────────

class PostgreSQLBaseRepository(BaseRepository[Dict[str, Any]]):
    """
    Concrete base repository using PostgreSQL + psycopg2.
    Subclasses must define:
      - _table_name: str
      - _id_column: str (default 'id')
    """
    _table_name: str = ""
    _id_column: str = "id"

    def __init__(self):
        self._conn_params = {
            "host":     os.getenv("DB_HOST", "127.0.0.1"),
            "port":     int(os.getenv("DB_PORT", 5432)),
            "dbname":   os.getenv("DB_NAME", "osi_system"),
            "user":     os.getenv("DB_USER", "postgres"),
            "password": os.environ.get("DB_PASSWORD", ""),
        }

    def _connect(self):
        return PGConnection()

    def get_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        f"SELECT * FROM {self._table_name} WHERE {self._id_column} = %s LIMIT 1",
                        (entity_id,)
                    )
                    row = cur.fetchone()
                    return dict(row) if row else None
        except Exception as e:
            logger.error("[%s] get_by_id(%s) failed: %s", self.__class__.__name__, entity_id, e, exc_info=True)
            return None

    def get_all(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        f"SELECT * FROM {self._table_name} ORDER BY {self._id_column} LIMIT %s OFFSET %s",
                        (limit, offset)
                    )
                    return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error("[%s] get_all failed: %s", self.__class__.__name__, e, exc_info=True)
            return []

    def add(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        if not entity:
            return entity
        columns = ", ".join(entity.keys())
        placeholders = ", ".join(["%s"] * len(entity))
        values = list(entity.values())
        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        f"INSERT INTO {self._table_name} ({columns}) VALUES ({placeholders}) RETURNING *",
                        values
                    )
                    conn.commit()
                    row = cur.fetchone()
                    return dict(row) if row else entity
        except Exception as e:
            logger.error("[%s] add failed: %s", self.__class__.__name__, e, exc_info=True)
            return entity

    def update(self, entity_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not updates:
            return None
        set_clause = ", ".join([f"{k} = %s" for k in updates.keys()])
        values = list(updates.values()) + [entity_id]
        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        f"UPDATE {self._table_name} SET {set_clause} WHERE {self._id_column} = %s RETURNING *",
                        values
                    )
                    conn.commit()
                    row = cur.fetchone()
                    return dict(row) if row else None
        except Exception as e:
            logger.error("[%s] update(%s) failed: %s", self.__class__.__name__, entity_id, e, exc_info=True)
            return None

    def delete(self, entity_id: str) -> bool:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"DELETE FROM {self._table_name} WHERE {self._id_column} = %s",
                        (entity_id,)
                    )
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            logger.error("[%s] delete(%s) failed: %s", self.__class__.__name__, entity_id, e, exc_info=True)
            return False

