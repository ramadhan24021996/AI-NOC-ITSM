"""
SERVER.security.vault - Secret Provider Interface
Centralised secret resolution so business modules never read .env directly.
"""
from abc import ABC, abstractmethod
from typing import Optional

class SecretProvider(ABC):
    """Abstract Secret Provider. All modules resolve secrets through this interface only."""

    @abstractmethod
    def get_secret(self, secret_name: str) -> Optional[str]:
        """Retrieve a secret value by name. Returns None if not found."""
        pass

    @abstractmethod
    def set_secret(self, secret_name: str, value: str) -> bool:
        """Store or update a secret. Returns True on success."""
        pass

    @abstractmethod
    def delete_secret(self, secret_name: str) -> bool:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# CONCRETE IMPLEMENTATIONS — Step 4.1 (P2-2 Vault Adapter Support)
# ══════════════════════════════════════════════════════════════════════════════
import os
import json
import logging
import urllib.request
import urllib.error

try:
    from dotenv import dotenv_values
except ImportError:
    def dotenv_values(env_path: str = ".env") -> dict:
        vals = {}
        if not os.path.exists(env_path):
            return vals
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    vals[k.strip()] = v.strip().strip("'\"")
        except Exception:
            pass
        return vals

_slog = logging.getLogger("security.vault")

class EnvSecretProvider(SecretProvider):
    """
    Concrete secret provider backed by environment variables.
    Resolution order: OS env → .env file → None
    """
    def __init__(self, env_file: str = ".env"):
        self._env_file = env_file
        self._cache: dict = {}

    def _load(self) -> dict:
        """Load .env file values (does NOT override existing OS env vars)."""
        try:
            return dotenv_values(self._env_file)
        except Exception:
            return {}

    def get_secret(self, secret_name: str) -> Optional[str]:
        # 1. OS environment (highest priority)
        val = os.environ.get(secret_name)
        if val:
            return val
        # 2. .env file
        env_vals = self._load()
        val = env_vals.get(secret_name)
        if val:
            return val
        _slog.warning("[EnvSecretProvider] Secret '%s' not found in env or .env file", secret_name)
        return None

    def set_secret(self, secret_name: str, value: str) -> bool:
        """Writes secret to .env file. Does not override OS-level env vars."""
        try:
            env_vals = self._load()
            env_vals[secret_name] = value
            with open(self._env_file, "w") as f:
                for k, v in env_vals.items():
                    f.write(f"{k}={v}\n")
            _slog.info("[EnvSecretProvider] Secret '%s' updated in %s", secret_name, self._env_file)
            return True
        except Exception as e:
            _slog.error("[EnvSecretProvider] set_secret(%s) failed: %s", secret_name, e, exc_info=True)
            return False

    def delete_secret(self, secret_name: str) -> bool:
        try:
            env_vals = self._load()
            if secret_name not in env_vals:
                return False
            del env_vals[secret_name]
            with open(self._env_file, "w") as f:
                for k, v in env_vals.items():
                    f.write(f"{k}={v}\n")
            _slog.info("[EnvSecretProvider] Secret '%s' deleted from %s", secret_name, self._env_file)
            return True
        except Exception as e:
            _slog.error("[EnvSecretProvider] delete_secret(%s) failed: %s", secret_name, e, exc_info=True)
            return False


class VaultSecretProvider(SecretProvider):
    """
    HashiCorp Vault KV v2 secret provider via HTTP REST API.
    Falls back gracefully if Vault endpoint is unreachable.
    """
    def __init__(self, vault_addr: Optional[str] = None, vault_token: Optional[str] = None, mount_point: str = "secret"):
        self.vault_addr = (vault_addr or os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")).rstrip("/")
        self.vault_token = vault_token or os.getenv("VAULT_TOKEN", "")
        self.mount_point = mount_point

    def get_secret(self, secret_name: str) -> Optional[str]:
        if not self.vault_token:
            return None
        url = f"{self.vault_addr}/v1/{self.mount_point}/data/{secret_name}"
        req = urllib.request.Request(url, headers={"X-Vault-Token": self.vault_token})
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                return data.get("data", {}).get("data", {}).get("value")
        except Exception as e:
            _slog.warning("[VaultSecretProvider] Failed to fetch secret '%s' from Vault: %s", secret_name, e)
            return None

    def set_secret(self, secret_name: str, value: str) -> bool:
        if not self.vault_token:
            return False
        url = f"{self.vault_addr}/v1/{self.mount_point}/data/{secret_name}"
        payload = json.dumps({"data": {"value": value}}).encode()
        req = urllib.request.Request(url, data=payload, headers={"X-Vault-Token": self.vault_token, "Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status in (200, 204)
        except Exception as e:
            _slog.error("[VaultSecretProvider] Failed to set secret '%s' in Vault: %s", secret_name, e)
            return False

    def delete_secret(self, secret_name: str) -> bool:
        if not self.vault_token:
            return False
        url = f"{self.vault_addr}/v1/{self.mount_point}/metadata/{secret_name}"
        req = urllib.request.Request(url, headers={"X-Vault-Token": self.vault_token}, method="DELETE")
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status in (200, 204)
        except Exception as e:
            _slog.error("[VaultSecretProvider] Failed to delete secret '%s' in Vault: %s", secret_name, e)
            return False


class CompositeSecretProvider(SecretProvider):
    """
    Composite provider trying Vault first, then falling back to EnvSecretProvider.
    """
    def __init__(self, primary: Optional[SecretProvider] = None, secondary: Optional[SecretProvider] = None):
        self.primary = primary or VaultSecretProvider()
        self.secondary = secondary or EnvSecretProvider()

    def get_secret(self, secret_name: str) -> Optional[str]:
        val = self.primary.get_secret(secret_name)
        if val is not None:
            return val
        return self.secondary.get_secret(secret_name)

    def set_secret(self, secret_name: str, value: str) -> bool:
        success = self.primary.set_secret(secret_name, value)
        if not success:
            return self.secondary.set_secret(secret_name, value)
        return True

    def delete_secret(self, secret_name: str) -> bool:
        p_res = self.primary.delete_secret(secret_name)
        s_res = self.secondary.delete_secret(secret_name)
        return p_res or s_res

