"""
AI MEMORY GRAPH (CAUSAL SEQUENCE MEMORY ENGINE)
Tracks directed temporal and causal transitions between incident events.
Example Chain: Device A -> Disk Full -> Soft Restart Failed -> Rollback Intervened -> Operator Approved -> Solved.
Calculates edge weights and conditional probabilities P(E_next | E_curr) to predict future incident progression.
"""

import logging
import sqlite3
import time
import os
import json
from typing import Dict, List, Any, Tuple, Optional

logger = logging.getLogger("AI_MEMORY_GRAPH")

class AIMemoryGraph:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), "..", "cognitive_memory.db")
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initializes graph nodes and directed weighted edges tables in SQLite."""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS memory_graph_nodes (
                        node_id TEXT PRIMARY KEY,
                        node_type TEXT NOT NULL,
                        label TEXT NOT NULL,
                        occurrence_count INTEGER DEFAULT 1,
                        updated_at TEXT NOT NULL
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS memory_graph_edges (
                        edge_id TEXT PRIMARY KEY,
                        source_node TEXT NOT NULL,
                        relation TEXT NOT NULL,
                        target_node TEXT NOT NULL,
                        weight REAL DEFAULT 1.0,
                        transition_count INTEGER DEFAULT 1,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY(source_node) REFERENCES memory_graph_nodes(node_id),
                        FOREIGN KEY(target_node) REFERENCES memory_graph_nodes(node_id)
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_edge_source ON memory_graph_edges(source_node)")
                conn.commit()
                logger.info(f"[MEMORY GRAPH] Graph schema initialized successfully at {self.db_path}")
        except Exception as e:
            logger.error(f"[MEMORY GRAPH] Failed to initialize graph database: {e}")

    def record_transition(self, source_label: str, source_type: str, relation: str, target_label: str, target_type: str) -> bool:
        """
        Records a directed causal edge: source --(relation)--> target.
        Increments transition_count and updates weight.
        """
        try:
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ")
            src_id = f"{source_type.upper()}:{source_label.lower().replace(' ', '_')}"
            tgt_id = f"{target_type.upper()}:{target_label.lower().replace(' ', '_')}"
            edge_id = f"{src_id}->{relation.upper()}->{tgt_id}"

            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Upsert Source Node
                cursor.execute("""
                    INSERT INTO memory_graph_nodes (node_id, node_type, label, occurrence_count, updated_at)
                    VALUES (?, ?, ?, 1, ?)
                    ON CONFLICT(node_id) DO UPDATE SET
                        occurrence_count = occurrence_count + 1,
                        updated_at = excluded.updated_at
                """, (src_id, source_type, source_label, now))

                # Upsert Target Node
                cursor.execute("""
                    INSERT INTO memory_graph_nodes (node_id, node_type, label, occurrence_count, updated_at)
                    VALUES (?, ?, ?, 1, ?)
                    ON CONFLICT(node_id) DO UPDATE SET
                        occurrence_count = occurrence_count + 1,
                        updated_at = excluded.updated_at
                """, (tgt_id, target_type, target_label, now))

                # Upsert Edge
                cursor.execute("""
                    INSERT INTO memory_graph_edges (edge_id, source_node, relation, target_node, weight, transition_count, updated_at)
                    VALUES (?, ?, ?, ?, 1.0, 1, ?)
                    ON CONFLICT(edge_id) DO UPDATE SET
                        transition_count = transition_count + 1,
                        weight = weight + 0.5,
                        updated_at = excluded.updated_at
                """, (edge_id, src_id, relation.upper(), tgt_id, now))

                conn.commit()
                logger.info(f"[MEMORY GRAPH] Recorded edge: {src_id} -[{relation}]-> {tgt_id}")
                return True
        except Exception as e:
            logger.error(f"[MEMORY GRAPH] Error recording transition: {e}")
            return False

    def predict_next_events(self, current_label: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Predicts probable next events and actions given the current incident event.
        Calculates P(E_next | E_curr) = transition_count(E_curr -> E_next) / total_outbound(E_curr).
        """
        results = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Find matching node IDs
                cursor.execute("SELECT node_id FROM memory_graph_nodes WHERE label LIKE ?", (f"%{current_label}%",))
                nodes = cursor.fetchall()
                if not nodes:
                    return results

                node_ids = [n["node_id"] for n in nodes]
                placeholders = ",".join(["?"] * len(node_ids))
                
                cursor.execute(f"""
                    SELECT e.relation, e.target_node, n.label as target_label, n.node_type as target_type, e.weight, e.transition_count
                    FROM memory_graph_edges e
                    JOIN memory_graph_nodes n ON e.target_node = n.node_id
                    WHERE e.source_node IN ({placeholders})
                    ORDER BY e.weight DESC
                    LIMIT ?
                """, (*node_ids, top_k))

                rows = cursor.fetchall()
                total_transitions = sum(r["transition_count"] for r in rows) or 1.0

                for r in rows:
                    prob = float(r["transition_count"]) / total_transitions
                    results.append({
                        "relation": r["relation"],
                        "target_node": r["target_node"],
                        "target_label": r["target_label"],
                        "target_type": r["target_type"],
                        "weight": float(r["weight"]),
                        "probability": round(prob, 3)
                    })
        except Exception as e:
            logger.error(f"[MEMORY GRAPH] Error predicting next events: {e}")

        return results


# Demo test run
if __name__ == "__main__":
    graph = AIMemoryGraph()
    print("=== UJI AI MEMORY GRAPH (CAUSAL SEQUENCE ENGINE) ===")

    # Populate sample incident chain for Print Spooler
    graph.record_transition("Device POS Kasir A", "DEVICE", "HAS_ANOMALY", "Print Spooler Stalled", "METRIC")
    graph.record_transition("Print Spooler Stalled", "METRIC", "TRIGGERS_ACTION", "Restart Spooler Gagal", "ACTION")
    graph.record_transition("Restart Spooler Gagal", "ACTION", "RESULTED_IN", "Automated Rollback", "OUTCOME")
    graph.record_transition("Automated Rollback", "OUTCOME", "INTERVENED_BY", "Operator Approve Telegram", "HITL")
    graph.record_transition("Operator Approve Telegram", "HITL", "FINISHED_WITH", "Incident Solved Zero Downtime", "SOLUTION")

    print("\n[Predicting Next Events for 'Print Spooler Stalled']:")
    predictions = graph.predict_next_events("Print Spooler Stalled")
    for p in predictions:
        print(f" -> Relation: {p['relation']} | Target: {p['target_label']} ({p['target_type']}) | Prob: {p['probability']*100:.1f}%")
