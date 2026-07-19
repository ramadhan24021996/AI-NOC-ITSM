"""
P15: Knowledge Edge Manager
OSI Incident Ops — Knowledge Graph Evolution v1.0

Architecture:
  Each time an incident is successfully resolved, this module:
    1. Looks up the resolved incident's knowledge_vectors entry.
    2. Finds the top-N semantically similar knowledge nodes using pgvector.
    3. Upserts a weighted edge between them in knowledge_edges:
       - If edge exists: increment co_occurrence_count, bump weight, refresh timestamp.
       - If new: insert with weight 1.0.
    4. This allows the graph to evolve naturally over time — frequently
       co-occurring resolution patterns gain higher weights and surface first.

Edge relationship_types:
  SIMILAR_SYMPTOM    — same symptom set, different root cause
  SAME_ROOT_CAUSE    — same root cause, possibly different device/site
  SAME_RESOLUTION    — same resolution procedure applied
  CO_SITE            — occurred at the same site within 24h window
  ESCALATION_PATH    — this incident led to escalation of another

Weight evolution formula:
  new_weight = min(old_weight + 0.1 * (1 / (rank + 1)), 5.0)
  Capped at 5.0 to prevent unbounded growth.
  Decays are NOT applied automatically — this is intentional for
  long-term pattern preservation. Future: add a scheduled decay job.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("KNOWLEDGE_EDGE_MANAGER")

DB_HOST     = os.getenv("DB_HOST", "postgres")
DB_PORT     = int(os.getenv("DB_PORT", 5432))
DB_NAME     = os.getenv("DB_NAME", "osi_system")
DB_USER     = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

WEIGHT_INCREMENT = 0.1
WEIGHT_CAP       = 5.0
SIMILARITY_LIMIT = 5       # How many similar nodes to link per resolution
SIMILARITY_THRESHOLD = 0.6  # Minimum cosine similarity to form an edge


def _get_db():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, database=DB_NAME,
        user=DB_USER, password=DB_PASSWORD, connect_timeout=5
    )


class KnowledgeEdgeManager:
    """
    Manages evolution of weighted edges in the knowledge graph.
    Called after each successful incident resolution.
    """

    def reinforce_edges(
        self,
        resolved_incident_id: str,
        site_id: Optional[str] = None,
        relationship_hint: str = "SAME_RESOLUTION"
    ) -> int:
        """
        Find semantically similar knowledge nodes to the resolved incident
        and reinforce or create weighted edges between them.

        Args:
            resolved_incident_id: The incident_id key in knowledge_vectors.
            site_id: Optional site context for CO_SITE relationship detection.
            relationship_hint: Default relationship type for new edges.

        Returns:
            Number of edges created or reinforced.
        """
        edges_affected = 0
        try:
            conn = _get_db()
            with conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # 1. Fetch the resolved incident's embedding
                    cur.execute("""
                        SELECT incident_id, embedding, tags
                        FROM knowledge_vectors
                        WHERE incident_id = %s
                    """, (resolved_incident_id,))
                    source_row = cur.fetchone()
                    if not source_row:
                        logger.warning(
                            "[KNOWLEDGE EDGE] Incident %s not found in knowledge_vectors — skipping edge reinforcement.",
                            resolved_incident_id
                        )
                        return 0

                    embedding = source_row["embedding"]
                    if not embedding:
                        logger.warning("[KNOWLEDGE EDGE] No embedding for %s — skipping.", resolved_incident_id)
                        return 0

                    # 2. Find top-N similar nodes using pgvector cosine distance
                    cur.execute("""
                        SELECT
                            incident_id,
                            title,
                            (1 - (embedding <=> %s::vector)) AS similarity
                        FROM knowledge_vectors
                        WHERE incident_id != %s
                          AND embedding IS NOT NULL
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                    """, (embedding, resolved_incident_id, embedding, SIMILARITY_LIMIT))
                    similar_nodes = cur.fetchall()

                    # 3. Upsert edges for nodes above similarity threshold
                    for rank, node in enumerate(similar_nodes):
                        similarity = float(node["similarity"])
                        if similarity < SIMILARITY_THRESHOLD:
                            continue

                        target_id = node["incident_id"]
                        weight_bump = WEIGHT_INCREMENT * (1.0 / (rank + 1))

                        cur.execute("""
                            INSERT INTO knowledge_edges
                                (source_id, target_id, relationship_type, weight, co_occurrence_count, last_reinforced_at)
                            VALUES (%s, %s, %s, %s, 1, NOW())
                            ON CONFLICT (source_id, target_id, relationship_type) DO UPDATE SET
                                weight = LEAST(knowledge_edges.weight + %s, %s),
                                co_occurrence_count = knowledge_edges.co_occurrence_count + 1,
                                last_reinforced_at = NOW()
                        """, (
                            resolved_incident_id, target_id, relationship_hint,
                            round(1.0 + weight_bump, 3),
                            round(weight_bump, 3), WEIGHT_CAP
                        ))
                        edges_affected += 1
                        logger.debug(
                            "[KNOWLEDGE EDGE] Edge reinforced: %s -> %s (type=%s, similarity=%.3f)",
                            resolved_incident_id, target_id, relationship_hint, similarity
                        )

                    # 4. CO_SITE edge: link to other incidents resolved at the same site recently
                    if site_id:
                        cur.execute("""
                            SELECT kv.incident_id
                            FROM knowledge_vectors kv
                            JOIN fleet_incidents fi ON fi.incident_id::TEXT = kv.incident_id
                            WHERE fi.site_id = %s
                              AND fi.resolved_at > NOW() - INTERVAL '24 hours'
                              AND kv.incident_id != %s
                            LIMIT 3
                        """, (site_id, resolved_incident_id))
                        site_peers = cur.fetchall()
                        for peer in site_peers:
                            cur.execute("""
                                INSERT INTO knowledge_edges
                                    (source_id, target_id, relationship_type, weight, co_occurrence_count, last_reinforced_at)
                                VALUES (%s, %s, 'CO_SITE', 0.5, 1, NOW())
                                ON CONFLICT (source_id, target_id, relationship_type) DO UPDATE SET
                                    weight = LEAST(knowledge_edges.weight + 0.05, %s),
                                    co_occurrence_count = knowledge_edges.co_occurrence_count + 1,
                                    last_reinforced_at = NOW()
                            """, (resolved_incident_id, peer["incident_id"], WEIGHT_CAP))
                            edges_affected += 1

            conn.close()
            logger.info(
                "[KNOWLEDGE EDGE] Reinforcement complete for %s: %d edges affected.",
                resolved_incident_id, edges_affected
            )
        except Exception as exc:
            logger.error("[KNOWLEDGE EDGE] Error during edge reinforcement: %s", exc)

        return edges_affected

    def get_neighbors(self, incident_id: str, min_weight: float = 0.5, limit: int = 10) -> list:
        """
        Retrieve the highest-weight neighboring knowledge nodes for a given incident.
        Used by the RAG engine to enrich context with graph-connected resolutions.
        """
        try:
            conn = _get_db()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        ke.target_id,
                        ke.relationship_type,
                        ke.weight,
                        ke.co_occurrence_count,
                        kv.title,
                        kv.symptoms,
                        kv.resolution
                    FROM knowledge_edges ke
                    JOIN knowledge_vectors kv ON kv.incident_id = ke.target_id
                    WHERE ke.source_id = %s
                      AND ke.weight >= %s
                    ORDER BY ke.weight DESC
                    LIMIT %s
                """, (incident_id, min_weight, limit))
                results = [dict(row) for row in cur.fetchall()]
            conn.close()
            return results
        except Exception as exc:
            logger.error("[KNOWLEDGE EDGE] get_neighbors error: %s", exc)
            return list()


# ── Singleton ────────────────────────────────────────────────────────────────────
_instance: Optional[KnowledgeEdgeManager] = None


def get_edge_manager() -> KnowledgeEdgeManager:
    global _instance
    if _instance is None:
        _instance = KnowledgeEdgeManager()
    return _instance
