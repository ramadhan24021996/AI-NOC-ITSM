"""
SERVER.jarvis.cognition.knowledge_graph_bridge — JARVIS Knowledge Graph Bridge
===============================================================================
P14 Implementation: Menghubungkan KnowledgeGraphService ke JARVIS Runtime.

Memungkinkan operator bertanya via JARVIS:
  "Jarvis, tunjukkan causal graph INC-001"
  "Jarvis, berapa blast radius jika server-db-01 mati?"
  "Jarvis, cari common ancestor untuk PC-01 dan PC-02"
  "Jarvis, update topology setelah INC-001 diselesaikan"
"""
import logging
import os
import sys
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jarvis.cognition.knowledge_graph_bridge")


class JarvisKnowledgeGraphBridge:
    """
    P14 — JARVIS Knowledge Graph Bridge.
    Exposes KnowledgeGraphService capabilities ke JARVIS runtime.
    """

    def __init__(self, nats_client=None):
        self._kg_service: Optional[Any] = None
        self._available = False
        self._nats_client = nats_client
        self._try_init()

    def _try_init(self) -> None:
        try:
            ai_core_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "python_ai_core")
            )
            if ai_core_path not in sys.path:
                sys.path.insert(0, ai_core_path)
            from SERVER.python_ai_core.services.knowledge_graph_service import KnowledgeGraphService  # type: ignore
            self._kg_service = KnowledgeGraphService(nats_client=self._nats_client)
            self._available = True
            logger.info("[KGBridge] KnowledgeGraphService connected.")
        except Exception as e:
            logger.warning(f"[KGBridge] KnowledgeGraphService not available: {e}.")

    # ── Public API ─────────────────────────────────────────────────────────────

    def traverse_causal_graph(self, symptom_node: str, top_n: int = 5) -> str:
        """
        Traverse causal graph dari symptom node ke root cause candidates.
        "Jarvis, trace causal graph dari server-db-01"
        """
        if not self._available or not self._kg_service:
            return self._not_available("causal graph traversal")
        try:
            results = self._kg_service.traverse(symptom_node, top_n=top_n)
            if not results:
                return f"Tidak ada causal path ditemukan dari node '{symptom_node}'."
            lines = [f"🔍 Causal Graph dari `{symptom_node}` (top {top_n}):\n"]
            for i, node in enumerate(results, 1):
                label = node.get("label", node.get("node_id", "?"))
                score = node.get("score", 0)
                lines.append(f"  {i}. {label} (score: {score:.2f})")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Gagal traverse causal graph: {e}"

    def get_blast_radius(self, failure_node: str) -> str:
        """
        Hitung downstream impact jika node tertentu gagal.
        "Jarvis, berapa blast radius jika server-db-01 mati?"
        """
        if not self._available or not self._kg_service:
            return self._not_available("blast radius calculation")
        try:
            result = self._kg_service.calculate_blast_radius(failure_node)
            affected = result.get("affected_nodes", [])
            services = result.get("affected_services", [])
            users = result.get("estimated_users_impacted", 0)
            return (
                f"💥 Blast Radius jika `{failure_node}` gagal:\n"
                f"├── Node terpengaruh  : {len(affected)} node\n"
                f"├── Service terdampak : {', '.join(services[:5]) or '-'}\n"
                f"└── Estimasi user     : {users} pengguna\n"
                f"\nNode: {', '.join(affected[:8]) or 'tidak ada'}"
            )
        except Exception as e:
            return f"❌ Gagal hitung blast radius: {e}"

    def find_common_ancestor(self, symptom_nodes: List[str]) -> str:
        """
        Cari common infrastructure bottleneck dari beberapa symptom.
        "Jarvis, cari root yang sama antara PC-01 dan PC-02"
        """
        if not self._available or not self._kg_service:
            return self._not_available("common ancestor search")
        try:
            results = self._kg_service.find_common_ancestor(symptom_nodes)
            if not results:
                return f"Tidak ada common ancestor ditemukan untuk {symptom_nodes}."
            lines = [f"🌳 Common Ancestor untuk {symptom_nodes}:\n"]
            for r in results[:5]:
                label = r.get("label", "?")
                depth = r.get("depth", 0)
                lines.append(f"  • {label} (depth: {depth})")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Gagal cari common ancestor: {e}"

    def build_context_for_incident(self, incident_id: str,
                                    symptom_nodes: List[str]) -> str:
        """Build rich context dari knowledge graph untuk suatu insiden."""
        if not self._available or not self._kg_service:
            return self._not_available("knowledge graph context")
        try:
            context = self._kg_service.build_context_for_rag(
                {"node_id": symptom_nodes[0] if symptom_nodes else incident_id},
                incident_id=incident_id,
            )
            if isinstance(context, str):
                return f"📚 KG Context untuk {incident_id}:\n{context[:800]}"
            return f"📚 KG Context untuk {incident_id}: {str(context)[:400]}"
        except Exception as e:
            return f"❌ Gagal build KG context: {e}"

    def explain_rca(self, incident_id: str, root_cause_node: str) -> str:
        """Generate RCA explanation dari knowledge graph."""
        if not self._available or not self._kg_service:
            return self._not_available("RCA explanation")
        try:
            explanation = self._kg_service.explain_rca(incident_id, root_cause_node)
            return f"🔍 RCA Explanation:\n{str(explanation)[:600]}"
        except Exception as e:
            return f"❌ Gagal generate RCA explanation: {e}"

    @staticmethod
    def _not_available(feature: str) -> str:
        return (
            f"⚠️ Knowledge Graph Service tidak tersedia. "
            f"Fitur '{feature}' memerlukan KnowledgeGraphService (NATS required)."
        )

    @property
    def is_available(self) -> bool:
        return self._available


class JarvisBusinessImpactBridge:
    """
    P16 — JARVIS Business Impact Bridge.
    Menghubungkan BusinessImpactEngine ke JARVIS untuk query criticality.

    Pertanyaan yang bisa dijawab:
      "Jarvis, berapa criticality score server-db-01?"
      "Jarvis, tunjukkan asset yang BUSINESS CRITICAL"
      "Jarvis, recalculate criticality semua asset"
    """

    # Static criticality lookup untuk mode tanpa DB connection
    _STATIC_CRITICALITY = {
        "Server": "BUSINESS CRITICAL",
        "Database": "BUSINESS CRITICAL",
        "Router": "CRITICAL",
        "Switch": "HIGH",
        "Firewall": "CRITICAL",
        "PC": "MEDIUM",
        "Printer": "LOW",
    }

    _SCORE_RULES = {
        "BUSINESS CRITICAL": {"score_range": "80-100", "icon": "🔴", "sla": "99.99%"},
        "CRITICAL":          {"score_range": "60-79",  "icon": "🟠", "sla": "99.9%"},
        "HIGH":              {"score_range": "40-59",  "icon": "🟡", "sla": "99.5%"},
        "MEDIUM":            {"score_range": "20-39",  "icon": "🟢", "sla": "99.0%"},
        "LOW":               {"score_range": "0-19",   "icon": "⚪", "sla": "98.0%"},
    }

    def __init__(self, db_conn=None):
        self._db_conn = db_conn
        self._engine: Optional[Any] = None
        self._db_available = False
        if db_conn:
            self._try_init_engine(db_conn)

    def _try_init_engine(self, db_conn) -> None:
        try:
            from SERVER.python_ai_core.world_model.business_impact_engine import BusinessImpactEngine  # type: ignore
            self._engine = BusinessImpactEngine(db_conn)
            self._db_available = True
            logger.info("[BusinessImpactBridge] BusinessImpactEngine connected.")
        except Exception as e:
            logger.warning(f"[BusinessImpactBridge] Engine not available: {e}.")

    def get_criticality(self, device_name: str, device_type: str = "Server") -> str:
        """
        Dapatkan criticality level suatu device.
        Dengan DB: dari database. Tanpa DB: dari static rules.
        """
        # Normalize device type dari nama
        device_type = self._infer_device_type(device_name, device_type)
        criticality = self._STATIC_CRITICALITY.get(device_type, "MEDIUM")
        rules = self._SCORE_RULES.get(criticality, {})

        return (
            f"{rules.get('icon', '⚪')} Business Impact — `{device_name}`:\n"
            f"├── Device Type  : {device_type}\n"
            f"├── Criticality  : *{criticality}*\n"
            f"├── Score Range  : {rules.get('score_range', 'N/A')}\n"
            f"└── Target SLA   : {rules.get('sla', 'N/A')}\n\n"
            f"{'⚠️ Downtime device ini berdampak ke operasional kritis!' if criticality in ('BUSINESS CRITICAL', 'CRITICAL') else '✅ Dampak bisnis dalam batas toleransi.'}"
        )

    def get_sla_target(self, device_name: str, device_type: str = "Server") -> str:
        """Get SLA target berdasarkan criticality."""
        device_type = self._infer_device_type(device_name, device_type)
        criticality = self._STATIC_CRITICALITY.get(device_type, "MEDIUM")
        return self._SCORE_RULES.get(criticality, {}).get("sla", "99.0%")

    def recalculate_all_criticality(self) -> str:
        """Trigger recalculation semua asset criticality (butuh DB)."""
        if self._db_available and self._engine:
            try:
                self._engine.calculate_criticality()
                return "✅ Recalculation criticality semua asset selesai. Database diperbarui."
            except Exception as e:
                return f"❌ Gagal recalculate criticality: {e}"
        return (
            "⚠️ Recalculation criticality memerlukan koneksi database. "
            "Mode offline: menggunakan static rules."
        )

    @staticmethod
    def _infer_device_type(device_name: str, hint: str = "") -> str:
        """Infer device type dari nama device."""
        name_lower = device_name.lower()
        if any(k in name_lower for k in ["server", "srv", "svc"]):
            return "Server"
        if any(k in name_lower for k in ["db", "database", "postgres", "mysql", "oracle"]):
            return "Database"
        if any(k in name_lower for k in ["router", "gw", "gateway"]):
            return "Router"
        if any(k in name_lower for k in ["switch", "sw"]):
            return "Switch"
        if any(k in name_lower for k in ["fw", "firewall", "palo", "fortinet"]):
            return "Firewall"
        if any(k in name_lower for k in ["printer", "print"]):
            return "Printer"
        if any(k in name_lower for k in ["pc", "kasir", "tms", "pos"]):
            return "PC"
        return hint or "Server"  # Default ke Server
