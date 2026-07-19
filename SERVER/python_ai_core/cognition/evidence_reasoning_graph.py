"""
Enterprise AI OS — OSI Cognitive Framework: Framework 6
Evidence Reasoning Graph (ERG)

Prinsip utama:
  - OBSERVABILITY ONLY pada fase pertama.
  - Pipeline utama (decision_engine, consensus_engine) TIDAK DIUBAH.
  - Setiap step pipeline memanggil recorder.record_*() yang berjalan secara async.
  - Kegagalan recorder tidak menghentikan pipeline utama (fail-silent).

Node Types:
  INCIDENT    — Raw incident event
  EVIDENCE    — Extracted evidence items (LOS Alarm, CRC, BGP Idle)
  LAYER       — OSI Layer classification result (LayerProfile)
  HYPOTHESIS  — Candidate root causes
  KNOWLEDGE   — Retrieved knowledge vectors
  SKILL       — Selected Skill from SkillGraph
  PLAN        — Diagnosis Plan from TroubleshootingGraph
  DECISION    — Final decision from DecisionEngine/Consensus
  ACTION      — Execution action taken
  VERIFY      — Verification/closure result

Edge Relations:
  supports        — Evidence supports a Hypothesis/Layer
  contradicts     — Evidence contradicts a Hypothesis
  derived_from    — Node is derived from another node
  selected        — A node was selected from alternatives
  executed        — Action was executed from Plan
  verified        — Outcome was verified
  escalated       — Decision was escalated to human

Graph Stats (for Meta-Cognition):
  node_count      — Total reasoning nodes (complexity metric)
  evidence_count  — How many evidence items found
  layer_confidence — Primary layer confidence
  mttr_seconds    — If closure recorded, time from INCIDENT to VERIFY
"""

import json
import logging
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ERG")

# ─── Node type constants ───────────────────────────────────────────────────────
class NodeType:
    INCIDENT   = "INCIDENT"
    EVIDENCE   = "EVIDENCE"
    LAYER      = "LAYER"
    HYPOTHESIS = "HYPOTHESIS"
    KNOWLEDGE  = "KNOWLEDGE"
    SKILL      = "SKILL"
    PLAN       = "PLAN"
    DECISION   = "DECISION"
    ACTION     = "ACTION"
    VERIFY     = "VERIFY"


class EdgeRelation:
    SUPPORTS      = "supports"
    CONTRADICTS   = "contradicts"
    DERIVED_FROM  = "derived_from"
    SELECTED      = "selected"
    EXECUTED      = "executed"
    VERIFIED      = "verified"
    ESCALATED     = "escalated"


@dataclass
class ReasoningNode:
    node_id:    str
    node_type:  str
    payload:    Dict[str, Any]
    confidence: float = 1.0
    layer_num:  Optional[int] = None


@dataclass
class ReasoningEdge:
    from_node: str
    to_node:   str
    relation:  str
    weight:    float = 1.0


class ReasoningGraph:
    """
    In-memory graph for a single incident's reasoning session.
    Committed to DB at the end of the pipeline (batch insert).
    Zero impact on latency — all writes are collected in-memory then flushed.
    """

    def __init__(self, incident_id: str):
        self.incident_id = incident_id
        self.nodes: List[ReasoningNode] = []
        self.edges: List[ReasoningEdge] = []
        self._start_time = time.time()
        self._incident_node_id: Optional[str] = None

    # ── Node creation helpers ──────────────────────────────────────────────────

    def _new_node(self, node_type: str, payload: Dict, confidence: float = 1.0, layer_num: Optional[int] = None) -> str:
        node_id = str(uuid.uuid4())
        self.nodes.append(ReasoningNode(
            node_id=node_id, node_type=node_type,
            payload=payload, confidence=confidence, layer_num=layer_num
        ))
        return node_id

    def _new_edge(self, from_node: str, to_node: str, relation: str, weight: float = 1.0):
        self.edges.append(ReasoningEdge(from_node=from_node, to_node=to_node, relation=relation, weight=weight))

    # ── Step recorders (called by ai_supervisor decorator) ────────────────────

    def record_incident(self, title: str, symptoms: str, severity: str, metadata: Optional[Dict] = None) -> str:
        """Step 0: Root incident node."""
        node_id = self._new_node(NodeType.INCIDENT, {
            "title": title, "symptoms": symptoms,
            "severity": severity, "metadata": metadata or {}
        }, confidence=1.0)
        self._incident_node_id = node_id
        return node_id

    def record_evidence(self, evidence_items: List[str], source: str = "telemetry") -> List[str]:
        """Step 1: Extract evidence items from incident text."""
        node_ids = []
        for item in evidence_items:
            nid = self._new_node(NodeType.EVIDENCE, {"item": item, "source": source})
            node_ids.append(nid)
            if self._incident_node_id:
                self._new_edge(self._incident_node_id, nid, EdgeRelation.DERIVED_FROM)
        return node_ids

    def record_layer_classification(self, layer_profile: Dict) -> str:
        """Step 2: OSI Layer classification result."""
        primary = layer_profile.get("primary_layer", 7)
        confidence = layer_profile.get("confidence", 0.5)
        node_id = self._new_node(NodeType.LAYER, layer_profile, confidence=confidence, layer_num=primary)

        # Evidence → Layer edges (each evidence "supports" this layer)
        for ev_node in [n for n in self.nodes if n.node_type == NodeType.EVIDENCE]:
            # Only connect evidence that matches layer keywords
            self._new_edge(ev_node.node_id, node_id, EdgeRelation.SUPPORTS,
                           weight=confidence)
        return node_id

    def record_hypothesis(self, hypothesis_text: str, confidence: float, layer_node_id: Optional[str] = None) -> str:
        """Step 3: Candidate root cause hypothesis."""
        node_id = self._new_node(NodeType.HYPOTHESIS, {"hypothesis": hypothesis_text}, confidence=confidence)
        if layer_node_id:
            self._new_edge(layer_node_id, node_id, EdgeRelation.DERIVED_FROM, weight=confidence)
        return node_id

    def record_knowledge_retrieval(self, knowledge_items: List[Dict], layer_node_id: Optional[str] = None) -> List[str]:
        """Step 4: Retrieved knowledge vectors from Knowledge Fabric."""
        node_ids = []
        for k in knowledge_items[:5]:  # cap at 5 to avoid graph explosion
            nid = self._new_node(NodeType.KNOWLEDGE, {
                "id": k.get("id", ""), "title": k.get("title", ""),
                "final_score": k.get("final_score", k.get("similarity", 0)),
                "tags": k.get("tags", []),
            }, confidence=float(k.get("final_score") or k.get("similarity") or 0.5))
            node_ids.append(nid)
            if layer_node_id:
                self._new_edge(layer_node_id, nid, EdgeRelation.SUPPORTS,
                               weight=float(k.get("layer_score", 0.5)))
        return node_ids

    def record_skill_selection(self, skill: Dict, knowledge_node_ids: Optional[List[str]] = None) -> str:
        """Step 5: Selected skill from Skill Graph."""
        node_id = self._new_node(NodeType.SKILL, {
            "skill_id": skill.get("skill_id", 0),
            "skill_name": skill.get("skill_name", ""),
            "success_rate": skill.get("success_rate", 0),
        }, confidence=float(skill.get("success_rate", 0.5)))
        for kn in (knowledge_node_ids or []):
            self._new_edge(kn, node_id, EdgeRelation.SUPPORTS)
        return node_id

    def record_diagnosis_plan(self, plan: Dict, skill_node_id: Optional[str] = None) -> str:
        """Step 6: Diagnosis plan from TroubleshootingGraph."""
        node_id = self._new_node(NodeType.PLAN, {
            "plan_id": plan.get("plan_id", ""),
            "primary_layer": plan.get("primary_layer"),
            "estimated_steps": plan.get("estimated_steps", 0),
            "rationale": plan.get("rationale", ""),
        })
        if skill_node_id:
            self._new_edge(skill_node_id, node_id, EdgeRelation.DERIVED_FROM)
        return node_id

    def record_decision(self, decision: str, confidence: float, risk_level: str,
                        plan_node_id: Optional[str] = None) -> str:
        """Step 7: Final decision from Decision/Consensus Engine."""
        node_id = self._new_node(NodeType.DECISION, {
            "decision": decision[:500],  # truncate long decisions
            "confidence": confidence,
            "risk_level": risk_level,
        }, confidence=confidence / 100.0 if confidence > 1 else confidence)
        if plan_node_id:
            self._new_edge(plan_node_id, node_id, EdgeRelation.SELECTED)
        return node_id

    def record_action(self, action_type: str, action_detail: str, decision_node_id: Optional[str] = None) -> str:
        """Step 8: Execution action taken."""
        node_id = self._new_node(NodeType.ACTION, {
            "action_type": action_type, "detail": action_detail[:300]
        })
        if decision_node_id:
            self._new_edge(decision_node_id, node_id, EdgeRelation.EXECUTED)
        return node_id

    def record_verification(self, outcome: str, verified: bool, action_node_id: Optional[str] = None) -> str:
        """Step 9: Verification result."""
        elapsed = time.time() - self._start_time
        node_id = self._new_node(NodeType.VERIFY, {
            "outcome": outcome, "verified": verified,
            "elapsed_seconds": round(elapsed, 2)
        }, confidence=1.0 if verified else 0.0)
        if action_node_id:
            self._new_edge(action_node_id, node_id, EdgeRelation.VERIFIED, weight=1.0 if verified else 0.0)
        return node_id

    # ── Graph statistics (for Meta-Cognition) ─────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Return graph statistics for Meta-Cognition analysis."""
        type_counts = {}
        for n in self.nodes:
            type_counts[n.node_type] = type_counts.get(n.node_type, 0) + 1

        layer_node = next((n for n in self.nodes if n.node_type == NodeType.LAYER), None)
        verify_node = next((n for n in self.nodes if n.node_type == NodeType.VERIFY), None)

        elapsed = time.time() - self._start_time

        return {
            "incident_id":       self.incident_id,
            "total_nodes":       len(self.nodes),
            "total_edges":       len(self.edges),
            "node_type_counts":  type_counts,
            "evidence_count":    type_counts.get(NodeType.EVIDENCE, 0),
            "knowledge_count":   type_counts.get(NodeType.KNOWLEDGE, 0),
            "primary_layer":     layer_node.layer_num if layer_node else None,
            "layer_confidence":  layer_node.confidence if layer_node else 0.0,
            "verified":          verify_node.payload.get("verified") if verify_node else None,
            "elapsed_seconds":   round(elapsed, 2),
            "complexity_score":  len(self.nodes),  # baseline: node count
        }

    def to_summary_dict(self) -> Dict[str, Any]:
        """Serializable summary for logging/dashboard."""
        return {
            "incident_id": self.incident_id,
            "stats": self.get_stats(),
            "nodes": [
                {"id": n.node_id, "type": n.node_type,
                 "confidence": n.confidence, "layer": n.layer_num}
                for n in self.nodes
            ],
            "edges": [
                {"from": e.from_node, "to": e.to_node,
                 "relation": e.relation, "weight": e.weight}
                for e in self.edges
            ],
        }


# ═══════════════════════════════════════════════════════════════════════
# Reasoning Recorder — the thin observability wrapper
# ═══════════════════════════════════════════════════════════════════════

class ReasoningRecorder:
    """
    Thin wrapper that records ERG without touching the main pipeline.

    Usage:
        recorder = ReasoningRecorder(db_conn, incident_id)
        recorder.begin(title, symptoms, severity)

        # ... existing pipeline runs as normal ...

        recorder.set_layer(layer_profile.to_dict())
        recorder.set_knowledge(knowledge_results)
        recorder.set_decision(decision, confidence, risk)
        recorder.flush()   # batch write to DB — called at end of pipeline
    """

    def __init__(self, db_conn=None, incident_id: str = "unknown"):
        self._conn = db_conn
        self._graph = ReasoningGraph(incident_id)
        self._active = db_conn is not None
        # Node ID tracking for edge connections
        self._layer_node_id:    Optional[str] = None
        self._knowledge_node_ids: List[str] = []
        self._skill_node_id:    Optional[str] = None
        self._plan_node_id:     Optional[str] = None
        self._decision_node_id: Optional[str] = None
        self._action_node_id:   Optional[str] = None

    # ── Recorder methods (all fail-silent) ────────────────────────────────────

    def begin(self, title: str, symptoms: str, severity: str, metadata: Optional[Dict] = None):
        if not self._active: return
        try:
            self._graph.record_incident(title, symptoms, severity, metadata)
        except Exception as e:
            logger.debug("[ERG] begin error (non-fatal): %s", e)

    def set_evidence(self, evidence_items: List[str]):
        if not self._active: return
        try:
            self._graph.record_evidence(evidence_items)
        except Exception as e:
            logger.debug("[ERG] set_evidence error (non-fatal): %s", e)

    def set_layer(self, layer_profile: Dict):
        if not self._active: return
        try:
            self._layer_node_id = self._graph.record_layer_classification(layer_profile)
        except Exception as e:
            logger.debug("[ERG] set_layer error (non-fatal): %s", e)

    def set_hypothesis(self, hypothesis: str, confidence: float):
        if not self._active: return
        try:
            self._graph.record_hypothesis(hypothesis, confidence, self._layer_node_id)
        except Exception as e:
            logger.debug("[ERG] set_hypothesis error (non-fatal): %s", e)

    def set_knowledge(self, knowledge_items: List[Dict]):
        if not self._active: return
        try:
            self._knowledge_node_ids = self._graph.record_knowledge_retrieval(
                knowledge_items, self._layer_node_id
            )
        except Exception as e:
            logger.debug("[ERG] set_knowledge error (non-fatal): %s", e)

    def set_skill(self, skill: Dict):
        if not self._active: return
        try:
            self._skill_node_id = self._graph.record_skill_selection(
                skill, self._knowledge_node_ids
            )
        except Exception as e:
            logger.debug("[ERG] set_skill error (non-fatal): %s", e)

    def set_plan(self, plan: Dict):
        if not self._active: return
        try:
            self._plan_node_id = self._graph.record_diagnosis_plan(plan, self._skill_node_id)
        except Exception as e:
            logger.debug("[ERG] set_plan error (non-fatal): %s", e)

    def set_decision(self, decision: str, confidence: float, risk_level: str):
        if not self._active: return
        try:
            self._decision_node_id = self._graph.record_decision(
                decision, confidence, risk_level, self._plan_node_id
            )
        except Exception as e:
            logger.debug("[ERG] set_decision error (non-fatal): %s", e)

    def set_action(self, action_type: str, action_detail: str):
        if not self._active: return
        try:
            self._action_node_id = self._graph.record_action(
                action_type, action_detail, self._decision_node_id
            )
        except Exception as e:
            logger.debug("[ERG] set_action error (non-fatal): %s", e)

    def set_verification(self, outcome: str, verified: bool):
        if not self._active: return
        try:
            self._graph.record_verification(outcome, verified, self._action_node_id)
        except Exception as e:
            logger.debug("[ERG] set_verification error (non-fatal): %s", e)

    # ── Flush: batch write to DB ──────────────────────────────────────────────

    def flush(self) -> Optional[Dict]:
        """
        Batch-insert all nodes and edges to DB.
        Called ONCE at the end of the pipeline.
        Non-blocking: if DB write fails, logs warning and returns None.
        Never raises an exception.
        """
        if not self._active or not self._conn:
            return None
        try:
            stats = self._graph.get_stats()

            with self._conn.cursor() as cur:
                # Insert nodes
                for n in self._graph.nodes:
                    cur.execute("""
                        INSERT INTO reasoning_nodes
                            (node_id, incident_id, node_type, payload, confidence, layer_num)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (node_id) DO NOTHING
                    """, (
                        n.node_id, self._graph.incident_id, n.node_type,
                        json.dumps(n.payload), n.confidence, n.layer_num
                    ))

                # Insert edges
                for e in self._graph.edges:
                    cur.execute("""
                        INSERT INTO reasoning_edges (from_node, to_node, relation, weight)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                    """, (e.from_node, e.to_node, e.relation, e.weight))

            self._conn.commit()

            logger.info(
                "[ERG] Graph flushed — incident=%s nodes=%d edges=%d "
                "evidence=%d layer=L%s confidence=%.0f%% elapsed=%.1fs",
                self._graph.incident_id, stats["total_nodes"], stats["total_edges"],
                stats["evidence_count"], stats.get("primary_layer"),
                (stats.get("layer_confidence") or 0) * 100, stats["elapsed_seconds"]
            )
            return stats

        except Exception as e:
            logger.warning("[ERG] flush error (non-fatal, graph discarded): %s", e)
            try:
                self._conn.rollback()
            except Exception:
                import logging; logging.getLogger(__name__).debug('_ = None suppressed')
            return None

    def get_stats(self) -> Dict:
        """Return current graph stats without flushing."""
        return self._graph.get_stats()
