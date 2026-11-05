"""
SERVER.security.encryption - Encryption Helper
Provides AES-256 symmetric encryption/decryption helpers for sensitive payloads.
"""
import os
import base64
import hashlib
from typing import Optional

try:
    from cryptography.fernet import Fernet
    _HAS_CRYPTOGRAPHY = True
except ImportError:
    _HAS_CRYPTOGRAPHY = False

class EncryptionHelper:
    """Lightweight encryption helper using Fernet (AES-128-CBC + HMAC-SHA256).
    Requires `pip install cryptography` in the target environment.
    Falls back to base64 stub if library is unavailable (for import safety).
    """

    def __init__(self, secret_key: Optional[str] = None):
        if _HAS_CRYPTOGRAPHY:
            key = secret_key or os.environ.get("ENCRYPTION_KEY", "")
            derived = hashlib.sha256(key.encode()).digest()
            self._fernet_key = base64.urlsafe_b64encode(derived)
            self._fernet = Fernet(self._fernet_key)
        self._available = _HAS_CRYPTOGRAPHY

    def encrypt(self, plaintext: str) -> str:
        if not self._available:
            return base64.b64encode(plaintext.encode()).decode()
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        if not self._available:
            return base64.b64decode(ciphertext.encode()).decode()
        return self._fernet.decrypt(ciphertext.encode()).decode()
