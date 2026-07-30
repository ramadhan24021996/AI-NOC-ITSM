import asyncio
import time
import json
from typing import Dict, Any

def standard_output(engine_name: str, status: str, confidence: float, start_time: float, evidence_used: list, findings: dict, recommendation: str, metadata: dict | None = None) -> Dict[str, Any]:
    latency_ms = int((time.time() - start_time) * 1000)
    return {
        "engine": engine_name,
        "status": status,
        "confidence": confidence,
        "latency_ms": latency_ms,
        "evidence_used": evidence_used,
        "findings": findings,
        "recommendation": recommendation,
        "metadata": metadata or {}
    }

async def run_correlation_engine(data, conn) -> Dict[str, Any]:
    start = time.time()
    try:
        from core.correlation_engine import CorrelationEngine
        eng = CorrelationEngine(conn)
        res = await eng.correlate_incident(data.get("pc_name", "UNKNOWN"), data)
        return standard_output("CorrelationEngine", "SUCCESS", 85.0, start, [], res, "Correlated incident data")
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return standard_output("CorrelationEngine", "ERROR", 0.0, start, [], {"error": str(e)}, "Error")

async def run_intent_engine(data) -> Dict[str, Any]:
    start = time.time()
    try:
        from intent_classifier import get_intent_classifier
        classifier = get_intent_classifier()
        text = str(data)
        res = classifier.predict_multi(text)
        return standard_output("IntentEngine", "SUCCESS", res[0]["confidence"] if res else 0.0, start, [], {"intents": res}, "Use primary intent")
    except Exception as e:
        return standard_output("IntentEngine", "ERROR", 0.0, start, [], {"error": str(e)}, "Error")

async def run_osi_engine(data, evidence_pkg) -> Dict[str, Any]:
    start = time.time()
    try:
        from cognition.osi_taxonomy import classify_incident_layer
        res = classify_incident_layer(str(data), evidence_pkg.validated_telemetry if evidence_pkg else {})
        conf_val = float(res.confidence.strip('%')) if isinstance(res.confidence, str) else float(res.confidence)
        return standard_output("OSITaxonomyEngine", "SUCCESS", conf_val, start, [], res.to_dict(), "Focus on root cause layer")
    except Exception as e:
        return standard_output("OSITaxonomyEngine", "ERROR", 0.0, start, [], {"error": str(e)}, "Error")

async def run_knowledge_graph(data, conn) -> Dict[str, Any]:
    start = time.time()
    try:
        # Simple extraction of keywords from the data string to find related nodes
        text = str(data).lower()
        findings = {"related_entities": [], "relationships": []}
        
        with conn.cursor() as cur:
            # Query edges where source or target matches any word in the text (very basic fuzzy matching for demonstration)
            cur.execute("""
                SELECT source_id, target_id, relationship, confidence 
                FROM knowledge_graph_edges 
                LIMIT 5
            """)
            edges = cur.fetchall()
            
            for source_id, target_id, relationship, confidence in edges:
                if source_id in text or target_id in text:
                    findings["relationships"].append({
                        "source": source_id,
                        "target": target_id,
                        "relationship": relationship,
                        "confidence": confidence
                    })
        
        return standard_output("KnowledgeGraphEngine", "SUCCESS", 80.0, start, [], findings, "Leverage relational entities")
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return standard_output("KnowledgeGraphEngine", "ERROR", 0.0, start, [], {"error": str(e)}, "Error")

async def run_timeline(data, conn) -> Dict[str, Any]:
    start = time.time()
    try:
        from core.timeline_builder import TimelineBuilder
        tb = TimelineBuilder(conn)
        pc_name = data.get("pc_name", "")
        timeline = tb.build_timeline(pc_name) if pc_name else []
        return standard_output("TimelineEngine", "SUCCESS", 90.0, start, [], {"timeline": timeline}, "Analyzed device timeline")
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return standard_output("TimelineEngine", "ERROR", 0.0, start, [], {"error": str(e)}, "Error")

async def run_dependency(data) -> Dict[str, Any]:
    start = time.time()
    try:
        from cognition.service_dependency_map import ServiceDependencyMap
        sdm = ServiceDependencyMap()
        svcs = [data.get("component", "unknown")]
        res = sdm.correlate_evidence_to_graph({"involved_services": svcs})
        return standard_output("ServiceDependencyEngine", "SUCCESS", 75.0, start, [], res, "Mapped dependencies")
    except Exception as e:
        return standard_output("ServiceDependencyEngine", "ERROR", 0.0, start, [], {"error": str(e)}, "Error")

async def run_blast_radius(data) -> Dict[str, Any]:
    start = time.time()
    try:
        from cognition.knowledge_graph import DynamicKnowledgeGraph
        kg = DynamicKnowledgeGraph()
        comp = data.get("component", "unknown")
        res = kg.calculate_blast_radius(comp)
        return standard_output("BlastRadiusEngine", "SUCCESS", 85.0, start, [], res, "Calculated downstream blast radius")
    except Exception as e:
        return standard_output("BlastRadiusEngine", "ERROR", 0.0, start, [], {"error": str(e)}, "Error")

async def run_rag(data, nc) -> Dict[str, Any]:
    start = time.time()
    try:
        req = {"incident_text": str(data), "limit": 3}
        res_bytes = await nc.request("ai.engine.rag", json.dumps(req).encode(), timeout=5.0)
        res = json.loads(res_bytes.data.decode())
        return standard_output("RAGEngine", "SUCCESS", 95.0, start, [], {"results": res.get("results", [])}, "Apply historical resolutions")
    except Exception as e:
        return standard_output("RAGEngine", "ERROR", 0.0, start, [], {"error": str(e)}, "Error")

async def run_causal(data) -> Dict[str, Any]:
    start = time.time()
    try:
        from cognition.causal_engine import CausalReasoningEngine
        eng = CausalReasoningEngine()
        res = eng.infer_root_cause([data])
        return standard_output("CausalEngine", "SUCCESS", 80.0, start, [], res, "Review root cause")
    except Exception as e:
        return standard_output("CausalEngine", "ERROR", 0.0, start, [], {"error": str(e)}, "Error")

async def run_health_score(data, conn) -> Dict[str, Any]:
    start = time.time()
    try:
        pc_name = data.get("pc_name", "")
        score = 100
        if pc_name and conn:
            with conn.cursor() as cur:
                cur.execute("SELECT hardware_info FROM fleet_devices WHERE pc_name = %s", (pc_name,))
                row = cur.fetchone()
                if row and row[0]:
                    hardware = row[0]
                    if isinstance(hardware, str):
                        try:
                            hardware = json.loads(hardware)
                        except:
                            hardware = {}
                    cpu = float(hardware.get("cpu_usage", 0.0))
                    mem = float(hardware.get("memory_usage", 0.0))
                    score = max(0.0, 100.0 - (cpu/2) - (mem/2))
        return standard_output("HealthScoringEngine", "SUCCESS", 100.0, start, [], {"dynamic_score": score}, "Score calculated from live DB")
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return standard_output("HealthScoringEngine", "ERROR", 0.0, start, [], {"error": str(e)}, "Error")
