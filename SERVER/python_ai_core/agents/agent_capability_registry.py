"""
Enterprise Agent Capability Registry (Phase 3 Capability 6)
Maps specialized capabilities and permitted tools to each Specialist Agent.
"""

import logging
from typing import Dict, List, Set

logger = logging.getLogger("AGENT_CAPABILITY_REGISTRY")

class AgentCapabilityRegistry:
    """
    Enterprise Capability Registry
    Ensures agents only execute actions within their assigned domains.
    """

    def __init__(self):
        self.agent_capabilities: Dict[str, Set[str]] = {
            "NetworkAgent": {"ping", "traceroute", "dns_lookup", "reset_switch_port", "flush_dns"},
            "OSAgent": {"restart_service", "clear_temp", "query_process", "query_eventlog"},
            "StorageAgent": {"check_smart", "check_disk_usage", "clear_logs"},
            "DatabaseAgent": {"check_pg_connections", "explain_query", "restart_db_pool"},
            "SecurityAgent": {"query_firewall_rules", "audit_rbac", "check_ssl_certs"},
            "ApplicationAgent": {"check_app_health", "query_http_metrics"},
            "IdentityAgent": {"verify_ldap_user", "check_active_directory"},
            "VirtualizationAgent": {"query_vm_stats", "check_proxmox_cluster"},
            "CloudAgent": {"check_aws_health", "query_azure_status"},
            "BrowserAgent": {"check_browser_cache", "query_extension_errors"},
            "PrinterAgent": {"clear_spooler", "check_printer_status"},
            "KnowledgeAgent": {"search_rag", "query_kedb", "get_sop"},
            "RemediationAgent": {"execute_script", "trigger_rollback"},
            "LearningAgent": {"update_graph_weights", "store_feedback"}
        }

    def can_agent_use_tool(self, agent_name: str, tool_name: str) -> bool:
        """Verifies if agent has permission to execute specific tool."""
        caps = self.agent_capabilities.get(agent_name, set())
        return tool_name.lower() in caps
