"""
Enterprise Script Signature Verification Engine (Phase 3.4)
Generates and verifies SHA256 digital signatures for AI-generated candidate scripts.
Rejects tampered or unverified scripts automatically.
"""

import hashlib
import logging
from typing import Dict, Any

logger = logging.getLogger("SCRIPT_SIGNATURE")

class ScriptSignatureEngine:
    """
    Enterprise SHA256 Signature Engine
    Ensures script integrity and prevents execution of modified scripts.
    """

    def generate_signature(self, script_content: str, author: str = "AI_Developer_Agent") -> Dict[str, str]:
        """Generates SHA256 hash signature for candidate script."""
        content_bytes = f"{author}:{script_content.strip()}".encode("utf-8")
        sha256_hash = hashlib.sha256(content_bytes).hexdigest()
        return {
            "author": author,
            "signature": sha256_hash,
            "algorithm": "SHA256"
        }

    def verify_signature(self, script_content: str, expected_signature: str, author: str = "AI_Developer_Agent") -> bool:
        """Verifies if script content matches expected SHA256 signature."""
        computed = self.generate_signature(script_content, author)["signature"]
        is_valid = computed == expected_signature
        if not is_valid:
            logger.warning("[SIGNATURE REJECTED] Hash mismatch! Computed: %s | Expected: %s", computed, expected_signature)
        return is_valid
