"""
Enterprise AI OS — Routers Package (routers/)
"""
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from routers.api_router import ApiRouter
from routers.incident_router import IncidentRouter
from routers.telemetry_router import TelemetryRouter
from routers.remediation_router import RemediationRouter


__all__ = ["ApiRouter", "IncidentRouter", "TelemetryRouter", "RemediationRouter"]
