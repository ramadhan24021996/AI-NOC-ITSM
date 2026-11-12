# ==============================================================================
# Fail-Closed Database Configuration Helper
# Enforces that DB_PASSWORD / POSTGRES_PASSWORD must be provided via environment.
# Zero hardcoded fallback passwords allowed.
# ==============================================================================
import os
import logging

logger = logging.getLogger("DB_CONFIG")


def get_db_password(fail_closed: bool = False) -> str:
    """
    Retrieves the database password from environment variables.
    If fail_closed is True and no password is set, raises RuntimeError.
    """
    password = (
        os.environ.get("DB_PASSWORD")
        or os.environ.get("POSTGRES_PASSWORD")
        or ""
    )
    if fail_closed and not password:
        raise RuntimeError(
            "[SECURITY ERROR] DB_PASSWORD / POSTGRES_PASSWORD environment variable is not configured! "
            "Fail-closed policy prevents connecting with empty credentials."
        )
    return password


def get_db_params(default_port: str = "5432", fail_closed: bool = False) -> dict:
    """
    Returns standard database connection parameters dictionary.
    """
    return {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": os.environ.get("DB_PORT", default_port),
        "database": os.environ.get("DB_NAME", "osi_system"),
        "user": os.environ.get("DB_USER", "postgres"),
        "password": get_db_password(fail_closed=fail_closed),
    }
