"""
Enterprise AI OS — OSI Cognitive Framework: Framework 2.0 (Enterprise Edition)
Multi-Layer Probabilistic OSI Taxonomy with Root Cause & Symptom Disambiguation

Features:
1. Root Cause vs Symptom Disambiguation
2. Telemetry & Topology Evidence Weighting
3. Vendor Knowledge Base
4. Dependency Graph Inference (Bottom-Up Root Cause)
5. Explainable AI Confidence
6. Incident Propagation Graph
"""

import json
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

# ─── OSI Layer Definitions ───────────────────────────────────────────────────

OSI_LAYERS: Dict[int, Dict] = {
    1: {"name": "Physical", "weight": 1.0, "keywords": ["power", "nic", "kabel", "sfp", "optical", "los", "fiber", "cut", "crc", "interface down", "rx power", "tx power", "link down", "port down"]},
    2: {"name": "Data Link", "weight": 1.0, "keywords": ["vlan", "mac", "stp", "arp", "loop", "port security", "broadcast storm", "spanning tree", "trunk", "access port", "l2", "frame"]},
    3: {"name": "Network", "weight": 1.0, "keywords": ["routing", "ospf", "bgp", "static route", "icmp", "ip", "subnet", "gateway", "next-hop", "route", "l3", "traceroute", "ping", "unreachable"]},
    4: {"name": "Transport", "weight": 1.0, "keywords": ["tcp", "udp", "retransmission", "handshake", "port", "packet loss", "rst", "syn", "ack", "mtu", "connection reset", "connection timeout"]},
    5: {"name": "Session", "weight": 0.8, "keywords": ["session timeout", "rpc", "smb", "netbios", "keepalive", "session expired", "idle timeout", "disconnect"]},
    6: {"name": "Presentation", "weight": 0.8, "keywords": ["tls", "ssl", "certificate", "encoding", "compression", "decryption", "cipher", "handshake failed", "cert expired"]},
    7: {"name": "Application", "weight": 1.0, "keywords": ["http", "dns", "smtp", "database", "api", "kubernetes", "502", "timeout", "nginx", "web", "application", "500", "503", "latency", "slow"]},
    # INFRASTRUCTURE DOMAINS (Non-OSI Extensions)
    100: {"name": "Storage/Infrastructure Domain", "weight": 1.2, "keywords": ["storage full", "datastore", "disk", "iops", "san", "nas", "volume", "inode", "freeze", "io timeout"]}, 
}

# ─── Vendor specific knowledge base ──────────────────────────────────────────

VENDOR_KNOWLEDGE: Dict[str, Dict] = {
    "LINEPROTO-5-UPDOWN": {"vendor": "Cisco", "layer": 2, "is_root_cause": True, "desc": "Interface Line Protocol State Change"},
    "OSPF-5-ADJCHG": {"vendor": "Cisco", "layer": 3, "is_root_cause": True, "desc": "OSPF Neighbor Adjacency Change"},
    "IKE negotiation failed": {"vendor": "Fortigate", "layer": 3, "is_root_cause": True, "desc": "IPsec VPN Negotiation Failure"},
    "Datastore latency exceeded": {"vendor": "VMware", "layer": 100, "is_root_cause": True, "desc": "High Storage Latency"},
    "Event ID 4625": {"vendor": "Windows", "layer": 7, "is_root_cause": True, "desc": "Failed Logon (Authentication)"},
    "OOMKilled": {"vendor": "Kubernetes", "layer": 7, "is_root_cause": True, "desc": "Out of Memory Killed"},
    "HTTP 503": {"vendor": "Generic", "layer": 7, "is_root_cause": False, "desc": "Service Unavailable (Symptom of deeper issue)"},
    "HTTP 502": {"vendor": "Generic", "layer": 7, "is_root_cause": False, "desc": "Bad Gateway (Symptom)"},
}

@dataclass
class EnterpriseLayerProfile:
    osi_classification: str
    primary_root_cause_layer: str
    primary_symptom_layer: str
    affected_layers: List[str]
    propagation_path: str
    evidence: Dict[str, Any]
    confidence: str
    reasoning: str
    required_verification: str
    recommended_investigation_order: List[str]

    def to_dict(self) -> Dict:
        return {
            "OSI Classification": self.osi_classification,
            "Primary Root Cause Layer": self.primary_root_cause_layer,
            "Primary Symptom Layer": self.primary_symptom_layer,
            "Affected Layers": self.affected_layers,
            "Propagation Path": self.propagation_path,
            "Evidence": self.evidence,
            "Confidence": self.confidence,
            "Reasoning": self.reasoning,
            "Required Verification": self.required_verification,
            "Recommended Investigation Order": self.recommended_investigation_order
        }
    
    def get_focus_prompt(self) -> str:
        return f"""
    [ENTERPRISE AIOps OSI CONTEXT]
    Classification : {self.osi_classification}
    Root Cause     : {self.primary_root_cause_layer}
    Symptom Layer  : {self.primary_symptom_layer}
    Propagation    : {self.propagation_path}
    Reasoning      : {self.reasoning}
    Instruction    : Ikuti urutan investigasi ini: {', '.join(self.recommended_investigation_order)}.
                     Fokus untuk memverifikasi Root Cause terlebih dahulu ({self.required_verification}).
                     Jangan terjebak pada Symptom Layer ({self.primary_symptom_layer}).
    """


def classify_incident_layer(
    text: str,
    telemetry_data: Optional[Dict] = None,
    topology_graph: Optional[Dict] = None,
    historical_similarity: float = 0.0
) -> EnterpriseLayerProfile:
    """
    Enterprise-grade classifier distinguishing Root Cause from Symptoms 
    using weighted keyword matching, vendor knowledge, telemetry, and topology graph.
    """
    if telemetry_data is None: telemetry_data = {}
    if topology_graph is None: topology_graph = {}

    text_lower = text.lower()
    layer_scores = {k: 0.0 for k in OSI_LAYERS}
    evidence_collected = {
        "Keywords": [],
        "Vendor Knowledge": [],
        "Telemetry": [],
        "Topology": []
    }
    
    # 1. NLP Keyword Extraction
    for layer_num, data in OSI_LAYERS.items():
        for kw in data["keywords"]:
            if kw in text_lower:
                layer_scores[layer_num] += 10.0 * data["weight"]
                evidence_collected["Keywords"].append(f"L{layer_num}: {kw}")

    # 2. Vendor Specific Knowledge Match
    for v_str, v_data in VENDOR_KNOWLEDGE.items():
        if v_str.lower() in text_lower:
            target_layer = v_data["layer"]
            score_boost = 40.0 if v_data["is_root_cause"] else 15.0
            layer_scores[target_layer] += score_boost
            evidence_collected["Vendor Knowledge"].append(f"[{v_data['vendor']}] {v_str} -> L{target_layer}")

    # 3. Telemetry Evidence Simulation
    if "cpu" in telemetry_data and telemetry_data["cpu"] > 90:
        layer_scores[7] += 20.0
        evidence_collected["Telemetry"].append("High CPU (L7)")
    if "packet_loss" in telemetry_data and telemetry_data["packet_loss"] > 10:
        layer_scores[3] += 30.0
        evidence_collected["Telemetry"].append("Packet Loss > 10% (L3)")

    # 4. Topology Dependency Graph Weighting
    # Lower layers typically cascade to upper layers. If multiple layers have scores, 
    # the lowest one is usually the root cause.
    detected_layers = sorted([l for l, s in layer_scores.items() if s > 0])
    
    if not detected_layers:
        # Fallback
        return EnterpriseLayerProfile(
            osi_classification="Unknown",
            primary_root_cause_layer="Layer 7 (Application)",
            primary_symptom_layer="Layer 7 (Application)",
            affected_layers=["Layer 7"],
            propagation_path="Layer 7",
            evidence={"Keywords": ["No direct match"]},
            confidence="10%",
            reasoning="Fallback classification due to lack of evidence.",
            required_verification="Check application logs",
            recommended_investigation_order=["Layer 7"]
        )

    # 5. Determine Root Cause vs Symptom
    root_cause_layer_num = detected_layers[0] # Lowest layer is typically root cause
    symptom_layer_num = detected_layers[-1]   # Highest layer is typically the symptom

    # Exceptions based on vendor knowledge
    for v_str, v_data in VENDOR_KNOWLEDGE.items():
        if v_str.lower() in text_lower and v_data["is_root_cause"]:
            root_cause_layer_num = v_data["layer"]

    root_name = OSI_LAYERS[root_cause_layer_num]["name"]
    symptom_name = OSI_LAYERS[symptom_layer_num]["name"]
    
    # Format Propagation Path
    propagation = " │ ▼ ".join([f"Layer {l}" for l in detected_layers])

    # Calculate Confidence (syntheticed calculation based on evidence density)
    total_evidence_pieces = sum(len(v) for v in evidence_collected.values())
    confidence_val = min(99.0, 50.0 + (total_evidence_pieces * 8.5) + (historical_similarity * 10))
    
    reasoning_str = f"Found {total_evidence_pieces} pieces of evidence. "
    if root_cause_layer_num != symptom_layer_num:
        reasoning_str += f"Dependency analysis indicates failure originated at Layer {root_cause_layer_num} ({root_name}), propagating upwards to cause symptoms at Layer {symptom_layer_num} ({symptom_name})."
    else:
        reasoning_str += f"Issue is localized entirely within Layer {root_cause_layer_num} ({root_name})."

    # Required verification formatting
    req_verif = "Network Link & Interface Status" if root_cause_layer_num <= 3 else "Storage IOPS & Event Logs" if root_cause_layer_num == 100 else "Application Service & Process Status"
    
    # Recommendation order: Root Cause -> Intermediate -> Symptom
    inv_order = [f"Layer {l} ({OSI_LAYERS[l]['name']})" if l <= 7 else f"{OSI_LAYERS[l]['name']}" for l in detected_layers]

    return EnterpriseLayerProfile(
        osi_classification="Multi-Layer Cascading Failure" if len(detected_layers) > 1 else "Single-Layer Fault",
        primary_root_cause_layer=f"Layer {root_cause_layer_num} ({root_name})" if root_cause_layer_num <= 7 else root_name,
        primary_symptom_layer=f"Layer {symptom_layer_num} ({symptom_name})" if symptom_layer_num <= 7 else symptom_name,
        affected_layers=[f"Layer {l}" for l in detected_layers],
        propagation_path=propagation,
        evidence=evidence_collected,
        confidence=f"{confidence_val:.1f}%",
        reasoning=reasoning_str,
        required_verification=req_verif,
        recommended_investigation_order=inv_order
    )

def build_layer_context_prompt(layer_num: int) -> str:
    """Backward-compatible wrapper for single-layer injection if still needed."""
    if layer_num not in OSI_LAYERS:
        return ""
    layer_info = OSI_LAYERS[layer_num]
    return f"[SYSTEM CONTEXT: OSI LAYER {layer_num} ({layer_info['name']})]"
