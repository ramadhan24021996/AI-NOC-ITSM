"""
SERVER.python_ai_core.engines.agentic_rag_engine
=================================================
Enterprise Multi-Step Agentic RAG Engine.

Menerapkan 4 Pilar Utama Agentic RAG:
  1. ReAct Reasoning Loop (Plan -> Act -> Observe -> Reflect)
  2. Corrective RAG (CRAG): Auto-reformulate & Graph Fallback jika relevance < 0.70
  3. GraphRAG: High-resolution Topology Search via KnowledgeGraphService (CMDB & Causal DAG)
  4. Actionable Executable Plan DTO: Output berupa DTO siap eksekusi + Narasi Voice JARVIS
"""

import asyncio
import json
import logging
import os
import sys
import time
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("AGENTIC_RAG_ENGINE")

# Ensure python_ai_core modules are resolvable
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from python_ai_core.engines.rag_engine import RAGEngine
except ImportError:
    try:
        from engines.rag_engine import RAGEngine
    except ImportError:
        from .rag_engine import RAGEngine

try:
    from services.knowledge_graph_service import KnowledgeGraphService
except ImportError:
    KnowledgeGraphService = None


# ─────────────────────────────────────────────────────────────────────────────
# ACTIONABLE RAG PLAN DTO
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AgenticRAGPlanDTO:
    """
    Output DTO terstruktur hasil eksekusi Agentic RAG.
    Dapat langsung dieksekusi oleh ExecutionOrchestrator dan disuarakan JARVIS.
    """
    query: str
    target_device: str
    root_cause_hypothesis: str
    relevance_score: float
    is_crag_triggered: bool
    evidence_sources: List[Dict[str, Any]] = field(default_factory=list)
    executable_actions: List[Dict[str, Any]] = field(default_factory=list)
    risk_level: str = "LOW"             # LOW | MEDIUM | HIGH | CRITICAL
    confidence_score: float = 0.85
    narrative_for_voice: str = ""
    latency_ms: int = 0
    reasoning_steps: List[str] = field(default_factory=list)
    observability_metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "target_device": self.target_device,
            "root_cause_hypothesis": self.root_cause_hypothesis,
            "relevance_score": round(self.relevance_score, 3),
            "is_crag_triggered": self.is_crag_triggered,
            "evidence_sources": self.evidence_sources,
            "executable_actions": self.executable_actions,
            "risk_level": self.risk_level,
            "confidence_score": round(self.confidence_score, 3),
            "narrative_for_voice": self.narrative_for_voice,
            "latency_ms": self.latency_ms,
            "reasoning_steps": self.reasoning_steps,
            "observability_metrics": self.observability_metrics,
        }


# ─────────────────────────────────────────────────────────────────────────────
# CORRECTIVE RAG (CRAG) EVALUATOR & REFORMULATOR
# ─────────────────────────────────────────────────────────────────────────────

class CorrectiveRAGEvaluator:
    """
    Mengevaluasi hasil pencarian RAG dengan Adaptive Thresholding berdasarkan Severity.
    
    Tingkat Relevansi Minimum (Adaptive Threshold):
      - CRITICAL: 0.85 (Presisi tinggi untuk insiden kritis, cepat memicu CRAG jika belum yakin)
      - HIGH    : 0.75
      - MEDIUM  : 0.65
      - LOW     : 0.55
      - INFO    : 0.50 (Default permisif untuk query informasi umum)
    
    Jika skor relevansi < threshold untuk severity tersebut:
      - Reformulasi sub-query dengan memperluas terminologi domain NOC
      - Memicu pencarian GraphRAG (KnowledgeGraph) sebagai suplemen topologi
    """

    DEFAULT_THRESHOLD = 0.70

    SEVERITY_THRESHOLDS = {
        "CRITICAL": 0.85,
        "HIGH":     0.75,
        "MEDIUM":   0.65,
        "LOW":      0.55,
        "INFO":     0.50,
    }

    TECHNICAL_SYNONYMS = {
        "printer": ["spooler", "print jobs", "printer driver", "paper jam", "thermal printer"],
        "kasir": ["pos terminal", "checkout pc", "kasir store", "pos db lock"],
        "server": ["database host", "backend node", "primary server", "app server"],
        "offline": ["unreachable", "ping drop", "network disconnect", "timeout"],
        "lambat": ["high latency", "cpu bottleneck", "memory leak", "disk queue length"],
        "cpu": ["processor overload", "high utilization", "wmiprvse", "thread exhaustion"],
        "ram": ["memory leak", "oomkilled", "swap usage", "high memory allocation"],
        "memory": ["memory leak", "oomkilled", "swap usage", "high memory allocation"],
        "disk": ["storage full", "disk space running out", "high iops", "disk queue stall"],
        "bgp": ["flapping", "neighbor down", "peering drop", "route flap"],
        "vpn": ["tunnel down", "disconnect", "session expired", "rasdial"],
        "nats": ["deserialization error", "connection refused", "jetstream timeout", "deadletter"],
        "database": ["db lock", "query timeout", "connection pool exhausted", "deadlock"],
        "sql": ["query timeout", "connection pool exhausted", "db lock", "deadlock"],
    }

    @classmethod
    def get_threshold(cls, severity: str = "INFO") -> float:
        """Mendapatkan threshold relevansi RAG adaptif sesuai severity insiden."""
        if not severity:
            return cls.DEFAULT_THRESHOLD
        sev_upper = severity.upper().strip()
        return cls.SEVERITY_THRESHOLDS.get(sev_upper, cls.DEFAULT_THRESHOLD)

    @classmethod
    def evaluate(cls, results: List[Dict[str, Any]], severity: str = "INFO") -> Tuple[float, bool]:
        """
        Returns (max_relevance_score, is_low_relevance).
        is_low_relevance is True jika max_relevance_score < threshold (adaptive per severity).
        """
        threshold = cls.get_threshold(severity)
        if not results:
            return 0.0, True

        scores = []
        for r in results:
            raw_val = (
                r.get("similarity_score") or
                r.get("score") or
                r.get("similarity") or
                r.get("rrf_score") or
                r.get("rerank_score") or
                0.0
            )
            try:
                score = float(raw_val)
            except (ValueError, TypeError):
                score = 0.0
            scores.append(score)

        max_score = max(scores) if scores else 0.0
        is_low = max_score < threshold
        return max_score, is_low

    @classmethod
    def reformulate_query(cls, query: str, device: str = "") -> List[str]:
        """
        Menghasilkan sub-queries tambahan untuk perbaikan pencarian RAG.
        """
        sub_queries = [query]
        q_lower = query.lower()

        if device and device.lower() not in q_lower:
            sub_queries.append(f"{query} pada perangkat {device}")

        for term, synonyms in cls.TECHNICAL_SYNONYMS.items():
            if term in q_lower:
                for syn in synonyms[:2]:
                    sub_q = f"{query} {syn}"
                    if sub_q not in sub_queries:
                        sub_queries.append(sub_q)

        return sub_queries[:4]


# ─────────────────────────────────────────────────────────────────────────────
# AGENTIC RAG ENGINE (ReAct Loop + GraphRAG + CRAG)
# ─────────────────────────────────────────────────────────────────────────────

class AgenticRAGEngine:
    """
    Enterprise Multi-Step Agentic RAG Engine.
    Mengeksekusi ReAct Reasoning Cycle:
      Plan -> Act -> Observe -> Reflect -> Output Executable DTO
    """

    def __init__(self):
        self.rag_vector_engine = RAGEngine()
        self.kg_service = KnowledgeGraphService() if KnowledgeGraphService else None
        logger.info("[AGENTIC_RAG] AgenticRAGEngine initialized with Dense RAG & GraphRAG Facade.")

    def run_agentic_rag(
        self,
        query: str,
        device: str = "",
        site_id: str = "",
        incident_id: str = "",
        severity: str = "INFO",
    ) -> AgenticRAGPlanDTO:
        """
        Eksekusi penuh 4-Step ReAct Loop Agentic RAG dengan Adaptive CRAG Threshold.
        """
        t0 = time.time()
        reasoning_steps = []
        evidence_sources = []
        executable_actions = []

        # ── STEP 1: PLAN — Urutkan intent & ruang lingkup investigasi ─────────
        reasoning_steps.append(f"[PLAN] Menganalisis query '{query}' (severity={severity}) untuk device='{device}' site='{site_id}'")
        target_dev = device or self._extract_device_from_text(query)

        # ── STEP 2: ACT — Parallel Search (Vector KEDB + Graph CMDB Topology) ──
        reasoning_steps.append(f"[ACT] Melakukan Dense Vector Search di KEDB...")
        vec_results = self._search_vector_kedb(query, limit=5)

        graph_nodes = []
        if self.kg_service and target_dev and target_dev not in ("GLOBAL-SYSTEM", "SYSTEM-TARGET"):
            reasoning_steps.append(f"[ACT] GraphRAG: Traversal topologi CMDB untuk '{target_dev}'...")
            try:
                graph_nodes = self.kg_service.traverse(target_dev, top_n=5)
                for node in graph_nodes:
                    evidence_sources.append({
                        "source": "KNOWLEDGE_GRAPH_CMDB",
                        "node_id": node.get("node_id", node.get("id")),
                        "relationship": node.get("relationship", "CONNECTED_TO"),
                        "impact_score": node.get("impact_score", 0.8),
                    })
            except Exception as kg_err:
                logger.warning(f"[AGENTIC_RAG] GraphRAG traversal warning: {kg_err}")

        # ── STEP 3: OBSERVE & REFLECT (CRAG Check dengan Adaptive Threshold) ──
        max_score, is_low_rel = CorrectiveRAGEvaluator.evaluate(vec_results, severity=severity)
        threshold = CorrectiveRAGEvaluator.get_threshold(severity)
        crag_triggered = False

        if is_low_rel:
            crag_triggered = True
            reasoning_steps.append(
                f"[OBSERVE] Relevance score ({max_score:.2f}) < {threshold:.2f} (Threshold severity '{severity}'). "
                f"CRAG Terpicu! Memformulasi ulang sub-queries..."
            )
            sub_queries = CorrectiveRAGEvaluator.reformulate_query(query, target_dev)

            for sub_q in sub_queries[1:]:
                reasoning_steps.append(f"[CRAG RETRY] Query ulang KEDB dengan: '{sub_q}'")
                retry_results = self._search_vector_kedb(sub_q, limit=3)
                vec_results.extend(retry_results)

            max_score, _ = CorrectiveRAGEvaluator.evaluate(vec_results, severity=severity)

        # Collect evidence dari Vector Search
        for r in vec_results[:5]:
            raw_score = r.get("similarity_score") or r.get("score") or 0.75
            try:
                score_val = float(raw_score)
            except (ValueError, TypeError):
                score_val = 0.75

            evidence_sources.append({
                "source": "KEDB_VECTOR_DB",
                "title": r.get("title", r.get("incident_title", "KEDB Entry")),
                "similarity_score": round(score_val, 3),
                "solution": r.get("solution", r.get("remediation", "")),
            })

        # ── STEP 4: REFLECT & BUILD EXECUTABLE ACTION PLAN DTO ────────────────
        reasoning_steps.append(f"[REFLECT] Mengompilasi bukti ({len(evidence_sources)} sumber) menjadi Executable Action Plan...")
        
        # If no evidence sources were found from Vector KEDB nor Graph CMDB:
        if not evidence_sources or (target_dev in ("GLOBAL-SYSTEM", "SYSTEM-TARGET") and not vec_results):
            root_cause = "Pertanyaan di luar konteks telemetri/SOP NOC."
            actions = []
            risk = "LOW"
            confidence = 0.0
            voice_text = "Mohon maaf, saya belum dapat menjawab pertanyaan Anda. Silakan berikan konteks atau detail yang lebih spesifik."
        else:
            root_cause, actions, risk, confidence = self._synthesize_actionable_plan(query, target_dev, vec_results, graph_nodes)
            voice_text = self._build_voice_narration(target_dev, root_cause, actions, risk)

        latency = int((time.time() - t0) * 1000)

        # Observability Metrics (P2-5)
        rel_count = sum(
            1 for r in vec_results
            if float(r.get("similarity_score") or r.get("score") or r.get("similarity") or r.get("rrf_score") or 0.0) >= threshold
        )
        precision_at_k = round(rel_count / float(len(vec_results) or 1), 3)

        obs_metrics = {
            "precision_at_k": precision_at_k,
            "top1_score": round(max_score, 3),
            "total_candidates_retrieved": len(vec_results),
            "relevant_candidates_count": rel_count,
            "crag_triggered": crag_triggered,
            "severity": severity,
            "severity_threshold_applied": threshold,
            "latency_ms": latency,
            "kg_nodes_retrieved": len(graph_nodes),
            "evidence_sources_count": len(evidence_sources),
            "execution_mode": "SYNC",
        }

        plan_dto = AgenticRAGPlanDTO(
            query=query,
            target_device=target_dev,
            root_cause_hypothesis=root_cause,
            relevance_score=max_score,
            is_crag_triggered=crag_triggered,
            evidence_sources=evidence_sources,
            executable_actions=actions,
            risk_level=risk,
            confidence_score=confidence,
            narrative_for_voice=voice_text,
            latency_ms=latency,
            reasoning_steps=reasoning_steps,
            observability_metrics=obs_metrics,
        )

        logger.info(
            f"[AGENTIC_RAG] ✅ Executed ReAct loop | device={target_dev} | "
            f"score={max_score:.2f} | P@K={precision_at_k} | CRAG={crag_triggered} | actions={len(actions)} | {latency}ms"
        )
        return plan_dto

    async def run_agentic_rag_async(
        self,
        query: str,
        device: str = "",
        site_id: str = "",
        incident_id: str = "",
        severity: str = "INFO",
    ) -> AgenticRAGPlanDTO:
        """
        Eksekusi asynchronous 4-Step ReAct Loop Agentic RAG (P2-6).
        Menjalankan KEDB Vector Search & GraphRAG CMDB Traversal secara PARALEL (asyncio.gather)
        sehingga tidak mengunci asyncio event loop.
        """
        t0 = time.time()
        reasoning_steps = []
        evidence_sources = []

        target_dev = device or self._extract_device_from_text(query)
        reasoning_steps.append(f"[PLAN-ASYNC] Menganalisis query '{query}' (severity={severity}) untuk device='{target_dev}' site='{site_id}'")

        # ── STEP 2: ACT — Parallel Async Search (Vector KEDB + Graph CMDB Topology) ──
        reasoning_steps.append(f"[ACT-ASYNC] Parallel Search: Vector KEDB + GraphRAG CMDB Traversal...")

        async def _async_vector_search():
            return await asyncio.to_thread(self._search_vector_kedb, query, 5)

        async def _async_kg_traverse():
            if self.kg_service and target_dev and target_dev not in ("GLOBAL-SYSTEM", "SYSTEM-TARGET"):
                try:
                    return await asyncio.to_thread(self.kg_service.traverse, target_dev, 5)
                except Exception as kg_err:
                    logger.warning(f"[AGENTIC_RAG_ASYNC] GraphRAG warning: {kg_err}")
            return []

        vec_results, graph_nodes = await asyncio.gather(_async_vector_search(), _async_kg_traverse())

        for node in graph_nodes:
            evidence_sources.append({
                "source": "KNOWLEDGE_GRAPH_CMDB",
                "node_id": node.get("node_id", node.get("id")),
                "relationship": node.get("relationship", "CONNECTED_TO"),
                "impact_score": node.get("impact_score", 0.8),
            })

        # ── STEP 3: OBSERVE & REFLECT (CRAG Check dengan Adaptive Threshold) ──
        max_score, is_low_rel = CorrectiveRAGEvaluator.evaluate(vec_results, severity=severity)
        threshold = CorrectiveRAGEvaluator.get_threshold(severity)
        crag_triggered = False

        if is_low_rel:
            crag_triggered = True
            reasoning_steps.append(
                f"[OBSERVE-ASYNC] Relevance score ({max_score:.2f}) < {threshold:.2f} (Severity '{severity}'). "
                f"CRAG Terpicu! Memformulasi ulang sub-queries..."
            )
            sub_queries = CorrectiveRAGEvaluator.reformulate_query(query, target_dev)

            retry_tasks = [asyncio.to_thread(self._search_vector_kedb, sub_q, 3) for sub_q in sub_queries[1:]]
            if retry_tasks:
                retry_results_list = await asyncio.gather(*retry_tasks)
                for res_batch in retry_results_list:
                    vec_results.extend(res_batch)

            max_score, _ = CorrectiveRAGEvaluator.evaluate(vec_results, severity=severity)

        # Collect evidence dari Vector Search
        for r in vec_results[:5]:
            raw_score = r.get("similarity_score") or r.get("score") or 0.75
            try:
                score_val = float(raw_score)
            except (ValueError, TypeError):
                score_val = 0.75

            evidence_sources.append({
                "source": "KEDB_VECTOR_DB",
                "title": r.get("title", r.get("incident_title", "KEDB Entry")),
                "similarity_score": round(score_val, 3),
                "solution": r.get("solution", r.get("remediation", "")),
            })

        # ── STEP 4: REFLECT & BUILD EXECUTABLE ACTION PLAN DTO ────────────────
        reasoning_steps.append(f"[REFLECT-ASYNC] Mengompilasi bukti ({len(evidence_sources)} sumber) menjadi Executable Action Plan...")

        if not evidence_sources or (target_dev in ("GLOBAL-SYSTEM", "SYSTEM-TARGET") and not vec_results):
            root_cause = "Pertanyaan di luar konteks telemetri/SOP NOC."
            actions = []
            risk = "LOW"
            confidence = 0.0
            voice_text = "Mohon maaf, saya belum dapat menjawab pertanyaan Anda. Silakan berikan konteks atau detail yang lebih spesifik."
        else:
            root_cause, actions, risk, confidence = await asyncio.to_thread(
                self._synthesize_actionable_plan, query, target_dev, vec_results, graph_nodes
            )
            voice_text = await asyncio.to_thread(
                self._build_voice_narration, target_dev, root_cause, actions, risk
            )

        latency = int((time.time() - t0) * 1000)

        # Observability Metrics (P2-5)
        rel_count = sum(
            1 for r in vec_results
            if float(r.get("similarity_score") or r.get("score") or r.get("similarity") or r.get("rrf_score") or 0.0) >= threshold
        )
        precision_at_k = round(rel_count / float(len(vec_results) or 1), 3)

        obs_metrics = {
            "precision_at_k": precision_at_k,
            "top1_score": round(max_score, 3),
            "total_candidates_retrieved": len(vec_results),
            "relevant_candidates_count": rel_count,
            "crag_triggered": crag_triggered,
            "severity": severity,
            "severity_threshold_applied": threshold,
            "latency_ms": latency,
            "kg_nodes_retrieved": len(graph_nodes),
            "evidence_sources_count": len(evidence_sources),
            "execution_mode": "ASYNC_PARALLEL",
        }

        plan_dto = AgenticRAGPlanDTO(
            query=query,
            target_device=target_dev,
            root_cause_hypothesis=root_cause,
            relevance_score=max_score,
            is_crag_triggered=crag_triggered,
            evidence_sources=evidence_sources,
            executable_actions=actions,
            risk_level=risk,
            confidence_score=confidence,
            narrative_for_voice=voice_text,
            latency_ms=latency,
            reasoning_steps=reasoning_steps,
            observability_metrics=obs_metrics,
        )

        logger.info(
            f"[AGENTIC_RAG_ASYNC] ✅ Parallel ReAct loop completed | device={target_dev} | "
            f"score={max_score:.2f} | P@K={precision_at_k} | CRAG={crag_triggered} | {latency}ms"
        )
        return plan_dto

    # ── PRIVATE HELPERS ───────────────────────────────────────────────────────

    def _search_vector_kedb(self, query_text: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search KEDB via RAGEngine."""
        try:
            # Fast offline probe with 30s retry cooldown if DB connection is unavailable
            if not getattr(self.rag_vector_engine, "conn", None) or getattr(self.rag_vector_engine.conn, "closed", 1):
                last_offline_ts = getattr(self.rag_vector_engine, "_db_offline_ts", 0.0)
                if time.time() - last_offline_ts > 30.0:
                    setattr(self.rag_vector_engine, "_db_offline_ts", time.time())
                    try:
                        self.rag_vector_engine.connect()
                    except Exception:
                        pass
                if not getattr(self.rag_vector_engine, "conn", None) or getattr(self.rag_vector_engine.conn, "closed", 1):
                    return []
                else:
                    setattr(self.rag_vector_engine, "_db_offline_ts", 0.0)


            res = self.rag_vector_engine.embed_and_query(incident_text=query_text, limit=limit)
            if isinstance(res, dict) and "results" in res:
                results_data = res["results"]
                if isinstance(results_data, list):
                    return [x for x in results_data if isinstance(x, dict)]
            elif isinstance(res, list):
                return [x for x in res if isinstance(x, dict)]
        except Exception as e:
            logger.warning(f"[AGENTIC_RAG] Vector search warning: {e}")
        return []

    def _extract_device_from_text(self, text: str) -> str:
        """Ekstrak nama device dari teks."""
        m = re.search(r'\b(KASIR|PRINTER|SERVER|PC|SWITCH|ROUTER)[-_]?\w*(?:\s+\d+)?\b', text, re.IGNORECASE)
        if m:
            return m.group(0).upper().replace(" ", "-")
        return "GLOBAL-SYSTEM"

    def _synthesize_actionable_plan(
        self,
        query: str,
        device: str,
        vec_results: List[Dict[str, Any]],
        graph_nodes: List[Dict[str, Any]],
    ) -> Tuple[str, List[Dict[str, Any]], str, float]:
        """
        Sintesis bukti menjadi Root Cause, Executable Actions, Risk Level, dan Confidence.
        """
        q_lower = query.lower()
        actions = []
        risk = "LOW"
        confidence = 0.85

        if "printer" in q_lower or "cetak" in q_lower or "spooler" in q_lower:
            root_cause = f"Print spooler service mengalami dead lock / queue jam pada {device}."
            actions.append({
                "action_id": "RESTART_SPOOLER",
                "name": "Restart Print Spooler Service",
                "target_device": device,
                "command": "net stop spooler && net start spooler",
                "risk_level": "LOW",
                "success_probability": 0.92,
                "estimated_downtime_sec": 3.0,
            })
            actions.append({
                "action_id": "CLEAR_PRINT_QUEUE",
                "name": "Purge Stuck Print Queue",
                "target_device": device,
                "command": "del /Q /F %systemroot%\\System32\\Spool\\Printers\\*.*",
                "risk_level": "LOW",
                "success_probability": 0.88,
                "estimated_downtime_sec": 2.0,
            })

        elif "kasir" in q_lower or "pos" in q_lower or "db lock" in q_lower:
            root_cause = f"Database lokal POS Kasir mengalami lock transaction / connection limit."
            actions.append({
                "action_id": "FLUSH_POS_CONNECTIONS",
                "name": "Flush Stale POS DB Connections",
                "target_device": device,
                "command": "pg_terminate_backend(pid) FROM pg_stat_activity WHERE state='idle in transaction'",
                "risk_level": "MEDIUM",
                "success_probability": 0.90,
                "estimated_downtime_sec": 5.0,
            })
            risk = "MEDIUM"
            confidence = 0.88

        elif "jaringan" in q_lower or "offline" in q_lower or "ping" in q_lower:
            root_cause = f"Koneksi jaringan terputus atau DNS cache corrupt pada {device}."
            actions.append({
                "action_id": "FLUSH_DNS_CACHE",
                "name": "Flush DNS & Renew IP Lease",
                "target_device": device,
                "command": "ipconfig /flushdns && ipconfig /renew",
                "risk_level": "LOW",
                "success_probability": 0.85,
                "estimated_downtime_sec": 2.0,
            })

        else:
            root_cause = f"Anomali performa / resource utilization berlebihan pada {device}."
            actions.append({
                "action_id": "RESTART_CLIENT_AGENT",
                "name": "Restart Client Telemetry Agent",
                "target_device": device,
                "command": "systemctl restart osi-agent",
                "risk_level": "LOW",
                "success_probability": 0.95,
                "estimated_downtime_sec": 2.0,
            })

        for r in vec_results[:2]:
            sol = r.get("solution") or r.get("remediation")
            if sol and len(actions) < 4:
                actions.append({
                    "action_id": f"KEDB_RUNBOOK_{len(actions)+1}",
                    "name": r.get("title", "Runbook KEDB"),
                    "target_device": device,
                    "command": str(sol)[:120],
                    "risk_level": "LOW",
                    "success_probability": float(r.get("similarity_score", 0.80)),
                    "estimated_downtime_sec": 5.0,
                })

        return root_cause, actions, risk, confidence

    def _build_voice_narration(
        self,
        device: str,
        root_cause: str,
        actions: List[Dict[str, Any]],
        risk: str,
    ) -> str:
        """Buat narasi suara Bahasa Indonesia dengan persona Senior Witty Infrastructure Engineer."""
        act_names = [a.get("name", "remediasi") for a in actions[:2]]
        act_str = " serta ".join(act_names) if act_names else "tindakan penanganan"
        dev_display = f"pada {device}" if device and device != "GLOBAL-SYSTEM" else "pada sistem"

        if risk in ("HIGH", "CRITICAL"):
            return (
                f"Perhatian Senior! Hasil analisis telemetri {dev_display}: {root_cause} "
                f"Saya menyarankan langkah {act_str}. "
                f"Tindakan ini punya tingkat risiko {risk}, jadi butuh persetujuan Anda dulu nih. Gimana bos?"
            )

        return (
            f"Hasil investigasi telemetri {dev_display}: {root_cause} "
            f"Saran Senior: kita eksekusi {act_str}. Apakah Anda setuju saya jalankan sekarang?"
        )

    def dispatch_n8n_async_task(self, plan_dto: AgenticRAGPlanDTO) -> Dict[str, Any]:
        """Dispatches Agentic Plan task to n8n Workflow Node via N8NWorkflowDispatcher (Phase 1)."""
        try:
            try:
                from SERVER.integration.n8n.n8n_dispatcher import get_dispatcher
            except ImportError:
                from integration.n8n.n8n_dispatcher import get_dispatcher
            dispatcher = get_dispatcher()
            payload = plan_dto.to_dict()
            payload["action_id"] = "N8N_TASK_DISPATCH"
            return dispatcher.dispatch_action(
                action_id="N8N_TASK_DISPATCH",
                payload=payload,
                target_device=plan_dto.target_device
            )
        except Exception as e:
            logger.warning(f"[AGENTIC_RAG_ENGINE] n8n async task dispatch failed: {e}")
            return {"status": "FALLBACK_LOCAL", "error": str(e)}
