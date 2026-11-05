"""
Multi-Site Correlation Engine Module
Correlates diagnostic probing outcomes across Site A, Site B, Site C, Cloud Infrastructure, and ISP Gateways.
Distinguishes local endpoint issues, branch issues, regional outages, cloud degradation, or ISP disruptions.
"""

from dataclasses import dataclass
from typing import Dict, List, Any


@dataclass
class MultiSiteCorrelationReport:
    impact_scope: str   # "LOCAL_ENDPOINT", "BRANCH_SITE_A", "REGIONAL_OUTAGE", "CLOUD_PROVIDER", "ISP_DISRUPTION"
    affected_sites: List[str]
    confidence: float
    summary: str


class MultiSiteCorrelationEngine:
    """Correlates probe telemetry across multi-site enterprise topology."""

    def correlate_sites(
        self,
        site_probe_outcomes: Dict[str, str]  # site_id -> probe_status ("PASSED" / "FAILED")
    ) -> MultiSiteCorrelationReport:
        if not site_probe_outcomes:
            return MultiSiteCorrelationReport(
                impact_scope="LOCAL_ENDPOINT",
                affected_sites=["SITE_LOCAL"],
                confidence=0.90,
                summary="Single endpoint probing: Local scope assumed"
            )

        failed_sites = [site for site, status in site_probe_outcomes.items() if status == "FAILED"]
        passed_sites = [site for site, status in site_probe_outcomes.items() if status == "PASSED"]

        if len(failed_sites) == 1:
            scope = f"BRANCH_{failed_sites[0]}"
            confidence = 0.95
            summary = f"Failure isolated to single branch site {failed_sites[0]}; other sites operational"
        elif len(failed_sites) > 1 and "CLOUD_AWS" in failed_sites:
            scope = "CLOUD_PROVIDER"
            confidence = 0.97
            summary = f"Failure observed across multiple sites affecting Cloud AWS: Cloud degradation detected"
        elif len(failed_sites) > 1 and "ISP_GATEWAY" in failed_sites:
            scope = "ISP_DISRUPTION"
            confidence = 0.98
            summary = "Upstream ISP Gateway failure affecting multiple regional sites"
        elif len(failed_sites) > 2:
            scope = "REGIONAL_OUTAGE"
            confidence = 0.96
            summary = f"Regional outage affecting multiple sites: {failed_sites}"
        else:
            scope = "LOCAL_ENDPOINT"
            confidence = 0.92
            summary = "Local endpoint connectivity anomaly"

        return MultiSiteCorrelationReport(
            impact_scope=scope,
            affected_sites=failed_sites if failed_sites else ["SITE_LOCAL"],
            confidence=confidence,
            summary=summary
        )
