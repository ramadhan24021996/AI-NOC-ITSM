"""
Layer 4 AI Core — Remediation Divergence Matrix Engine (L4_RemediationDivergenceMatrix)
Maps incident categories to distinct, highly specific remediation action taxonomies.
Guarantees distinct issue handling (e.g. POS Hardware vs Printer Spooler vs Database Slow Query).
"""

import logging
import time
from typing import Dict, List, Any

logger = logging.getLogger("REMEDIATION_DIVERGENCE_MATRIX")

class RemediationDivergenceMatrix:
    def __init__(self):
        # Distinct Remediation Taxonomies per Incident Domain
        self.taxonomy_matrix = {
            "PRINT_SPOOLER": {
                "primary_action": "RESTART_WINDOWS_SPOOLER_SERVICE",
                "secondary_action": "PURGE_SPOOL_PRINTER_QUEUE_FILES",
                "isolation_action": "DISABLE_PRINTER_RPC_PORT",
                "safety_guard": "VERIFY_NO_ACTIVE_PRINT_JOB"
            },
            "DATABASE_LOCK": {
                "primary_action": "TERMINATE_BLOCKING_PID_QUERIES",
                "secondary_action": "ADD_MISSING_DB_INDEX",
                "isolation_action": "DRAIN_READ_REPLICA_CONNECTIONS",
                "safety_guard": "PRESERVE_ACTIVE_TRANSACTIONS"
            },
            "MEMORY_LEAK": {
                "primary_action": "SCALE_OUT_CONTAINER_REPLICAS",
                "secondary_action": "FLUSH_HEAP_GC_AND_RESTART_POD",
                "isolation_action": "ISOLATE_LEAKING_WORKER_NODE",
                "safety_guard": "VERIFY_HEAP_DUMP_SAVED"
            },
            "NETWORK_LATENCY": {
                "primary_action": "FLUSH_DNS_RESOLVER_CACHE",
                "secondary_action": "FAILOVER_TO_BACKUP_GATEWAY",
                "isolation_action": "REROUTE_NATS_CLUSTER_TRAFFIC",
                "safety_guard": "VERIFY_BGP_ROUTE_HEALTH"
            },
            "POS_HARDWARE": {
                "primary_action": "RESTART_POS_KASIR_SERVICE",
                "secondary_action": "RESET_BARCODE_RECEIPT_USB_PORT",
                "isolation_action": "SWITCH_POS_TO_OFFLINE_LOCAL_STORE",
                "safety_guard": "MUST_NOT_INTERRUPT_ACTIVE_CUSTOMER_CHECKOUT"
            },
            "UNKNOWN_NOVEL": {
                "primary_action": "TRIGGER_HITL_DIAGNOSTIC_QUEUE",
                "secondary_action": "COLLECT_FULL_FORENSIC_SNAPSHOT",
                "isolation_action": "ENABLE_SAFE_BACKPRESSURE_LIMIT",
                "safety_guard": "DO_NOT_APPLY_GENERIC_RESTART"
            }
        }

    def get_divergent_remediation_path(self, incident_category: str, symptom: str) -> Dict[str, Any]:
        """
        Extracts specific, non-generic remediation taxonomy for an incident.
        """
        category_key = incident_category.upper()
        if "SPOOLER" in symptom.upper() or "PRINT" in symptom.upper():
            category_key = "PRINT_SPOOLER"
        elif "QUERY" in symptom.upper() or "SQL" in symptom.upper() or "LOCK" in symptom.upper():
            category_key = "DATABASE_LOCK"
        elif "MEMORY" in symptom.upper() or "RAM" in symptom.upper() or "LEAK" in symptom.upper():
            category_key = "MEMORY_LEAK"
        elif "POS" in symptom.upper() or "KASIR" in symptom.upper():
            category_key = "POS_HARDWARE"
        elif "LATENCY" in symptom.upper() or "NETWORK" in symptom.upper():
            category_key = "NETWORK_LATENCY"

        path_info = self.taxonomy_matrix.get(category_key, self.taxonomy_matrix["UNKNOWN_NOVEL"])

        result = {
            "incident_category": category_key,
            "symptom": symptom,
            "remediation_taxonomy": path_info,
            "is_generic_fallback": category_key == "UNKNOWN_NOVEL",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }

        logger.info(f"[REMEDIATION_DIVERGENCE] Mapped symptom '{symptom}' to distinct taxonomy '{category_key}' (Primary Action: {path_info['primary_action']}).")
        return result

# Global instance
remediation_divergence_matrix = RemediationDivergenceMatrix()
