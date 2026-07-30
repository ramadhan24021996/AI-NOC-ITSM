"""
supervisor/core.py
------------------
AI Supervisor Core — Lifecycle, Runtime State Manager, & Utility Helpers.
Dipecah dari ai_supervisor.py untuk isolasi tanggung jawab.
"""
import logging
import json
import os
from datetime import datetime, timezone

logger = logging.getLogger("AI_SUPERVISOR.core")

NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")

# ── Runtime State Manager ─────────────────────────────────────────────────────
try:
    from runtime.ai_runtime_state import AIRuntimeState, RuntimeState
    _ai_runtime = AIRuntimeState("ai_supervisor")
    logger.info("[AI OS] Runtime State Manager initialized.")
except Exception as _rt_err:
    _ai_runtime = None
    logger.warning("[AI OS] Runtime State Manager unavailable (graceful fallback): %s", _rt_err)


def set_runtime_state(state_str: str):
    """Safely set AI runtime state without crashing the supervisor."""
    if _ai_runtime is None:
        return
    try:
        _ai_runtime.set_state(RuntimeState(state_str))
        _ai_runtime.heartbeat()
    except Exception as _se:
        logger.debug("[AI OS] State transition skipped: %s", _se)


# ── Utility Helpers ───────────────────────────────────────────────────────────

def parse_rfc3339_or_unix(ts_str) -> float:
    """Parse timestamp string (RFC3339 or unix float) → float epoch."""
    if not ts_str:
        return 0.0
    ts_str = str(ts_str).strip()
    try:
        return float(ts_str)
    except ValueError:
        pass
    try:
        if ts_str.endswith('Z'):
            ts_str = ts_str[:-1] + '+00:00'
        dt = datetime.fromisoformat(ts_str)
        return dt.timestamp()
    except Exception:
        return 0.0


def get_active_recovery_mode(conn) -> str:
    """Load active recovery mode from DB. Falls back to 'HITL'."""
    if not conn:
        return "HITL"
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT config_data FROM config_versions WHERE is_active = TRUE LIMIT 1")
            row = cur.fetchone()
            if row and row[0]:
                cfg_data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                mode = cfg_data.get("recovery_mode", "HITL")
                if mode == "Semi-Auto":
                    return "HITL"
                if mode == "Auto":
                    return "Autonomous"
                return mode
            cur.execute("SELECT auto_rollback FROM recovery_mode_policy WHERE id = 1")
            row = cur.fetchone()
            if row:
                return "Autonomous" if bool(row[0]) else "HITL"
    except Exception as e:
        logger.warning(f"Failed to load active recovery mode from DB: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
    return "HITL"


def get_active_consensus_pattern(conn) -> str:
    """Load active consensus pattern from DB. Falls back to 'WEIGHTED CONFIDENCE'."""
    if not conn:
        return "WEIGHTED CONFIDENCE"
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT config_data FROM config_versions WHERE is_active = TRUE LIMIT 1")
            row = cur.fetchone()
            if row and row[0]:
                cfg_data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                return cfg_data.get("consensus_pattern", "WEIGHTED CONFIDENCE").upper()
    except Exception as e:
        logger.warning(f"Failed to load active consensus pattern from DB: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
    return "WEIGHTED CONFIDENCE"
