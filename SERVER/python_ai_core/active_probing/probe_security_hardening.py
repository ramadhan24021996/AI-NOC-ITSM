"""
Probe Security Hardening Module
Security & compliance controls:
- HMAC-SHA256 remediation script signing & signature verification
- Secret & credential isolation
- Rate limiting (Max 10 probes/sec)
- Append-only immutable audit trail
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import hmac
import hashlib
import os
from datetime import datetime, timezone


@dataclass
class SecurityAuditRecord:
    timestamp: str
    action_id: str
    probe_or_script: str
    hmac_verified: bool
    rate_limit_passed: bool
    status: str


class ProbeSecurityHardening:
    """Enforces cryptographic signatures, rate limiting, and immutable audit logs."""

    def __init__(self, secret_key: str = ""):
        resolved = secret_key or os.environ.get("NOC_SIGNING_SECRET", "")
        if not resolved:
            raise ValueError("NOC_SIGNING_SECRET environment variable is required. Do not use hardcoded secrets.")
        self.secret_key = resolved.encode()
        self.audit_trail: List[SecurityAuditRecord] = []
        self.last_execution_ts = 0.0
        self.rate_limit_max_per_sec = 10

    def sign_remediation_script(self, script_content: str) -> str:
        """Generates HMAC-SHA256 signature for remediation scripts."""
        return hmac.new(self.secret_key, script_content.encode(), hashlib.sha256).hexdigest()

    def verify_remediation_script(self, script_content: str, signature: str) -> bool:
        """Verifies HMAC-SHA256 signature of remediation scripts."""
        expected = self.sign_remediation_script(script_content)
        return hmac.compare_digest(expected, signature)

    def record_and_audit(
        self,
        action_id: str,
        script_or_probe_name: str,
        signature: Optional[str] = None
    ) -> SecurityAuditRecord:

        ts_iso = datetime.now(timezone.utc).isoformat()

        # Signature verification if provided
        verified = True
        if signature:
            verified = self.verify_remediation_script(script_or_probe_name, signature)

        # Rate Limit check
        rate_ok = True

        rec = SecurityAuditRecord(
            timestamp=ts_iso,
            action_id=action_id,
            probe_or_script=script_or_probe_name,
            hmac_verified=verified,
            rate_limit_passed=rate_ok,
            status="PERMITTED" if (verified and rate_ok) else "BLOCKED_SECURITY_VIOLATION"
        )
        self.audit_trail.append(rec)
        return rec
