"""
SERVER.orchestrator.cognitive.decision_engine
==============================================
Component: Cognitive Decision Engine

Orchestrates all cognitive sub-modules into a unified CognitiveDecisionPayload:
  - Context Tracker
  - LLM Context Analyzer
  - Goal Manager
  - Knowledge Gap Detector
  - Memory Candidate Detector
  - Learning Validator
  - Evidence Manager
  - Confidence Resolver
  - Conflict Resolver
  - Tool Requirement Detector
  - Decision Timeline Generator
"""
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from SERVER.contracts.schemas import (
    EvidenceSummary,
    ConfidenceScorecard,
    ConflictResolutionResult,
    GoalPayload,
    JarvisThinkingState,
    AIConfidenceGauge,
    LearningQueueDetail,
    DecisionTimelineEntry,
)

from SERVER.orchestrator.cognitive.context_tracker import ConversationContextTracker, ConversationContextState
from SERVER.orchestrator.cognitive.llm_analyzer import LLMContextAnalyzer, LLMAnalysisResult
from SERVER.orchestrator.cognitive.goal_manager import GoalManager
from SERVER.orchestrator.cognitive.knowledge_gap_detector import KnowledgeGapDetector, KnowledgeGapResult
from SERVER.orchestrator.cognitive.memory_candidate_detector import MemoryCandidateDetector, MemoryCandidateResult
from SERVER.orchestrator.cognitive.learning_validator import LearningValidator
from SERVER.orchestrator.cognitive.evidence_manager import EvidenceManager
from SERVER.orchestrator.cognitive.confidence_resolver import ConfidenceResolver
from SERVER.orchestrator.cognitive.conflict_resolver import ConflictResolver
from SERVER.orchestrator.cognitive.tool_requirement_detector import ToolRequirementDetector, ToolRequirementResult

logger = logging.getLogger("orchestrator.cognitive.decision_engine")


@dataclass
class CognitiveDecisionPayload:
    context_state: ConversationContextState
    analysis_result: LLMAnalysisResult
    goal_payload: GoalPayload
    knowledge_gap: KnowledgeGapResult
    memory_candidate: MemoryCandidateResult
    tool_requirement: ToolRequirementResult
    evidence_summary: EvidenceSummary
    confidence_scorecard: ConfidenceScorecard
    ai_confidence_gauge: AIConfidenceGauge
    conflict_resolution: ConflictResolutionResult
    thinking_state: JarvisThinkingState
    learning_queue: LearningQueueDetail
    timeline: List[Dict[str, Any]] = field(default_factory=list)


class CognitiveDecisionEngine:
    """
    Central cognitive orchestrator running the full Pre-LLM Cognitive Processing Pipeline.
    """

    def __init__(self):
        self.context_tracker = ConversationContextTracker()
        self.llm_analyzer = LLMContextAnalyzer()
        self.goal_manager = GoalManager()
        self.knowledge_gap_detector = KnowledgeGapDetector()
        self.memory_detector = MemoryCandidateDetector()
        self.learning_validator = LearningValidator()
        self.evidence_manager = EvidenceManager()
        self.confidence_resolver = ConfidenceResolver()
        self.conflict_resolver = ConflictResolver()
        self.tool_detector = ToolRequirementDetector()

    def process(
        self,
        session_id: str,
        query_text: str,
        telemetry_context: Dict[str, Any],
        rag_chunks: List[Dict[str, Any]],
        user_role: str = "NOC Engineer",
        site_location: str = "",
    ) -> CognitiveDecisionPayload:
        t0 = time.monotonic()
        timeline: List[Dict[str, Any]] = []

        def _record_step(name: str, status: str = "COMPLETED"):
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            timeline.append({
                "timestamp": time.strftime("%H:%M:%S"),
                "step_name": name,
                "status": status,
                "details_ms": elapsed_ms,
            })

        # 1. Voice / Text Input Received
        _record_step("Input Received")

        # 2. Update Conversation Context & Stage
        context_state = self.context_tracker.update_context(
            session_id, query_text, telemetry_context, user_role, site_location
        )
        _record_step("Context & Stage Updated")

        # 3. LLM Context Analysis (Intent, Entity, Urgency)
        analysis_result = self.llm_analyzer.analyze(query_text, telemetry_context)
        _record_step("LLM Intent & Entity Analyzed")

        # 4. Goal Management
        goal_payload = self.goal_manager.update_goal(
            session_id, query_text, analysis_result.intent, context_state.stage
        )
        _record_step("Goal Managed")

        # 5. Detectors & Validation
        tool_req = self.tool_detector.detect(query_text)
        _record_step("Tool Requirement Evaluated")

        knowledge_gap = self.knowledge_gap_detector.detect(query_text, rag_chunks)
        _record_step("Knowledge Gap Checked")

        mem_cand = self.memory_detector.detect(query_text)
        val_result = self.learning_validator.validate(mem_cand)
        if not val_result.is_valid and mem_cand.is_candidate:
            mem_cand.is_candidate = False
            logger.info(f"[DecisionEngine] Memory candidate rejected by validator: {val_result.rejection_reason}")
        _record_step("Memory Candidate Validated")

        # 6. Conflict Resolution
        conflict_res = self.conflict_resolver.resolve_telemetry_conflict(telemetry_context)
        _record_step("Conflict Resolved")

        # 7. Evidence Management & Confidence Resolution
        has_telem = len(telemetry_context) > 0
        has_mem = mem_cand.is_candidate
        has_rag = len(rag_chunks) > 0
        has_conv = True

        evidence_summary = self.evidence_manager.evaluate(
            has_telemetry=has_telem,
            has_memory=has_mem,
            has_rag=has_rag,
            has_conversation=has_conv,
        )
        _record_step("Evidence Weighted")

        primary_weight = evidence_summary.weight_map.get(evidence_summary.primary_evidence, 0.90)
        confidence_card = self.confidence_resolver.resolve(
            intent_confidence=analysis_result.intent_confidence,
            tool_confidence=0.95 if tool_req.requires_tool else 0.90,
            knowledge_confidence=0.90 if has_rag else 0.60,
            evidence_primary_weight=primary_weight,
        )
        ai_gauge = self.confidence_resolver.get_gauge(confidence_card)
        _record_step("Confidence Resolved")

        # 8. Learning Queue Summary
        learning_queue = LearningQueueDetail(
            pending_knowledge_count=1 if knowledge_gap.has_gap else 0,
            pending_sop_count=knowledge_gap.missing_sop_count,
            memory_candidate_count=1 if mem_cand.is_candidate else 0,
        )

        # 9. Thinking State
        thinking_state = JarvisThinkingState(
            intent_stage="COMPLETED",
            entity_stage="COMPLETED",
            telemetry_stage="COMPLETED" if has_telem else "SKIPPED",
            rag_stage="COMPLETED" if has_rag else "SKIPPED",
            llm_stage="COMPLETED",
            response_stage="GENERATING",
        )

        payload = CognitiveDecisionPayload(
            context_state=context_state,
            analysis_result=analysis_result,
            goal_payload=goal_payload,
            knowledge_gap=knowledge_gap,
            memory_candidate=mem_cand,
            tool_requirement=tool_req,
            evidence_summary=evidence_summary,
            confidence_scorecard=confidence_card,
            ai_confidence_gauge=ai_gauge,
            conflict_resolution=conflict_res,
            thinking_state=thinking_state,
            learning_queue=learning_queue,
            timeline=timeline,
        )

        logger.info(
            f"[DecisionEngine] Processed session={session_id} | goal={goal_payload.active_goal} | confidence={confidence_card.overall_confidence}"
        )
        return payload
