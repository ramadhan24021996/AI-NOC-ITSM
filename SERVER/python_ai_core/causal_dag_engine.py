import logging
import json
import uuid
from typing import Dict, Any, List

logger = logging.getLogger("CAUSAL_DAG_ENGINE")

class CausalDAGEngine:
    """
    Tahap 3: Causal DAG Engine
    Generates Probabilistic Root Cause Analysis (RCA) graphs using PostgreSQL tables 
    (reasoning_nodes, reasoning_edges) based on topology, dependencies, and telemetry.
    """
    def __init__(self, db_conn=None):
        self.db = db_conn

    def build_causal_graph(self, incident_id: int, root_device: str, incident_data: dict) -> dict:
        """
        Constructs a causal DAG for a given incident and root device.
        Nodes represent hypotheses (e.g., "Network Failure", "Service Crash").
        Edges represent causal links with probabilities (weights).
        """
        if not self.db:
            logger.warning("[DAG ENGINE] No DB connection. Cannot build graph.")
            return {}

        logger.info(f"[DAG ENGINE] Building Causal DAG for Incident {incident_id} (Device: {root_device})")
        
        # 1. Clear existing graph for this incident (if regenerating)
        try:
            with self.db.cursor() as cur:
                cur.execute("DELETE FROM reasoning_nodes WHERE incident_id = %s", (str(incident_id),))
            self.db.commit()
        except Exception as e:
            logger.error(f"[DAG ENGINE] Failed to clear old DAG: {e}")
            if self.db:
                self.db.rollback()

        nodes = []
        edges = []

        # 2. Extract context & generate heuristic hypotheses
        symptoms = incident_data.get("symptoms", [])
        if isinstance(symptoms, list):
            primary_symptom = symptoms[0] if symptoms else "Unknown Failure"
        else:
            primary_symptom = str(symptoms)
            
        severity = incident_data.get("metadata", {}).get("severity", "MEDIUM")
        
        # A. Create Root Observation Node (Effect)
        effect_node_id = str(uuid.uuid4())
        nodes.append({
            "node_id": effect_node_id,
            "type": "OBSERVATION",
            "payload": {"description": f"Symptom: {primary_symptom} on {root_device}"},
            "confidence": 1.0,
            "layer_num": 1
        })

        # B. Query dependencies to form causal hypotheses
        dependencies = []
        try:
            with self.db.cursor() as cur:
                cur.execute("SELECT depends_on, dep_type FROM device_dependencies WHERE pc_name = %s", (root_device,))
                dependencies = cur.fetchall()
        except Exception as e:
            logger.error(f"[DAG ENGINE] Failed to fetch dependencies: {e}")
            if self.db:
                self.db.rollback()

        # Generate Hypotheses
        hypothesis_nodes = []
        
        # Base Hypothesis 1: Resource Exhaustion on device itself
        h1_id = str(uuid.uuid4())
        h1_prob = 0.6 if severity in ["HIGH", "CRITICAL"] else 0.4
        nodes.append({
            "node_id": h1_id,
            "type": "HYPOTHESIS",
            "payload": {"description": f"Resource Exhaustion (CPU/RAM/Disk) on {root_device}", "category": "SYSTEM"},
            "confidence": h1_prob,
            "layer_num": 2
        })
        hypothesis_nodes.append((h1_id, h1_prob, "CAUSES"))

        # Base Hypothesis 2: Local Service Crash
        h2_id = str(uuid.uuid4())
        h2_prob = 0.5
        nodes.append({
            "node_id": h2_id,
            "type": "HYPOTHESIS",
            "payload": {"description": f"Critical Service Crash on {root_device}", "category": "APPLICATION"},
            "confidence": h2_prob,
            "layer_num": 2
        })
        hypothesis_nodes.append((h2_id, h2_prob, "CAUSES"))

        # Topology Hypotheses based on dependencies
        for dep_pc, dep_type in dependencies:
            h_dep_id = str(uuid.uuid4())
            dep_prob = 0.8 if dep_type.upper() == 'NETWORK' else 0.5
            nodes.append({
                "node_id": h_dep_id,
                "type": "HYPOTHESIS",
                "payload": {"description": f"Dependency Failure: {dep_pc} ({dep_type})", "category": "DEPENDENCY"},
                "confidence": dep_prob,
                "layer_num": 3
            })
            hypothesis_nodes.append((h_dep_id, dep_prob, "CAUSES"))

        # Create Edges from Hypotheses to Effect
        for h_id, prob, relation in hypothesis_nodes:
            edges.append({
                "from_node": h_id, # Hypothesis CAUSES Effect
                "to_node": effect_node_id,
                "relation": relation,
                "weight": prob
            })

        # 3. Persist to DB
        try:
            with self.db.cursor() as cur:
                # Insert nodes
                for n in nodes:
                    cur.execute("""
                        INSERT INTO reasoning_nodes (node_id, incident_id, node_type, payload, confidence, layer_num, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    """, (n["node_id"], str(incident_id), n["type"], json.dumps(n["payload"]), n["confidence"], n["layer_num"]))
                
                # Insert edges
                for e in edges:
                    cur.execute("""
                        INSERT INTO reasoning_edges (from_node, to_node, relation, weight, created_at)
                        VALUES (%s, %s, %s, %s, NOW())
                    """, (e["from_node"], e["to_node"], e["relation"], e["weight"]))
            self.db.commit()
            logger.info(f"[DAG ENGINE] Successfully persisted DAG: {len(nodes)} nodes, {len(edges)} edges.")
        except Exception as e:
            logger.error(f"[DAG ENGINE] Failed to persist DAG: {e}")
            if self.db:
                self.db.rollback()

        return {
            "incident_id": incident_id,
            "nodes_count": len(nodes),
            "edges_count": len(edges)
        }

def get_causal_dag_engine(db_conn):
    return CausalDAGEngine(db_conn)
