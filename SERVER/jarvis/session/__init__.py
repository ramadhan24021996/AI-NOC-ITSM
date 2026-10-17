"""
SERVER.jarvis.session — JARVIS Multi-Turn Session Management Domain
=====================================================================
Contains session state, reference bindings, memory compaction engine,
cross-context memory graph, remediation learning, and V3.6 hardened causal evidence engine.
"""
from SERVER.jarvis.session.multi_turn_session_memory import (
    MultiTurnSessionMemoryManagerV31,
    AnaphoraResolverV31,
    SessionContextWindowV31,
    TurnRecordV31,
    ReferenceBinding,
    ContextInvalidationType,
    MemorySnapshotV32,
    CompressedFactV32,
    MemoryDecisionEntry,
    PendingCommitmentEntry,
    IncidentSignatureV34,
    OutcomeEffectivenessV34,
    WeightedSimilarityBreakdownV35,
    RemediationLearningEvidenceV35,
    RemediationRecommendationRecordV35,
    RemediationEffectivenessLearnerV35,
    EvidenceSufficiencyV36,
    CausalEvidenceScoreV36,
    CausalEvidenceCounterfactualEngineV36,
    ArchivedIncidentEntryV34,
    HistoricalOutcomeEngineV34,
    ArchivedIncidentMemoryStoreV34,
    ConversationMemoryCompactorV32,
    CrossContextOperationalMemoryGraph,
    get_multi_turn_memory_manager_v31
)

__all__ = [
    "MultiTurnSessionMemoryManagerV31",
    "AnaphoraResolverV31",
    "SessionContextWindowV31",
    "TurnRecordV31",
    "ReferenceBinding",
    "ContextInvalidationType",
    "MemorySnapshotV32",
    "CompressedFactV32",
    "MemoryDecisionEntry",
    "PendingCommitmentEntry",
    "IncidentSignatureV34",
    "OutcomeEffectivenessV34",
    "WeightedSimilarityBreakdownV35",
    "RemediationLearningEvidenceV35",
    "RemediationRecommendationRecordV35",
    "RemediationEffectivenessLearnerV35",
    "EvidenceSufficiencyV36",
    "CausalEvidenceScoreV36",
    "CausalEvidenceCounterfactualEngineV36",
    "ArchivedIncidentEntryV34",
    "HistoricalOutcomeEngineV34",
    "ArchivedIncidentMemoryStoreV34",
    "ConversationMemoryCompactorV32",
    "CrossContextOperationalMemoryGraph",
    "get_multi_turn_memory_manager_v31"
]
