"""
Enterprise AI OS — OSI Cognitive Framework: Framework 2
Layer-aware Knowledge Fabric

Single access point untuk semua graph pengetahuan dengan multi-signal ranking:
  - Semantic Similarity  (0.45) — pgvector cosine distance
  - Layer Match          (0.20) — OSI layer alignment dari LayerProfile
  - Device Match         (0.10) — device/hostname match
  - Vendor Match         (0.10) — vendor/os_version match
  - Freshness            (0.10) — freshness_score dari database
  - Success Rate         (0.05) — success_count / (success_count + failure_count)

Schema verified against production DB:
  knowledge_vectors: incident_id(text PK), title, symptoms, root_cause, resolution,
                     embedding, tags(array), status, freshness_score, usage_count,
                     success_count, failure_count, last_validated, source_doc,
                     layer_primary(int?), layer_related(int[]?)
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("KNOWLEDGE_FABRIC")

# ─── Ranking weights ──────────────────────────────────────────────────────────
WEIGHT_SEMANTIC  = 0.45
WEIGHT_LAYER     = 0.20
WEIGHT_DEVICE    = 0.10
WEIGHT_VENDOR    = 0.10
WEIGHT_FRESHNESS = 0.10
WEIGHT_SUCCESS   = 0.05


class KnowledgeFabric:
    """
    Unified abstraction layer over all Knowledge Domains.
    All callers use this class — no direct DB access needed.
    """

    def __init__(self, db_conn=None):
        self._conn = db_conn

    # ─── 1. Multi-Signal Ranked Knowledge Query ───────────────────────────────
    def query_knowledge(
        self,
        topic: str,
        embedding: Optional[list] = None,
        limit: int = 5,
        layer_profile: Optional[Dict] = None,    # LayerProfile.to_dict()
        device_name: Optional[str] = None,
        vendor: Optional[str] = None,
    ) -> List[Dict]:
        """
        Multi-signal ranked semantic search across knowledge_vectors (GOLDEN only).

        Ranking formula:
          FinalScore = 0.45*Semantic + 0.20*LayerMatch + 0.10*DeviceMatch
                     + 0.10*VendorMatch + 0.10*Freshness + 0.05*SuccessRate
        """
        if not self._conn:
            return [{"status": "DEGRADED", "source": "database", "confidence": 0, "error": "db_not_connected"}]

        # Extract layer info from profile
        primary_layer    = layer_profile.get("primary_layer") if layer_profile else None
        secondary_layers = layer_profile.get("secondary_layers", []) if layer_profile else []

        try:
            with self._conn.cursor() as cur:
                if embedding and any(v != 0.0 for v in embedding):
                    vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
                    cur.execute("""
                        SELECT incident_id, title, symptoms, root_cause, resolution,
                               tags, freshness_score, success_count, failure_count,
                               1 - (embedding <=> %s::vector) AS semantic_score
                        FROM knowledge_vectors
                        WHERE status = 'GOLDEN'
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                    """, (vec_str, vec_str, limit * 4))   # over-fetch for re-ranking
                else:
                    cur.execute("""
                        SELECT incident_id, title, symptoms, root_cause, resolution,
                               tags, freshness_score, success_count, failure_count,
                               1.0 AS semantic_score
                        FROM knowledge_vectors
                        WHERE status = 'GOLDEN'
                          AND (title ILIKE %s OR symptoms ILIKE %s)
                        ORDER BY freshness_score DESC
                        LIMIT %s
                    """, (f"%{topic}%", f"%{topic}%", limit * 4))

                rows = cur.fetchall()

            # ── Re-rank with multi-signal scoring ────────────────────────────
            results = []
            for r in rows:
                incident_id  = r[0]
                title        = r[1] or ""
                symptoms     = r[2] or ""
                root_cause   = r[3] or ""
                resolution   = r[4] or ""
                tags         = r[5] or []
                freshness    = float(r[6] or 0.5)
                success_c    = int(r[7] or 0)
                failure_c    = int(r[8] or 0)
                semantic     = float(r[9] or 0.0)

                # Layer Match Score
                layer_score = 0.0
                if primary_layer is not None and tags:
                    tag_str = " ".join(str(t) for t in tags).upper()
                    if f"L{primary_layer}_" in tag_str:
                        layer_score = 1.0
                    elif any(f"L{sl}_" in tag_str for sl in secondary_layers):
                        layer_score = 0.5

                # Device Match Score
                device_score = 0.0
                if device_name:
                    dn_lower = device_name.lower()
                    if dn_lower in title.lower() or dn_lower in symptoms.lower():
                        device_score = 1.0

                # Vendor Match Score
                vendor_score = 0.0
                if vendor:
                    v_lower = vendor.lower()
                    if v_lower in symptoms.lower() or v_lower in root_cause.lower():
                        vendor_score = 1.0

                # Success Rate Score
                total_uses = success_c + failure_c
                success_rate = success_c / total_uses if total_uses > 0 else 0.5

                # Final weighted score
                final_score = (
                    WEIGHT_SEMANTIC  * semantic  +
                    WEIGHT_LAYER     * layer_score +
                    WEIGHT_DEVICE    * device_score +
                    WEIGHT_VENDOR    * vendor_score +
                    WEIGHT_FRESHNESS * freshness  +
                    WEIGHT_SUCCESS   * success_rate
                )

                results.append({
                    "id":          incident_id,
                    "title":       title,
                    "content":     symptoms,     # backward compat alias
                    "symptoms":    symptoms,
                    "root_cause":  root_cause,
                    "resolution":  resolution,
                    "tags":        tags,
                    "freshness":   freshness,
                    "similarity":  semantic,
                    "layer_score": layer_score,
                    "final_score": round(final_score, 4),
                    "signal_breakdown": {
                        "semantic":  round(semantic, 3),
                        "layer":     round(layer_score, 3),
                        "device":    round(device_score, 3),
                        "vendor":    round(vendor_score, 3),
                        "freshness": round(freshness, 3),
                        "success":   round(success_rate, 3),
                    }
                })

            # Sort by final_score descending, return top limit
            results.sort(key=lambda x: -x["final_score"])
            return results[:limit]

        except Exception as e:
            logger.error("[KNOWLEDGE_FABRIC] query_knowledge error: %s", e)
            try:
                self._conn.rollback()
            except Exception:
                import logging; logging.getLogger(__name__).debug('_ = None suppressed')
            return [{"status": "DEGRADED", "source": "database", "confidence": 0, "error": f"query_knowledge: {e}"}]

    # ─── 2. Experience Graph (Past Incident Lessons) ──────────────────────────
    def query_experience(self, incident_type: Optional[str] = None, limit: int = 5) -> List[Dict]:
        """Retrieve lessons learned from past incidents in golden_resolutions / golden_solutions."""
        if not self._conn:
            return [{"status": "DEGRADED", "source": "database", "confidence": 0, "error": "db_not_connected"}]
        try:
            with self._conn.cursor() as cur:
                # Use golden_resolutions which is confirmed in DB (\dt shows it)
                if incident_type:
                    cur.execute("""
                        SELECT incident_layer, symptoms, resolution_steps, confidence_score, created_at
                        FROM golden_resolutions
                        WHERE symptoms ILIKE %s
                        ORDER BY confidence_score DESC
                        LIMIT %s
                    """, (f"%{incident_type}%", limit))
                else:
                    cur.execute("""
                        SELECT incident_layer, symptoms, resolution_steps, confidence_score, created_at
                        FROM golden_resolutions
                        ORDER BY confidence_score DESC
                        LIMIT %s
                    """, (limit,))
                rows = cur.fetchall()
                return [
                    {"layer": r[0], "symptoms": r[1], "resolution": r[2],
                     "confidence": float(r[3] or 0), "timestamp": str(r[4])}
                    for r in rows
                ]
        except Exception as e:
            logger.error("[KNOWLEDGE_FABRIC] query_experience error: %s", e)
            try:
                self._conn.rollback()
            except Exception:
                import logging; logging.getLogger(__name__).debug('_ = None suppressed')
            return [{"status": "DEGRADED", "source": "database", "confidence": 0, "error": f"query_experience: {e}"}]

    # ─── 3. World Model (Infrastructure Topology) ─────────────────────────────
    def query_world(self, device_name: Optional[str] = None, site_id: Optional[str] = None) -> Dict[str, Any]:
        """Returns the infrastructure topology context. Delegates to WorldModel."""
        if not self._conn:
            return {"status": "DEGRADED", "source": "database", "confidence": 0, "error": "db_not_connected"}
        try:
            from knowledge.world_model import WorldModel
            wm = WorldModel(self._conn)
            result = {}
            if device_name:
                result["device_context"] = wm.get_device_context(device_name)
                result["blast_radius"]   = wm.get_blast_radius(device_name)
            if site_id:
                result["topology"] = wm.get_site_topology(site_id)
            return result
        except Exception as e:
            logger.error("[KNOWLEDGE_FABRIC] query_world error: %s", e)
            return {"status": "DEGRADED", "source": "database", "confidence": 0, "error": f"query_world: {e}"}

    # ─── 4. Capability Query (Skill Graph) ────────────────────────────────────
    def query_skill(self, layer_num: Optional[int] = None, symptom_text: Optional[str] = None) -> List[Dict]:
        """Returns matching skills from skill_graph table (if it exists)."""
        if not self._conn:
            return [{"status": "DEGRADED", "source": "database", "confidence": 0, "error": "db_not_connected"}]
        try:
            with self._conn.cursor() as cur:
                # Check if skill_graph exists
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_name = 'skill_graph'
                    )
                """)
                if not cur.fetchone()[0]:
                    return [{"status": "DEGRADED", "source": "database", "confidence": 0, "error": "skill_graph_table_missing"}]

                if layer_num is not None:
                    cur.execute("""
                        SELECT skill_id, skill_name, required_layers, tools,
                               success_rate, experience_count, status
                        FROM skill_graph
                        WHERE status IN ('GOLDEN', 'CERTIFIED')
                          AND %s = ANY(required_layers)
                        ORDER BY success_rate DESC, experience_count DESC
                        LIMIT 5
                    """, (layer_num,))
                else:
                    cur.execute("""
                        SELECT skill_id, skill_name, required_layers, tools,
                               success_rate, experience_count, status
                        FROM skill_graph
                        WHERE status IN ('GOLDEN', 'CERTIFIED')
                        ORDER BY success_rate DESC, experience_count DESC
                        LIMIT 5
                    """)
                rows = cur.fetchall()
                return [
                    {"skill_id": r[0], "skill_name": r[1], "layers": r[2],
                     "tools": r[3], "success_rate": r[4], "experience": r[5], "status": r[6]}
                    for r in rows
                ]
        except Exception as e:
            logger.error("[KNOWLEDGE_FABRIC] query_skill error: %s", e)
            try:
                self._conn.rollback()
            except Exception:
                import logging; logging.getLogger(__name__).debug('_ = None suppressed')
            return [{"status": "DEGRADED", "source": "database", "confidence": 0, "error": f"query_skill: {e}"}]

    # ─── 5. Knowledge Gap Detection ───────────────────────────────────────────
    def find_knowledge_gaps(self) -> List[str]:
        """Cross-reference fleet OS types against knowledge_vectors GOLDEN titles."""
        if not self._conn:
            return ["ERROR: db_not_connected"]
        try:
            with self._conn.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT LOWER(os_version)
                    FROM fleet_devices
                    WHERE os_version IS NOT NULL AND os_version != ''
                    LIMIT 50
                """)
                fleet_topics = {row[0] for row in cur.fetchall() if row[0]}

                cur.execute("SELECT LOWER(title) FROM knowledge_vectors WHERE status = 'GOLDEN'")
                covered = {row[0] for row in cur.fetchall()}

            gaps = [t for t in fleet_topics if t and not any(t in c for c in covered if c)]
            logger.info("[KNOWLEDGE_FABRIC] Found %d knowledge gaps.", len(gaps))
            return gaps
        except Exception as e:
            logger.error("[KNOWLEDGE_FABRIC] find_knowledge_gaps error: %s", e)
            return [f"ERROR: {e}"]

    # ─── 6. Knowledge Freshness Summary ───────────────────────────────────────
    def get_freshness_report(self) -> Dict[str, Any]:
        """Return aggregated freshness statistics for the knowledge base."""
        if not self._conn:
            return {"status": "DEGRADED", "source": "database", "confidence": 0, "error": "db_not_connected"}
        try:
            with self._conn.cursor() as cur:
                cur.execute("""
                    SELECT status, COUNT(*) as total,
                           AVG(freshness_score) as avg_freshness,
                           MIN(last_validated) as oldest_validation
                    FROM knowledge_vectors
                    GROUP BY status
                """)
                rows = cur.fetchall()
                return {
                    "by_status": [
                        {"status": r[0], "total": r[1],
                         "avg_freshness": round(float(r[2] or 0), 3),
                         "oldest_validation": str(r[3])}
                        for r in rows
                    ]
                }
        except Exception as e:
            logger.error("[KNOWLEDGE_FABRIC] freshness report error: %s", e)
            return {"status": "DEGRADED", "source": "database", "confidence": 0, "error": str(e)}

    # ─── 7. Vendor Documentation Auto-Update ──────────────────────────────────
    def update_vendor_documentation(self, filepath: str = "local_knowledge_base.json") -> Dict[str, Any]:
        """
        Auto-update feature for Vendor Documentation.
        Reads a local knowledge base JSON and upserts into knowledge_vectors
        with status = 'VENDOR_DOC'.
        """
        if not self._conn:
            return {"status": "DEGRADED", "error": "db_not_connected"}
        
        if not os.path.exists(filepath):
            return {"status": "ERROR", "error": f"File {filepath} not found for auto-update"}
            
        try:
            with open(filepath, 'r') as f:
                vendor_docs = json.load(f)
                
            updated_count = 0
            with self._conn.cursor() as cur:
                for doc in vendor_docs.get("documents", []):
                    # Ensure embedding is processed before inserting (using placeholder or actual RAG generation if integrated)
                    # For now we insert without embedding or with a dummy [0]*768 if required, 
                    # but typically knowledge_vectors requires pgvector embedding.
                    # As a pure auto-update sync, we flag it as VENDOR_DOC.
                    cur.execute("""
                        INSERT INTO knowledge_vectors (incident_id, title, symptoms, resolution, status, tags, freshness_score)
                        VALUES (%s, %s, %s, %s, 'VENDOR_DOC', %s, 1.0)
                        ON CONFLICT (incident_id) DO UPDATE SET 
                            title = EXCLUDED.title,
                            symptoms = EXCLUDED.symptoms,
                            resolution = EXCLUDED.resolution,
                            tags = EXCLUDED.tags,
                            freshness_score = 1.0,
                            last_validated = NOW()
                    """, (
                        doc.get("id", f"vendor_{updated_count}"),
                        doc.get("title", "Vendor Document"),
                        doc.get("content", ""),
                        doc.get("solution", ""),
                        doc.get("tags", [])
                    ))
                    updated_count += 1
            self._conn.commit()
            logger.info(f"[KNOWLEDGE_FABRIC] Successfully auto-updated {updated_count} vendor documents.")
            return {"status": "SUCCESS", "updated_count": updated_count}
        except Exception as e:
            logger.error(f"[KNOWLEDGE_FABRIC] Vendor documentation auto-update failed: {e}")
            try:
                self._conn.rollback()
            except:
                pass
            return {"status": "ERROR", "error": str(e)}
