"""
Domain Enums for Enterprise AI Operations Platform
"""
from enum import Enum

class IncidentSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ExecutionTrack(str, Enum):
    FAST_TRACK = "fast_track"
    STANDARD_TRACK = "standard_track"
    CRITICAL_TRACK = "critical_track"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"

class TrustRating(str, Enum):
    OFFICIAL_VENDOR = "official_vendor"       # 5/5
    RFC_STANDARD = "rfc_standard"             # 5/5
    CVE_NVD = "cve_nvd"                       # 4/5
    GITHUB_OFFICIAL = "github_official"       # 4/5
    STACK_OVERFLOW = "stack_overflow"         # 3/5
    COMMUNITY_BLOG = "community_blog"         # 2/5
    UNKNOWN = "unknown"                       # 1/5

class ActionRiskLevel(str, Enum):
    READ_ONLY = "read_only"
    LOW_RISK = "low_risk"
    MEDIUM_RISK = "medium_risk"
    HIGH_RISK = "high_risk"
    CRITICAL_RISK = "critical_risk"
