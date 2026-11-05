"""
SERVER.security.privacy_redactor — Enterprise Data Auto-Redaction Guard
======================================================================
Provides automatic redaction and sanitization for sensitive data in voice transcripts,
log payloads, API responses, and persistent memory records.

Redacts:
 - Passwords, Secret Keys, & Credentials
 - Bearer Tokens, JWTs, & API Keys
 - Database Connection Strings & URIs
 - Personal Identifiable Information (PII) such as NIK, Credit Cards, & Emails
"""
import re
import logging
from typing import Dict, Any, Union, List, Tuple, Optional, overload

logger = logging.getLogger("security.privacy_redactor")

# ── Enterprise Redaction Patterns ─────────────────────────────────────────────
DEFAULT_PATTERNS: List[Tuple[str, str]] = [
    # Flexible Password Pattern: "password [DB/server] adalah/is/: Secret123" -> "password [REDACTED_PASSWORD]"
    (r"(?i)\b(password|passwd|pass|katasandi|sandi)\b(?:[\w\s]{0,15}?)(?:is|=|:|adalah|yaitu)\s*([^\s,\.\!\?]+)", r"\1 : [REDACTED_PASSWORD]"),
    # Connection Strings: postgresql://user:pass@host:5432/db -> postgresql://[REDACTED_URI]
    (r"(?i)(postgres|postgresql|mysql|mongodb|redis|amqp)://[^\s\"']+", r"\1://[REDACTED_URI]"),
    # Bearer Tokens & JWTs
    (r"(?i)bearer\s+[a-zA-Z0-9\-\._~\+\/]+=*", "Bearer [REDACTED_TOKEN]"),
    (r"eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]+", "[REDACTED_JWT]"),
    # API Keys: gAAAAA... or sk-...
    (r"\b(sk-[a-zA-Z0-9]{20,})\b", "[REDACTED_API_KEY]"),
    (r"\b(gAAAAA[a-zA-Z0-9_-]{30,})\b", "[REDACTED_ENCRYPTED_KEY]"),
    # Emails
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b", "[REDACTED_EMAIL]"),
    # Credit Card Numbers (13-19 digits)
    (r"\b(?:\d[ -]*?){13,19}\b", "[REDACTED_CARD_NUMBER]"),
]


class PrivacyAutoRedactor:
    """Enterprise Data Sanitizer & Privacy Auto-Redaction Guard."""

    def __init__(self, custom_patterns: Optional[List[Tuple[str, str]]] = None):
        self.patterns = DEFAULT_PATTERNS + (custom_patterns or [])

    def redact_text(self, text: str) -> str:
        """
        Sanitizes text string by redacting sensitive data patterns.

        Args:
            text: Raw input text or voice transcript.

        Returns:
            Sanitized text string safe for logging, LLM prompting, and DB persistence.
        """
        if not text or not isinstance(text, str):
            return text or ""

        sanitized = text
        for pattern, replacement in self.patterns:
            try:
                sanitized = re.sub(pattern, replacement, sanitized)
            except Exception as e:
                logger.error(f"[PrivacyAutoRedactor] Regex replacement error for pattern '{pattern}': {e}")

        if sanitized != text:
            logger.info("[PrivacyAutoRedactor] Sensitive data DETECTED and REDACTED successfully.")

        return sanitized

    @overload
    def redact_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]: ...

    @overload
    def redact_payload(self, payload: List[Any]) -> List[Any]: ...

    @overload
    def redact_payload(self, payload: str) -> str: ...

    @overload
    def redact_payload(self, payload: Any) -> Any: ...

    def redact_payload(self, payload: Any) -> Any:
        """
        Recursively sanitizes dictionary or list data structures.

        Args:
            payload: JSON dict, list structure, or string.

        Returns:
            Sanitized data payload with sensitive fields redacted.
        """
        if isinstance(payload, dict):
            redacted_dict: Dict[str, Any] = {}
            for key, val in payload.items():
                key_lower = key.lower() if isinstance(key, str) else str(key).lower()
                if any(sec_k in key_lower for sec_k in ["password", "secret", "token", "api_key", "private_key"]):
                    redacted_dict[key] = "[REDACTED_SENSITIVE_FIELD]"
                else:
                    redacted_dict[key] = self.redact_payload(val)
            return redacted_dict
        elif isinstance(payload, list):
            return [self.redact_payload(item) for item in payload]
        elif isinstance(payload, str):
            return self.redact_text(payload)
        else:
            return payload
