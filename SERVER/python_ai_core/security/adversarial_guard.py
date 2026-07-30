"""
Layer 4 AI Core — Adversarial Prompt Injection & Output Guard Engine (L4_AdversarialGuard & L4_OutputGuard)
Removes security blind spots:
1. Multi-stage Input Normalization (URL Decoding, Base64 Decoding, Unicode NFKC Homoglyph Normalization) before regex scanning.
2. L4_OutputGuard: Post-Processing Response Redaction scanning LLM outputs for PII/Internal IP data leaks before rendering to UI/Telegram.
"""

import re
import base64
import urllib.parse
import unicodedata
import logging
import json
import time
from typing import Dict, List, Any

logger = logging.getLogger("ADVERSARIAL_GUARD")


class MultiStageInputNormalizer:
    """Stage 1: Multi-stage normalization decoding URL, Base64, and Unicode NFKC Homoglyphs."""

    @staticmethod
    def normalize_input(raw_text: str) -> List[str]:
        candidates = [raw_text]

        # 1. URL Unquote
        try:
            url_decoded = urllib.parse.unquote(raw_text)
            if url_decoded != raw_text:
                candidates.append(url_decoded)
        except Exception:
            pass

        # 2. Base64 Decode
        try:
            # Check if input resembles base64 string
            stripped = raw_text.strip()
            if len(stripped) % 4 == 0 and re.match(r"^[A-Za-z0-9+/=]+$", stripped):
                b64_decoded = base64.b64decode(stripped).decode("utf-8", errors="ignore")
                if b64_decoded and b64_decoded != raw_text:
                    candidates.append(b64_decoded)
        except Exception:
            pass

        # 3. Unicode NFKC Homoglyph Normalization
        normalized_candidates = []
        for cand in candidates:
            nfkc_norm = unicodedata.normalize("NFKC", cand)
            normalized_candidates.append(nfkc_norm)

        return list(set(normalized_candidates))


class AdversarialGuardEngine:
    """Scans multi-stage normalized prompt inputs against adversarial injection rules."""

    def __init__(self):
        self.injection_patterns = [
            r"ignore\s+previous\s+instructions",
            r"disregard\s+all\s+prior\s+rules",
            r"you\s+are\s+now\s+in\s+god\s+mode",
            r"system\s*:\s*override",
            r"rm\s+-rf\s+[\/\*]",
            r"drop\s+database",
            r"drop\s+table",
            r"sudo\s+shutdown",
            r"format\s+c:",
            r"curl\s+.*\|\s*sh",
            r"wget\s+.*\|\s*bash"
        ]

    def scan_prompt_injection(self, prompt_text: str, user_id: str = "UNKNOWN") -> Dict[str, Any]:
        """
        1. Normalizes input (URL, Base64, Unicode NFKC).
        2. Scans against BLOCKED_PATTERNS.
        3. Returns PROMPT_INJECTION_BLOCKED if attack detected.
        """
        normalized_variants = MultiStageInputNormalizer.normalize_input(prompt_text)
        matched_rules = []

        for variant in normalized_variants:
            variant_lower = variant.lower()
            for pattern in self.injection_patterns:
                if re.search(pattern, variant_lower):
                    matched_rules.append(f"Pattern '{pattern}' matched on variant: '{variant[:40]}...'")

        matched_rules = list(set(matched_rules))
        is_attack = len(matched_rules) > 0

        result = {
            "raw_prompt_snippet": prompt_text[:80],
            "user_id": user_id,
            "normalized_variants_evaluated": len(normalized_variants),
            "is_adversarial_attack": is_attack,
            "status": "PROMPT_INJECTION_BLOCKED" if is_attack else "CLEARED_SAFE",
            "matched_rules": matched_rules,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }

        if is_attack:
            logger.error(f"[ADVERSARIAL_GUARD] ENCODED/PLAIN PROMPT INJECTION ATTACK BLOCKED from User '{user_id}'! Matched: {matched_rules}")
        else:
            logger.info(f"[ADVERSARIAL_GUARD] Prompt from User '{user_id}' cleared multi-stage security scan.")

        return result


class OutputGuardEngine:
    """L4_OutputGuard: Post-processing response redaction scanning LLM output for internal IP / PII leaks."""

    def __init__(self):
        self.leak_patterns = {
            "INTERNAL_IP": r"\b(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})\b",
            "PLAINTEXT_SECRET": r"(?i)(password|secret|bearer_token|jwt_token)\s*=\s*['\"]?[A-Za-z0-9+/=_-]{6,}['\"]?",
            "CREDIT_CARD_PAN": r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b"
        }

    def sanitize_llm_response(self, llm_response_text: str) -> Dict[str, Any]:
        """
        Scans LLM output before sending to UI (#p-chat, Dashboard) or Telegram.
        Redacts detected internal IPs, secret keys, or credit card PAN numbers.
        """
        sanitized_text = llm_response_text
        leaks_detected = []

        for leak_type, pattern in self.leak_patterns.items():
            matches = re.findall(pattern, sanitized_text)
            if matches:
                leaks_detected.append(f"{leak_type} ({len(matches)} occurrences)")
                if leak_type == "INTERNAL_IP":
                    sanitized_text = re.sub(pattern, "[REDACTED_INTERNAL_IP]", sanitized_text)
                elif leak_type == "PLAINTEXT_SECRET":
                    sanitized_text = re.sub(pattern, "password=[REDACTED_SECRET_TOKEN]", sanitized_text)
                elif leak_type == "CREDIT_CARD_PAN":
                    sanitized_text = re.sub(pattern, "[REDACTED_PCI_PAN]", sanitized_text)

        has_leaks = len(leaks_detected) > 0

        result = {
            "sanitized_response": sanitized_text,
            "has_data_leaks": has_leaks,
            "leaks_detected": leaks_detected,
            "status": "OUTPUT_PII_AUTO_REDACTED" if has_leaks else "CLEARED_NO_LEAKS",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }

        if has_leaks:
            logger.warning(f"[OUTPUT_GUARD] LLM RESPONSE CONTAINED PII/LEAKS! Auto-redacted: {leaks_detected}")

        return result


# Global instances
adversarial_guard_engine = AdversarialGuardEngine()
output_guard_engine = OutputGuardEngine()
