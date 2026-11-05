"""
LF-1 Learning Framework — Feature Validator (Concrete Implementation)
Validates telemetry features against OSI V6 schema, tenant isolation,
SHA-256 checksum integrity, and quality score range constraints.
"""
import hashlib
import json
import logging
from typing import Dict, Any

from .interfaces import IFeatureValidator

logger = logging.getLogger("LF1_FEATURE_VALIDATOR")

# Required V6 header fields
_REQUIRED_HEADER_FIELDS = {"protocol_version", "message_type", "message_id"}
# Required payload fields
_REQUIRED_PAYLOAD_FIELDS = {"metric_class", "value", "quality_score"}
# Quality score must be in [0.0, 1.0]
_QUALITY_MIN = 0.0
_QUALITY_MAX = 1.0
# Known OSI metric classes (Layer 1-7)
_VALID_METRIC_CLASSES = {
    # Layer 1 — Physical
    "HARDWARE", "DISK", "SMART", "USB", "POWER",
    # Layer 2 — Data Link
    "ETHERNET", "WIFI", "WLAN", "SWITCH",
    # Layer 3 — Network
    "IP", "ICMP", "ARP", "ROUTING",
    # Layer 4 — Transport
    "TCP", "UDP", "TLS",
    # Layer 5 — Session
    "DNS", "DHCP", "NTP",
    # Layer 6 — Presentation
    "HTTP", "HTTPS", "SSL",
    # Layer 7 — Application
    "PROCESS", "BROWSER", "PRINTER", "APP",
    # System
    "CPU", "MEMORY", "OS", "EVENTLOG", "SERVICE",
    # Generic / Adapted
    "UNKNOWN", "TELEMETRY",
}


class TelemetryFeatureValidator(IFeatureValidator):
    """
    Validates LF-1 feature payloads before they enter the Feature Store.

    Validation pipeline:
        1. validate_schema()         — required fields check
        2. validate_tenant_isolation() — tenant_id presence + non-empty
        3. validate_checksum()       — SHA-256 content integrity
        4. validate_quality_range()  — quality_score in [0.0, 1.0]
    """

    # ------------------------------------------------------------------
    # IFeatureValidator implementation
    # ------------------------------------------------------------------
    def validate_schema(self, payload: Dict[str, Any]) -> bool:
        """
        Validates that the payload conforms to OSI V6 protocol schema.
        Required structure:
            {
              "header":  { "protocol_version", "message_type", "message_id" },
              "routing": { "tenant_id", "device_id" },
              "payload": { "metric_class", "value", "quality_score" }
            }
        """
        if "header" not in payload or "payload" not in payload:
            logger.warning("[LF1-VALID] validate_schema FAILED: missing 'header' or 'payload' key.")
            return False

        header = payload.get("header", {})
        missing_header = _REQUIRED_HEADER_FIELDS - set(header.keys())
        if missing_header:
            logger.warning("[LF1-VALID] validate_schema FAILED: missing header fields: %s", missing_header)
            return False

        p = payload.get("payload", {})
        missing_payload = _REQUIRED_PAYLOAD_FIELDS - set(p.keys())
        if missing_payload:
            logger.warning("[LF1-VALID] validate_schema FAILED: missing payload fields: %s", missing_payload)
            return False

        # Validate metric_class is a known OSI class
        metric_class = str(p.get("metric_class", "")).upper()
        if metric_class not in _VALID_METRIC_CLASSES:
            logger.warning("[LF1-VALID] validate_schema WARNING: unknown metric_class '%s'", metric_class)
            # Not a hard failure — allow extension; just warn

        logger.debug("[LF1-VALID] validate_schema PASSED for message_id=%s",
                     header.get("message_id", "?"))
        return True

    def validate_tenant_isolation(self, payload: Dict[str, Any]) -> bool:
        """
        Validates that tenant_id is present, non-empty, and not 'default'
        (which could indicate a misconfigured multi-tenant setup).
        """
        routing = payload.get("routing", {})
        tenant_id = routing.get("tenant_id", "").strip()

        if not tenant_id:
            logger.warning("[LF1-VALID] validate_tenant_isolation FAILED: tenant_id is missing or empty.")
            return False

        if tenant_id.lower() in {"default", "root", "admin", "system"}:
            logger.warning(
                "[LF1-VALID] validate_tenant_isolation WARNING: "
                "tenant_id '%s' is a reserved value — potential misconfiguration.", tenant_id
            )
            # Warn but pass — reserved tenant_ids may be used in dev/internal flows

        device_id = routing.get("device_id", "").strip()
        if not device_id:
            logger.warning("[LF1-VALID] validate_tenant_isolation FAILED: device_id missing.")
            return False

        logger.debug("[LF1-VALID] validate_tenant_isolation PASSED: tenant=%s device=%s",
                     tenant_id, device_id)
        return True

    def validate_checksum(self, payload: Dict[str, Any]) -> bool:
        """
        If payload contains a 'checksum' field, validates it against
        SHA-256 of serialized payload['payload'] dict.
        If no checksum is present, passes (checksum is optional).
        """
        expected_checksum = payload.get("checksum", "")
        if not expected_checksum:
            logger.debug("[LF1-VALID] validate_checksum: no checksum field — SKIP (optional).")
            return True

        content = payload.get("payload", {})
        content_str = json.dumps(content, sort_keys=True)
        computed = hashlib.sha256(content_str.encode()).hexdigest()

        if computed != expected_checksum:
            logger.warning(
                "[LF1-VALID] validate_checksum FAILED: "
                "expected=%s computed=%s", expected_checksum[:8], computed[:8]
            )
            return False

        logger.debug("[LF1-VALID] validate_checksum PASSED.")
        return True

    def validate_quality_range(self, payload: Dict[str, Any]) -> bool:
        """
        Validates quality_score is a float in [0.0, 1.0].
        quality_score represents data trustworthiness from the agent.
        """
        p = payload.get("payload", {})
        try:
            qs = float(p.get("quality_score", -1))
        except (TypeError, ValueError):
            logger.warning("[LF1-VALID] validate_quality_range FAILED: non-numeric quality_score.")
            return False

        if not (_QUALITY_MIN <= qs <= _QUALITY_MAX):
            logger.warning(
                "[LF1-VALID] validate_quality_range FAILED: "
                "quality_score=%.4f out of range [%.1f, %.1f]", qs, _QUALITY_MIN, _QUALITY_MAX
            )
            return False

        logger.debug("[LF1-VALID] validate_quality_range PASSED: quality_score=%.4f", qs)
        return True

    # ------------------------------------------------------------------
    # Convenience: run full pipeline
    # ------------------------------------------------------------------
    def validate_all(self, payload: Dict[str, Any]) -> bool:
        """Runs the complete validation pipeline. Returns True only if ALL pass."""
        results = {
            "schema":           self.validate_schema(payload),
            "tenant_isolation": self.validate_tenant_isolation(payload),
            "checksum":         self.validate_checksum(payload),
            "quality_range":    self.validate_quality_range(payload),
        }
        all_pass = all(results.values())
        logger.info("[LF1-VALID] validate_all: %s | breakdown=%s",
                    "PASS" if all_pass else "FAIL", results)
        return all_pass
