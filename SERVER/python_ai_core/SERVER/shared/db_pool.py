"""
Re-export shim for SERVER.shared.db_pool inside the python_ai_core container (/app).
Ensures that both `from shared.db_pool import ...` and `from SERVER.shared.db_pool import ...`
share the exact same singleton ThreadedConnectionPool and Redis pool without code duplication.
"""
from shared.db_pool import (  # noqa: F401
    _PG_MIN_CONN,
    _PG_MAX_CONN,
    _STMT_TIMEOUT,
    _build_pg_dsn,
    get_pg_pool,
    get_db_connection,
    _PooledConnectionProxy,
    PGConnection,
    get_redis,
    close_all,
)

__all__ = [
    "_PG_MIN_CONN",
    "_PG_MAX_CONN",
    "_STMT_TIMEOUT",
    "_build_pg_dsn",
    "get_pg_pool",
    "get_db_connection",
    "_PooledConnectionProxy",
    "PGConnection",
    "get_redis",
    "close_all",
]
