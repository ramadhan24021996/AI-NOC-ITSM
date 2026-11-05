"""
osi_classifier.py
=================
OSI 7-Layer Adaptive Multi-Evidence Classifier.
Mengklasifikasikan bukti insiden ke dalam 7 Lapisan OSI (L1 Physical - L7 Application)
berdasarkan matriks telemetri, status port, log sistem, dan bukti jaringan.
"""

import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger("OSI7LayerClassifier")


class OSI7LayerAdaptiveClassifier:
    """
    Engine Pengklasifikasi OSI 7-Layer Adaptif.
    Membangun Evidence Matrix per lapisan OSI dan menentukan primary + secondary layers.
    """

    def classify_incident(
        self,
        symptoms: List[str],
        telemetry: Dict[str, Any],
        evidence: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Mengklasifikasikan bukti insiden ke 7 Layer OSI.
        Returns:
            {
                "primary_layer": "L7_APPLICATION",
                "secondary_layers": ["L4_TRANSPORT"],
                "layer_scores": {"L1": 0.1, ..., "L7": 0.85},
                "evidence_matrix": {...}
            }
        """
        layer_scores = {
            "L1_PHYSICAL": 0.05,
            "L2_DATA_LINK": 0.05,
            "L3_NETWORK": 0.05,
            "L4_TRANSPORT": 0.05,
            "L5_SESSION": 0.05,
            "L6_PRESENTATION": 0.05,
            "L7_APPLICATION": 0.05,
        }

        evidence_matrix = {k: [] for k in layer_scores.keys()}

        # Synthesize text from symptoms & evidence
        text_corpus = " ".join(symptoms).lower()
        for ev in evidence:
            text_corpus += f" {ev.get('key', '')} {ev.get('value', '')}".lower()

        # L1 Physical: Kabel, NIC hardware, link down, PHY error
        if any(w in text_corpus for w in ["cable", "nic down", "link down", "phy error", "power off", "hardware jam"]):
            layer_scores["L1_PHYSICAL"] += 0.70
            evidence_matrix["L1_PHYSICAL"].append("Hardware / Link down indicator detected")

        # L2 Data Link: MAC, ARP, Wi-Fi RSSI, BSSID drop, VLAN
        if any(w in text_corpus for w in ["wifi", "rssi", "bssid", "arp", "vlan", "mac address", "disconnected ssid"]):
            layer_scores["L2_DATA_LINK"] += 0.65
            evidence_matrix["L2_DATA_LINK"].append("L2 Wireless / Data-Link metric detected")

        # L3 Network: IP, ICMP ping, unreachable, route, gateway
        if any(w in text_corpus for w in ["ping", "unreachable", "ip drop", "gateway", "packet loss", "routing"]):
            layer_scores["L3_NETWORK"] += 0.75
            evidence_matrix["L3_NETWORK"].append("L3 IP Connectivity / Routing failure detected")

        # L4 Transport: TCP, UDP, port closed, connection refused, socket leak
        if any(w in text_corpus for w in ["tcp", "port", "connection refused", "socket", "syn_sent", "reset_stream"]):
            layer_scores["L4_TRANSPORT"] += 0.70
            evidence_matrix["L4_TRANSPORT"].append("L4 Transport Port / TCP Connection error detected")

        # L5 Session: Session timeout, RPC disconnect, authentication session
        if any(w in text_corpus for w in ["session", "auth timeout", "rpc disconnect", "token expired"]):
            layer_scores["L5_SESSION"] += 0.55
            evidence_matrix["L5_SESSION"].append("L5 Session Lifecycle timeout detected")

        # L6 Presentation: SSL/TLS handshake, JSON parse error, serialization
        if any(w in text_corpus for w in ["ssl", "tls", "cert", "json parse", "encoding", "decryption"]):
            layer_scores["L6_PRESENTATION"] += 0.60
            evidence_matrix["L6_PRESENTATION"].append("L6 Presentation Encoders / Certificate error detected")

        # L7 Application: Spooler, Postgres, Nginx, HTTP 500/504, Process crash, OOM
        if any(w in text_corpus for w in ["spooler", "print", "postgres", "nginx", "http 500", "http 504", "process stopped", "oom", "crash"]):
            layer_scores["L7_APPLICATION"] += 0.85
            evidence_matrix["L7_APPLICATION"].append("L7 Application / Service execution failure detected")

        # Telemetry evaluation boosts
        if telemetry.get("wifi_rssi_dbm", 0) < -80:
            layer_scores["L2_DATA_LINK"] += 0.30
            evidence_matrix["L2_DATA_LINK"].append("Weak Wi-Fi RSSI signal (< -80 dBm)")

        if telemetry.get("spooler_stopped") or telemetry.get("app_crash"):
            layer_scores["L7_APPLICATION"] += 0.40
            evidence_matrix["L7_APPLICATION"].append("Active Application Process Halt Telemetry")

        # Normalize & Rank Layers
        sorted_layers = sorted(layer_scores.items(), key=lambda x: x[1], reverse=True)
        primary_layer = sorted_layers[0][0]
        secondary_layers = [l[0] for l in sorted_layers[1:3] if l[1] > 0.30]

        logger.info(f"[OSIClassifier] Primary: {primary_layer} ({sorted_layers[0][1]:.2f}) | Secondary: {secondary_layers}")

        return {
            "primary_layer": primary_layer,
            "secondary_layers": secondary_layers,
            "layer_scores": layer_scores,
            "layer_confidence": round(sorted_layers[0][1], 2),
            "evidence_matrix": evidence_matrix
        }
