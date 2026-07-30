"""
Production-Ready Non-Invasive LLM Output Validation & Synthesizer Adapter (Phase 2B + Refinements)

Enhanced Architecture Highlights:
1. Vendor Decoupling: LLMRouterSynthesizer implements OutputSynthesizerInterface(ABC) via LLMRouter.
2. Prompt Registry: Dynamic versioned prompt management (v1.0, v1.1, v1.2, v2.0).
3. Dual Evidence Handling: Compact Evidence Summary to LLM, full Original Evidence to Audit Logs.
4. Explainable Composite Confidence: 0.4 * Evidence + 0.3 * Consensus + 0.3 * Validation.
5. Explicit Latency Breakdown: validator_ms, adapter_overhead_ms, llm_network_ms.
6. Full Hyperparameter Audit Metadata: provider, model, temperature, max_output_tokens, prompt_version, adapter_version.
"""

import abc
import asyncio
import json
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from adapters.prompt_registry import PromptRegistry

logger = logging.getLogger("OutputSynthesizerAdapter")

PROMPT_VERSION = "v1.2"
ADAPTER_VERSION = "2.0"


# ============================================================================
# CONFIGURATION & DATA MODELS
# ============================================================================

@dataclass
class SynthesizerConfig:
    """Configuration data model for OutputSynthesizerAdapter Phase 2B."""
    enabled: bool = True
    quality_threshold: float = 75.0
    timeout_seconds: float = 8.0
    max_retries: int = 2
    retry_backoff_ms: int = 200
    circuit_breaker_threshold: int = 3
    min_length_chars: int = 150
    model_version: str = "gemini-1.5-flash"
    temperature: float = 0.3
    max_output_tokens: int = 1024
    prompt_version: str = PROMPT_VERSION
    adapter_version: str = ADAPTER_VERSION
    strict_evidence_mode: bool = True


class ValidationTriggerReason(str, Enum):
    IDEMPOTENT = "ALREADY_SYNTHESIZED"
    RAW_JSON_DETECTED = "RAW_JSON_DETECTED"
    RAW_YAML_DETECTED = "RAW_YAML_DETECTED"
    STACK_TRACE_DETECTED = "STACK_TRACE_DETECTED"
    NETDATA_DUMP_DETECTED = "NETDATA_DUMP_DETECTED"
    EXTREMELY_SHORT = "EXTREMELY_SHORT"
    LOW_QUALITY_SCORE = "LOW_QUALITY_SCORE"
    MISSING_RCA = "MISSING_RCA"
    MISSING_RECOMMENDATION = "MISSING_RECOMMENDATION"
    DUPLICATE_SENTENCES = "DUPLICATE_SENTENCES"
    PASSED = "PASSED_HIGH_QUALITY"


@dataclass
class QualityScoreMetrics:
    """Detailed breakdown of the 8 reasoning quality metrics (0.0 to 1.0 each)."""
    readability: float = 1.0
    completeness: float = 1.0
    evidence_coverage: float = 1.0
    rca_presence: float = 1.0
    recommendation_presence: float = 1.0
    training_feedback_presence: float = 1.0
    consistency: float = 1.0
    confidence: float = 1.0

    def calculate_overall_score(self) -> float:
        weights = {
            "readability": 0.10,
            "completeness": 0.15,
            "evidence_coverage": 0.15,
            "rca_presence": 0.20,
            "recommendation_presence": 0.15,
            "training_feedback_presence": 0.05,
            "consistency": 0.10,
            "confidence": 0.10,
        }
        score = (
            self.readability * weights["readability"] +
            self.completeness * weights["completeness"] +
            self.evidence_coverage * weights["evidence_coverage"] +
            self.rca_presence * weights["rca_presence"] +
            self.recommendation_presence * weights["recommendation_presence"] +
            self.training_feedback_presence * weights["training_feedback_presence"] +
            self.consistency * weights["consistency"] +
            self.confidence * weights["confidence"]
        ) * 100.0
        return round(score, 2)


@dataclass
class ValidationResult:
    """Result of the OutputValidator evaluation."""
    is_valid: bool
    is_idempotent: bool
    quality_score: float
    metrics: QualityScoreMetrics
    trigger_reasons: List[ValidationTriggerReason]
    should_bypass_synthesizer: bool


@dataclass
class AdapterResponse:
    """Final output response returned by the OutputAdapterFacade."""
    raw_final_decision: str
    clean_final_decision: str
    is_synthesized: bool
    is_idempotent: bool
    quality_score: float
    composite_confidence: float
    trigger_reasons: List[str]
    execution_time_ms: float
    validator_latency_ms: float
    adapter_overhead_ms: float
    llm_network_ms: float
    fallback_used: bool
    model_version: str
    telemetry_metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# EXPLAINABLE CONFIDENCE ENGINE
# ============================================================================

class CompositeConfidenceEngine:
    """
    Calculates an explainable composite confidence score:
    Confidence = 0.4 * EvidenceScore + 0.3 * ConsensusScore + 0.3 * ValidationQualityScore
    """

    @classmethod
    def calculate_confidence(cls, evidence_score: float, consensus_confidence: float, validation_quality_score: float) -> float:
        ev = min(100.0, max(0.0, evidence_score))
        cs = min(100.0, max(0.0, consensus_confidence if consensus_confidence <= 1.0 else consensus_confidence))
        vq = min(100.0, max(0.0, validation_quality_score))

        composite = (ev * 0.40) + (cs * 0.30) + (vq * 0.30)
        return round(composite, 2)


# ============================================================================
# PROMPT INJECTION GUARD
# ============================================================================

class PromptInjectionGuard:
    """Sanitizes evidence and raw strings to prevent prompt injection attacks."""

    INJECTION_PATTERNS = [
        r"(?i)ignore\s+(all\s+)?previous\s+instruction",
        r"(?i)system\s+prompt\s+override",
        r"(?i)output\s+json\s+only",
        r"(?i)disregard\s+above",
        r"(?i)you\s+are\s+now\s+a",
    ]

    @classmethod
    def sanitize(cls, input_text: str) -> str:
        if not input_text:
            return ""
        clean = input_text
        for pattern in cls.INJECTION_PATTERNS:
            clean = re.sub(pattern, "[REDACTED_INJECTION_ATTEMPT]", clean)
        return clean.strip()


# ============================================================================
# TELEMETRY ANOMALY EXTRACTOR
# ============================================================================

class TelemetryAnomalyExtractor:
    """Extracts top anomaly signals from raw Netdata dumps while keeping original telemetry for audit."""

    @classmethod
    def extract_top_anomalies(cls, raw_telemetry: str) -> Tuple[str, str]:
        """Returns (summary_evidence, original_evidence)."""
        original_evidence = raw_telemetry.strip() if raw_telemetry else "No telemetry data provided."
        
        if not raw_telemetry:
            return "No specific telemetry anomaly payload attached.", original_evidence

        anomalies = []
        text_lower = raw_telemetry.lower()

        if "cpu" in text_lower or "system.cpu" in text_lower:
            cpu_matches = re.findall(r'(\d+(?:\.\d+)?)\s*%', raw_telemetry)
            val = cpu_matches[0] if cpu_matches else "High"
            anomalies.append(f"- CPU Utilization Anomaly: {val}% workload detected")

        if "ram" in text_lower or "memory" in text_lower or "system.ram" in text_lower:
            anomalies.append("- Memory Consumption Anomaly: Elevated RAM allocation/leak pattern detected")

        if "disk" in text_lower or "disk_space" in text_lower or "disk_io" in text_lower:
            anomalies.append("- Disk I/O Anomaly: High storage usage or queue stall detected")

        if "network" in text_lower or "netdata" in text_lower or "socket" in text_lower:
            anomalies.append("- Network Connectivity Anomaly: Intermittent packet latency/loss observed")

        if "process" in text_lower or "wmiprvse" in text_lower or "service" in text_lower:
            anomalies.append("- Process State Anomaly: Service response degradation or deadlock state")

        if not anomalies:
            clean_str = re.sub(r'[\{\}\[\]"\'\n]', ' ', raw_telemetry)[:150]
            anomalies.append(f"- Telemetry Anomaly Summary: {clean_str.strip()}")

        summary_evidence = "\n".join(anomalies)
        return summary_evidence, original_evidence


# ============================================================================
# EVIDENCE GUARD
# ============================================================================

class EvidenceGuard:
    """Validates evidence sufficiency before permitting LLM synthesis."""

    FALLBACK_INSUFFICIENT_EVIDENCE = "Evidence is currently insufficient to determine the exact root cause."

    @classmethod
    def is_evidence_sufficient(cls, evidence: str) -> bool:
        if not evidence or len(evidence.strip()) < 10:
            return False
        if "insufficient" in evidence.lower() or "unknown" in evidence.lower():
            return False
        return True


# ============================================================================
# IDEMPOTENCY DETECTOR
# ============================================================================

class IdempotencyDetector:
    """Detects if an output has already been synthesized using Exact + Semantic Header Groups."""

    SEMANTIC_HEADER_GROUPS = [
        [r"(?i)executive summary", r"(?i)summary", r"(?i)ringkasan", r"(?i)overview", r"(?i)deskripsi"],
        [r"(?i)issue analysis", r"(?i)problem", r"(?i)masalah", r"(?i)gejala", r"(?i)analisis"],
        [r"(?i)root cause", r"(?i)akar masalah", r"(?i)penyebab", r"(?i)cause", r"(?i)rca"]
    ]

    @classmethod
    def is_already_synthesized(cls, text: str) -> bool:
        if not text or len(text.strip()) < 50:
            return False

        group_matches = 0
        for group in cls.SEMANTIC_HEADER_GROUPS:
            if any(re.search(pattern, text) for pattern in group):
                group_matches += 1

        return group_matches >= 3


# ============================================================================
# QUALITY SCORE ENGINE
# ============================================================================

class QualityScoreEngine:
    """Evaluates 8 quality metrics of AI reasoning output (returns 0-100 overall score)."""

    @classmethod
    def evaluate(cls, text: str, evidence: str = "", confidence: float = 0.8) -> QualityScoreMetrics:
        if not text or not text.strip():
            return QualityScoreMetrics(
                readability=0.0, completeness=0.0, evidence_coverage=0.0,
                rca_presence=0.0, recommendation_presence=0.0,
                training_feedback_presence=0.0, consistency=0.0, confidence=0.0
            )

        text_lower = text.lower()
        length = len(text.strip())

        readability = 1.0
        if "{" in text and "}" in text and ":" in text:
            readability -= 0.4
        if "traceback" in text_lower or "exception" in text_lower:
            readability -= 0.4
        readability = max(0.0, readability)

        completeness = 1.0 if length >= 200 else max(0.2, length / 200.0)

        evidence_coverage = 0.8
        if evidence:
            ev_words = [w.lower() for w in re.findall(r'\w{4,}', evidence)]
            if ev_words:
                matches = sum(1 for w in set(ev_words) if w in text_lower)
                evidence_coverage = min(1.0, max(0.3, matches / min(len(set(ev_words)), 5)))

        rca_presence = 1.0 if any(kw in text_lower for kw in ["root cause", "akar masalah", "penyebab", "because", "due to", "cause"]) else 0.3

        recommendation_presence = 1.0 if any(kw in text_lower for kw in ["recommendation", "rekomendasi", "action", "tindakan", "step", "remedi"]) else 0.3

        training_feedback_presence = 1.0 if "training feedback" in text_lower or "feedback" in text_lower else 0.5

        consistency = 1.0
        if "unknown" in text_lower and "resolved" in text_lower:
            consistency = 0.5

        conf_metric = min(1.0, max(0.1, confidence if confidence <= 1.0 else confidence / 100.0))

        return QualityScoreMetrics(
            readability=round(readability, 2),
            completeness=round(completeness, 2),
            evidence_coverage=round(evidence_coverage, 2),
            rca_presence=round(rca_presence, 2),
            recommendation_presence=round(recommendation_presence, 2),
            training_feedback_presence=round(training_feedback_presence, 2),
            consistency=round(consistency, 2),
            confidence=round(conf_metric, 2),
        )


# ============================================================================
# OUTPUT VALIDATOR
# ============================================================================

class OutputValidator:
    """Hybrid Output Validator combining Regex, Rule Engine, Heuristics, and Quality Score."""

    REGEX_JSON = re.compile(r'^\s*[\{\[\"].*[\}\]\"]\s*$', re.DOTALL)
    REGEX_YAML = re.compile(r'^\s*\w+:\s*["\']?.*["\']?\s*\n\s*\w+:', re.MULTILINE)
    REGEX_STACKTRACE = re.compile(r'(Traceback \(most recent call last\)|Exception in thread|Error:.*at line|\.py:\d+|\.go:\d+)', re.IGNORECASE)
    REGEX_NETDATA_DUMP = re.compile(r'(netdata|/api/v1/data|chart_id|chart_type|dimensions|units)', re.IGNORECASE)

    def __init__(self, config: SynthesizerConfig):
        self.config = config

    def validate(self, text: str, evidence: str = "", confidence: float = 0.8) -> ValidationResult:
        reasons: List[ValidationTriggerReason] = []

        if IdempotencyDetector.is_already_synthesized(text):
            reasons.append(ValidationTriggerReason.IDEMPOTENT)
            metrics = QualityScoreEngine.evaluate(text, evidence, confidence)
            return ValidationResult(
                is_valid=True,
                is_idempotent=True,
                quality_score=metrics.calculate_overall_score(),
                metrics=metrics,
                trigger_reasons=reasons,
                should_bypass_synthesizer=True
            )

        stripped = text.strip() if text else ""
        if not stripped or len(stripped) < self.config.min_length_chars:
            reasons.append(ValidationTriggerReason.EXTREMELY_SHORT)

        if self.REGEX_JSON.search(stripped) and (stripped.startswith("{") or stripped.startswith("[")):
            reasons.append(ValidationTriggerReason.RAW_JSON_DETECTED)

        if self.REGEX_YAML.search(stripped) and not stripped.startswith("#"):
            reasons.append(ValidationTriggerReason.RAW_YAML_DETECTED)

        if self.REGEX_STACKTRACE.search(stripped):
            reasons.append(ValidationTriggerReason.STACK_TRACE_DETECTED)

        if self.REGEX_NETDATA_DUMP.search(stripped) and ("{" in stripped or "chart" in stripped):
            reasons.append(ValidationTriggerReason.NETDATA_DUMP_DETECTED)

        text_lower = stripped.lower()
        if not any(kw in text_lower for kw in ["root cause", "akar masalah", "penyebab", "due to", "because", "cause"]):
            reasons.append(ValidationTriggerReason.MISSING_RCA)

        if not any(kw in text_lower for kw in ["recommendation", "rekomendasi", "action", "tindakan", "step", "remedi"]):
            reasons.append(ValidationTriggerReason.MISSING_RECOMMENDATION)

        sentences = [s.strip() for s in re.split(r'[.!?]', stripped) if len(s.strip()) > 15]
        if len(sentences) > 3 and len(set(sentences)) < len(sentences) * 0.7:
            reasons.append(ValidationTriggerReason.DUPLICATE_SENTENCES)

        metrics = QualityScoreEngine.evaluate(stripped, evidence, confidence)
        overall_score = metrics.calculate_overall_score()

        if overall_score < self.config.quality_threshold:
            reasons.append(ValidationTriggerReason.LOW_QUALITY_SCORE)

        should_bypass = len(reasons) == 0 and overall_score >= self.config.quality_threshold
        if should_bypass:
            reasons.append(ValidationTriggerReason.PASSED)

        return ValidationResult(
            is_valid=should_bypass,
            is_idempotent=False,
            quality_score=overall_score,
            metrics=metrics,
            trigger_reasons=reasons,
            should_bypass_synthesizer=should_bypass
        )


# ============================================================================
# THREAD-SAFE CIRCUIT BREAKER
# ============================================================================

class CircuitBreaker:
    """Thread-safe Circuit Breaker protection using threading.RLock."""

    def __init__(self, failure_threshold: int = 3, recovery_time_sec: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_time_sec = recovery_time_sec
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = "CLOSED"
        self._lock = threading.RLock()

    def allow_execution(self) -> bool:
        with self._lock:
            if self.state == "CLOSED":
                return True
            if self.state == "OPEN":
                if time.time() - self.last_failure_time > self.recovery_time_sec:
                    self.state = "HALF-OPEN"
                    return True
                return False
            return True

    def record_success(self):
        with self._lock:
            self.failure_count = 0
            self.state = "CLOSED"

    def record_failure(self):
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"


# ============================================================================
# SYNTHESIZER ABSTRACTION & LLM ROUTER IMPLEMENTATION
# ============================================================================

class OutputSynthesizerInterface(abc.ABC):
    """Abstract Base Class for LLM Output Synthesizers."""

    @abc.abstractmethod
    async def synthesize_async(
        self,
        raw_input: str,
        evidence: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, float]:
        """Returns (synthesized_text, llm_network_ms)."""
        pass

    def synthesize(
        self,
        raw_input: str,
        evidence: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, float]:
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # We are inside an active running event loop
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(lambda: asyncio.run(self.synthesize_async(raw_input, evidence, metadata)))
                    return future.result(timeout=10.0)
            else:
                return asyncio.run(self.synthesize_async(raw_input, evidence, metadata))
        except Exception as syn_err:
            logger.warning(f"[OutputSynthesizer] Async synthesize fallback used due to: {syn_err}")
            return raw_input, 0.0


class LLMRouterSynthesizer(OutputSynthesizerInterface):
    """
    Production Synthesizer implementation using system LLMRouter.
    Fully vendor-decoupled: delegating model execution to LLMRouter.
    """

    def __init__(self, config: SynthesizerConfig):
        self.config = config
        self.circuit_breaker = CircuitBreaker(failure_threshold=config.circuit_breaker_threshold)

    async def synthesize_async(
        self,
        raw_input: str,
        evidence: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, float]:
        if not self.circuit_breaker.allow_execution():
            logger.warning("[LLMRouterSynthesizer] Circuit breaker is OPEN.")
            raise RuntimeError("Circuit Breaker OPEN - Instant Fallback")

        if not EvidenceGuard.is_evidence_sufficient(evidence):
            logger.info("[LLMRouterSynthesizer] Evidence Guard: Telemetry insufficient. Bypassing LLM.")
            return self._build_insufficient_evidence_report(evidence), 0.0

        sanitized_raw = PromptInjectionGuard.sanitize(raw_input)
        sanitized_evidence = PromptInjectionGuard.sanitize(evidence)
        summary_anomalies, original_ev = TelemetryAnomalyExtractor.extract_top_anomalies(sanitized_evidence)

        # Retrieve prompt version from PromptRegistry
        prompt = PromptRegistry.get_prompt(
            version=self.config.prompt_version,
            anomalies=summary_anomalies,
            raw_reasoning=sanitized_raw[:1000]
        )

        t0 = time.perf_counter()
        try:
            from llm_router import get_router
            router = get_router()
            
            res = await router.execute_with_retry(
                severity_score=75,
                prompt=prompt,
                max_retries=self.config.max_retries,
                incident_id=str(metadata.get("incident_id", "")) if metadata else ""
            )
            llm_network_ms = (time.perf_counter() - t0) * 1000.0

            if res and isinstance(res, dict) and res.get("status") == "SUCCESS" and res.get("response"):
                self.circuit_breaker.record_success()
                return res["response"].strip(), llm_network_ms
            else:
                self.circuit_breaker.record_failure()
                err_msg = res.get('error') if (res and isinstance(res, dict)) else 'null response from router'
                raise RuntimeError(f"LLMRouter returned failure: {err_msg}")

        except Exception as err:
            llm_network_ms = (time.perf_counter() - t0) * 1000.0
            logger.error(f"[LLMRouterSynthesizer] Synthesis failed: {err}")
            self.circuit_breaker.record_failure()
            raise err

    def _build_insufficient_evidence_report(self, evidence: str) -> str:
        return f"""### Executive Summary
Sistem terdeteksi mengalami sinyal anomali ringan. Diperlukan bukti telemetri tambahan untuk analisis penuh.

### Issue Analysis
{evidence or 'Telemetry payload contains insufficient anomalous signals.'}

### Root Cause Analysis
{EvidenceGuard.FALLBACK_INSUFFICIENT_EVIDENCE}

### Recommendation
1. Lakukan pemantauan berlanjut pada agen Netdata host.
2. Verifikasi keterhubungan layanan pendukung.

### Action Plan
- Pantau status insiden di dashboard NOC."""


class MockOutputSynthesizer(OutputSynthesizerInterface):
    """Mock implementation for testing."""
    def __init__(self, config: SynthesizerConfig):
        self.config = config

    async def synthesize_async(self, raw_input: str, evidence: str = "", metadata=None) -> Tuple[str, float]:
        await asyncio.sleep(0.003)
        res = f"""### Executive Summary
Sistem terdeteksi mengalami anomali operasional.

### Issue Analysis
{evidence or 'Netdata telemetry anomaly detected.'}

### Root Cause Analysis
Automated Causal Analysis determined potential root cause.

### Recommendation
1. Lakukan pemantauan beban kerja.

### Action Plan
- Verifikasi status konektivitas agent."""
        return res, 3.0


# ============================================================================
# OUTPUT ADAPTER FACADE
# ============================================================================

class OutputAdapterFacade:
    """Main thread-safe facade entry point for Output Validation & Synthesis."""

    def __init__(self, config: Optional[SynthesizerConfig] = None, synthesizer: Optional[OutputSynthesizerInterface] = None):
        self.config = config or SynthesizerConfig()
        self.validator = OutputValidator(self.config)
        self.synthesizer = synthesizer or LLMRouterSynthesizer(self.config)

    def process(
        self,
        raw_final_decision: str,
        evidence: str = "",
        confidence: float = 0.8,
        incident_id: Optional[int] = None,
        device_name: str = "SYSTEM"
    ) -> AdapterResponse:
        start_time = time.perf_counter()

        if not self.config.enabled:
            exec_time = (time.perf_counter() - start_time) * 1000.0
            return AdapterResponse(
                raw_final_decision=raw_final_decision,
                clean_final_decision=raw_final_decision,
                is_synthesized=False,
                is_idempotent=False,
                quality_score=100.0,
                composite_confidence=confidence,
                trigger_reasons=["FEATURE_FLAG_DISABLED"],
                execution_time_ms=exec_time,
                validator_latency_ms=0.0,
                adapter_overhead_ms=exec_time,
                llm_network_ms=0.0,
                fallback_used=False,
                model_version=self.config.model_version,
                telemetry_metadata={
                    "provider": "llm-router",
                    "model": self.config.model_version,
                    "temperature": self.config.temperature,
                    "max_output_tokens": self.config.max_output_tokens,
                    "prompt_version": self.config.prompt_version,
                    "adapter_version": self.config.adapter_version,
                    "status": "DISABLED"
                }
            )

        clean_final_decision = raw_final_decision
        fallback_used = False
        is_synthesized = False
        reasons_str: List[str] = []
        llm_network_ms = 0.0

        t_val_0 = time.perf_counter()
        val_result = self.validator.validate(raw_final_decision, evidence, confidence)
        validator_latency_ms = (time.perf_counter() - t_val_0) * 1000.0

        composite_conf = CompositeConfidenceEngine.calculate_confidence(
            evidence_score=80.0 if evidence else 40.0,
            consensus_confidence=confidence * 100.0 if confidence <= 1.0 else confidence,
            validation_quality_score=val_result.quality_score
        )

        try:
            reasons_str = [r.value for r in val_result.trigger_reasons]

            if val_result.should_bypass_synthesizer:
                exec_time = (time.perf_counter() - start_time) * 1000.0
                adapter_overhead_ms = exec_time - validator_latency_ms
                return AdapterResponse(
                    raw_final_decision=raw_final_decision,
                    clean_final_decision=raw_final_decision,
                    is_synthesized=False,
                    is_idempotent=val_result.is_idempotent,
                    quality_score=val_result.quality_score,
                    composite_confidence=composite_conf,
                    trigger_reasons=reasons_str,
                    execution_time_ms=round(exec_time, 2),
                    validator_latency_ms=round(validator_latency_ms, 2),
                    adapter_overhead_ms=round(adapter_overhead_ms, 2),
                    llm_network_ms=0.0,
                    fallback_used=False,
                    model_version=self.config.model_version,
                    telemetry_metadata={
                        "provider": "llm-router",
                        "model": self.config.model_version,
                        "temperature": self.config.temperature,
                        "max_output_tokens": self.config.max_output_tokens,
                        "prompt_version": self.config.prompt_version,
                        "adapter_version": self.config.adapter_version,
                        "status": "BYPASSED"
                    }
                )

            summary_ev, original_ev = TelemetryAnomalyExtractor.extract_top_anomalies(evidence)

            synthesized_text, llm_net_ms = self.synthesizer.synthesize(
                raw_final_decision,
                evidence,
                {"incident_id": incident_id, "device_name": device_name}
            )
            llm_network_ms = llm_net_ms

            if synthesized_text and len(synthesized_text.strip()) > 20:
                clean_final_decision = synthesized_text
                is_synthesized = True
            else:
                fallback_used = True
                clean_final_decision = raw_final_decision

        except Exception as err:
            logger.error(f"[OutputAdapterFacade] Exception in adapter process: {err}. Falling back to raw_final_decision.")
            fallback_used = True
            clean_final_decision = raw_final_decision
            reasons_str.append(f"ADAPTER_EXCEPTION: {str(err)}")

        total_exec_time = (time.perf_counter() - start_time) * 1000.0
        adapter_overhead_ms = total_exec_time - validator_latency_ms - llm_network_ms

        telemetry_meta = {
            "provider": "llm-router",
            "model": self.config.model_version,
            "temperature": self.config.temperature,
            "max_output_tokens": self.config.max_output_tokens,
            "prompt_version": self.config.prompt_version,
            "adapter_version": self.config.adapter_version,
            "event": "OUTPUT_SYNTHESIZER_INVOKED",
            "incident_id": incident_id,
            "device_name": device_name,
            "is_synthesized": is_synthesized,
            "quality_score": val_result.quality_score if 'val_result' in locals() else 0.0,
            "composite_confidence": composite_conf,
            "trigger_reasons": reasons_str,
            "validator_latency_ms": round(validator_latency_ms, 2),
            "adapter_overhead_ms": round(max(0.0, adapter_overhead_ms), 2),
            "llm_network_ms": round(llm_network_ms, 2),
            "total_execution_ms": round(total_exec_time, 2),
            "fallback_used": fallback_used,
            "original_evidence": original_ev if 'original_ev' in locals() else evidence
        }

        logger.info(f"[OutputAdapterFacade] Audit Log: {json.dumps(telemetry_meta)}")

        return AdapterResponse(
            raw_final_decision=raw_final_decision,
            clean_final_decision=clean_final_decision,
            is_synthesized=is_synthesized,
            is_idempotent=False,
            quality_score=val_result.quality_score if 'val_result' in locals() else 0.0,
            composite_confidence=composite_conf,
            trigger_reasons=reasons_str,
            execution_time_ms=round(total_exec_time, 2),
            validator_latency_ms=round(validator_latency_ms, 2),
            adapter_overhead_ms=round(max(0.0, adapter_overhead_ms), 2),
            llm_network_ms=round(llm_network_ms, 2),
            fallback_used=fallback_used,
            model_version=self.config.model_version,
            telemetry_metadata=telemetry_meta
        )
