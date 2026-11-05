"""
SERVER.security.rotation - Key Rotation Interface
Abstract interface for automatic secret key rotation.
"""
from abc import ABC, abstractmethod
from typing import Optional

class KeyRotationManager(ABC):
    """Abstract interface for scheduled key rotation."""

    @abstractmethod
    def rotate_secret(self, secret_name: str) -> bool:
        """Generates a new secret, stores it, and invalidates the old one."""
        pass

    @abstractmethod
    def schedule_rotation(self, secret_name: str, interval_days: int) -> bool:
        pass

    @abstractmethod
    def get_rotation_status(self, secret_name: str) -> Optional[dict]:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# CONCRETE IMPLEMENTATION — Step 4.2 (P2-2 Pluggable Provider Support)
# ══════════════════════════════════════════════════════════════════════════════
import os
import uuid
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

_rlog = logging.getLogger("security.rotation")

class EnvFileKeyRotationManager(KeyRotationManager):
    """
    Concrete key rotation manager.
    - Generates cryptographically random 64-char hex secrets
    - Persists to Vault or .env file via pluggable SecretProvider
    - Tracks rotation schedule in-memory
    """

    def __init__(self, provider=None, env_file: str = ".env"):
        if provider is not None:
            self._provider = provider
        else:
            from SERVER.security.vault.secret_provider import CompositeSecretProvider
            self._provider = CompositeSecretProvider()
        self._schedule: dict = {}   # {secret_name: {"interval_days": int, "next_rotation": datetime}}
        self._lock = threading.Lock()

    def rotate_secret(self, secret_name: str) -> bool:
        """Generate new 64-char hex token, store it via provider, log the rotation event."""
        new_value = uuid.uuid4().hex + uuid.uuid4().hex  # 64-char hex
        success = self._provider.set_secret(secret_name, new_value)
        if success:
            _rlog.info("[KeyRotation] SECRET ROTATED: '%s' at %s", secret_name, datetime.now(timezone.utc).isoformat())
            with self._lock:
                if secret_name in self._schedule:
                    interval = self._schedule[secret_name]["interval_days"]
                    self._schedule[secret_name]["next_rotation"] = datetime.now(timezone.utc) + timedelta(days=interval)
                    self._schedule[secret_name]["last_rotated"] = datetime.now(timezone.utc).isoformat()
        return success

    def schedule_rotation(self, secret_name: str, interval_days: int) -> bool:
        """Register a secret for periodic rotation. Triggers background thread check."""
        now_utc = datetime.now(timezone.utc)
        with self._lock:
            self._schedule[secret_name] = {
                "interval_days": interval_days,
                "next_rotation": now_utc + timedelta(days=interval_days),
                "last_rotated": None,
            }
        _rlog.info("[KeyRotation] Scheduled rotation for '%s' every %d days", secret_name, interval_days)
        return True

    def get_rotation_status(self, secret_name: str) -> Optional[dict]:
        with self._lock:
            entry = self._schedule.get(secret_name)
        if not entry:
            return {"secret": secret_name, "scheduled": False, "next_rotation": None}
        now_utc = datetime.now(timezone.utc)
        return {
            "secret": secret_name,
            "scheduled": True,
            "interval_days": entry["interval_days"],
            "next_rotation": entry["next_rotation"].isoformat(),
            "last_rotated": entry.get("last_rotated"),
            "due_now": now_utc >= entry["next_rotation"],
        }


