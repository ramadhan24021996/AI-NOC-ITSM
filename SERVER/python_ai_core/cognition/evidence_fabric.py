import hashlib
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

@dataclass
class EvidenceVersion:
    evidence_id: str
    revision: int
    parent_id: Optional[str]
    state: str  # "RAW", "NORMALIZED", "VALIDATED", "ENRICHED"
    evidence_hash: str

@dataclass
class EvidenceItem:
    version_info: EvidenceVersion
    source: str
    collector: str
    host: str
    timestamp: datetime
    trace_id: str
    raw_data: Any
    priority: int = 50
    confidence_weight: float = 1.0
    status: str = "ACTIVE" # "ACTIVE", "STALE", "DUPLICATE"

@dataclass
class EvidenceQuality:
    source_reliability: float
    timestamp_accuracy: float
    completeness: float
    cross_validation: float
    freshness: float
    overall_score: float

@dataclass
class EvidencePackage:
    incident_id: str
    status: str  # "VALIDATED", "NEED_MORE_EVIDENCE", "CONFLICT_DETECTED", "REJECTED"
    quality: EvidenceQuality
    overall_confidence: float
    timeline: List[EvidenceItem]
    conflicts: List[str]
    missing_sources: List[str]
    graph_edges: List[Dict[str, str]]
    validated_telemetry: Dict[str, Any]

class EnterpriseEvidenceFabric:
    """
    Sprint P: Enterprise Evidence Fabric (V2)
    Implements Versioning, Confidence vs Quality, Aging, Deduplication, Priority, and Decay.
    """

    SOURCE_RELIABILITY_MAP = {
        "prometheus": 0.99, "netdata": 0.98, "snmp": 0.95,
        "zabbix": 0.95, "syslog": 0.85, "agent": 0.90, "custom_script": 0.70,
        "windows_event": 0.92, "linux_audit": 0.92, "smart": 0.99,
        "network_lldp": 0.98, "bgp_monitor": 0.99
    }

    PRIORITY_MAP = {
        "panic": 100, "kernel oops": 95, "filesystem readonly": 92,
        "oom killer": 90, "timeout": 80, "cpu": 20, "http 404": 30,
        "smart failure": 98, "battery critical": 85, "temperature high": 88,
        "vpn disconnect": 75, "bgp down": 99, "packet loss": 70,
        "antivirus disabled": 90, "firewall blocked": 60, "erp application error": 80,
        "pos application error": 85
    }

    # Enterprise Telemetry Categories (Sprint P1)
    CLIENT_PC_METRICS = {
        "cpu", "ram", "memory", "disk", "temperature", "smart", "battery", 
        "network", "wifi", "bluetooth", "usb", "printer", "scanner", "camera", 
        "audio", "com", "gpu", "monitor", "windows service", "linux service", 
        "scheduled task", "startup program", "antivirus", "firewall", 
        "windows update", "linux package", "process", "application", "browser", 
        "pos application", "office application", "tms application", "erp application"
    }

    NETWORK_METRICS = {
        "snmp", "switch", "router", "vpn", "access point", "lldp", "arp", "bgp", 
        "dns", "dhcp", "internet", "packet loss", "latency", "bandwidth",
        "link_status", "crc_error", "optical_rx", "optical_tx", 
        "mac_table", "stp_status", "port_security", "vlan_mismatch",
        "broadcast_storm", "wifi_rssi"
    }

    def __init__(self, incident_id: str):
        self.incident_id = incident_id
        self.evidence_timeline: List[EvidenceItem] = []
        self.conflicts: List[str] = []
        self.missing: List[str] = []
        self.graph: List[Dict[str, str]] = []
        self._hash_registry = set()
        self._seq = 1

    def _generate_hash(self, source: str, raw_data: Dict[str, Any]) -> str:
        # Simplistic hash for deduplication
        payload = f"{source}_{sorted(raw_data.items())}"
        return hashlib.sha256(payload.encode()).hexdigest()

    def ingest_telemetry(self, source: str, host: str, raw_data: Dict[str, Any], trace_id: str, timestamp_str: Optional[str] = None):
        dt = datetime.now(timezone.utc)
        if timestamp_str:
            try:
                dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except ValueError:
                import logging; logging.getLogger(__name__).debug('_ = None suppressed')

        # 0. SPRINT P1: Enterprise Telemetry Expansion (Unrolling Bulk Payloads)
        extracted_payloads = []
        if isinstance(raw_data, dict):
            found_metrics = {}
            for k, v in raw_data.items():
                k_lower = k.lower()
                if k_lower in self.CLIENT_PC_METRICS or k_lower in self.NETWORK_METRICS:
                    found_metrics[k_lower] = v
            
            # If we found specific enterprise metrics, split them to individual Evidence Items
            if found_metrics:
                for k, v in found_metrics.items():
                    extracted_payloads.append({k: v})
                
                # If there are left over generic fields, bundle them
                leftovers = {k: v for k, v in raw_data.items() if k.lower() not in self.CLIENT_PC_METRICS and k.lower() not in self.NETWORK_METRICS}
                if leftovers:
                    extracted_payloads.append(leftovers)
            else:
                extracted_payloads.append(raw_data)
        else:
            extracted_payloads.append(raw_data)

        for payload in extracted_payloads:
            # 1. Versioning
            e_hash = self._generate_hash(source, payload)
            
            # 4. Duplicate Detection
            status = "ACTIVE"
            if e_hash in self._hash_registry:
                status = "DUPLICATE"
            self._hash_registry.add(e_hash)

            # 5. Priority Evaluation
            priority = 50
            raw_str = str(payload).lower()
            for kw, prio in self.PRIORITY_MAP.items():
                if kw in raw_str and prio > priority:
                    priority = prio

            # 3. Aging
            now = datetime.now(timezone.utc)
            diff_mins = (now - dt).total_seconds() / 60.0
            if diff_mins > 60:
                status = "STALE"

            # 6. Evidence Decay
            weight = self.SOURCE_RELIABILITY_MAP.get(source.lower(), 0.80)
            if status == "STALE":
                weight *= 0.5  # Decay weight by 50% if old

            version = EvidenceVersion(
                evidence_id=f"EV-{self.incident_id}-{self._seq}",
                revision=1,
                parent_id=None,
                state="RAW",
                evidence_hash=e_hash
            )
            self._seq += 1

            item = EvidenceItem(
                version_info=version,
                source=source,
                collector=f"collector-{source}",
                host=host,
                timestamp=dt,
                trace_id=trace_id,
                raw_data=payload,
                priority=priority,
                confidence_weight=weight,
                status=status
            )
            
            # Only append if not duplicate (or append and filter later, but let's filter now for clean graph)
            if status != "DUPLICATE":
                item.version_info.state = "NORMALIZED" # Transition state
                self.evidence_timeline.append(item)
                
        self.evidence_timeline.sort(key=lambda x: x.timestamp)

    def _calculate_quality(self) -> EvidenceQuality:
        if not self.evidence_timeline:
            return EvidenceQuality(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

        rel_score = sum(e.confidence_weight for e in self.evidence_timeline) / len(self.evidence_timeline)

        now = datetime.now(timezone.utc)
        freshness_scores = []
        for e in self.evidence_timeline:
            diff_seconds = abs((now - e.timestamp).total_seconds())
            f_score = max(0.0, 1.0 - (diff_seconds / 3600.0)) # 1 hour decay
            freshness_scores.append(f_score)
        
        fresh_score = sum(freshness_scores) / len(freshness_scores) if freshness_scores else 0.0
        time_accuracy = 1.0 

        keys_found = set()
        for e in self.evidence_timeline:
            keys_found.update(str(k).lower() for k in e.raw_data.keys())
            # Search within values if they are dicts or strings
            for v in e.raw_data.values():
                if isinstance(v, str):
                    keys_found.update(word for word in v.lower().split() if word in self.CLIENT_PC_METRICS or word in self.NETWORK_METRICS)
        
        # We consider completeness based on whether at least some critical categories are covered
        client_found = self.CLIENT_PC_METRICS.intersection(keys_found)
        net_found = self.NETWORK_METRICS.intersection(keys_found)
        
        # If we found at least 2 metrics, we give good completeness
        total_found = len(client_found) + len(net_found)
        completeness = min(1.0, total_found / 3.0) if total_found > 0 else 0.5

        cross_val = max(0.0, 1.0 - (len(self.conflicts) * 0.2))
        overall = (rel_score * 0.25) + (time_accuracy * 0.1) + (completeness * 0.25) + (cross_val * 0.2) + (fresh_score * 0.2)

        return EvidenceQuality(
            source_reliability=round(rel_score * 100, 1),
            timestamp_accuracy=round(time_accuracy * 100, 1),
            completeness=round(completeness * 100, 1),
            cross_validation=round(cross_val * 100, 1),
            freshness=round(fresh_score * 100, 1),
            overall_score=round(overall * 100, 1)
        )

    def _detect_conflicts_and_missing(self):
        has_http_error = False
        has_db_metrics = False
        has_network_metrics = False
        db_status = None
        
        for e in self.evidence_timeline:
            raw = e.raw_data
            if "http_status" in raw and str(raw["http_status"]).startswith("5"):
                has_http_error = True
            if "db_status" in raw:
                has_db_metrics = True
                if db_status is None:
                    db_status = raw["db_status"]
                elif db_status != raw["db_status"]:
                    self.conflicts.append(f"Conflict: DB Status says {db_status} but {e.source} says {raw['db_status']}")
            if "packet_loss" in raw or "ping" in raw:
                has_network_metrics = True

        if has_http_error and not has_db_metrics:
            self.missing.append("Database Metrics (Required for HTTP 5xx)")
        if has_http_error and not has_network_metrics:
            self.missing.append("Network Topology (Required for HTTP 5xx)")

        # Evidence Enrichment: Check if asset context is missing
        has_asset_context = any(
            "criticality" in e.raw_data or "sla" in e.raw_data or "role" in e.raw_data 
            for e in self.evidence_timeline
        )
        if not has_asset_context:
            self.missing.append("Asset Context (Criticality/SLA/Role required for precise enrichment)")

    def validate_and_package(self) -> EvidencePackage:
        self._detect_conflicts_and_missing()
        quality = self._calculate_quality()

        # Evidence Prioritization: Sort timeline by Priority (Descending) then Freshness
        self.evidence_timeline.sort(key=lambda x: (x.priority, x.timestamp), reverse=True)

        # 2. Confidence Calculation (Distinct from Quality)
        # High quality but many conflicts -> Low Confidence
        confidence_score = quality.overall_score
        if len(self.conflicts) > 0:
            confidence_score *= 0.6  # Drop confidence by 40%
        if any(e.status == "STALE" for e in self.evidence_timeline):
            confidence_score *= 0.8  # Drop confidence if stale data used

        status = "VALIDATED"
        if len(self.conflicts) > 0:
            status = "CONFLICT_DETECTED"
        elif len(self.missing) > 0:
            status = "NEED_MORE_EVIDENCE"
        elif quality.overall_score < 70.0:
            status = "REJECTED"

        # Build Graph
        if len(self.evidence_timeline) > 1:
            for i in range(len(self.evidence_timeline) - 1):
                e1 = self.evidence_timeline[i]
                e2 = self.evidence_timeline[i+1]
                self.graph.append({"from": e1.source, "to": e2.source, "relation": "followed_by", "weight": str(e2.priority)})

        # Transition to VALIDATED/ENRICHED
        merged_telemetry = {}
        if status in ["VALIDATED", "NEED_MORE_EVIDENCE", "CONFLICT_DETECTED"]:
             for e in self.evidence_timeline:
                 e.version_info.state = "VALIDATED"
                 merged_telemetry.update(e.raw_data)

        return EvidencePackage(
            incident_id=self.incident_id,
            status=status,
            quality=quality,
            overall_confidence=round(confidence_score, 1),
            timeline=self.evidence_timeline,
            conflicts=self.conflicts,
            missing_sources=self.missing,
            graph_edges=self.graph,
            validated_telemetry=merged_telemetry
        )
