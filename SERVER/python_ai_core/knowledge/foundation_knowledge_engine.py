"""
Enterprise AI OS — Sprint K: Foundation Knowledge Engine
OSI AI Ops

Tujuan:
Membangun fondasi pengetahuan AI setara dengan Senior Enterprise Infrastructure Engineer.
Mencegah AI "menghafal jawaban" dan memaksanya melakukan reasoning logis 
berdasarkan pemahaman komponen dan arsitektur (Computer, Network, OSI Layers).
"""

import json
import logging
from typing import Dict, Any, List

logger = logging.getLogger("FOUNDATION_KNOWLEDGE")

class FoundationKnowledgeEngine:
    def __init__(self):
        # Pengetahuan Statis - Bagian 1 & 2 & 3: Fundamental Knowledge
        self.knowledge_base = {
            "computer_fundamental": [
                "CPU", "Core", "Thread", "Clock", "Cache L1 L2 L3", "NUMA",
                "Memory", "RAM", "Swap", "Virtual Memory",
                "Storage", "SSD", "NVME", "SATA", "RAID",
                "Filesystem", "NTFS", "EXT4", "XFS", "ZFS",
                "Boot Process", "BIOS", "UEFI", "Kernel", "Driver", "Interrupt", "DMA", "PCIe", "USB",
                "Power Management", "Windows Architecture", "Linux Architecture"
            ],
            "network_fundamental": [
                "IP Address", "Subnet", "CIDR", "Gateway", "ARP", "MAC", "Broadcast", "Multicast",
                "DNS", "DHCP", "NAT", "PAT", "Routing", "VLAN", "STP", "LACP", "QoS", "VPN",
                "Firewall", "Proxy", "Load Balancer", "Reverse Proxy",
                "Packet Flow", "Session", "TCP", "UDP", "ICMP", "MTU", "TTL",
                "Handshake", "RST", "FIN", "ACK", "Window Size", "Fragmentation",
                "Packet Loss", "Latency", "Jitter", "Bandwidth", "Throughput"
            ],
            "osi_layers": {
                "Layer 1 - Physical": ["Media", "Fiber", "UTP", "Power", "Connector", "Speed", "Duplex", "Signal", "CRC Error"],
                "Layer 2 - Data Link": ["MAC", "Switch", "Bridge", "VLAN", "STP", "Loop", "ARP", "Broadcast Storm"],
                "Layer 3 - Network": ["IP", "Routing", "OSPF", "BGP", "Static Route", "ICMP", "Gateway", "Traceroute"],
                "Layer 4 - Transport": ["TCP", "UDP", "Port", "Session", "Timeout", "RST", "Handshake"],
                "Layer 5 - Session": ["Authentication", "Session Timeout", "RPC", "SMB", "NetBIOS"],
                "Layer 6 - Presentation": ["Encryption", "Compression", "TLS", "SSL", "Certificate", "Encoding"],
                "Layer 7 - Application": ["HTTP", "HTTPS", "DNS", "SMTP", "POP3", "IMAP", "FTP", "SSH", "RDP", "Database", "REST API", "gRPC"]
            }
        }

    def inject_system_prompt(self) -> str:
        """
        Menghasilkan System Prompt untuk memastikan AI bertindak sebagai 
        Senior Enterprise Infrastructure Engineer dengan aturan yang ketat.
        """
        prompt = """
Anda adalah Enterprise Cognitive Reliability AI (OSI AI Ops), menggabungkan kapabilitas Senior Infrastructure Engineer, Senior SRE, Senior NOC Engineer, Senior Network Engineer, Senior System Engineer, Senior DBA, dan Senior Cloud Engineer. Anda bekerja 24 jam secara proaktif, berbasis evidence, BUKAN chatbot pasif.

ATURAN KESELAMATAN & HUMAN IN THE LOOP (HITL):
1. ZERO AUTONOMY & READ ONLY: Anda HANYA boleh membaca, menganalisa, menghubungkan, mempelajari, memprediksi, memberikan rekomendasi, dan memberikan warning.
2. DILARANG KERAS: restart service, shutdown, reboot, kill process, delete, modify, execute, remote command, powershell, cmd, registry, database, network device.
3. ANTI-HALLUCINATION: Jika Confidence rendah atau bukti tidak cukup, Anda WAJIB menjawab "Need More Evidence".

FONDASI PENGETAHUAN ANDA:
Anda WAJIB memahami keterkaitan komponen-komponen berikut:
- Computer Fundamentals: CPU, NUMA, RAM, Swap, SSD, RAID, Filesystems, Kernel, Interrupts.
- Network Fundamentals: CIDR, ARP, BGP, NAT, Load Balancer, TCP Handshake, MTU, Jitter.
- OSI Layers: Dari Physical (L1: Fiber, CRC) hingga Application (L7: HTTP, gRPC).

INSTRUKSI REASONING (ROOT CAUSE ANALYSIS):
Jangan pernah mengambil kesimpulan prematur. Lakukan reasoning langkah-demi-langkah.
Pola Reasoning yang Benar: Check Nginx -> Check Upstream -> Check PHP-FPM -> Check PostgreSQL -> Check DNS -> Check Firewall -> Check Network -> Check CPU/Mem/Disk -> Root Cause.

KNOWLEDGE GRAPH DEPENDENCY:
Selalu pertimbangkan hirarki dampak:
Business -> User -> Application -> Service -> Database -> Storage -> Network -> Power.
Jika Storage (L1) mati, Database (L6) akan mati, dan Application (L7) akan error. Jangan salahkan Application.
"""
        return prompt

    def enforce_issue_classification(self, telemetry_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Bagian 4: Memastikan setiap issue diklasifikasikan dengan properti dasar.
        (Ini adalah template klasifikasi yang harus diisi AI atau Parser).
        """
        return {
            "primary_osi_layer": None,
            "secondary_layer": None,
            "affected_component": None,
            "affected_service": None,
            "affected_application": None,
            "affected_user": None,
            "affected_dependency": None,
            "business_impact": None,
            "technical_impact": None
        }

    def generate_output_schema(self) -> Dict[str, Any]:
        """
        Bagian 7: Memaksa LLM untuk mematuhi format JSON ini untuk setiap analisis.
        """
        return {
            "type": "object",
            "properties": {
                "executive_summary": {"type": "string", "description": "Ringkasan eksekutif untuk manajemen."},
                "severity": {"type": "string", "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"]},
                "confidence": {"type": "integer", "description": "0-100 persen keyakinan. Jika rendah, katakan 'Need More Evidence'."},
                "osi_layer": {"type": "string", "description": "Contoh: Layer 7 - Application"},
                "root_cause": {"type": "string", "description": "Akar masalah sejati berdasarkan reasoning."},
                "evidence": {"type": "array", "items": {"type": "string"}},
                "affected_component": {"type": "string"},
                "affected_dependency": {"type": "array", "items": {"type": "string"}},
                "business_impact": {"type": "string"},
                "technical_impact": {"type": "string"},
                "risk": {"type": "string", "description": "Risiko jika masalah dibiarkan."},
                "blast_radius": {"type": "string", "description": "Komponen lain yang ikut terdampak."},
                "recommendations": {
                    "type": "array",
                    "description": "Ranked list of Top 3 recommendations for the operator.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "confidence": {"type": "integer", "description": "0-100"},
                            "downtime_estimate": {"type": "string", "description": "e.g., '2 detik', '0 detik'"},
                            "risk_level": {"type": "string", "enum": ["RENDAH", "SEDANG", "TINGGI"]},
                            "description": {"type": "string"}
                        },
                        "required": ["title", "confidence", "downtime_estimate", "risk_level", "description"]
                    }
                },
                "temporary_workaround": {"type": "string"},
                "permanent_solution": {"type": "string"},
                "prevention": {"type": "string"},
                "monitoring_recommendation": {"type": "string"},
                "related_knowledge": {"type": "array", "items": {"type": "string"}},
                "related_playbook": {"type": "array", "items": {"type": "string"}},
                "reference": {"type": "array", "items": {"type": "string"}}
            },
            "required": [
                "executive_summary", "severity", "confidence", "osi_layer", 
                "root_cause", "evidence", "recommendations"
            ]
        }

    def augment_learning_context(self, current_incident: Dict[str, Any], historical_db) -> Dict[str, Any]:
        """
        Bagian 8: Jika issue baru muncul, AI mencari kemiripan di database historis.
        (Fungsi ini akan dipanggil oleh RAG engine/Vector DB).
        """
        try:
            with historical_db.cursor() as cur:
                # Cari insiden yang mirip dari histori
                search_term = f"%{current_incident.get('description', '')[:50]}%"
                cur.execute("""
                    SELECT incident_id, first_hypothesis, final_decision, confidence_score
                    FROM ai_reflection_logs
                    WHERE first_hypothesis ILIKE %s
                       OR second_hypothesis ILIKE %s
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (search_term, search_term))
                
                row = cur.fetchone()
                if row:
                    return {
                        "similar_incident_found": True,
                        "similar_incident_id": f"INC-{row[0]}",
                        "similar_root_cause": row[1],
                        "similar_resolution": row[2],
                        "historical_success_rate": row[3] if row[3] else 0.0
                    }
        except Exception as e:
            logger.error(f"[KNOWLEDGE ENGINE] DB Query failed: {e}")
            try:
                historical_db.rollback()
            except:
                import logging; logging.getLogger(__name__).debug('_ = None suppressed')
                
        return {
            "similar_incident_found": False,
            "similar_incident_id": None,
            "similar_root_cause": None,
            "similar_resolution": None,
            "historical_success_rate": 0.0
        }

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    engine = FoundationKnowledgeEngine()
    logger.info("Sprint K: Foundation Knowledge Engine Initialized.")
    logger.info("System Prompt Sample:\n" + engine.inject_system_prompt())
    logger.info("Output Schema Sample Keys:\n" + str(engine.generate_output_schema()["properties"].keys()))
