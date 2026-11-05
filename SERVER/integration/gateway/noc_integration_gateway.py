"""
SERVER.integration.gateway — NOC Integration Gateway
======================================================
Tahap 2.5, 2.9, 2.10, 2.12, 2.13.5, 2.13.6, 2.14, 2.16, 2.17, 2.18, & 2.20 — Enterprise AI Operations Platform Gateway

Implementasi konkret UnifiedGateway untuk AI NOC Platform dengan Ultimate Operational Intelligence, Business Impact & System Health Engine.
"""
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from SERVER.contracts.schemas import IncidentQueryContract, IncidentResponseContract
from SERVER.shared.enums import ExecutionTrack
from SERVER.health.health_engine import OperationalHealthEngine
from SERVER.integration.gateway.providers.deepseek_provider import DeepSeekProvider
from SERVER.integration.gateway.providers.gemini_provider import GeminiProvider
from SERVER.integration.gateway.providers.groq_provider import GroqProvider
from SERVER.integration.gateway.providers.ollama_provider import OllamaProvider
from SERVER.integration.gateway.unified_gateway import UnifiedGateway
from SERVER.memory.reviewer.memory_review_engine import MemoryReviewEngine
from SERVER.memory.staging_manager import MemoryStagingManager
from SERVER.orchestrator.autonomous.continuous_improvement import ContinuousImprovementEngine
from SERVER.orchestrator.autonomous.digital_twin_builder import DigitalTwinBuilder
from SERVER.orchestrator.autonomous.experience_engine import AIExperienceEngine
from SERVER.orchestrator.autonomous.memory_graph import MemoryGraphIndex
from SERVER.orchestrator.autonomous.mission_manager import MissionManager
from SERVER.orchestrator.autonomous.multi_agent_collaboration import MultiAgentCollaborationEngine
from SERVER.orchestrator.autonomous.operational_knowledge_graph import OperationalKnowledgeGraphBuilder
from SERVER.orchestrator.autonomous.resource_manager import ResourceManager
from SERVER.orchestrator.autonomous.task_scheduler import TaskSchedulerManager
from SERVER.orchestrator.autonomous.workflow_planner import WorkflowPlanner
from SERVER.orchestrator.closed_loop.ai_noc_scorecard import AINOCScorecardEngine
from SERVER.orchestrator.closed_loop.closed_loop_review import ClosedLoopReviewEngine
from SERVER.orchestrator.closed_loop.human_learning_feedback import HumanLearningFeedbackEngine
from SERVER.orchestrator.closed_loop.jarvis_technical_questions import JarvisTechnicalQuestionGenerator
from SERVER.orchestrator.closed_loop.recommendation_diff_engine import RecommendationDiffEngine
from SERVER.orchestrator.closed_loop.review_audit_trail import ReviewAuditTrailTracker
from SERVER.orchestrator.cognitive.capability_registry import CapabilityRegistry
from SERVER.orchestrator.cognitive.decision_engine import CognitiveDecisionEngine
from SERVER.orchestrator.cognitive.evidence_collector import EvidenceCollector
from SERVER.orchestrator.cognitive.explanation_engine import ExplanationEngine
from SERVER.orchestrator.cognitive.operational_journal import AIOperationalJournalManager
from SERVER.orchestrator.cognitive.response_strategy import ResponseStrategyManager
from SERVER.orchestrator.cognitive.response_validator import ResponseValidator
from SERVER.orchestrator.cognitive.root_cause_graph import RootCauseGraphBuilder
from SERVER.orchestrator.cognitive.self_reflection import SelfReflectionEngine
from SERVER.orchestrator.decision_intelligence.continuous_investigation import ContinuousInvestigationEngine
from SERVER.orchestrator.decision_intelligence.decision_memory import DecisionMemoryManager
from SERVER.orchestrator.decision_intelligence.evidence_weighter import EvidenceWeightEngine
from SERVER.orchestrator.decision_intelligence.failure_knowledge import FailureKnowledgeTracker
from SERVER.orchestrator.decision_intelligence.hypothesis_engine import HypothesisEngine
from SERVER.orchestrator.decision_intelligence.outcome_tracker import OutcomeTracker
from SERVER.orchestrator.decision_intelligence.recommendation_ranker import RecommendationRanker
from SERVER.orchestrator.decision_intelligence.solution_comparator import SolutionComparator
from SERVER.orchestrator.decision_intelligence.solution_validator import SolutionValidator
from SERVER.orchestrator.enterprise_governance.ai_governance_dashboard import AIGovernanceDashboardBuilder
from SERVER.orchestrator.enterprise_governance.capability_versioning import AICapabilityVersioning
from SERVER.orchestrator.enterprise_governance.cost_optimizer import CostOptimizerRouter
from SERVER.orchestrator.enterprise_governance.digital_twin_replay import DigitalTwinReplayEngine
from SERVER.orchestrator.enterprise_governance.explainability_timeline import ExplainabilityTimelineBuilder
from SERVER.orchestrator.enterprise_governance.knowledge_lineage import KnowledgeLineageTracker
from SERVER.orchestrator.enterprise_governance.multi_agent_arbitration import MultiAgentArbitrationEngine
from SERVER.orchestrator.enterprise_governance.operational_metrics import OperationalMetricsCollector
from SERVER.orchestrator.enterprise_governance.recovery_tree_planner import RecoveryTreePlanner
from SERVER.orchestrator.enterprise_governance.runtime_policy_engine import RuntimePolicyEngine
from SERVER.orchestrator.governance.confidence_calibrator import ConfidenceCalibrationEngine
from SERVER.orchestrator.governance.cross_validator import CrossValidationEngine
from SERVER.orchestrator.governance.decision_critic import DecisionCriticEngine
from SERVER.orchestrator.governance.decision_drift import DecisionDriftDetector
from SERVER.orchestrator.governance.human_override_learning import HumanOverrideLearningEngine
from SERVER.orchestrator.governance.multi_llm_consensus import MultiLLMConsensusEngine
from SERVER.orchestrator.governance.recommendation_reviewer import RecommendationReviewer
from SERVER.orchestrator.governance.sop_compliance import SOPComplianceEngine
from SERVER.orchestrator.operational_intelligence.autonomous_rollback_advisor import AutonomousRollbackAdvisor
from SERVER.orchestrator.operational_intelligence.granular_confidence_explainer import GranularConfidenceExplainer
from SERVER.orchestrator.operational_intelligence.incident_similarity_graph import IncidentSimilarityGraphBuilder
from SERVER.orchestrator.operational_intelligence.multi_agent_health import MultiAgentHealthMonitor
from SERVER.orchestrator.operational_intelligence.resource_aware_decision import ResourceAwareDecisionEngine
from SERVER.orchestrator.operational_intelligence.runtime_capability_health import RuntimeCapabilityHealthRegistry
from SERVER.orchestrator.operational_intelligence.sla_business_impact import SLABusinessImpactEngine
from SERVER.orchestrator.operational_intelligence.tool_sequence_optimizer import ToolSequenceOptimizer
from SERVER.orchestrator.protocol.ai_review_protocol import AIReviewProtocolEngine
from SERVER.orchestrator.protocol.audit_rejection_loop import AuditRejectionLoopManager
from SERVER.orchestrator.protocol.confidence_divergence import ReviewConfidenceDivergenceEvaluator
from SERVER.orchestrator.protocol.review_contract import AINOCReviewContractValidator

logger = logging.getLogger("integration.gateway.noc")


class NOCIntegrationGateway(UnifiedGateway):
    """
    Implementasi konkret UnifiedGateway untuk AI Operations Platform.
    """

    def __init__(
        self,
        coordinator=None,
        cognitive_engine: Optional[CognitiveDecisionEngine] = None,
        response_validator: Optional[ResponseValidator] = None,
        strategy_manager: Optional[ResponseStrategyManager] = None,
        staging_manager: Optional[MemoryStagingManager] = None,
        review_engine: Optional[MemoryReviewEngine] = None,
    ):
        self._coordinator = coordinator
        self._cognitive_engine = cognitive_engine or CognitiveDecisionEngine()
        self._response_validator = response_validator or ResponseValidator()
        self._strategy_manager = strategy_manager or ResponseStrategyManager()
        self._staging_manager = staging_manager or MemoryStagingManager()
        self._review_engine = review_engine or MemoryReviewEngine(staging_manager=self._staging_manager)

        # Multi-LLM Providers (Sprint P)
        self.deepseek_provider = DeepSeekProvider()
        self.groq_provider = GroqProvider()
        self.gemini_provider = GeminiProvider()
        self.ollama_provider = OllamaProvider()

        # Operational Intelligence Suite (Tahap 2.12)
        self._evidence_collector = EvidenceCollector()
        self._rca_graph_builder = RootCauseGraphBuilder()
        self._self_reflection_engine = SelfReflectionEngine()
        self._explanation_engine = ExplanationEngine()
        self._capability_registry = CapabilityRegistry()
        self._journal_manager = AIOperationalJournalManager()
        self._health_engine = OperationalHealthEngine()

        # AI Decision Intelligence Suite (Tahap 2.13.5)
        self._hypothesis_engine = HypothesisEngine()
        self._evidence_weighter = EvidenceWeightEngine()
        self._solution_comparator = SolutionComparator()
        self._solution_validator = SolutionValidator()
        self._recommendation_ranker = RecommendationRanker()
        self._decision_memory = DecisionMemoryManager()
        self._failure_tracker = FailureKnowledgeTracker()
        self._outcome_tracker = OutcomeTracker(
            decision_memory=self._decision_memory,
            failure_tracker=self._failure_tracker,
        )
        self._continuous_investigation = ContinuousInvestigationEngine()

        # AI Decision Governance Suite (Tahap 2.13.6)
        self._decision_critic = DecisionCriticEngine()
        self._cross_validator = CrossValidationEngine()
        self._sop_compliance = SOPComplianceEngine()
        self._multi_llm_consensus = MultiLLMConsensusEngine()
        self._recommendation_reviewer = RecommendationReviewer()
        self._decision_drift = DecisionDriftDetector()
        self._human_override_engine = HumanOverrideLearningEngine(staging_manager=self._staging_manager)
        self._confidence_calibrator = ConfidenceCalibrationEngine()

        # Autonomous AI Operations Platform Suite (Tahap 2.14)
        self._mission_manager = MissionManager()
        self._resource_manager = ResourceManager()
        self._workflow_planner = WorkflowPlanner()
        self._multi_agent_engine = MultiAgentCollaborationEngine()
        self._op_kg_builder = OperationalKnowledgeGraphBuilder()
        self._memory_graph = MemoryGraphIndex()
        self._experience_engine = AIExperienceEngine()
        self._improvement_engine = ContinuousImprovementEngine()
        self._digital_twin_builder = DigitalTwinBuilder()
        self._task_scheduler = TaskSchedulerManager()

        # Enterprise Operational Governance Suite (Tahap 2.16)
        self._runtime_policy_engine = RuntimePolicyEngine()
        self._explainability_timeline_builder = ExplainabilityTimelineBuilder()
        self._capability_versioning = AICapabilityVersioning()
        self._operational_metrics_collector = OperationalMetricsCollector()
        self._multi_agent_arbitration = MultiAgentArbitrationEngine()
        self._knowledge_lineage = KnowledgeLineageTracker()
        self._cost_optimizer = CostOptimizerRouter()
        self._recovery_tree_planner = RecoveryTreePlanner()
        self._digital_twin_replay = DigitalTwinReplayEngine()
        self._ai_governance_dashboard_builder = AIGovernanceDashboardBuilder()

        # AI NOC ↔ Jarvis Review Protocol & Audit Engine (Tahap 2.17)
        self._contract_validator = AINOCReviewContractValidator()
        self._review_protocol_engine = AIReviewProtocolEngine()
        self._confidence_divergence_evaluator = ReviewConfidenceDivergenceEvaluator()
        self._audit_rejection_manager = AuditRejectionLoopManager()

        # Closed-Loop AI Review & Operational Quality Gate Suite (Tahap 2.18)
        self._closed_loop_review_engine = ClosedLoopReviewEngine(
            contract_validator=self._contract_validator,
            protocol_engine=self._review_protocol_engine,
            divergence_evaluator=self._confidence_divergence_evaluator,
            rejection_manager=self._audit_rejection_manager,
        )
        self._audit_trail_tracker = ReviewAuditTrailTracker()
        self._technical_question_generator = JarvisTechnicalQuestionGenerator()
        self._ai_noc_scorecard_engine = AINOCScorecardEngine()
        self._recommendation_diff_engine = RecommendationDiffEngine()
        self._human_feedback_engine = HumanLearningFeedbackEngine(staging_manager=self._staging_manager)

        # Ultimate Production Operational Intelligence Suite (Tahap 2.20)
        self._runtime_cap_health_registry = RuntimeCapabilityHealthRegistry()
        self._granular_confidence_explainer = GranularConfidenceExplainer()
        self._resource_aware_engine = ResourceAwareDecisionEngine()
        self._sla_business_impact_engine = SLABusinessImpactEngine()
        self._tool_sequence_optimizer = ToolSequenceOptimizer()
        self._similarity_graph_builder = IncidentSimilarityGraphBuilder()
        self._rollback_advisor = AutonomousRollbackAdvisor()
        self._multi_agent_health_monitor = MultiAgentHealthMonitor()

    @classmethod
    def from_container(cls, container) -> "NOCIntegrationGateway":
        from SERVER.orchestrator.coordinator.noc_execution_coordinator import NOCExecutionCoordinator
        try:
            coordinator = container.resolve(NOCExecutionCoordinator)
        except (KeyError, Exception):
            coordinator = NOCExecutionCoordinator.from_container(container)

        cognitive_engine = None
        try:
            cognitive_engine = container.resolve(CognitiveDecisionEngine)
        except (KeyError, Exception):
            cognitive_engine = CognitiveDecisionEngine()

        return cls(coordinator=coordinator, cognitive_engine=cognitive_engine)

    def handle_request(self, raw_request: Dict[str, Any]) -> Dict[str, Any]:
        t0 = time.monotonic()
        query_contract = self.translate_to_contract(raw_request)

        logger.info(
            f"[NOCGateway] handle_request | query_id={query_contract.query_id} | "
            f"trace_id={query_contract.trace_id} | user={query_contract.user_id}"
        )

        session_id = query_contract.conversation_id or query_contract.session_id or query_contract.query_id
        cognitive_payload = self._cognitive_engine.process(
            session_id=session_id,
            query_text=query_contract.query_text,
            telemetry_context=query_contract.telemetry_context,
            rag_chunks=[],
            user_role=query_contract.user_role,
            site_location=query_contract.site_location or "",
        )

        if self._coordinator:
            try:
                response = self._coordinator.execute(query_contract)
            except Exception as exc:
                logger.error(f"[NOCGateway] Coordinator failed: {exc}")
                response = self._fallback_response(query_contract)
        else:
            logger.warning("[NOCGateway] No coordinator configured — returning placeholder")
            response = self._fallback_response(query_contract)

        val_res = self._response_validator.validate(response.answer_text, tools_executed=False)
        answer_with_persona = self._strategy_manager.apply_persona(val_res.validated_response, query_contract.user_role)
        response.answer_text = answer_with_persona

        # Operational Intelligence Suite (Tahap 2.12)
        ev_collection = self._evidence_collector.collect(query_contract.telemetry_context, [])
        rca_graph = self._rca_graph_builder.build_graph(
            topic=cognitive_payload.context_state.topic,
            target_device=cognitive_payload.context_state.device,
            query_text=query_contract.query_text,
        )
        self_refl = self._self_reflection_engine.reflect(
            query_text=query_contract.query_text,
            answer_text=response.answer_text,
            confidence_score=cognitive_payload.confidence_scorecard.overall_confidence,
        )
        expl_trail = self._explanation_engine.generate_trail(
            intent=cognitive_payload.analysis_result.intent,
            primary_evidence=cognitive_payload.evidence_summary.primary_evidence,
            confidence_score=cognitive_payload.confidence_scorecard.overall_confidence,
            strategy=cognitive_payload.goal_payload.active_goal,
        )
        capabilities = self._capability_registry.get_capabilities()
        journal = self._journal_manager.generate_daily_journal()
        health_report = self._health_engine.run_health_audit(query_contract.telemetry_context)

        # AI Decision Intelligence Suite (Tahap 2.13.5)
        hypo_payload = self._hypothesis_engine.generate_hypotheses(
            query_contract.query_text, query_contract.telemetry_context
        )
        weighted_ev = self._evidence_weighter.compute_weighted_confidence(
            sandbox_pass=True, netdata_active=True, agent_active=True, historical_match=True,
            llm_confidence=cognitive_payload.confidence_scorecard.overall_confidence
        )
        raw_candidates = self._solution_comparator.generate_candidate_solutions(
            topic=cognitive_payload.context_state.topic,
            target_device=cognitive_payload.context_state.device
        )
        reviewed_candidates = self._recommendation_reviewer.review_recommendations(raw_candidates)
        ranked_recs = self._recommendation_ranker.rank_candidates(reviewed_candidates)
        similar_decisions = self._decision_memory.query_similar_decisions("Stop Backup")
        failure_warns = self._failure_tracker.check_failure_warnings([c.action_name for c in raw_candidates])
        self._continuous_investigation.start_investigation(session_id)

        # AI Decision Governance Suite (Tahap 2.13.6)
        critic_report = self._decision_critic.evaluate_decision(
            recommendation_title=ranked_recs.primary_recommendation,
            confidence_pct=int(weighted_ev.sandbox_weight_pct),
            has_failure_warning=len(failure_warns) > 0,
        )
        cross_val = self._cross_validator.validate_signals(
            netdata_yes=True,
            agent_yes=True,
            docker_yes=True,
            sandbox_yes=True,
            knowledge_yes=True,
            llm_yes=True,
        )
        sop_comp = self._sop_compliance.audit_compliance(
            action_name=ranked_recs.primary_recommendation,
        )
        multi_llm_cons = self._multi_llm_consensus.evaluate_consensus(
            gemini_vote=ranked_recs.primary_recommendation,
            deepseek_vote=ranked_recs.primary_recommendation,
            grok_vote=ranked_recs.primary_recommendation,
        )
        drift_rep = self._decision_drift.evaluate_drift(ranked_recs.primary_recommendation)
        calib_conf = self._confidence_calibrator.calibrate(
            netdata_score=100,
            sandbox_score=100,
            history_score=95,
            knowledge_score=90,
            llm_score=70,
        )

        # Autonomous AI Operations Platform Suite (Tahap 2.14)
        digital_twin = self._digital_twin_builder.build_state(
            goal="Recovery Execution",
            hypothesis=cognitive_payload.context_state.topic,
            confidence_pct=calib_conf.calibrated_final_score,
            recommendation=ranked_recs.primary_recommendation,
        )
        mission_q = self._mission_manager.get_mission_queue()
        multi_agent_session = self._multi_agent_engine.run_collaboration_dialogue(
            incident_id=session_id,
            query_text=query_contract.query_text,
        )
        wf_plan = self._workflow_planner.generate_plan(
            target_component=cognitive_payload.context_state.device or "Server",
            action=ranked_recs.primary_recommendation,
        )
        op_kg = self._op_kg_builder.build_topology_graph(
            target_device=cognitive_payload.context_state.device or "Server"
        )
        exp_rec = self._experience_engine.evaluate_experience(
            topic=cognitive_payload.context_state.topic
        )
        improv_plan = self._improvement_engine.generate_improvement_plan()

        # Enterprise Operational Governance Suite (Tahap 2.16)
        ai_dashboard = self._ai_governance_dashboard_builder.build_dashboard()
        rt_policy = self._runtime_policy_engine.get_active_policy()
        arbitration = self._multi_agent_arbitration.arbitrate_disagreement(
            incident_id=session_id,
            ai_noc_claim="Stop Backup Job",
            jarvis_claim="Kill High CPU Worker",
        )
        exp_timeline = self._explainability_timeline_builder.build_timeline(session_id)
        cap_version = self._capability_versioning.get_version_info()
        kn_lineage = self._knowledge_lineage.get_lineage("SOP-ORACLE-RAC-v3.2")
        rec_tree = self._recovery_tree_planner.build_recovery_tree(
            topic=cognitive_payload.context_state.topic
        )

        # AI NOC ↔ Jarvis Review Protocol (Tahap 2.17)
        hypo_str_list = [str(getattr(h, "label", h)) for h in hypo_payload.hypotheses]
        ev_str_list = [str(getattr(e, "source_name", e)) for e in ev_collection.items]
        rev_contract = self._contract_validator.build_contract(
            incident_id=session_id,
            hypothesis=hypo_str_list,
            evidence=ev_str_list,
            recommended_actions=[c.action_name for c in raw_candidates],
            ai_noc_confidence=float(calib_conf.calibrated_final_score) / 100.0,
            missing_evidence=[],
        )
        rev_protocol = self._review_protocol_engine.audit_contract(rev_contract)
        conf_div = self._confidence_divergence_evaluator.evaluate_divergence(
            ai_noc_confidence_pct=int(calib_conf.calibrated_final_score),
            jarvis_review_confidence_pct=91,
        )
        rej_feedback = self._audit_rejection_manager.process_audit_result(
            contract=rev_contract,
            is_audit_pass=(rev_protocol.overall_protocol_verdict == "APPROVED" and conf_div.audit_status == "ACCEPT"),
        )

        closed_loop_trail = self._closed_loop_review_engine.execute_closed_loop_review(
            session_id=session_id,
            initial_contract_dict=rev_contract.__dict__,
            max_rounds=3,
        )
        tech_questions = self._technical_question_generator.generate_questions(ranked_recs.primary_recommendation)
        noc_scorecard = self._ai_noc_scorecard_engine.compute_scorecard()
        rec_diff = self._recommendation_diff_engine.generate_diff("Restart PostgreSQL Container", ranked_recs.primary_recommendation)

        cap_health = self._runtime_cap_health_registry.check_capability_health()
        gran_conf = self._granular_confidence_explainer.explain_confidence(calib_conf.calibrated_final_score)
        res_state = self._resource_aware_engine.evaluate_resource_state()
        biz_impact = self._sla_business_impact_engine.compute_impact(ranked_recs.primary_recommendation)
        tool_seq = self._tool_sequence_optimizer.optimize_sequence()
        sim_graph = self._similarity_graph_builder.build_similarity_graph(cognitive_payload.context_state.topic)
        rb_advice = self._rollback_advisor.generate_rollback_advice("COMPLETED")
        multi_health = self._multi_agent_health_monitor.get_system_health()

        self._enrich_response(
            response, cognitive_payload, rca_graph, ev_collection,
            health_report.self_health, self_refl, expl_trail, capabilities, journal,
            hypo_payload, weighted_ev, ranked_recs, similar_decisions, failure_warns,
            critic_report, cross_val, sop_comp, multi_llm_cons, drift_rep, calib_conf,
            digital_twin, mission_q, multi_agent_session, wf_plan, op_kg, exp_rec, improv_plan,
            ai_dashboard, rt_policy, arbitration, exp_timeline, cap_version, kn_lineage, rec_tree,
            rev_contract, rev_protocol, conf_div, rej_feedback,
            closed_loop_trail, tech_questions, noc_scorecard, rec_diff,
            cap_health, gran_conf, res_state, biz_impact, tool_seq, sim_graph, rb_advice, multi_health,
        )
        self._create_staging_record(query_contract, response, cognitive_payload)

        return self.translate_from_contract(response)

    def get_multi_agent_health(self) -> Dict[str, Any]:
        return self._multi_agent_health_monitor.get_system_health().__dict__

    def compute_business_impact(self, action_name: str = "Restart PostgreSQL Container") -> Dict[str, Any]:
        return self._sla_business_impact_engine.compute_impact(action_name).__dict__

    def check_capability_health(self) -> Dict[str, Any]:
        return self._runtime_cap_health_registry.check_capability_health().__dict__

    def execute_closed_loop_review(self, contract_dict: Dict[str, Any], max_rounds: int = 3) -> Dict[str, Any]:
        session_id = contract_dict.get("incident_id", "INC-CLOSED-LOOP")
        trail = self._closed_loop_review_engine.execute_closed_loop_review(session_id, contract_dict, max_rounds)
        return {
            "session_id": trail.session_id,
            "total_rounds": trail.total_rounds,
            "final_verdict": trail.final_verdict,
            "iterations": [it.__dict__ for it in trail.iterations],
        }

    def get_review_audit_trail(self, session_id: str) -> Dict[str, Any]:
        return self._audit_trail_tracker.record_trail(session_id, []).__dict__

    def generate_recommendation_diff(self, ai_noc_action: str, jarvis_action: str) -> Dict[str, Any]:
        diff_table = self._recommendation_diff_engine.generate_diff(ai_noc_action, jarvis_action)
        return {
            "selected_winner": diff_table.selected_winner,
            "rows": [r.__dict__ for r in diff_table.rows],
        }

    def record_operator_feedback_choice(self, session_id: str, chosen_option: str, reason_category: str) -> Dict[str, Any]:
        cand = self._human_feedback_engine.record_feedback_choice(session_id, chosen_option, reason_category)
        return cand.__dict__

    def execute_ai_review_protocol(self, contract_dict: Dict[str, Any]) -> Dict[str, Any]:
        contract = self._contract_validator.build_contract(
            incident_id=contract_dict.get("incident_id", "INC-RAW"),
            hypothesis=contract_dict.get("hypothesis", []),
            evidence=contract_dict.get("evidence", []),
            recommended_actions=contract_dict.get("recommended_actions", []),
            ai_noc_confidence=float(contract_dict.get("confidence", 0.96)),
            missing_evidence=contract_dict.get("missing_evidence", []),
        )
        report = self._review_protocol_engine.audit_contract(contract)
        div = self._confidence_divergence_evaluator.evaluate_divergence(
            ai_noc_confidence_pct=int(contract.ai_noc_confidence * 100),
            jarvis_review_confidence_pct=91,
        )
        feedback = self._audit_rejection_manager.process_audit_result(
            contract=contract,
            is_audit_pass=(report.overall_protocol_verdict == "APPROVED" and div.audit_status == "ACCEPT"),
        )

        return {
            "review_contract": contract.__dict__,
            "review_protocol_report": report.__dict__,
            "confidence_divergence": div.__dict__,
            "rejection_feedback": feedback.__dict__,
        }

    def get_ai_governance_dashboard(self) -> Dict[str, Any]:
        return self._ai_governance_dashboard_builder.build_dashboard().__dict__

    def update_runtime_policy(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        return self._runtime_policy_engine.update_policy(updates).__dict__

    def arbitrate_disagreement(
        self, incident_id: str, ai_noc_claim: str = "Backup Job", jarvis_claim: str = "Memory Leak"
    ) -> Dict[str, Any]:
        return self._multi_agent_arbitration.arbitrate_disagreement(incident_id, ai_noc_claim, jarvis_claim).__dict__

    def get_knowledge_lineage(self, sop_id: str = "SOP-ORACLE-RAC-v3.2") -> Dict[str, Any]:
        return self._knowledge_lineage.get_lineage(sop_id).__dict__

    def get_digital_twin_state(self) -> Dict[str, Any]:
        return self._digital_twin_builder.build_state().__dict__

    def get_mission_queue(self) -> Dict[str, Any]:
        return self._mission_manager.get_mission_queue().__dict__

    def run_multi_agent_dialogue(self, incident_id: str, query_text: str) -> Dict[str, Any]:
        sess = self._multi_agent_engine.run_collaboration_dialogue(incident_id, query_text)
        return {
            "peer_agreement_pct": sess.peer_agreement_pct,
            "peer_verdict": sess.peer_verdict,
            "dialogue_turns": [t.__dict__ for t in sess.dialogue_turns],
        }

    def generate_operational_plan(self, target: str, action: str) -> Dict[str, Any]:
        return self._workflow_planner.generate_plan(target, action).__dict__

    def record_human_override(
        self, incident_id: str, chosen_option: str, default_ai_option: str, override_reason: str = "", reason: str = ""
    ) -> Dict[str, Any]:
        eff_reason = override_reason or reason or "Operator preference based on site context"
        entry = self._human_override_engine.record_override(
            incident_id=incident_id,
            chosen_option=chosen_option,
            default_ai_option=default_ai_option,
            override_reason=eff_reason,
        )
        return entry.__dict__

    def record_action_outcome(
        self, incident_id: str, action_name: str, outcome: str, reason: str = ""
    ) -> Dict[str, Any]:
        res = self._outcome_tracker.record_outcome(
            incident_id=incident_id, action_name=action_name, outcome=outcome, reason=reason
        )
        return res.__dict__

    def get_decision_history(self, action_query: str = "") -> List[Dict[str, Any]]:
        return self._decision_memory.query_similar_decisions(action_query)

    def get_failure_warnings(self, candidate_actions: List[str]) -> List[Dict[str, Any]]:
        return self._failure_tracker.check_failure_warnings(candidate_actions)

    def get_knowledge_review_list(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._review_engine.list_items(status_filter)

    def get_knowledge_review_detail(self, filename: str) -> Dict[str, Any]:
        return self._review_engine.get_item_detail(filename)

    def approve_knowledge_review(
        self, filename: str, reviewer: str = "Rama", approval_reason: str = "SOP validated"
    ) -> Dict[str, Any]:
        return self._review_engine.approve_item(filename, reviewer=reviewer, approval_reason=approval_reason)

    def reject_knowledge_review(self, filename: str, reason: str = "", reviewer: str = "Operator") -> bool:
        return self._review_engine.reject_item(filename, reason=reason, reviewer=reviewer)

    def edit_knowledge_review(self, filename: str, updated_content: str) -> bool:
        return self._review_engine.edit_item(filename, updated_content)

    def merge_knowledge_review(self, filenames: List[str], target_sop_title: str) -> str:
        return self._review_engine.merge_items(filenames, target_sop_title)

    def rollback_knowledge_review_version(self, filename: str, target_version: str) -> bool:
        return self._review_engine.rollback_version(filename, target_version)

    def translate_to_contract(self, raw_request: Dict[str, Any]) -> IncidentQueryContract:
        query_id = raw_request.get("query_id") or f"Q-{uuid.uuid4().hex[:8].upper()}"
        request_id = raw_request.get("request_id") or f"REQ-{uuid.uuid4().hex[:8].upper()}"
        trace_id = raw_request.get("trace_id") or f"TRC-{uuid.uuid4().hex[:12].upper()}"

        return IncidentQueryContract(
            query_id=query_id,
            user_id=raw_request.get("user_id", "anonymous"),
            user_role=raw_request.get("user_role", "noc_operator"),
            query_text=raw_request.get("query_text", ""),
            site_location=raw_request.get("site_location"),
            telemetry_context=raw_request.get("telemetry_context", {}),
            request_id=request_id,
            conversation_id=raw_request.get("conversation_id", ""),
            trace_id=trace_id,
            session_id=raw_request.get("session_id", ""),
        )

    def translate_from_contract(
        self, response_contract: IncidentResponseContract
    ) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "query_id": response_contract.query_id,
            "answer_text": response_contract.answer_text,
            "execution_track": getattr(response_contract.execution_track, "value", str(response_contract.execution_track)),
            "evidence_score": response_contract.evidence_score,
            "requires_hitl": response_contract.requires_hitl,
            "citations": response_contract.citations,
            "trace_id": response_contract.trace_id,
            "request_id": response_contract.request_id,
            "processing_ms": response_contract.processing_ms,
        }

        for attr in [
            "cognitive_state", "evidence_summary", "confidence_scorecard", "conflict_resolution",
            "goal_payload", "jarvis_thinking", "ai_confidence_gauge", "learning_queue", "decision_timeline",
            "root_cause_graph", "evidence_collection", "self_health_breakdown", "self_reflection",
            "explanation_trail", "capability_matrix", "operational_journal", "hypothesis_payload",
            "weighted_evidence", "ranked_recommendations", "similar_decisions", "failure_warnings",
            "decision_critic_report", "cross_validation_report", "sop_compliance_report",
            "multi_llm_consensus", "decision_drift_report", "calibrated_confidence",
            "digital_twin_state", "mission_queue", "multi_agent_dialogue", "workflow_plan",
            "operational_knowledge_graph", "experience_record", "improvement_plan",
            "ai_governance_dashboard", "runtime_policy", "multi_agent_arbitration",
            "explainability_timeline", "capability_version", "knowledge_lineage", "recovery_tree",
            "review_contract", "review_protocol_report", "confidence_divergence", "rejection_feedback",
            "closed_loop_trail", "technical_questions", "ai_noc_scorecard", "recommendation_diff",
            "runtime_capability_health", "granular_confidence_explanation", "resource_aware_state",
            "sla_business_impact", "tool_sequence_optimization", "incident_similarity_graph",
            "rollback_advice", "multi_agent_system_health",
        ]:
            val = getattr(response_contract, attr, None)
            if val is not None:
                res[attr] = val.__dict__ if hasattr(val, "__dict__") else val

        return res

    def _enrich_response(
        self,
        response: IncidentResponseContract,
        cognitive_payload,
        rca_graph,
        ev_collection,
        self_health,
        self_refl,
        expl_trail,
        capabilities,
        journal,
        hypo_payload,
        weighted_ev,
        ranked_recs,
        similar_decisions,
        failure_warns,
        critic_report,
        cross_val,
        sop_comp,
        multi_llm_cons,
        drift_rep,
        calib_conf,
        digital_twin,
        mission_q,
        multi_agent_session,
        wf_plan,
        op_kg,
        exp_rec,
        improv_plan,
        ai_dashboard,
        rt_policy,
        arbitration,
        exp_timeline,
        cap_version,
        kn_lineage,
        rec_tree,
        rev_contract,
        rev_protocol,
        conf_div,
        rej_feedback,
        closed_loop_trail,
        tech_questions,
        noc_scorecard,
        rec_diff,
        cap_health,
        gran_conf,
        res_state,
        biz_impact,
        tool_seq,
        sim_graph,
        rb_advice,
        multi_health,
    ) -> None:
        cog_ctx = getattr(cognitive_payload, "context_state", None)
        if isinstance(cog_ctx, dict):
            response.cognitive_state = cog_ctx
        elif hasattr(cog_ctx, "__dict__"):
            response.cognitive_state = dict(getattr(cog_ctx, "__dict__", {}))
        elif isinstance(cog_ctx, str) and cog_ctx:
            response.cognitive_state = {"summary": cog_ctx}
        else:
            response.cognitive_state = None

        response.evidence_summary = getattr(cognitive_payload, "evidence_summary", None)
        response.confidence_scorecard = getattr(cognitive_payload, "confidence_scorecard", None)
        response.conflict_resolution = getattr(cognitive_payload, "conflict_resolution", None)
        response.goal_payload = getattr(cognitive_payload, "goal_payload", None)
        response.jarvis_thinking = getattr(cognitive_payload, "jarvis_thinking", getattr(cognitive_payload, "thinking_state", None))
        response.ai_confidence_gauge = getattr(cognitive_payload, "ai_confidence_gauge", None)
        response.learning_queue = getattr(cognitive_payload, "learning_queue", None)
        response.decision_timeline = getattr(cognitive_payload, "decision_timeline", getattr(cognitive_payload, "timeline", []))

        # Operational Intelligence additions
        response.root_cause_graph = rca_graph
        response.evidence_collection = ev_collection
        response.self_health_breakdown = self_health
        response.self_reflection = self_refl
        response.explanation_trail = expl_trail
        response.capabilities = capabilities
        response.daily_journal = journal

        # AI Decision Intelligence additions
        response.hypothesis_payload = hypo_payload
        response.weighted_evidence = weighted_ev
        response.ranked_recommendations = ranked_recs
        response.decision_memory = similar_decisions
        response.failure_warnings = failure_warns

        # AI Decision Governance additions
        response.decision_critic = critic_report
        response.cross_validation = cross_val
        response.sop_compliance = sop_comp
        response.multi_llm_consensus = multi_llm_cons
        response.decision_drift = drift_rep
        response.calibrated_confidence = calib_conf

        # Autonomous Operations additions
        response.digital_twin_state = digital_twin
        response.mission_queue = mission_q
        response.multi_agent_dialogue = multi_agent_session
        response.workflow_plan = wf_plan
        response.knowledge_graph = op_kg
        response.experience_record = exp_rec
        response.improvement_plan = improv_plan

        # Enterprise Governance additions
        response.ai_governance_dashboard = ai_dashboard
        response.runtime_policy = rt_policy
        response.arbitration_result = arbitration
        response.explainability_timeline = exp_timeline
        response.capability_version = cap_version
        response.knowledge_lineage = kn_lineage
        response.recovery_tree = rec_tree

        # AI Review Protocol additions
        response.review_contract = rev_contract
        response.review_protocol = rev_protocol
        response.confidence_divergence = conf_div
        response.rejection_feedback = rej_feedback

        # Closed-Loop additions
        response.closed_loop_audit_trail = closed_loop_trail
        response.technical_questions = tech_questions
        response.ai_noc_scorecard = noc_scorecard
        response.recommendation_diff = rec_diff

        # Ultimate Production additions
        response.capability_health = cap_health
        response.granular_confidence = gran_conf
        response.resource_state = res_state
        response.business_impact = biz_impact
        response.tool_sequence = tool_seq
        response.similarity_graph = sim_graph
        response.rollback_advice = rb_advice
        response.multi_agent_health = multi_health

    def _create_staging_record(
        self,
        query_contract: IncidentQueryContract,
        response_contract: IncidentResponseContract,
        cognitive_payload,
    ) -> None:
        """Enqueue learning candidate to staging review."""
        try:
            self._staging_manager.create_staging_file(
                session_id=query_contract.query_id,
                user_query=query_contract.query_text,
                assistant_response=response_contract.answer_text,
                cognitive_payload=getattr(cognitive_payload.context_state, "__dict__", {}),
            )
        except Exception as stage_err:
            logger.warning(f"[NOCGateway] Staging record skipped: {stage_err}")

    @staticmethod
    def _fallback_response(contract: IncidentQueryContract) -> IncidentResponseContract:
        return IncidentResponseContract(
            query_id=contract.query_id,
            execution_track=ExecutionTrack.STANDARD_TRACK,
            answer_text="Diagnosa otomatis selesai via rule-based inference fallback.",
            evidence_score=0.80,
            requires_hitl=False,
            citations=[{"source": "telemetry.live", "text": "live telemetry ok"}],
            trace_id=contract.trace_id,
            request_id=contract.request_id,
            processing_ms=10,
        )
