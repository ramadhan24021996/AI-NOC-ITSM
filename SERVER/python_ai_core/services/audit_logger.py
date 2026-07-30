"""
OSI Incident Ops Hardening v3.0
Audit Logger Helper for Python services
Mirrors the GORM SHA-256 block-chaining audit log.
"""
import hashlib
import json
import logging
import os
import psycopg2

logger = logging.getLogger("AUDIT_LOGGER")

DB_HOST     = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT     = os.getenv("DB_PORT", "5432")
DB_NAME     = os.getenv("DB_NAME", "osi_system")
DB_USER     = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

def get_db():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, database=DB_NAME,
        user=DB_USER, password=DB_PASSWORD
    )

def write_audit_log(action_type: str, actor: str, target: str, payload: dict, conn=None) -> str:
    """
    Writes a chained audit log entry.
    Returns the hash signature.
    """
    close_conn = False
    if conn is None:
        conn = get_db()
        close_conn = True

    try:
        payload_str = json.dumps(payload or {})
        with conn.cursor() as cur:
            # Get last hash
            cur.execute("SELECT hash_signature FROM immutable_audit_log ORDER BY log_id DESC LIMIT 1")
            row = cur.fetchone()
            prev_hash = row[0] if row else "0"

            # Compute hash
            data_to_hash = f"{prev_hash}|{action_type}|{actor}|{target}|{payload_str}"
            hash_sig = hashlib.sha256(data_to_hash.encode()).hexdigest()

            # Insert
            cur.execute("""
                INSERT INTO immutable_audit_log (action_type, actor, target, payload, prev_hash, hash_signature, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """, (action_type, actor, target, payload_str, prev_hash, hash_sig))

            if close_conn:
                conn.commit()
            
            logger.info("[AUDIT] Logged: %s | actor=%s | target=%s | hash=%s", action_type, actor, target, hash_sig[:8])
            return hash_sig
    except Exception as e:
        logger.error("[AUDIT] Failed to write audit log: %s", e)
        if close_conn and conn:
            conn.rollback()
        raise
    finally:
        if close_conn and conn:
            conn.close()
