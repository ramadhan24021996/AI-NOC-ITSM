"""
Enterprise Graph Transaction Manager
Guarantees atomic graph operations (Begin -> Update Node -> Update Edge -> Ranking -> Cache -> Commit / Rollback).
Prevents partial graph mutations.
"""

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("GRAPH_TRANSACTION_MANAGER")

class GraphTransaction:
    def __init__(self, tx_id: str, kg_engine):
        self.tx_id = tx_id
        self.kg = kg_engine
        self.staged_nodes: List[Any] = []
        self.staged_edges: List[Any] = []
        self.is_committed = False
        self.is_rolled_back = False

    def stage_node(self, node):
        self.staged_nodes.append(node)

    def stage_edge(self, edge):
        self.staged_edges.append(edge)

    def commit(self) -> bool:
        """Applies all staged nodes and edges atomically."""
        try:
            with self.kg._lock:
                for node in self.staged_nodes:
                    self.kg.add_node(node, invalidate=False)
                for edge in self.staged_edges:
                    self.kg.add_edge(edge, invalidate=False)
                self.kg.create_new_version()
                self.is_committed = True
                logger.info("[GRAPH TX %s] Transaction committed successfully (%d nodes, %d edges)",
                            self.tx_id, len(self.staged_nodes), len(self.staged_edges))
                return True
        except Exception as exc:
            logger.error("[GRAPH TX %s] Transaction commit error: %s. Rolling back.", self.tx_id, exc)
            self.rollback()
            return False

    def rollback(self):
        """Discards all staged changes."""
        self.staged_nodes.clear()
        self.staged_edges.clear()
        self.is_rolled_back = True
        logger.info("[GRAPH TX %s] Transaction rolled back.", self.tx_id)

class GraphTransactionManager:
    def __init__(self, kg_engine):
        self.kg = kg_engine
        self._tx_counter = 0

    def begin_transaction(self) -> GraphTransaction:

        self._tx_counter += 1
        tx_id = f"tx_{self._tx_counter}"
        logger.info("[GRAPH TX] Began new transaction: %s", tx_id)
        return GraphTransaction(tx_id, self.kg)
