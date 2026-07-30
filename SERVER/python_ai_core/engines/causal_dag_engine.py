import logging
import json
import uuid
from typing import Dict, Any, List

import os
import threading
import redis

logger = logging.getLogger("CAUSAL_DAG_ENGINE")

class CausalDAGEngine:
    """
    Tahap 3: Causal DAG Engine
    Generates Probabilistic Root Cause Analysis (RCA) graphs using PostgreSQL tables 
    (reasoning_nodes, reasoning_edges) based on topology, dependencies, and telemetry.
    Supports real-time in-memory cache hot-reload via Redis Pub/Sub 'dag:reload'.
    """
    def __init__(self, db_conn=None, redis_client=None):
        self.db = db_conn
        self.redis = redis_client
        self._cached_topology = {}
        self._init_redis_subscriber()

    def _init_redis_subscriber(self):
        """BAB 19.9 Patch 1: Background Redis subscriber for 'dag:reload' hot cache invalidation."""
        try:
            redis_host = os.environ.get("REDIS_HOST", "localhost")
            redis_port = int(os.environ.get("REDIS_PORT", 6379))
            redis_pass = os.environ.get("REDIS_PASSWORD", os.environ.get("OSI_SECURITY_KEY", None))
            r = redis.Redis(host=redis_host, port=redis_port, password=redis_pass, decode_responses=True)
            
            def listen_loop():
                pubsub = r.pubsub()
                pubsub.subscribe("dag:reload")
                logger.info("[DAG ENGINE] Subscribed to Redis Pub/Sub channel 'dag:reload' for hot-reload.")
                for message in pubsub.listen():
                    if message and message.get("type") == "message":
                        logger.info(f"[DAG ENGINE] Hot-Reload Signal received: {message.get('data')}. Invalidation completed.")
                        self._cached_topology.clear()

            t = threading.Thread(target=listen_loop, daemon=True)
            t.start()
        except Exception as e:
            logger.warning(f"[DAG ENGINE] Redis Pub/Sub hot-reload subscriber setup skipped: {e}")

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

        # B. Query dependencies to form causal hypotheses (checking ACTIVE first, then DEGRADED fallback; ARCHIVED ignored)
        dependencies = []
        try:
            with self.db.cursor() as cur:
                # First fetch ACTIVE dependencies
                cur.execute("""
                    SELECT depends_on, dep_type, COALESCE(confidence_score, 0.85), COALESCE(status, 'ACTIVE') 
                    FROM device_dependencies 
                    WHERE pc_name = %s AND (status = 'ACTIVE' OR status IS NULL)
                """, (root_device,))
                dependencies = cur.fetchall()
                
                # Fallback to DEGRADED edges if no ACTIVE edge exists
                if not dependencies:
                    cur.execute("""
                        SELECT depends_on, dep_type, COALESCE(confidence_score, 0.50), status 
                        FROM device_dependencies 
                        WHERE pc_name = %s AND status = 'DEGRADED'
                    """, (root_device,))
                    dependencies = cur.fetchall()
        except Exception as e:
            logger.error(f"[DAG ENGINE] Failed to fetch dependencies: {e}")
            if self.db:
                self.db.rollback()

        # Generate Hypotheses using Bayesian Inference Engine
        try:
            from probabilistic.probabilistic_engine import BayesianHypothesisEngine
            bayesian_engine = BayesianHypothesisEngine()
            
            telemetry_evidence = {
                "z_score_cpu": incident_data.get("metadata", {}).get("z_score_cpu", 3.2 if severity in ["HIGH", "CRITICAL"] else 1.5),
                "z_score_mem": incident_data.get("metadata", {}).get("z_score_mem", 4.1 if severity == "CRITICAL" else 1.8),
                "high_disk_io": incident_data.get("metadata", {}).get("high_disk_io", False),
                "spooler_deadlock": "spooler" in primary_symptom.lower() or "print" in primary_symptom.lower(),
                "unindexed_query": "query" in primary_symptom.lower() or "sql" in primary_symptom.lower() or "lock" in primary_symptom.lower()
            }
            bayes_results = bayesian_engine.calculate_posterior_probabilities(telemetry_evidence)
            logger.info(f"[DAG ENGINE] Bayesian Posterior Probabilities computed: {bayes_results}")
        except Exception as e:
            logger.warning(f"[DAG ENGINE] Bayesian engine fallback: {e}")
            bayes_results = [
                {"hypothesis": "MEMORY_LEAK", "posterior_probability": 0.60 if severity in ["HIGH", "CRITICAL"] else 0.40},
                {"hypothesis": "SERVICE_DEADLOCK", "posterior_probability": 0.50}
            ]

        hypothesis_nodes = []
        for item in bayes_results[:4]:
            hyp_name = item["hypothesis"]
            hyp_prob = item["posterior_probability"]
            h_id = str(uuid.uuid4())
            
            nodes.append({
                "node_id": h_id,
                "type": "HYPOTHESIS",
                "payload": {
                    "description": f"Bayesian Hypothesis: {hyp_name} on {root_device}",
                    "category": "INFERRED_CAUSE",
                    "bayes_details": item
                },
                "confidence": hyp_prob,
                "layer_num": 2
            })
            hypothesis_nodes.append((h_id, hyp_prob, "CAUSES"))

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

    def build_cross_layer_cascading_dag(self, incident_id: str, events: list, window_seconds: int = 30) -> dict:
        """
        Builds a cross-layer cascading DAG from raw multi-layer event logs using 30-second time-window clustering.
        Correlates signals across Layer 1 - Layer 7 (Network -> Microservices -> Browser / App).
        """
        from core.event_correlation_engine import EventCorrelationEngine
        correlation_engine = EventCorrelationEngine(time_window_seconds=window_seconds)

        clusters = correlation_engine.cluster_events_by_window(events, window_seconds=window_seconds)
        if not clusters:
            return {"incident_id": incident_id, "nodes_count": 0, "edges_count": 0, "clusters_count": 0}

        # Analyze the largest cluster for cascading root cause
        primary_cluster = max(clusters, key=len)
        matrix = correlation_engine.build_causal_matrix(primary_cluster)

        logger.info(f"[DAG ENGINE] Built Cross-Layer Cascading DAG for Incident {incident_id}: {len(matrix['nodes'])} nodes, {len(matrix['edges'])} edges.")

        return {
            "incident_id": incident_id,
            "clusters_count": len(clusters),
            "nodes_count": len(matrix["nodes"]),
            "edges_count": len(matrix["edges"]),
            "nodes": matrix["nodes"],
            "edges": matrix["edges"],
            "summary": matrix.get("summary"),
            "is_cascading": matrix.get("is_cascading")
        }

def get_causal_dag_engine(db_conn):
    return CausalDAGEngine(db_conn)
