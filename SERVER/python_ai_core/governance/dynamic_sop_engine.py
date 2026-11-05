"""
dynamic_sop_engine.py
======================
Dynamic SOP Retrieval & Decision Tree Branching Engine.
Mengubah SOP linier menjadi Decision Tree kontekstual yang beradaptasi dengan
kondisi perangkat, OS, OSI layer, telemetri, dan hasil eksekusi sebelumnya.
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("DynamicSOPEngine")


class DynamicSOPEngine:
    """
    Engine SOP Dinamis dengan Konteks & Decision Tree Branching.
    """

    def __init__(self):
        # Database SOP Kontekstual berbasis Decision Tree
        self._sop_database: Dict[str, Dict[str, Any]] = {
            "SOP-PRINT-001": {
                "sop_id": "SOP-PRINT-001",
                "version": "2.1.0",
                "title": "Adaptive Windows Print Spooler & Driver Recovery",
                "category": "PRINTER",
                "applicable_devices": ["PC", "POS", "WORKSTATION"],
                "applicable_services": ["SPOOLER", "PRINTING"],
                "applicable_os": ["WINDOWS"],
                "osi_layers": ["L7_APPLICATION", "L4_TRANSPORT"],
                "risk_level": "LOW",
                "required_approval": False,
                "preconditions": ["device_online == True"],
                "decision_tree": {
                    "step_1": {
                        "condition": "spooler_stopped == True",
                        "action_if_true": {
                            "id": "ACT_RESTART_SPOOLER",
                            "name": "RESTART_PRINT_SPOOLER",
                            "command": "net stop spooler && net start spooler",
                            "risk_score": 0.05
                        },
                        "action_if_false": "step_2"
                    },
                    "step_2": {
                        "condition": "print_queue_stuck == True",
                        "action_if_true": {
                            "id": "ACT_CLEAR_QUEUE",
                            "name": "CLEAR_PRINT_QUEUE",
                            "command": 'net stop spooler && del /Q /F /S "%systemroot%\\System32\\Spool\\Printers\\*.*" && net start spooler',
                            "risk_score": 0.10
                        },
                        "action_if_false": "step_3"
                    },
                    "step_3": {
                        "condition": "printer_unreachable == True",
                        "action_if_true": {
                            "id": "ACT_NET_DIAG",
                            "name": "PRINTER_NETWORK_DIAGNOSTICS",
                            "command": "ping printer_ip && test-netconnection printer_ip -port 9100",
                            "risk_score": 0.02
                        },
                        "action_if_false": {
                            "id": "ACT_INSPECT_DRIVER",
                            "name": "INSPECT_PRINT_DRIVER",
                            "command": "powershell Get-PrinterDriver",
                            "risk_score": 0.15
                        }
                    }
                },
                "success_conditions": ["spooler_running == True", "print_queue_count == 0"],
                "failure_conditions": ["spooler_restart_failed == True", "print_queue_remains_stuck == True"],
                "escalation_conditions": ["attempt_count >= 2"]
            },

            "SOP-NET-001": {
                "sop_id": "SOP-NET-001",
                "version": "1.8.0",
                "title": "Network & Interface Diagnostic & Failover",
                "category": "NETWORK",
                "applicable_devices": ["ROUTER", "SWITCH", "SERVER", "PC"],
                "applicable_services": ["NETWORK", "DNS", "INGRESS"],
                "applicable_os": ["LINUX", "WINDOWS"],
                "osi_layers": ["L3_NETWORK", "L2_DATA_LINK"],
                "risk_level": "MEDIUM",
                "required_approval": False,
                "preconditions": ["device_online == True"],
                "decision_tree": {
                    "step_1": {
                        "condition": "ip_unreachable == True",
                        "action_if_true": {
                            "id": "ACT_FLUSH_DNS",
                            "name": "FLUSH_DNS_CACHE",
                            "command": "resolvectl flush-caches || ipconfig /flushdns",
                            "risk_score": 0.02
                        },
                        "action_if_false": "step_2"
                    },
                    "step_2": {
                        "condition": "interface_down == True",
                        "action_if_true": {
                            "id": "ACT_RESTART_INTERFACE",
                            "name": "RESTART_NETWORK_INTERFACE",
                            "command": "ip link set eth0 down && ip link set eth0 up",
                            "risk_score": 0.35
                        },
                        "action_if_false": {
                            "id": "ACT_CHECK_ROUTING",
                            "name": "CHECK_ROUTING_TABLE",
                            "command": "ip route show",
                            "risk_score": 0.01
                        }
                    }
                },
                "success_conditions": ["ping_gateway == True"],
                "failure_conditions": ["interface_restart_failed == True"],
                "escalation_conditions": ["attempt_count >= 2"]
            }
        }

    def match_sop_contextual(
        self,
        incident_context: Any
    ) -> List[Dict[str, Any]]:
        """
        Matching SOP berdasarkan Konteks Insiden (Device, OS, Service, OSI, Telemetry).
        Ranks SOPs by contextual suitability score.
        """
        ranked_sops = []

        for sop_id, sop in self._sop_database.items():
            score = 0.0

            # OS Match
            if incident_context.os.upper() in sop["applicable_os"]:
                score += 0.30

            # Device Type Match
            if incident_context.device_type.upper() in sop["applicable_devices"]:
                score += 0.25

            # Service Match
            if incident_context.service.upper() in sop["applicable_services"]:
                score += 0.25

            # OSI Layer Match
            for layer in incident_context.osi_layers:
                if layer in sop["osi_layers"]:
                    score += 0.20
                    break

            if score > 0.30:
                sop_entry = sop.copy()
                sop_entry["suitability_score"] = round(score, 2)
                ranked_sops.append(sop_entry)

        ranked_sops.sort(key=lambda x: x["suitability_score"], reverse=True)
        logger.info(f"[DynamicSOPEngine] Found {len(ranked_sops)} matching SOPs for incident {incident_context.incident_id}")
        return ranked_sops
