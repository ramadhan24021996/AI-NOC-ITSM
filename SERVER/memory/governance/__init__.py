"""
SERVER.memory.governance package
================================
Enterprise Knowledge Governance Platform components:
  - KnowledgeVersionManager
  - KnowledgeQualityChecker
  - KnowledgeDuplicateDetector
  - KnowledgeLinker
  - KnowledgeFreshnessManager
"""
from SERVER.memory.governance.version_manager import KnowledgeVersionManager
from SERVER.memory.governance.quality_checker import KnowledgeQualityChecker, QualityScorecard
from SERVER.memory.governance.duplicate_detector import KnowledgeDuplicateDetector, DuplicateCheckResult
from SERVER.memory.governance.knowledge_linker import KnowledgeLinker
from SERVER.memory.governance.freshness_manager import KnowledgeFreshnessManager, FreshnessStatus

__all__ = [
    "KnowledgeVersionManager",
    "KnowledgeQualityChecker",
    "QualityScorecard",
    "KnowledgeDuplicateDetector",
    "DuplicateCheckResult",
    "KnowledgeLinker",
    "KnowledgeFreshnessManager",
    "FreshnessStatus",
]
