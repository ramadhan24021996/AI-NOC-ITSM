"""
SERVER.compatibility - Legacy Models Adapter Bridge
Provides mapping between legacy python_ai_core dictionaries/tuples and new SERVER.shared DTOs.
"""
from typing import Dict, Any
from SERVER.shared.models import KnowledgeChunkDTO, EvidenceScoreDTO
from SERVER.shared.adapters import legacy_chunk_dict_to_dto, compute_composite_evidence_score

class LegacyModelAdapter:
    """Temporary compatibility bridge for converting legacy data structures."""

    @staticmethod
    def dict_to_chunk_dto(raw_dict: Dict[str, Any]) -> KnowledgeChunkDTO:
        return legacy_chunk_dict_to_dto(raw_dict)

    @staticmethod
    def chunk_dto_to_dict(dto: KnowledgeChunkDTO) -> Dict[str, Any]:
        return {
            "chunk_id": dto.chunk_id,
            "title": dto.title,
            "content": dto.content,
            "source_url": dto.source_url,
            "trust_rating": dto.trust_rating.value,
            "similarity_score": dto.similarity_score,
            "coverage_score": dto.coverage_score,
            "metadata": dto.metadata,
        }
