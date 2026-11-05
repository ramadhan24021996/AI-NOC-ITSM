"""
SERVER.orchestrator.autonomous.operational_knowledge_graph
==========================================================
Component: Operational Knowledge Graph Builder

Constructs relational topology graphs mapping physical and logical IT assets:
Accounting Server -> PostgreSQL DB -> Storage NAS -> Backup Agent -> Switch Core
"""
import logging
from typing import Dict, Any, List
from SERVER.contracts.schemas import OperationalKnowledgeGraphPayload

logger = logging.getLogger("orchestrator.autonomous.knowledge_graph")


class OperationalKnowledgeGraphBuilder:
    """
    Builds relational asset topology graphs for rapid root cause tracing.
    """

    def build_topology_graph(self, target_device: str) -> OperationalKnowledgeGraphPayload:
        nodes = [
            {"node_id": "srv_acc", "name": f"Server: {target_device}", "type": "Host Node"},
            {"node_id": "db_pg", "name": "Database: PostgreSQL 14", "type": "Database Engine"},
            {"node_id": "nas_stg", "name": "Storage: NAS Appliance 01", "type": "Storage"},
            {"node_id": "cron_bk", "name": "Agent: Backup Agent (cron)", "type": "Process"},
            {"node_id": "sw_core", "name": "Network: Switch Core 01", "type": "Switch"},
        ]

        relations = [
            {"from": "srv_acc", "to": "db_pg", "relation": "HOSTS"},
            {"from": "db_pg", "to": "nas_stg", "relation": "WRITES_TO"},
            {"from": "cron_bk", "to": "db_pg", "relation": "LOCKS"},
            {"from": "srv_acc", "to": "sw_core", "relation": "CONNECTED_TO"},
        ]

        payload = OperationalKnowledgeGraphPayload(
            nodes=nodes,
            relations=relations,
        )

        logger.debug(f"[OperationalKnowledgeGraphBuilder] Topology graph built for {target_device} ({len(nodes)} nodes)")
        return payload
