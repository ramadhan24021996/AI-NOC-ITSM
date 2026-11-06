"""
SERVER.shared.db_pool — Production-Grade Connection Pool Manager
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Provides:
  - PostgreSQL ThreadedConnectionPool (P0-2)
  - Redis singleton pool (P0-3)
  - statement_timeout enforcement (P0-4)

All implementations use this module — DO NOT call psycopg2.connect() directly.
"""
import os
import logging
import threading
from typing import Optional

import psycopg2
import psycopg2.pool
import redis as _redis

logger = logging.getLogger("shared.db_pool")

# ── Configuration ─────────────────────────────────────────────────────────────
_PG_MIN_CONN    = int(os.getenv("DB_POOL_MIN", 2))
_PG_MAX_CONN    = int(os.getenv("DB_POOL_MAX", 20))
_STMT_TIMEOUT   = int(os.getenv("DB_STMT_TIMEOUT_MS", 30000))  # 30s default

# ── PostgreSQL Connection Pool (P0-2 + P0-4) ──────────────────────────────────
_pg_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None
_pg_lock = threading.Lock()


def _build_pg_dsn() -> dict:
    return {
        "host":     os.getenv("DB_HOST", "127.0.0.1"),
        "port":     int(os.getenv("DB_PORT", 5432)),
        "dbname":   os.getenv("DB_NAME", "osi_system"),
        "user":     os.getenv("DB_USER", "postgres"),
        "password": os.environ.get("DB_PASSWORD") or "SecurePassword_123!",
        # P0-4: statement_timeout via options (applied to every connection in pool)
        "options":  f"-c statement_timeout={_STMT_TIMEOUT}",
        "connect_timeout": 5,
    }


def get_pg_pool() -> psycopg2.pool.ThreadedConnectionPool:
    """Return the shared PostgreSQL thread-safe connection pool (lazy init)."""
    global _pg_pool
    if _pg_pool is None:
        with _pg_lock:
            if _pg_pool is None:
                try:
                    _pg_pool = psycopg2.pool.ThreadedConnectionPool(
                        _PG_MIN_CONN, _PG_MAX_CONN, **_build_pg_dsn()
                    )
                    logger.info(
                        "[PGPool] Initialized ThreadedConnectionPool min=%d max=%d "
                        "statement_timeout=%dms",
                        _PG_MIN_CONN, _PG_MAX_CONN, _STMT_TIMEOUT
                    )
                except Exception as e:
                    logger.error("[PGPool] FAILED to create connection pool: %s", e, exc_info=True)
                    raise
    return _pg_pool


def get_db_connection() -> "_PooledConnectionProxy":
    """Return a pooled connection proxy. Calling conn.close() returns the connection back to the pool."""
    pool = get_pg_pool()
    raw_conn = pool.getconn()
    return _PooledConnectionProxy(pool, raw_conn)


class _PooledConnectionProxy:
    """
    Wraps a psycopg2 connection checked out from ThreadedConnectionPool so that:
      1. Calling conn.close() returns the connection to the pool instead of closing the socket.
      2. Garbage collection (__del__) returns any unreturned connection (e.g. from PGConnection().__enter__()) back to the pool.
    """
    def __init__(self, pool: psycopg2.pool.ThreadedConnectionPool, raw_conn):
        self._pool = pool
        self._raw_conn = raw_conn
        self._returned = False

    def _return_to_pool(self, rollback: bool = False):
        if not self._returned and self._raw_conn is not None:
            self._returned = True
            raw = self._raw_conn
            self._raw_conn = None
            try:
                if rollback and not getattr(raw, "closed", 1):
                    raw.rollback()
            except Exception:
                pass
            try:
                self._pool.putconn(raw)
            except Exception:
                pass

    def close(self):
        self._return_to_pool(rollback=False)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._return_to_pool(rollback=bool(exc_type))

    def __getattr__(self, name):
        if self._raw_conn is None:
            raise psycopg2.InterfaceError("Connection already returned to pool")
        return getattr(self._raw_conn, name)

    def __del__(self):
        self._return_to_pool(rollback=True)


class PGConnection:
    """
    Context manager for safe pool connection checkout/return.

    Usage:
        with PGConnection() as conn:
            with conn.cursor() as cur:
                cur.execute(...)
    """
    def __init__(self):
        self._pool = get_pg_pool()
        self._proxy: Optional[_PooledConnectionProxy] = None

    def __enter__(self):
        raw_conn = self._pool.getconn()
        self._proxy = _PooledConnectionProxy(self._pool, raw_conn)
        return self._proxy

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._proxy is not None:
            self._proxy._return_to_pool(rollback=bool(exc_type))
            self._proxy = None


# ── Redis Singleton Pool (P0-3) ───────────────────────────────────────────────
_redis_client: Optional[_redis.Redis] = None
_redis_lock = threading.Lock()


def get_redis() -> _redis.Redis:
    """
    Return singleton Redis client backed by connection pool.
    Thread-safe — safe to call from multiple threads.
    """
    global _redis_client
    if _redis_client is None:
        with _redis_lock:
            if _redis_client is None:
                _redis_client = _redis.Redis(
                    host=os.getenv("REDIS_HOST", "redis"),
                    port=int(os.getenv("REDIS_PORT", 6379)),
                    password=os.environ.get("REDIS_PASSWORD", "") or None,
                    decode_responses=True,
                    socket_timeout=3,
                    socket_connect_timeout=3,
                    # retry_on_timeout removed — deprecated in redis-py v6;
                    # TimeoutError is retried by default in v6+
                    max_connections=int(os.getenv("REDIS_POOL_MAX", 50)),
                )
                logger.info("[RedisPool] Singleton Redis client initialized pool max=%s",
                            os.getenv("REDIS_POOL_MAX", 50))
    return _redis_client


def close_all():
    """Gracefully close all connections. Call at application shutdown."""
    global _pg_pool, _redis_client
    if _pg_pool:
        try:
            _pg_pool.closeall()
            logger.info("[PGPool] All connections closed.")
        except Exception as e:
            logger.error("[PGPool] Error closing pool: %s", e)
        _pg_pool = None
    if _redis_client:
        try:
            _redis_client.close()
            logger.info("[RedisPool] Redis client closed.")
        except Exception as e:
            logger.error("[RedisPool] Error closing client: %s", e)
        _redis_client = None
