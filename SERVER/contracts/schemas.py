"""
Domain Schemas & Contracts for Enterprise AI Operations Platform
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from SERVER.shared.enums import IncidentSeverity, ExecutionTrack


@dataclass
class IncidentQueryContract:
    query_id: str
    user_id: str
    user_role: str
    query_text: str
    site_location: Optional[str] = None
    telemetry_context: Dict[str, Any] = field(default_factory=dict)
    request_id: str = ""
    conversation_id: str = ""
    trace_id: str = ""
    session_id: str = ""


@dataclass
class EvidenceSummary:
    primary_evidence: str = "Telemetry"
    secondary_evidence: str = "Memory"
    ignored_sources: List[str] = field(default_factory=list)
    weight_map: Dict[str, float] = field(default_factory=dict)


@dataclass
class ConfidenceScorecard:
    overall_confidence: float = 0.95
    intent_confidence: float = 0.98
    tool_confidence: float = 0.95
    knowledge_confidence: float = 0.85
    level_label: str = "GREEN"  # GREEN, YELLOW, RED


@dataclass
class ConflictResolutionResult:
    has_conflict: bool = False
    resolved_value: Any = None
    authority_source: str = ""
    explanation: str = ""


@dataclass
class GoalPayload:
    active_goal: str = "Find RCA"
    previous_goal: str = ""
    goal_status: str = "IN_PROGRESS"


@dataclass
class DecisionTimelineEntry:
    timestamp: str
    step_name: str
    status: str
    details_ms: int = 0


@dataclass
class JarvisThinkingState:
    intent_stage: str = "COMPLETED"
    entity_stage: str = "COMPLETED"
    telemetry_stage: str = "COMPLETED"
    rag_stage: str = "COMPLETED"
    llm_stage: str = "COMPLETED"
    response_stage: str = "COMPLETED"


@dataclass
class AIConfidenceGauge:
    score_pct: int = 95
    color_indicator: str = "GREEN"


@dataclass
class LearningQueueDetail:
    pending_knowledge_count: int = 0
    pending_sop_count: int = 0
    memory_candidate_count: int = 0


# ── Senior Systems Engineer Intelligence Schemas (Tahap 2.12) ─────────────────

@dataclass
class RootCauseNode:
    node_id: str
    label: str
    target_component: str
    parent_node_id: Optional[str] = None


@dataclass
class RootCauseGraphPayload:
    root_cause_node_id: str
    explanation_chain: str
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    edges: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class EvidenceItem:
    source_name: str
    is_available: bool
    details: str


@dataclass
class EvidenceCollection:
    items: List[Dict[str, Any]] = field(default_factory=list)
    verified_sources_count: int = 0


@dataclass
class SystemSelfHealthBreakdown:
    ai_health: int = 98
    knowledge: int = 95
    telemetry: int = 99
    llm: int = 92
    memory: int = 96
    sandbox: int = 100
    overall_system_health: int = 97


@dataclass
class SelfReflectionReport:
    is_sufficient: bool = True
    sop_checked: bool = True
    telemetry_checked: bool = True
    confidence_adequate: bool = True
    needs_clarification: bool = False
    reflection_notes: str = ""


@dataclass
class ExplanationTrail:
    reasoning_steps: List[str] = field(default_factory=list)
    audit_summary: str = ""


@dataclass
class CapabilityMatrix:
    supported_capabilities: List[str] = field(default_factory=list)
    forbidden_actions: List[str] = field(default_factory=list)


@dataclass
class DailyOperationalJournal:
    date_str: str
    total_incidents: int = 0
    critical_incidents: int = 0
    new_sops_added: int = 0
    sandbox_simulations_run: int = 0
    ai_accuracy_pct: int = 97
    key_findings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    health_delta_pct: int = 8


# ── AI Decision Intelligence Schemas (Tahap 2.13.5) ───────────────────────────

@dataclass
class HypothesisItem:
    label: str
    probability_pct: int
    evidence_support: str


@dataclass
class HypothesisPayload:
    hypotheses: List[Dict[str, Any]] = field(default_factory=list)
    top_hypothesis: str = "Backup Job Contention"


@dataclass
class WeightedEvidencePayload:
    sandbox_weight_pct: int = 40
    netdata_weight_pct: int = 30
    agent_weight_pct: int = 15
    historical_weight_pct: int = 10
    llm_weight_pct: int = 5
    calculated_confidence_pct: int = 95


@dataclass
class SolutionCandidate:
    rank: int
    action_name: str
    confidence_pct: int
    risk_level: str  # LOW, MEDIUM, HIGH
    has_rollback: bool = True
    eta_seconds: int = 30


@dataclass
class RecommendationRankedList:
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    primary_recommendation: str = ""


@dataclass
class DecisionMemoryEntry:
    incident_id: str
    decision_action: str
    reasoning: str
    sandbox_result: str
    confidence_pct: int
    outcome: str  # SUCCESS, FAILED, PENDING


@dataclass
class FailureKnowledgeEntry:
    action_name: str
    result: str  # FAILED
    reason: str
    confidence_impact_pct: int


@dataclass
class OutcomeTrackingResult:
    incident_id: str
    action_name: str
    outcome: str
    recorded_at: str


# ── AI Decision Governance Schemas (Tahap 2.13.6) ─────────────────────────────

@dataclass
class DecisionCriticReport:
    evidence_quality_pct: int = 94
    reasoning_quality_pct: int = 89
    safety_score_pct: int = 100
    risk_level: str = "LOW"
    need_more_evidence: bool = False
    critic_verdict: str = "APPROVED"


@dataclass
class CrossValidationMatrix:
    sources_checked: List[str] = field(default_factory=list)
    consensus_pct: int = 97
    has_conflict: bool = False
    validation_status: str = "VERIFIED"


@dataclass
class SOPComplianceReport:
    recovery_sop_compliance_pct: int = 95
    security_sop_compliance_pct: int = 100
    backup_sop_compliance_pct: int = 65
    has_deviation: bool = False
    deviation_reason: str = ""


@dataclass
class MultiLLMConsensusResult:
    gemini_vote: str = "Stop Backup Job"
    deepseek_vote: str = "Stop Backup Job"
    grok_vote: str = "Memory Leak Recovery"
    winning_consensus: str = "Stop Backup Job"
    consensus_confidence_pct: int = 92


@dataclass
class DecisionDriftReport:
    action_name: str = "Restart PostgreSQL Container"
    historical_success_pct: int = 93
    current_success_pct: int = 48
    drift_detected: bool = True
    action_recommendation: str = "Downgraded recommendation ranking due to drift"


@dataclass
class HumanOverrideLearningEntry:
    incident_id: str
    chosen_option: str
    default_ai_option: str
    override_reason: str
    staging_file_created: str


@dataclass
class CalibratedConfidenceScorecard:
    netdata_signal_score: int = 100
    sandbox_signal_score: int = 100
    history_signal_score: int = 95
    knowledge_signal_score: int = 90
    llm_signal_score: int = 70
    calibrated_final_score: int = 91


# ── Autonomous Platform & Multi-Agent Schemas (Tahap 2.14) ────────────────────

@dataclass
class MissionPriorityQueue:
    p1_active_incidents: List[str] = field(default_factory=list)
    p2_deferred_tasks: List[str] = field(default_factory=list)
    active_mission: str = "Investigate P1 Core Outage"


@dataclass
class LLMResourceStatus:
    active_provider: str = "Gemini 1.5 Pro"
    backup_provider: str = "DeepSeek V3"
    provider_health: Dict[str, str] = field(default_factory=dict)


@dataclass
class OperationalWorkflowPlan:
    plan_title: str
    target_component: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    rollback_plan: str = ""


@dataclass
class MultiAgentDialogueTurn:
    speaker: str  # AI NOC, Jarvis
    message: str
    evidence_tag: str = ""


@dataclass
class MultiAgentSessionPayload:
    dialogue_turns: List[MultiAgentDialogueTurn] = field(default_factory=list)
    peer_agreement_pct: int = 96
    peer_verdict: str = "VERIFIED"


@dataclass
class OperationalKnowledgeGraphPayload:
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    relations: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class MemoryGraphIndexPayload:
    indexed_links_count: int = 14
    top_connected_sop: str = "Oracle RAC Recovery SOP v3.2"


@dataclass
class AIExperienceRecord:
    matched_incidents_count: int = 5
    successful_outcomes_count: int = 4
    key_experience_lesson: str = "Throttle backup succeeded 4x; restart PG succeeded 1x"


@dataclass
class ContinuousImprovementPlan:
    weekly_accuracy_pct: int = 82
    target_learning_area: str = "Oracle RAC Maintenance"
    generated_learning_plan: List[str] = field(default_factory=list)


@dataclass
class DigitalTwinState:
    current_goal: str = "Recovery Execution"
    current_hypothesis: str = "Backup Job Contention"
    evidence_gauge_pct: int = 95
    confidence_pct: int = 92
    running_tasks_count: int = 4
    active_loop: bool = True
    sandbox_status: str = "COMPLETED"
    primary_recommendation: str = "Stop Backup Job"


# ── Enterprise Operational Governance Schemas (Tahap 2.16) ───────────────────

@dataclass
class RuntimePolicyConfig:
    autonomous_execution_low: bool = True
    autonomous_execution_med: bool = False
    autonomous_execution_high: bool = False
    maintenance_window_start: str = "22:00"
    maintenance_window_end: str = "04:00"
    approval_restart_db_required: bool = True
    max_parallel_investigation: int = 5


@dataclass
class ExplainabilityDecisionTimeline:
    steps: List[Dict[str, Any]] = field(default_factory=list)
    total_timeline_ms: int = 420


@dataclass
class AICapabilityVersionInfo:
    jarvis_version: str = "3.2.1"
    knowledge_date: str = "2026-08-05"
    sop_count: int = 2153
    active_llm: str = "Gemini 2.x"
    reasoning_engine_ver: str = "v14"
    decision_engine_ver: str = "v8"


@dataclass
class OperationalMetricsReport:
    avg_rag_time_ms: int = 45
    avg_llm_time_ms: int = 380
    sandbox_exec_time_ms: int = 120
    fallback_count: int = 0
    timeout_count: int = 0
    hallucination_count: int = 0
    human_override_count: int = 1
    recommendation_success_rate_pct: int = 97


@dataclass
class ArbitrationResult:
    has_disagreement: bool = True
    ai_noc_claim: str = "Backup Job"
    jarvis_claim: str = "Memory Leak"
    evidence_requested: List[str] = field(default_factory=list)
    arbitrated_decision: str = "Requesting PostgreSQL Log, Lock Table, and Disk Queue before final decision"


@dataclass
class KnowledgeLineageChain:
    sop_id: str
    original_author: str = "Oracle Vendor Doc v4"
    modified_by: str = "Rama (Operator)"
    reviewed_by: str = "Supervisor ITSM"
    approved_status: str = "APPROVED"
    incidents_applied_count: int = 24
    historical_accuracy_pct: int = 96


@dataclass
class RecoveryTreePlan:
    primary_branch: str = "Throttle Backup Job"
    fallback_branch_1: str = "Kill Long-running Query"
    fallback_branch_2: str = "Restart Container Service"
    emergency_branch: str = "Rollback Container Deployment"


@dataclass
class AIGovernanceDashboardPayload:
    ai_health_pct: int = 98
    knowledge_health_pct: int = 97
    memory_health_pct: int = 99
    hallucination_count: int = 0
    pending_review_count: int = 12
    learning_queue_count: int = 4
    trust_score_pct: int = 96
    runtime_policy_status: str = "ACTIVE"
    decision_drift_level: str = "LOW"
    active_llm_model: str = "Gemini 2.x"
    average_latency_ms: int = 420


# ── AI NOC ↔ Jarvis Review Protocol Schemas (Tahap 2.17) ──────────────────────

@dataclass
class AINOCReviewContract:
    incident_id: str
    hypothesis: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    missing_evidence: List[str] = field(default_factory=list)
    policy_result: Dict[str, Any] = field(default_factory=dict)
    sandbox_result: Dict[str, Any] = field(default_factory=dict)
    recommended_actions: List[str] = field(default_factory=list)
    ai_noc_confidence: float = 0.96
    review_required: bool = False


@dataclass
class AIReviewProtocolReport:
    evidence_review_pass: bool = True
    policy_review_pass: bool = True
    sop_freshness_review_pass: bool = True
    historical_memory_review_pass: bool = True
    sandbox_review_pass: bool = True
    llm_peer_review_pass: bool = True
    overall_protocol_verdict: str = "APPROVED"


@dataclass
class ReviewConfidenceDivergence:
    ai_noc_confidence_pct: int = 96
    jarvis_review_confidence_pct: int = 91
    divergence_delta_pct: int = 5
    audit_status: str = "ACCEPT"  # ACCEPT, REVIEW_REQUIRED


@dataclass
class AuditRejectionFeedback:
    is_rejected: bool = False
    rejection_reason: str = ""
    required_remediation: List[str] = field(default_factory=list)


# ── Closed-Loop AI Review & Quality Gate Schemas (Tahap 2.18) ────────────────

@dataclass
class IterativeReviewIteration:
    round_number: int
    status: str  # PASS, FAIL
    failed_dimensions: List[str] = field(default_factory=list)
    technical_questions: List[str] = field(default_factory=list)
    remediation_recommendation: str = ""


@dataclass
class ReviewAuditTrailRecord:
    session_id: str
    total_rounds: int
    iterations: List[IterativeReviewIteration] = field(default_factory=list)
    final_verdict: str = "APPROVED"


@dataclass
class JarvisTechnicalQuestionPayload:
    technical_questions: List[str] = field(default_factory=list)
    context_explanation: str = ""


@dataclass
class AINOCPerformanceScorecard:
    evidence_score: int = 98
    policy_score: int = 100
    historical_score: int = 72
    sandbox_score: int = 100
    knowledge_score: int = 94
    peer_consensus_score: int = 95
    final_overall_score: int = 92


@dataclass
class RecommendationDiffRow:
    dimension: str
    ai_noc_proposal: str
    jarvis_recommendation: str


@dataclass
class RecommendationDiffTable:
    rows: List[RecommendationDiffRow] = field(default_factory=list)
    selected_winner: str = "Jarvis Recommendation (Throttle Backup)"


@dataclass
class OperatorFeedbackLearningCandidate:
    session_id: str
    chosen_option: str
    operator_reason_category: str
    staging_file_created: str


# ── Ultimate Production Operational Intelligence Schemas (Tahap 2.20) ─────────

@dataclass
class RuntimeCapabilityHealthStatus:
    capabilities_health: Dict[str, str] = field(default_factory=dict)
    all_critical_capabilities_ready: bool = True


@dataclass
class GranularConfidenceExplanation:
    overall_confidence_pct: int = 92
    signal_scores: Dict[str, int] = field(default_factory=dict)
    degradation_reason: str = "Confidence lowered because PostgreSQL Log is unavailable."


@dataclass
class SystemResourceAwareState:
    host_ram_usage_pct: int = 95
    host_cpu_usage_pct: int = 92
    queue_length: int = 37
    active_mode: str = "RESOURCE_CONSTRAINED_LIGHT_MODEL"
    use_cache: bool = True


@dataclass
class SLABusinessImpactReport:
    impacted_users_count: int = 120
    stopped_pos_terminals_count: int = 3
    estimated_revenue_loss_usd: float = 450.0
    sla_risk_level: str = "HIGH (99.9% At Risk)"


@dataclass
class ToolExecutionSequencePayload:
    execution_order: List[Dict[str, Any]] = field(default_factory=list)
    estimated_total_time_seconds: int = 31


@dataclass
class IncidentSimilarityGraphPayload:
    similar_incidents: List[str] = field(default_factory=list)
    key_differences_explanation: str = "INC-102 & INC-85: Backup lock contention. Difference: INC-12 was caused by disk storage full."


@dataclass
class AutonomousRollbackAdvice:
    rollback_recommended: bool = True
    rollback_target: str = "v14.2 Container Image Snapshot"
    estimated_success_pct: int = 97
    estimated_downtime_seconds: int = 30


@dataclass
class MultiAgentSystemHealthPayload:
    ai_noc_status: str = "HEALTHY (1.2s Latency | 96% Consensus)"
    jarvis_status: str = "HEALTHY (0.8s Latency | 94% Review Accuracy)"


# ── P3: Structured Action Context for JARVIS Execution Feedback ───────────────

@dataclass
class StructuredActionContext:
    """
    Konteks eksekusi terstruktur yang dikembalikan bersama setiap respons JARVIS.
    Memungkinkan JARVIS memberikan feedback akurat ke operator tentang apa yang terjadi.
    """
    # Intent hasil klasifikasi
    detected_intent: str = "query"            # QUERY | REMEDIATE | HITL | REMOTE | CHAT | ISSUE
    intent_confidence: float = 0.0

    # Action execution status
    action_taken: Optional[str] = None        # e.g. RESTART_PRINT_SPOOLER, LAUNCH_VNC
    execution_status: Optional[str] = None    # SUCCESS | FAILED | PENDING | CANCELLED | HITL_QUEUED

    # HITL fields
    hitl_queue_id: Optional[str] = None       # Populated jika aksi masuk HITL queue
    requires_hitl_approval: bool = False

    # Safety gate fields
    risk_level: Optional[str] = None          # LOW | MEDIUM | HIGH | CRITICAL
    risk_score: Optional[float] = None
    blast_radius: Optional[int] = None
    policy_effect: Optional[str] = None       # AUTO_EXECUTE | REQUIRE_APPROVAL | FORCE_HITL

    # Follow-up context
    requires_followup: bool = False
    followup_message: str = ""

    # NOC Bridge data (raw response dari dashboard API)
    noc_bridge_data: Optional[Dict[str, Any]] = None

    # Remote session (untuk intent REMOTE)
    remote_session_id: Optional[str] = None
    remote_tool: Optional[str] = None
    remote_host: Optional[str] = None

    # Panel navigation (untuk intent NAVIGATE_PANEL)
    target_panel: Optional[str] = None        # e.g. "incidents", "fleet", "ai-panel", "logs", "sla"




@dataclass
class IncidentResponseContract:
    query_id: str
    execution_track: ExecutionTrack
    answer_text: str
    evidence_score: float
    citations: List[Dict[str, str]] = field(default_factory=list)
    requires_hitl: bool = False
    request_id: str = ""
    trace_id: str = ""
    processing_ms: int = 0
    # ── P3: Structured Execution Context (JARVIS Feedback Loop) ──────────────
    action_context: Optional[StructuredActionContext] = None
    # ── Cognitive Layer Payload Additions ────────────────────────────────────
    cognitive_state: Optional[Dict[str, Any]] = None
    evidence_summary: Optional[EvidenceSummary] = None
    confidence_scorecard: Optional[ConfidenceScorecard] = None
    conflict_resolution: Optional[ConflictResolutionResult] = None
    goal_payload: Optional[GoalPayload] = None
    jarvis_thinking: Optional[JarvisThinkingState] = None
    ai_confidence_gauge: Optional[AIConfidenceGauge] = None
    learning_queue: Optional[LearningQueueDetail] = None
    decision_timeline: List[Dict[str, Any]] = field(default_factory=list)
    # ── Senior Systems Engineer Operational Intelligence ─────────────────────
    root_cause_graph: Optional[RootCauseGraphPayload] = None
    evidence_collection: Optional[EvidenceCollection] = None
    self_health_breakdown: Optional[SystemSelfHealthBreakdown] = None
    self_reflection: Optional[SelfReflectionReport] = None
    explanation_trail: Optional[ExplanationTrail] = None
    capabilities: Optional[CapabilityMatrix] = None
    daily_journal: Optional[DailyOperationalJournal] = None
    # ── AI Decision Intelligence Payload Additions (Tahap 2.13.5) ─────────────
    hypothesis_payload: Optional[HypothesisPayload] = None
    weighted_evidence: Optional[WeightedEvidencePayload] = None
    ranked_recommendations: Optional[RecommendationRankedList] = None
    decision_memory: Optional[List[Dict[str, Any]]] = None
    failure_warnings: Optional[List[Dict[str, Any]]] = None
    # ── AI Decision Governance Payload Additions (Tahap 2.13.6) ───────────────
    decision_critic: Optional[DecisionCriticReport] = None
    cross_validation: Optional[CrossValidationMatrix] = None
    sop_compliance: Optional[SOPComplianceReport] = None
    multi_llm_consensus: Optional[MultiLLMConsensusResult] = None
    decision_drift: Optional[DecisionDriftReport] = None
    calibrated_confidence: Optional[CalibratedConfidenceScorecard] = None
    # ── Autonomous Platform Payload Additions (Tahap 2.14) ────────────────────
    digital_twin_state: Optional[DigitalTwinState] = None
    mission_queue: Optional[MissionPriorityQueue] = None
    multi_agent_dialogue: Optional[MultiAgentSessionPayload] = None
    workflow_plan: Optional[OperationalWorkflowPlan] = None
    knowledge_graph: Optional[OperationalKnowledgeGraphPayload] = None
    experience_record: Optional[AIExperienceRecord] = None
    improvement_plan: Optional[ContinuousImprovementPlan] = None
    # ── Enterprise Operational Governance Additions (Tahap 2.16) ──────────────
    ai_governance_dashboard: Optional[AIGovernanceDashboardPayload] = None
    runtime_policy: Optional[RuntimePolicyConfig] = None
    arbitration_result: Optional[ArbitrationResult] = None
    explainability_timeline: Optional[ExplainabilityDecisionTimeline] = None
    capability_version: Optional[AICapabilityVersionInfo] = None
    knowledge_lineage: Optional[KnowledgeLineageChain] = None
    recovery_tree: Optional[RecoveryTreePlan] = None
    # ── AI NOC ↔ Jarvis Review Protocol Additions (Tahap 2.17) ────────────────
    review_contract: Optional[AINOCReviewContract] = None
    review_protocol: Optional[AIReviewProtocolReport] = None
    confidence_divergence: Optional[ReviewConfidenceDivergence] = None
    rejection_feedback: Optional[AuditRejectionFeedback] = None
    # ── Closed-Loop Review Additions (Tahap 2.18) ─────────────────────────────
    closed_loop_audit_trail: Optional[ReviewAuditTrailRecord] = None
    technical_questions: Optional[JarvisTechnicalQuestionPayload] = None
    ai_noc_scorecard: Optional[AINOCPerformanceScorecard] = None
    recommendation_diff: Optional[RecommendationDiffTable] = None
    # ── Ultimate Operational Intelligence Additions (Tahap 2.20) ───────────────
    capability_health: Optional[RuntimeCapabilityHealthStatus] = None
    granular_confidence: Optional[GranularConfidenceExplanation] = None
    resource_state: Optional[SystemResourceAwareState] = None
    business_impact: Optional[SLABusinessImpactReport] = None
    tool_sequence: Optional[ToolExecutionSequencePayload] = None
    similarity_graph: Optional[IncidentSimilarityGraphPayload] = None
    rollback_advice: Optional[AutonomousRollbackAdvice] = None
    multi_agent_health: Optional[MultiAgentSystemHealthPayload] = None
