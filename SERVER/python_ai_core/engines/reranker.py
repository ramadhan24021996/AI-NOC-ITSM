"""
Enterprise AI OS — RAG 2.0 Cross-Encoder Reranker
Module for precision reranking of hybrid search (Vector + BM25) candidate documents.

Uses a Cross-Encoder transformer model if sentence_transformers is available,
or a multi-feature semantic overlap scoring algorithm as fallback.
"""

import logging
import math
import re
from typing import Dict, List, Optional

logger = logging.getLogger("CROSS_ENCODER_RERANKER")

try:
    from sentence_transformers import CrossEncoder  # type: ignore # pyright: ignore[reportMissingImports]
    _CROSS_ENCODER_AVAILABLE = True
except ImportError:
    _CROSS_ENCODER_AVAILABLE = False


class CrossEncoderReranker:
    """
    Cross-Encoder Reranker for RAG 2.0 pipeline.
    Re-scores and re-ranks top candidates returned by Reciprocal Rank Fusion (RRF).
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self.model = None
        if _CROSS_ENCODER_AVAILABLE:
            try:
                self.model = CrossEncoder(self.model_name)
                logger.info("[RERANKER] Successfully initialized CrossEncoder model: %s", self.model_name)
            except Exception as e:
                logger.warning("[RERANKER] Failed to load CrossEncoder model '%s': %s. Using heuristic reranker fallback.", self.model_name, e)
                self.model = None

    def rerank(self, query: str, candidates: List[Dict], top_k: int = 3) -> List[Dict]:
        """
        Reranks a list of candidate documents based on cross-encoder similarity with the query.

        Args:
            query: The search query / incident description / error message.
            candidates: List of candidate dicts from RAG query (must contain title/symptoms/resolution/root_cause).
            top_k: Number of top candidates to return.

        Returns:
            List of top_k reranked candidate dicts with added 'rerank_score'.
        """
        if not candidates:
            return []

        cleaned_query = query.strip()
        if not cleaned_query:
            return candidates[:top_k]

        # Prune candidates to top 10 for two-stage optimization (< 120ms max reranking latency)
        if len(candidates) > 10:
            candidates = candidates[:10]

        # 1. Primary path: Sentence-Transformers CrossEncoder
        if self.model is not None:
            try:
                pairs = []
                for c in candidates:
                    text = f"{c.get('title', '')} {c.get('symptoms', '')} {c.get('root_cause', '')} {c.get('resolution', '')}"
                    pairs.append([cleaned_query, text[:512]])

                scores = self.model.predict(pairs)
                for idx, c in enumerate(candidates):
                    c["rerank_score"] = float(scores[idx])

                candidates.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
                logger.info("[RERANKER] Applied CrossEncoder model reranking for %d candidates.", len(candidates))
                return candidates[:top_k]
            except Exception as e:
                logger.warning("[RERANKER] Model inference failed: %s. Falling back to heuristic reranking.", e)

        # 2. Fallback path: Precision heuristic cross-scoring
        reranked = []
        query_tokens = set(re.findall(r'\w+', cleaned_query.lower()))
        error_codes = set(re.findall(r'\b(?:ERR[-_]?\d+|[A-Z0-9_]{3,}_ERR|OOMKilled|404|500|502|503)\b', cleaned_query, re.IGNORECASE))

        for c in candidates:
            title = c.get("title", "")
            symptoms = c.get("symptoms", "")
            root_cause = c.get("root_cause", "")
            resolution = c.get("resolution", "")
            doc_text = f"{title} {symptoms} {root_cause} {resolution}".lower()

            doc_tokens = set(re.findall(r'\w+', doc_text))
            intersection = query_tokens.intersection(doc_tokens)
            
            # Base overlap score (Jaccard similarity)
            jaccard = len(intersection) / float(len(query_tokens.union(doc_tokens)) or 1)
            
            # Keyword error code match boost
            error_boost = 0.0
            for code in error_codes:
                if code.lower() in doc_text:
                    error_boost += 0.35

            # Original score preservation (from RRF or similarity)
            raw_orig = c.get("rrf_score")
            if raw_orig is None:
                raw_orig = c.get("similarity_score")
            if raw_orig is None:
                raw_orig = c.get("similarity")
            original_score = float(raw_orig) if raw_orig is not None else 0.5

            rerank_score = (original_score * 0.40) + (jaccard * 0.35) + min(0.35, error_boost)
            c_copy = dict(c)
            c_copy["rerank_score"] = round(rerank_score, 4)
            reranked.append(c_copy)

        reranked.sort(key=lambda x: x["rerank_score"], reverse=True)
        
        # Attach Platt Scaling Calibration & Softmax Temperature Calibration
        try:
            from probabilistic.probabilistic_engine import ProbabilityCalibrator
            calibrator = ProbabilityCalibrator()
            raw_scores = [float(x.get("rerank_score", 0.5)) for x in reranked[:top_k]]
            softmax_probs = calibrator.temperature_scale_softmax(raw_scores, temperature=1.2)
            
            for idx, item in enumerate(reranked[:top_k]):
                score = float(item.get("rerank_score", 0.5))
                prob = calibrator.calibrate_cosine_similarity(score)
                item["calibrated_probability"] = prob
                item["calibrated_probability_percent"] = f"{round(prob * 100, 2)}%"
                item["softmax_probability"] = softmax_probs[idx] if idx < len(softmax_probs) else prob
        except Exception as e:
            logger.warning("[RERANKER] Failed to apply probability calibration: %s", e)

        logger.info("[RERANKER] Applied heuristic cross-scoring reranking for %d candidates.", len(reranked))
        return reranked[:top_k]


_default_reranker = None


def get_reranker() -> CrossEncoderReranker:
    global _default_reranker
    if _default_reranker is None:
        _default_reranker = CrossEncoderReranker()
    return _default_reranker
