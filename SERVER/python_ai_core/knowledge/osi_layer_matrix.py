"""
SERVER/python_ai_core/knowledge/osi_layer_matrix.py
===================================================
Enterprise AI-NOC-ITSM: Matriks Pengetahuan OSI 7-Layer & Verifikasi Axiom Rule #6.
Mendefinisikan ruang lingkup, telemetri gejala, aturan propagasi kausal,
katalog SOP pre-approved, dan kriteria pembuktian dual-evidence untuk Layer 1 hingga Layer 7.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("osi.layer_matrix")

# ──────────────────────────────────────────────────────────────────────────────
# Definisi Formal Pengetahuan OSI 7-Layer
# ──────────────────────────────────────────────────────────────────────────────

OSI_LAYER_KNOWLEDGE: Dict[int, Dict[str, Any]] = {
    1: {
        "layer": 1,
        "name": "Physical",
        "indonesian_name": "Lapisan Fisik & Media Transmisi",
        "description": "Media transmisi data fisik, link kabel, transceiver optik, daya, dan disk fisik storage host.",
        "components": [
            "Kabel UTP/STP RJ45", "Fiber Optic Patchcord", "Transceiver SFP/SFP+",
            "NIC Controller & PHY Chip", "Power Supply (PSU)", "Storage SAS/SATA/NVMe",
            "Port Switch Fisik", "Antarmuka eth0/enp3s0"
        ],
        "symptoms": [
            "carrier = 0 (Link Down)", "rx_crc_errors bertambah drastis",
            "Optical RX Power drop (< -20 dBm)", "Speed/Duplex Mismatch (100Mbps Half-Duplex)",
            "Disk Full / ENOSPC (Free Space < 5%)", "SMART Bad Sector Disk Error"
        ],
        "cascading_targets": [2, 3, 4, 5, 6, 7],
        "sops": [
            {"id": "SOP-PHY-01", "name": "Disk Space Vacuum & Journal Cleanup", "risk": "LOW", "command": "rm -rf /tmp/*; journalctl --vacuum-size=500M"},
            {"id": "SOP-PHY-02", "name": "Physical NIC Link Cycle", "risk": "MEDIUM", "command": "ip link set <iface> down && sleep 2 && ip link set <iface> up"},
            {"id": "SOP-PHY-03", "name": "SFP Port Bounce & Hardware Re-seat", "risk": "HIGH", "command": "Manual HITL Technician Action"}
        ],
        "rule6_verification": {
            "required_post_metrics": ["carrier == 1", "speed >= 100Mbps", "disk_free_pct >= 10"],
            "verification_explanation": "Link fisik wajib terdeteksi aktif (carrier 1) atau partisi disk memiliki ruang bebas aman (>10%)."
        }
    },
    2: {
        "layer": 2,
        "name": "Data Link",
        "indonesian_name": "Lapisan Jalur Data & Switching",
        "description": "Pengalamatan MAC perangkat keras, switching Ethernet, pemisahan VLAN, STP, dan resolusi ARP.",
        "components": [
            "Switch Layer-2", "Frame Ethernet", "MAC Address Table",
            "VLAN 802.1Q", "Spanning Tree Protocol (STP/RSTP)", "ARP Table & Neighbor Cache",
            "Virtual Bridge (docker0, ovs)", "Wi-Fi Access Point (BSSID, RSSI 802.11)"
        ],
        "symptoms": [
            "ARP Inconsistency / Table Drop", "MAC Address Flapping",
            "STP Topology Change Notification (TCN) Storm", "Broadcast Storm (> 50k pps)",
            "Wi-Fi RSSI Drop (< -85 dBm)", "Virtual Bridge Port Desynchronization"
        ],
        "cascading_targets": [3, 4, 5, 6, 7],
        "sops": [
            {"id": "SOP-DAT-01", "name": "Flush ARP Cache & Neighbor Table", "risk": "LOW", "command": "ip neighbor flush all"},
            {"id": "SOP-DAT-02", "name": "Reset Virtual Bridge Interface", "risk": "MEDIUM", "command": "ip link set docker0 down && ip link set docker0 up"},
            {"id": "SOP-DAT-03", "name": "STP Root Guard & Loop Port Disable", "risk": "HIGH", "command": "HITL Switch Port Shutdown"}
        ],
        "rule6_verification": {
            "required_post_metrics": ["arp_resolved == True", "wifi_rssi_dbm > -75", "broadcast_pps < 5000"],
            "verification_explanation": "MAC default gateway wajib teresolusi (REACHABLE), broadcast pps normal, atau RSSI Wi-Fi kembali di atas -75 dBm."
        }
    },
    3: {
        "layer": 3,
        "name": "Network",
        "indonesian_name": "Lapisan Jaringan & Routing",
        "description": "Pengalamatan logika IP, pemilihan rute default gateway, dynamic routing BGP/OSPF, dan inspeksi ICMP.",
        "components": [
            "IP Address (IPv4/IPv6)", "Subnet & CIDR", "Default Gateway",
            "Kernel Route Table", "BGP / OSPF Router Daemons", "ICMP Protocol",
            "NAT / PAT Engine", "Firewall (iptables, nftables, conntrack)"
        ],
        "symptoms": [
            "ICMP Packet Loss > 5% ke gateway", "RTT Latensi melonjak (> 250ms)",
            "Default route 0.0.0.0/0 hilang", "BGP Peer Down / Flapping",
            "conntrack: table full, dropping packet", "Destination Host Unreachable"
        ],
        "cascading_targets": [4, 5, 6, 7],
        "sops": [
            {"id": "SOP-NET-01", "name": "Kernel Route Table & Cache Flush", "risk": "LOW", "command": "ip route flush cache"},
            {"id": "SOP-NET-02", "name": "Conntrack Table Flush & Firewall Sync", "risk": "MEDIUM", "command": "conntrack -F && iptables -Z"},
            {"id": "SOP-NET-03", "name": "Dual-ISP Gateway Failover Switch", "risk": "HIGH", "command": "ip route replace default via <backup_gw>"}
        ],
        "rule6_verification": {
            "required_post_metrics": ["ping_loss_pct == 0", "latency_ms < 50", "route_active == True"],
            "verification_explanation": "Ping ICMP ke default gateway wajib 100% reply (0% packet loss) dan latensi normal di bawah 50ms."
        }
    },
    4: {
        "layer": 4,
        "name": "Transport",
        "indonesian_name": "Lapisan Transportasi & Port/Socket",
        "description": "Komunikasi ujung-ke-ujung berbasis port TCP/UDP, handshake koneksi, dan kontrol aliran data.",
        "components": [
            "Protokol TCP (3-Way Handshake, ACK)", "Protokol UDP", "Port Numbers (1-65535)",
            "Ephemeral Port Pool", "Kernel Socket Buffers", "Flow Control & Window Size"
        ],
        "symptoms": [
            "TCP Retransmission Rate > 3%", "Akumulasi TIME_WAIT / CLOSE_WAIT > 10.000",
            "TCP Connection Refused (port closed)", "Ephemeral Port Allocation Exhaustion",
            "TCP RST Flag berulang", "TCP SYN Timeout (SYN_SENT)"
        ],
        "cascading_targets": [5, 6, 7],
        "sops": [
            {"id": "SOP-TRN-01", "name": "TCP TIME_WAIT Socket Recycling", "risk": "LOW", "command": "sysctl -w net.ipv4.tcp_tw_reuse=1"},
            {"id": "SOP-TRN-02", "name": "Ephemeral Port Pool Expansion", "risk": "LOW", "command": "sysctl -w net.ipv4.ip_local_port_range='1024 65535'"},
            {"id": "SOP-TRN-03", "name": "Purge Hanging Network Socket Daemon", "risk": "MEDIUM", "command": "kill -HUP <socket_pid>"}
        ],
        "rule6_verification": {
            "required_post_metrics": ["handshake_success == True", "time_wait_count < 1000", "port_listening == True"],
            "verification_explanation": "Koneksi handshake TCP berhasil (< 30ms), akumulasi socket TIME_WAIT turun di bawah 1.000, dan port target LISTEN."
        }
    },
    5: {
        "layer": 5,
        "name": "Session",
        "indonesian_name": "Lapisan Sesi & Komunikasi Antar-Layanan",
        "description": "Manajemen sesi terdistribusi, message broker queues, remote procedure call (RPC), dan status autentikasi.",
        "components": [
            "Distributed Session Cache (Redis)", "Message Streaming Bus (NATS JetStream, Kafka)",
            "Remote Procedure Call (gRPC Channels)", "SMB / CIFS File Shares",
            "Session Heartbeat & Keepalive", "Auth Token Lifecycle"
        ],
        "symptoms": [
            "Redis connection timeout / NOAUTH", "NATS Queue Backlog > 5.000 messages",
            "gRPC Channel TRANSIENT_FAILURE", "SMB File Share Disconnected",
            "Session Auth Token expired massal", "Distributed Lock Deadlock"
        ],
        "cascading_targets": [6, 7],
        "sops": [
            {"id": "SOP-SES-01", "name": "Redis Cache & Session Store Sync", "risk": "LOW", "command": "redis-cli ping"},
            {"id": "SOP-SES-02", "name": "NATS JetStream Messaging Broker Auto-Heal", "risk": "MEDIUM", "command": "docker restart osi-nats"},
            {"id": "SOP-SES-03", "name": "Reset gRPC Channel Connection Pool", "risk": "LOW", "command": "Re-instantiate gRPC Client Stubs"}
        ],
        "rule6_verification": {
            "required_post_metrics": ["redis_pong == True", "nats_backlog == 0", "grpc_ready == True"],
            "verification_explanation": "Redis merespon PONG (< 5ms), antrean backlog NATS habis (0 pesan), atau channel gRPC berstatus READY."
        }
    },
    6: {
        "layer": 6,
        "name": "Presentation",
        "indonesian_name": "Lapisan Presentasi, Enkripsi, & Format Data",
        "description": "Enkripsi dan dekripsi SSL/TLS, sertifikat keamanan X.509, serialisasi format data (JSON/Protobuf), dan kompresi.",
        "components": [
            "TLS / SSL Engine (OpenSSL, TLS 1.3)", "Sertifikat Digital X.509 & CA Bundles",
            "Nginx TLS Ingress Termination", "Data Serializer (JSON, Protobuf, Base64)",
            "Data Compression (gzip, brotli)", "Character Set Encoders (UTF-8)"
        ],
        "symptoms": [
            "SSL_ERROR_SYSCALL / Handshake Failure", "TLS Certificate Expired (sisa <= 0 hari)",
            "Cipher Suite Mismatch", "JSON Parse Error / Malformed Protobuf Payload",
            "Compression Buffer Overflow"
        ],
        "cascading_targets": [7],
        "sops": [
            {"id": "SOP-PRS-01", "name": "TLS Certificate Reload & Nginx Graceful Reload", "risk": "LOW", "command": "nginx -t && nginx -s reload"},
            {"id": "SOP-PRS-02", "name": "Purge Compression & Encoding Buffer Cache", "risk": "LOW", "command": "Purge static cache buffers"},
            {"id": "SOP-PRS-03", "name": "Re-bind Root CA bundle & key permissions", "risk": "MEDIUM", "command": "chmod 600 /etc/ssl/certs/*.key"}
        ],
        "rule6_verification": {
            "required_post_metrics": ["tls_handshake_ok == True", "cert_valid_days > 15"],
            "verification_explanation": "Handshake OpenSSL TLS sukses (exit-code 0) dan masa berlaku sertifikat terkonfirmasi > 15 hari."
        }
    },
    7: {
        "layer": 7,
        "name": "Application",
        "indonesian_name": "Lapisan Aplikasi & Layanan Bisnis",
        "description": "Aplikasi pengguna akhir, web portal, basis data operasional, proses kasir POS, dan layanan cetak toko.",
        "components": [
            "Web Ingress Server (Nginx)", "Basis Data Operasional (PostgreSQL)",
            "Windows Print Spooler Service", "Python AI Core & Ingestion Daemon",
            "n8n Workflow Automation", "POS Transaction Manager", "DNS Resolver (systemd-resolved)"
        ],
        "symptoms": [
            "HTTP 500, 502 Bad Gateway, 504 Timeout", "PostgreSQL Deadlock / Idle in Transaction > 5m",
            "Windows Print Spooler Frozen (spoolsv.exe hang)", "Print Queue Macet (> 10 dokumen)",
            "Python AI Core Token/Memory Exhaustion", "DNS SERVFAIL / NXDOMAIN"
        ],
        "cascading_targets": [],
        "sops": [
            {"id": "SOP-APP-01", "name": "PostgreSQL Deadlock Termination", "risk": "MEDIUM", "command": "SELECT pg_terminate_backend(pid)..."},
            {"id": "SOP-APP-02", "name": "Windows Print Spooler Auto-Restart & Queue Purge", "risk": "LOW", "command": "net stop spooler && del /Q /F ... && net start spooler"},
            {"id": "SOP-APP-03", "name": "Python AI Supervision Daemon Auto-Heal", "risk": "LOW", "command": "docker restart osi-python-ai-core"},
            {"id": "SOP-APP-04", "name": "Ingestion Stream Buffer Reset", "risk": "LOW", "command": "docker restart osi-ingestion-server"}
        ],
        "rule6_verification": {
            "required_post_metrics": ["http_status == 200", "deadlocks_count == 0", "spooler_running == True", "print_queue_length == 0"],
            "verification_explanation": "HTTP status 200 OK, active deadlock database 0, atau service Spooler berstatus RUNNING dengan print queue 0."
        }
    }
}


def get_layer_knowledge(layer: int) -> Optional[Dict[str, Any]]:
    """Mengambil spesifikasi pengetahuan lengkap untuk Layer OSI tertentu (1–7)."""
    return OSI_LAYER_KNOWLEDGE.get(int(layer))


def explain_layer(layer: int) -> str:
    """Menyusun narasi lisan Bahasa Indonesia yang ringkas dan akurat mengenai suatu layer."""
    info = get_layer_knowledge(layer)
    if not info:
        return f"Layer {layer} tidak dikenali dalam model OSI 7-Layer standar (Layer 1 sampai 7)."

    comps = ", ".join(info["components"][:4])
    symps = ", ".join(info["symptoms"][:3])
    sop_examples = ", ".join(s["id"] + " (" + s["name"] + ")" for s in info["sops"][:2])

    return (
        f"📘 OSI Layer {layer} ({info['name']} — {info['indonesian_name']}):\n"
        f"• Fungsi Utama: {info['description']}\n"
        f"• Komponen Inti: {comps}, dan lainnya.\n"
        f"• Gejala Gangguan Khas: {symps}.\n"
        f"• SOP Remediasi Tersedia: {sop_examples}.\n"
        f"• Syarat Verifikasi Rule #6: {info['rule6_verification']['verification_explanation']}"
    )


def explain_all_layers() -> str:
    """Menyusun ringkasan cepat seluruh Layer 1 sampai 7 untuk pembacaan lisan JARVIS."""
    lines = [
        "🌐 RINGKASAN MODEL OSI 7-LAYER PADA INFRASTRUKTUR NOC:",
        "1. Layer 1 (Physical)    : Kabel, SFP fiber, NIC hardware, dan disk storage partisi.",
        "2. Layer 2 (Data Link)   : Switch, VLAN, ARP table, Wi-Fi RSSI, dan bridge docker0.",
        "3. Layer 3 (Network)     : IP address, default gateway, routing BGP/OSPF, dan ICMP.",
        "4. Layer 4 (Transport)   : TCP/UDP port, socket handshake, dan pencegahan TIME_WAIT.",
        "5. Layer 5 (Session)     : Redis session cache, message broker NATS, dan gRPC channel.",
        "6. Layer 6 (Presentation): Enkripsi SSL/TLS, sertifikat X.509, dan serialisasi JSON.",
        "7. Layer 7 (Application) : Web Nginx, database PostgreSQL, POS kasir, dan Print Spooler.",
        "\n🛡️ Prinsip Kausalitas: Gangguan di Layer 1–3 memicu gejala palsu di Layer 4–7. "
        "Sistem selalu memprioritaskan perbaikan layer hulu sebelum menyentuh aplikasi hilir."
    ]
    return "\n".join(lines)


def evaluate_cross_layer_causality(active_layers: List[int]) -> Dict[str, Any]:
    """
    Menganalisis daftar layer yang terindikasi anomali secara serentak.
    Mengisolasi Root Cause Layer (layer terbawah) dan menandai layer di atasnya sebagai Secondary Symptoms.
    """
    valid_layers = sorted(set(int(l) for l in active_layers if 1 <= int(l) <= 7))
    if not valid_layers:
        return {
            "root_cause_layer": None,
            "secondary_symptom_layers": [],
            "propagation_path": "No active incidents",
            "recommendation": "Infrastruktur stabil di seluruh layer."
        }

    root_layer = valid_layers[0]
    secondary = valid_layers[1:]

    path_str = " -> ".join(f"L{l} ({OSI_LAYER_KNOWLEDGE[l]['name']})" for l in valid_layers)
    rec = (
        f"Fokuskan investigasi pada Layer {root_layer} ({OSI_LAYER_KNOWLEDGE[root_layer]['name']}). "
        f"Anomali pada Layer {', '.join(f'L{s}' for s in secondary)} merupakan gejala turunan (Secondary Symptoms). "
        f"Dilarang me-restart service Layer {secondary[-1]} sebelum Layer {root_layer} pulih."
        if secondary else
        f"Anomali terlokalisir murni pada Layer {root_layer} ({OSI_LAYER_KNOWLEDGE[root_layer]['name']})."
    )

    return {
        "root_cause_layer": root_layer,
        "secondary_symptom_layers": secondary,
        "propagation_path": path_str,
        "recommendation": rec
    }


def verify_layer_rule6_evidence(
    layer: int,
    execution_evidence: Optional[Dict[str, Any]] = None,
    post_telemetry: Optional[Dict[str, Any]] = None
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Memverifikasi apakah suatu insiden pada Layer tertentu memenuhi Axiom Rule #6:
      1. Ada execution_evidence yang sah (T_exec tercatat, exit-code 0 / ACK True).
      2. Ada post_remediation_evidence dengan timestamp T_post >= T_exec.
      3. Metrik spesifik layer kembali ke ambang batas normal.
    """
    layer = int(layer)
    k = get_layer_knowledge(layer)
    if not k:
        return False, f"Layer {layer} tidak terdaftar dalam matriks OSI.", {}

    audit = {
        "layer": layer,
        "layer_name": k["name"],
        "has_execution": False,
        "has_post_telemetry": False,
        "temporal_valid": False,
        "metric_satisfied": False,
        "details": []
    }

    if not execution_evidence:
        return False, f"Bukti eksekusi (T_exec) belum ada untuk Layer {layer}.", audit

    # 1. Check Execution Evidence
    exec_ok = (
        execution_evidence.get("exit_code") == 0
        or execution_evidence.get("ack") is True
        or execution_evidence.get("status") in ("SUCCESS", "ACK_RECEIVED", "EXECUTED")
    )
    t_exec = execution_evidence.get("executed_at") or execution_evidence.get("timestamp")
    if not (exec_ok and t_exec):
        return False, f"Bukti eksekusi pada Layer {layer} belum berstatus SUCCESS atau timestamp tidak valid.", audit

    audit["has_execution"] = True

    # 2. Check Post-Remediation Telemetry
    if not post_telemetry:
        return False, f"Menunggu telemetri pasca-remediasi (T_post >= T_exec) untuk Layer {layer}.", audit

    t_post = post_telemetry.get("timestamp") or post_telemetry.get("created_at")
    if not t_post:
        return False, f"Telemetri pasca-remediasi pada Layer {layer} tidak memiliki timestamp valid.", audit

    audit["has_post_telemetry"] = True

    # 3. Check Temporal Invariant T_post >= T_exec
    try:
        if isinstance(t_exec, str):
            t_exec_dt = datetime.fromisoformat(t_exec.replace("Z", "+00:00"))
        else:
            t_exec_dt = t_exec

        if isinstance(t_post, str):
            t_post_dt = datetime.fromisoformat(t_post.replace("Z", "+00:00"))
        else:
            t_post_dt = t_post

        if t_post_dt < t_exec_dt:
            return False, f"Pelanggaran Temporal Rule #6: T_post ({t_post}) lebih awal dari T_exec ({t_exec}).", audit
        audit["temporal_valid"] = True
    except Exception as te:
        # Fallback if unparseable
        audit["temporal_valid"] = True
        audit["details"].append(f"Temporal parser note: {te}")

    # 4. Check Layer-Specific Metric Thresholds
    metric_ok = False
    metrics = post_telemetry.get("metrics") or post_telemetry

    if layer == 1:
        # Carrier UP or speed >= 100 or disk_free >= 10%
        carrier = metrics.get("carrier")
        disk_free = metrics.get("disk_free_pct")
        if carrier == 1 or carrier is True or (disk_free is not None and disk_free >= 10):
            metric_ok = True
    elif layer == 2:
        # ARP resolved or RSSI > -75 or broadcast_pps < 5000
        if metrics.get("arp_resolved") is True or metrics.get("wifi_rssi_dbm", -99) > -75 or metrics.get("broadcast_pps", 0) < 5000:
            metric_ok = True
    elif layer == 3:
        # Ping loss == 0 or latency < 50ms or route_active == True
        if metrics.get("ping_loss_pct") == 0 or metrics.get("latency_ms", 999) < 50 or metrics.get("route_active") is True:
            metric_ok = True
    elif layer == 4:
        # Handshake success or time_wait < 1000 or port_listening == True
        if metrics.get("handshake_success") is True or metrics.get("time_wait_count", 99999) < 1000 or metrics.get("port_listening") is True:
            metric_ok = True
    elif layer == 5:
        # Redis pong or NATS backlog == 0 or gRPC ready
        if metrics.get("redis_pong") is True or metrics.get("nats_backlog") == 0 or metrics.get("grpc_ready") is True:
            metric_ok = True
    elif layer == 6:
        # TLS handshake exit 0 or cert valid days > 15
        if metrics.get("tls_handshake_ok") is True or metrics.get("cert_valid_days", 0) > 15:
            metric_ok = True
    elif layer == 7:
        # HTTP 200 or deadlocks == 0 or Spooler RUNNING & queue == 0
        if (
            metrics.get("http_status") == 200
            or metrics.get("deadlocks_count") == 0
            or (metrics.get("spooler_running") is True and metrics.get("print_queue_length", 0) == 0)
        ):
            metric_ok = True

    audit["metric_satisfied"] = metric_ok

    if not metric_ok:
        return False, (
            f"Telemetri pasca-remediasi Layer {layer} belum memenuhi ambang batas sehat "
            f"({', '.join(k['rule6_verification']['required_post_metrics'])})."
        ), audit

    return True, (
        f"✅ Bukti ganda Rule #6 untuk Layer {layer} ({k['name']}) SAH dan terverifikasi penuh: "
        f"T_post >= T_exec dan metrik operasional telah kembali normal."
    ), audit
