"""
Prompt Injection & Jailbreak Shield (security/prompt_injection_shield.py)

Zero-trust input security filter for AI NOC Pipeline.
Scans incoming telemetry strings, user prompts, and device description logs for:
1. Jailbreak patterns ("ignore previous instructions", "override system prompt", etc.)
2. Command injection / shell execution threats ("rm -rf", "drop database", "mkfs")
3. System prompt leakage attempts ("print system prompt", "show developer instructions")

Returns: (is_clean: bool, sanitized_text: str, threat_reason: str | None)
"""

import re
import logging

logger = logging.getLogger("PROMPT_INJECTION_SHIELD")

# High-risk prompt injection patterns
JAILBREAK_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
    r"disregard\s+(all\s+)?(previous|prior)\s+rules",
    r"override\s+(system\s+)?(prompt|policy|rules)",
    r"you\s+are\s+now\s+in\s+(developer|god|dan|unrestricted)\s+mode",
    r"forget\s+all\s+(your\s+)?constraints",
    r"system\s+prompt\s*:\s*",
    r"print\s+(the\s+)?(system|initial)\s+prompt",
    r"show\s+developer\s+instructions",
    r"cat\s+/etc/passwd",
    r"rm\s+-rf\s+/",
    r"drop\s+database",
    r"format\s+c:",
    r"chmod\s+777\s+/",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in JAILBREAK_PATTERNS]

class PromptInjectionShield:
    def __init__(self):
        pass

    def scan_and_sanitize(self, text: str) -> tuple[bool, str, str | None]:
        """
        Scans text for prompt injection and jailbreak threats.
        Returns: (is_clean: bool, sanitized_text: str, threat_reason: str | None)
        """
        if not text:
            return True, "", None

        for idx, pattern in enumerate(COMPILED_PATTERNS):
            match = pattern.search(text)
            if match:
                threat = f"Prompt Injection / Threat Pattern #{idx+1} detected: '{match.group(0)}'"
                logger.warning(f"[SECURITY SHIELD] Threat blocked! {threat}")
                # Neutralize threat string by redacting match
                sanitized = pattern.sub("[REDACTED_SECURITY_THREAT]", text)
                return False, sanitized, threat

        return True, text, None

def sanitize_input_payload(payload: str | dict) -> tuple[bool, str | dict, str | None]:
    """Helper to scan raw text or dictionary payloads."""
    shield = PromptInjectionShield()
    if isinstance(payload, str):
        return shield.scan_and_sanitize(payload)
    elif isinstance(payload, dict):
        text_repr = str(payload)
        is_clean, _, threat = shield.scan_and_sanitize(text_repr)
        if not is_clean:
            # Replace suspicious string values with sanitized version
            sanitized_dict = {}
            for k, v in payload.items():
                if isinstance(v, str):
                    _, clean_v, _ = shield.scan_and_sanitize(v)
                    sanitized_dict[k] = clean_v
                else:
                    sanitized_dict[k] = v
            return False, sanitized_dict, threat
        return True, payload, None
    return True, payload, None
