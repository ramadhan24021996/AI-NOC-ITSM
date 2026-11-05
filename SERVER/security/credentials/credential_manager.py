"""
SERVER.security.credentials - Credential Manager
Manages API keys, DB connection strings, and service credentials through SecretProvider.
"""
from typing import Optional
from SERVER.security.vault.secret_provider import SecretProvider

class CredentialManager:
    """Resolves runtime credentials via the abstract SecretProvider."""

    def __init__(self, provider: SecretProvider):
        self._provider = provider

    def get_db_url(self) -> Optional[str]:
        return self._provider.get_secret("DATABASE_URL")

    def get_redis_url(self) -> Optional[str]:
        return self._provider.get_secret("REDIS_URL")

    def get_api_key(self, service_name: str) -> Optional[str]:
        return self._provider.get_secret(f"{service_name.upper()}_API_KEY")

    def get_nats_url(self) -> Optional[str]:
        return self._provider.get_secret("NATS_URL")
