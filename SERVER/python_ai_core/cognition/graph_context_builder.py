"""
Enterprise GraphRAG Context Builder (L1-L7 Topology Injection Engine)
Constructs rich, structured markdown context from Knowledge Graph topology,
dependency paths, blast radius, centrality scores, and telemetry for LLM injection.
"""

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("GRAPH_CONTEXT_BUILDER")

class GraphContextBuilder:
    """
    Enterprise Graph Context Builder
    Aggregates L1-L7 topology information into structured prompt sections for LLM reasoning.
    """

    def __init__(self, kg_engine=None):
        self.kg = kg_engine

    def build_dependency_path(self, rca_candidates: List[Dict[str, Any]]) -> str:
        """Formats dependency path traversal from candidate root cause analysis."""
        if not rca_candidates:
            return "No dependency path identified."

        lines = ["### 🔗 Topology Dependency Path Traversal:"]
        for idx, cand in enumerate(rca_candidates[:3], 1):
            path = cand.get("path", [])
            node_id = cand.get("node_id", "Unknown")
            score = cand.get("score", 0.0)
            confidence = cand.get("confidence", 0.0)
            reason = cand.get("reason", "")

            path_str = " ➔ ".join(path) if path else node_id
            lines.append(f"{idx}. **Candidate Root Cause**: `{node_id}` (Score: {score}, Conf: {confidence*100:.1f}%)")
            lines.append(f"   - **Path**: {path_str}")
            lines.append(f"   - **Causal Rationale**: {reason}")
        return "\n".join(lines)

    def build_blast_radius(self, blast_radius_data: Dict[str, Any]) -> str:
        """Formats downstream blast radius and impact estimation."""
        if not blast_radius_data:
            return "Blast radius information unavailable."

        target = blast_radius_data.get("target", "Unknown")
        severity = blast_radius_data.get("severity_score", 0.0)
        impact = blast_radius_data.get("business_impact", "LOW")
        devices = blast_radius_data.get("affected_devices", [])
        services = blast_radius_data.get("affected_services", [])
        sites = blast_radius_data.get("affected_sites", [])

        lines = [
            "### 💥 Blast Radius & Downstream Impact:",
            f"- **Target Node**: `{target}`",
            f"- **Business Impact Level**: `{impact}` (Severity Score: {severity}/100)",
            f"- **Affected Services**: {', '.join(services) if services else 'None'}",
            f"- **Affected Devices ({len(devices)})**: {', '.join(devices[:5])}{'...' if len(devices)>5 else ''}",
            f"- **Affected Sites**: {', '.join(sites) if sites else 'GLOBAL'}"
        ]
        return "\n".join(lines)

    def build_common_failure(self, common_ancestors: List[Dict[str, Any]]) -> str:
        """Formats common cause analysis results across multiple symptom nodes."""
        if not common_ancestors:
            return "No common infrastructure bottleneck detected."

        lines = ["### 🧬 Common Cause Infrastructure Bottlenecks:"]
        for idx, anc in enumerate(common_ancestors[:2], 1):
            node_id = anc.get("node_id", "Unknown")
            score = anc.get("common_cause_score", 0.0)
            coverage = anc.get("symptom_coverage", 0.0)
            node_type = anc.get("node_type", "Unknown")
            lines.append(f"{idx}. `{node_id}` ({node_type}) - Coverage: {coverage*100:.0f}%, Common Cause Score: {score}")
        return "\n".join(lines)

    def build_network_context(self, topology_data: Dict[str, Any]) -> str:
        """Extracts Layer 1-Layer 4 Network context (IP, Subnet, Gateway, VLAN, Wi-Fi)."""
        net = topology_data.get("network", {})
        ip = net.get("ipv4", topology_data.get("ip_address", "N/A"))
        gw = net.get("gateway", "N/A")
        vlan = net.get("vlan_id", "Default")
        ssid = net.get("ssid", "N/A")
        bssid = net.get("bssid", "N/A")
        rssi = net.get("wifi_signal", "N/A")
        loss = net.get("packet_loss", "0%")

        return (
            "### 🌐 Network Layer (L1-L4) Context:\n"
            f"- **Client IP / Subnet**: `{ip}` | **VLAN**: `{vlan}`\n"
            f"- **Default Gateway**: `{gw}`\n"
            f"- **Wi-Fi Connection**: SSID `{ssid}` (BSSID: `{bssid}`, RSSI: `{rssi}` dBm)\n"
            f"- **Network Health**: Packet Loss: `{loss}`"
        )

    def build_service_context(self, topology_data: Dict[str, Any]) -> str:
        """Formats active services & DNS context."""
        net = topology_data.get("network", {})
        dns = net.get("dns", "N/A")
        dhcp = net.get("dhcp", "N/A")
        vpn = net.get("vpn", "Inactive")
        return (
            "### ⚙️ Core Infrastructure Services (L5):\n"
            f"- **DNS Servers**: `{dns}`\n"
            f"- **DHCP Lease**: `{dhcp}`\n"
            f"- **VPN / NetBird State**: `{vpn}`"
        )

    def build_application_context(self, topology_data: Dict[str, Any]) -> str:
        """Formats Application Layer (L7) context."""
        app = topology_data.get("application", {})
        target_app = app.get("name", topology_data.get("component", "Unknown Application"))
        http_code = app.get("last_http_code", "200")
        latency = app.get("latency_ms", "N/A")
        return (
            "### 💻 Application Layer (L7) Context:\n"
            f"- **Target Application / Endpoint**: `{target_app}`\n"
            f"- **HTTP Status Code**: `{http_code}`\n"
            f"- **Response Latency**: `{latency} ms`"
        )

    def build_storage_context(self, topology_data: Dict[str, Any]) -> str:
        """Formats Storage Layer (SAN/NAS/Local Disk) context."""
        storage = topology_data.get("storage", {})
        status = storage.get("status", "HEALTHY")
        usage = storage.get("usage_pct", "N/A")
        return (
            "### 💾 Storage Layer Context:\n"
            f"- **Disk Health / SMART**: `{status}`\n"
            f"- **Capacity Usage**: `{usage}%`"
        )

    def build_database_context(self, topology_data: Dict[str, Any]) -> str:
        """Formats Database Layer context."""
        db = topology_data.get("database", {})
        db_node = db.get("node_id", "N/A")
        conn_pool = db.get("conn_pool_status", "HEALTHY")
        return (
            "### 🗄️ Database Infrastructure Context:\n"
            f"- **Database Node**: `{db_node}`\n"
            f"- **Connection Pool Status**: `{conn_pool}`"
        )

    def build_switch_context(self, topology_data: Dict[str, Any]) -> str:
        """Formats Switch Port & Neighbor (LLDP/CDP) context."""
        sw = topology_data.get("switch", {})
        port = sw.get("switch_port", topology_data.get("switch_port", "N/A"))
        neighbor = sw.get("neighbor", "N/A")
        return (
            "### 🔌 Switch & Physical Access Layer (L1-L2):\n"
            f"- **Switch Port**: `{port}`\n"
            f"- **LLDP/CDP Switch Neighbor**: `{neighbor}`"
        )

    def build_firewall_context(self, topology_data: Dict[str, Any]) -> str:
        """Formats Firewall & Security Layer context."""
        fw = topology_data.get("firewall", {})
        cluster = fw.get("firewall_cluster", "N/A")
        rule_block = fw.get("blocked_rule", "None")
        return (
            "### 🛡️ Firewall & Perimeter Security (L4-L7):\n"
            f"- **Firewall Cluster**: `{cluster}`\n"
            f"- **Blocked Rule Hit**: `{rule_block}`"
        )

    def build_summary(self, topology_data: Dict[str, Any], rca_results: List[Dict[str, Any]], blast_data: Dict[str, Any]) -> str:
        """Generates executive summary header for Graph Context Injection."""
        target = topology_data.get("agent_id", topology_data.get("pc_name", "Client-PC"))
        top_cause = rca_results[0].get("node_id", "N/A") if rca_results else "N/A"
        impact = blast_data.get("business_impact", "LOW") if blast_data else "LOW"
        return (
            f"SUMMARY: GraphRAG analyzed device `{target}`. "
            f"Top Suspected Root Cause: `{top_cause}` with Business Impact `{impact}`."
        )

    def build_context(
        self,
        symptom_node_id: str,
        topology_data: Optional[Dict[str, Any]] = None,
        rca_candidates: Optional[List[Dict[str, Any]]] = None,
        blast_radius_data: Optional[Dict[str, Any]] = None,
        common_ancestors: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Master method aggregating all Graph Context Builder sections into a complete,
        high-density Graph Prompt Injection block.
        """
        topo = topology_data or {}
        rca = rca_candidates or []
        blast = blast_radius_data or {}
        common = common_ancestors or []

        summary_line = self.build_summary(topo, rca, blast)
        dep_path = self.build_dependency_path(rca)
        blast_str = self.build_blast_radius(blast)
        common_str = self.build_common_failure(common)
        net_str = self.build_network_context(topo)
        switch_str = self.build_switch_context(topo)
        fw_str = self.build_firewall_context(topo)
        service_str = self.build_service_context(topo)
        app_str = self.build_application_context(topo)
        db_str = self.build_database_context(topo)
        storage_str = self.build_storage_context(topo)

        context_prompt = (
            f"\n\n==================== 🕸️ GRAPH CONTEXT INJECTION (L1-L7 TOPOLOGY) ====================\n"
            f"{summary_line}\n\n"
            f"{dep_path}\n\n"
            f"{blast_str}\n\n"
            f"{common_str}\n\n"
            f"{net_str}\n"
            f"{switch_str}\n"
            f"{fw_str}\n"
            f"{service_str}\n"
            f"{app_str}\n"
            f"{db_str}\n"
            f"{storage_str}\n"
            f"=======================================================================================\n\n"
        )
        return context_prompt
