"""
Python Site Partitioner Helper (allsite.md)
Provides NATS JetStream subject routing per site_id:
- telemetry.site.<site_id>.critical
- telemetry.site.<site_id>.warning
- telemetry.site.<site_id>.normal
- incident.site.<site_id>.create
- approval.site.<site_id>
"""

import re
from typing import Dict, Any, List

def normalize_site_id(raw_site: str) -> str:
    """Normalize raw site string to NATS-safe subject token."""
    if not raw_site or not raw_site.strip():
        return "default-site"
    clean = raw_site.strip().lower().replace(" ", "-")
    clean = re.sub(r'[^a-z0-9_-]', '', clean)
    return clean if clean else "default-site"

def get_partitioned_subject(category: str, site_id: str, severity: str = "normal") -> str:
    """Construct site-partitioned NATS subject string."""
    clean_site = normalize_site_id(site_id)
    clean_sev = severity.strip().lower()
    cat = category.strip().lower()

    if cat == "telemetry":
        if clean_sev in ["critical", "error", "fatal"]:
            return f"telemetry.site.{clean_site}.critical"
        elif clean_sev in ["warning", "warn"]:
            return f"telemetry.site.{clean_site}.warning"
        else:
            return f"telemetry.site.{clean_site}.normal"
    elif cat == "incident":
        if clean_sev == "update":
            return f"incident.site.{clean_site}.update"
        return f"incident.site.{clean_site}.create"
    elif cat == "approval":
        return f"approval.site.{clean_site}"
    else:
        return f"telemetry.site.{clean_site}.normal"

def get_all_site_wildcards() -> List[Dict[str, str]]:
    """Return wildcard subjects for telemetry streams."""
    return [
        {"subject": "telemetry.site.*.critical", "role": "Site Critical Ingest Stream"},
        {"subject": "telemetry.site.*.warning", "role": "Site Warning Ingest Stream"},
        {"subject": "telemetry.site.*.normal", "role": "Site Normal Ingest Stream"},
        {"subject": "incident.site.*.create", "role": "Site Incident Creation Queue"},
        {"subject": "incident.site.*.update", "role": "Site Incident Update Channel"},
        {"subject": "approval.site.*", "role": "Site HITL Approval Channel"}
    ]

def get_nats_reconnection_opts() -> Dict[str, Any]:
    """Return resilient reconnection options for multi-site WAN NATS connections."""
    return {
        "max_reconnect_attempts": 10,
        "reconnect_time_wait": 2.0,
        "ping_interval": 15,
        "max_outstanding_pings": 3,
        "tls_handshake_timeout": 10.0
    }

if __name__ == "__main__":
    print("Default Site:", normalize_site_id("  Kantor Cabang Jakarta #01 "))
    print("Subject Critical:", get_partitioned_subject("telemetry", "Kantor Cabang Jakarta", "CRITICAL"))
    print("Subject Incident:", get_partitioned_subject("incident", "Kantor Pusat", "NEW"))
    print("NATS Reconnect Opts:", get_nats_reconnection_opts())
