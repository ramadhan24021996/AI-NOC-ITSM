"""
Domain DTO Adapters for Backward Compatibility
Converts legacy python_ai_core dictionaries/tuples into clean SERVER.shared DTOs.
"""
from typing import Dict, Any, List
from SERVER.shared.enums import TrustRating
from SERVER.shared.models import KnowledgeChunkDTO, EvidenceScoreDTO

def _safe_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

def legacy_chunk_dict_to_dto(raw_dict: Dict[str, Any]) -> KnowledgeChunkDTO:
    """Converts legacy dict from rag_engine into KnowledgeChunkDTO."""
    rating_str = raw_dict.get("trust_rating", "unknown")
    try:
        rating = TrustRating(rating_str)
    except ValueError:
        rating = TrustRating.UNKNOWN

    raw_sim = raw_dict.get("similarity_score") if raw_dict.get("similarity_score") is not None else raw_dict.get("score")
    raw_cov = raw_dict.get("coverage_score")

    return KnowledgeChunkDTO(
        chunk_id=str(raw_dict.get("chunk_id", raw_dict.get("id", ""))),
        title=str(raw_dict.get("title", raw_dict.get("site", "Legacy Document"))),
        content=str(raw_dict.get("content", raw_dict.get("text", raw_dict.get("prompt", "")))),
        source_url=str(raw_dict.get("source_url", raw_dict.get("source", ""))),
        trust_rating=rating,
        similarity_score=_safe_float(raw_sim, 0.0),
        coverage_score=_safe_float(raw_cov, 0.0),
        metadata=raw_dict.get("metadata", {}) or {}
    )

def compute_composite_evidence_score(
    similarity: float,
    coverage: float,
    freshness: float = 1.0,
    source_trust: float = 1.0,
    consensus: float = 1.0
) -> EvidenceScoreDTO:
    """Computes composite evidence score using multi-metric weighted formula."""
    w1, w2, w3, w4, w5 = 0.35, 0.25, 0.15, 0.15, 0.10
    composite = (w1 * similarity) + (w2 * coverage) + (w3 * freshness) + (w4 * source_trust) + (w5 * consensus)
    return EvidenceScoreDTO(
        similarity=similarity,
        coverage=coverage,
        freshness=freshness,
        source_trust=source_trust,
        consensus=consensus,
        composite_score=round(composite, 4)
    )
