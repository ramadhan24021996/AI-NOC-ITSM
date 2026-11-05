import logging
from typing import Any, Dict, List, Optional
from .short_term_memory import ShortTermMemoryManager
from .long_term_memory import LongTermMemoryManager
from .knowledge_memory import KnowledgeMemoryManager
from .experience_memory import ExperienceMemoryManager
from .policy_memory import PolicyMemoryManager
from .tools_memory import ToolsMemoryManager
from .command_gateway import CapabilityCommandGateway
from .knowledge_validation_engine import KnowledgeValidationEngine
from .memory_governance import MemoryGovernanceManager
from .knowledge_lifecycle import KnowledgeLifecycleManager
from .command_handler import TeachingCommandHandler

logger = logging.getLogger("UNIFIED_MEMORY_MANAGER")

class UnifiedMemoryManager:
    """
    Unified Memory Manager (Facade Pattern) for Jarvis AI 5-Layer Enterprise Memory System.
    Flow Architecture:
      Jarvis -> UnifiedMemoryManager -> Memory Governance & Knowledge Validation Engine & Knowledge Lifecycle Manager -> Knowledge Memory / PostgreSQL / pgvector

    Components:
      1. Short-Term Memory (Redis / RAM Session Context)
      2. Long-Term Memory (PostgreSQL Structured Records)
      3. Knowledge Memory (PostgreSQL pgvector + Hybrid Search BM25)
      4. Experience Memory (Closed-Loop Learning Engine)
      5. Policy Memory (Permanent Governance & OPA Rules)
      6. Tools Memory (AI NOC Tools Registry & Execution History)
      7. Capability Command Gateway (Whitelist, RBAC, Policy & HITL Enforcement, Audit Trail)
      8. Knowledge Validation Engine (Pre-ingestion Schema, Policy Conflict Check & Metadata Completeness)
      9. Memory Governance Manager (Access Control, Deduplication, Quality & Activation Control)
      10. Knowledge Lifecycle Manager (Post-ingestion Deprecation, Merging, Confidence Calibration & Version Archiving)
      11. Teaching Command Handler ("Jarvis, simpan pengetahuan berikut")
    """

    def __init__(self):
        self.short_term = ShortTermMemoryManager()
        self.long_term = LongTermMemoryManager()
        self.knowledge = KnowledgeMemoryManager()
        self.experience = ExperienceMemoryManager(knowledge_mgr=self.knowledge)
        self.policy = PolicyMemoryManager()
        self.tools = ToolsMemoryManager()
        self.gateway = CapabilityCommandGateway(tools_mgr=self.tools, policy_mgr=self.policy)
        self.validation_engine = KnowledgeValidationEngine(policy_mgr=self.policy, knowledge_mgr=self.knowledge)
        self.governance = MemoryGovernanceManager(validation_engine=self.validation_engine, knowledge_mgr=self.knowledge)
        self.lifecycle = KnowledgeLifecycleManager(knowledge_mgr=self.knowledge)
        self.teaching = TeachingCommandHandler(knowledge_mgr=self.knowledge)
        logger.info("[UNIFIED_MEMORY_MANAGER] All 11 Memory, Governance, Validation, Lifecycle & Gateway components initialized successfully.")

    def search_knowledge(self, query: str, category: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Performs hybrid vector + BM25 search across Knowledge Memory."""
        return self.knowledge.hybrid_search(query_text=query, category_filter=category, limit=limit)

    def evaluate_policy(self, command_str: str, risk_level: str) -> Dict[str, Any]:
        """Evaluates command against Policy Memory rules."""
        return self.policy.evaluate_command_against_policies(command_str, risk_level)

    def learn_from_completed_incident(
        self,
        incident_id: int,
        device_name: str,
        rca_id: str,
        root_cause: str,
        recovery_action: str,
        verification_status: str = "SUCCESS"
    ) -> Dict[str, Any]:
        """Triggers closed-loop Experience Memory learning."""
        return self.experience.process_incident_learning(
            incident_id=incident_id,
            device_name=device_name,
            rca_id=rca_id,
            root_cause=root_cause,
            recovery_action=recovery_action,
            verification_status=verification_status
        )

    def process_teaching_command(self, raw_text: str, operator_name: str = "OPERATOR") -> Dict[str, Any]:
        """Executes 'Jarvis, simpan pengetahuan berikut' teaching pipeline."""
        return self.teaching.process_teaching_command(raw_text, operator_name=operator_name)


_MEMORY_SINGLETON: Optional[UnifiedMemoryManager] = None

def get_unified_memory_manager() -> UnifiedMemoryManager:
    global _MEMORY_SINGLETON
    if _MEMORY_SINGLETON is None:
        _MEMORY_SINGLETON = UnifiedMemoryManager()
    return _MEMORY_SINGLETON
