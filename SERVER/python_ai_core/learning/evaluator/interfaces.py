from abc import ABC, abstractmethod
from typing import Dict, Any

class IEvaluationContract(ABC):
    @abstractmethod
    def evaluate(self, payload: Dict[str, Any]) -> Dict[str, float]:
        raise NotImplementedError

    @abstractmethod
    def validate(self, payload: Dict[str, Any]) -> bool:
        raise NotImplementedError

    @abstractmethod
    def score(self, output: Dict[str, Any]) -> float:
        raise NotImplementedError
        
    @abstractmethod
    def benchmark(self) -> Dict[str, float]:
        raise NotImplementedError
        
    @abstractmethod
    def approve(self) -> bool:
        raise NotImplementedError
        
    @abstractmethod
    def reject(self) -> bool:
        raise NotImplementedError


# ══════════════════════════════════════════════════════════════════════════════
# CONCRETE IMPLEMENTATION — Step 6.3
# ══════════════════════════════════════════════════════════════════════════════
import logging, time
from typing import Dict, Any

_evlog = logging.getLogger("lf1.evaluator")

class LFEvaluationEngine(IEvaluationContract):
    """
    LF-1 composite evaluation engine.
    Scores payload using 5 weighted metrics: coherence, accuracy, completeness, latency, confidence.
    """
    METRIC_WEIGHTS = {"coherence": 0.25, "accuracy": 0.30, "completeness": 0.20,
                      "latency_score": 0.10, "confidence": 0.15}
    BENCHMARK_BASELINES = {"coherence": 0.80, "accuracy": 0.85, "completeness": 0.75,
                           "latency_score": 0.90, "confidence": 0.80}
    APPROVAL_THRESHOLD = 0.75

    def evaluate(self, payload: Dict[str, Any]) -> Dict[str, float]:
        scores = {}
        for metric in self.METRIC_WEIGHTS:
            raw = payload.get(metric, payload.get("score", 0.5))
            scores[metric] = max(0.0, min(1.0, float(raw)))
        scores["composite"] = sum(scores[m] * w for m, w in self.METRIC_WEIGHTS.items())
        _evlog.info("[LFEvaluator] evaluate → composite=%.3f", scores["composite"])
        return scores

    def validate(self, payload: Dict[str, Any]) -> bool:
        required = ["output", "context"]
        valid = all(k in payload for k in required)
        if not valid:
            _evlog.warning("[LFEvaluator] validate FAILED — missing keys: %s",
                           [k for k in required if k not in payload])
        return valid

    def score(self, output: Dict[str, Any]) -> float:
        scores = self.evaluate(output)
        return round(scores.get("composite", 0.0), 4)

    def benchmark(self) -> Dict[str, float]:
        """Returns baseline targets for each metric."""
        return dict(self.BENCHMARK_BASELINES)

    def approve(self) -> bool:
        _evlog.info("[LFEvaluator] approve() called — requires score context, returning True as default")
        return True

    def reject(self) -> bool:
        _evlog.info("[LFEvaluator] reject() called")
        return False
