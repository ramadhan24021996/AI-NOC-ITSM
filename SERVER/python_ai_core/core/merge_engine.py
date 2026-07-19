import time
from typing import List, Dict, Any

class MergeEngine:
    def __init__(self):
        self.engine_name = "MergeEngine"

    def merge(self, parallel_results: List[Dict[str, Any]], evidence_pkg: Any) -> Dict[str, Any]:
        start_time = time.time()
        
        unified_context = {
            "evidence": {
                "status": evidence_pkg.status if hasattr(evidence_pkg, 'status') else "UNKNOWN",
                "quality": evidence_pkg.quality.overall_score if hasattr(evidence_pkg, 'quality') else 0.0,
                "timeline_length": len(evidence_pkg.evidence_timeline) if hasattr(evidence_pkg, 'evidence_timeline') else 0,
            },
            "findings": {},
            "recommendations": {},
            "confidences": {},
            "metadata": {}
        }
        
        for res in parallel_results:
            if not isinstance(res, dict):
                continue
            eng = res.get("engine", "unknown")
            unified_context["findings"][eng] = res.get("findings", {})
            unified_context["recommendations"][eng] = res.get("recommendation", "")
            unified_context["confidences"][eng] = res.get("confidence", 0.0)
            unified_context["metadata"][eng] = res.get("metadata", {})
            
        latency_ms = int((time.time() - start_time) * 1000)
        
        return {
            "engine": self.engine_name,
            "status": "SUCCESS",
            "confidence": 100.0,
            "latency_ms": latency_ms,
            "evidence_used": [],
            "findings": {"unified_context": unified_context},
            "recommendation": "PROCEED",
            "metadata": {}
        }

def get_merge_engine():
    return MergeEngine()
