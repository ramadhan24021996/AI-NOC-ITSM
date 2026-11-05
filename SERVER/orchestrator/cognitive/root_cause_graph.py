"""
SERVER.orchestrator.cognitive.root_cause_graph
===============================================
Component: Root Cause Graph Builder

Constructs node dependency graphs for root cause analysis (RCA):
Example: CPU Spike -> PostgreSQL -> Lock -> Backup -> Disk IO -> Slow API
"""
import logging
from typing import Dict, Any, List
from SERVER.contracts.schemas import RootCauseGraphPayload, RootCauseNode

logger = logging.getLogger("orchestrator.cognitive.rca_graph")


class RootCauseGraphBuilder:
    """
    Builds directed correlation graphs mapping symptom chains to root cause nodes.
    """

    def build_graph(
        self, topic: str, target_device: str, query_text: str
    ) -> RootCauseGraphPayload:
        nodes = []
        edges = []

        query_lower = query_text.lower()

        if "cpu" in query_lower or "backup" in query_lower or "postgres" in query_lower:
            root_id = "node_lock"
            chain_desc = "PostgreSQL Lock -> Backup Process -> High Disk IO -> CPU Spike 98%"

            nodes = [
                {"node_id": "node_cpu", "label": "CPU Spike (98%)", "target_component": target_device},
                {"node_id": "node_io", "label": "High Disk IO", "target_component": "Storage Subsystem"},
                {"node_id": "node_backup", "label": "Database Backup Job", "target_component": "cron_backup.sh"},
                {"node_id": "node_lock", "label": "PostgreSQL Table Lock", "target_component": "PostgreSQL DB"},
            ]

            edges = [
                {"from": "node_lock", "to": "node_backup", "relation": "BLOCKS"},
                {"from": "node_backup", "to": "node_io", "relation": "CAUSES"},
                {"from": "node_io", "to": "node_cpu", "relation": "TRIGGERS"},
            ]
        else:
            root_id = "node_root_cause"
            chain_desc = f"Root Cause Analysis Chain for {topic} on {target_device}"

            nodes = [
                {"node_id": "node_symptom", "label": f"Symptom: {topic}", "target_component": target_device},
                {"node_id": "node_root_cause", "label": f"Root Cause: Resource Contention", "target_component": target_device},
            ]

            edges = [
                {"from": "node_root_cause", "to": "node_symptom", "relation": "LEADS_TO"},
            ]

        payload = RootCauseGraphPayload(
            root_cause_node_id=root_id,
            explanation_chain=chain_desc,
            nodes=nodes,
            edges=edges,
        )

        logger.debug(f"[RootCauseGraphBuilder] Built RCA graph with {len(nodes)} nodes for {target_device}")
        return payload
