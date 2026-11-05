"""
SERVER.integration.telemetry — Telemetry Validator
====================================================
Tahap 2.6A — Telemetry Integration

Mencegah data buruk (empty metrics, NaN values, out-of-order timestamps,
missing device_id) diteruskan ke Correlation Engine atau NATS EventBus.
"""
import math
import logging
from typing import Tuple
from SERVER.integration.telemetry.telemetry_normalizer import NormalizedTelemetryDTO

logger = logging.getLogger("integration.telemetry.validator")


class TelemetryValidator:
    """Validates NormalizedTelemetryDTO to ensure high data quality."""

    def validate(self, dto: NormalizedTelemetryDTO) -> Tuple[bool, str]:
        """
        Validates DTO. Returns (is_valid, reason).
        """
        if not dto.device_id or dto.device_id.strip() == "":
            return False, "Missing device_id"

        if math.isnan(dto.value) or math.isinf(dto.value):
            return False, f"Invalid numeric value: {dto.value} (NaN/Inf)"

        if not dto.metric_name or dto.metric_name.strip() == "":
            return False, "Missing metric_name"

        if not dto.timestamp:
            return False, "Missing timestamp"

        return True, "VALID"
