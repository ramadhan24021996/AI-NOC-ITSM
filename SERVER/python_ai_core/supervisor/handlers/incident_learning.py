"""
supervisor/handlers/incident_learning.py
-----------------------------------------
RLOF Reinforcement Learning Feedback Loop, Reward Scoring, and Knowledge Base Ingestion.
"""
import asyncio
import json
import logging
import os
import sys
import time

try:
    from schemas import LearningSchema
    from supervisor.pipeline_logger import log_ai_pipeline
except ImportError:
    from SERVER.python_ai_core.schemas import LearningSchema
    from SERVER.python_ai_core.supervisor.pipeline_logger import log_ai_pipeline

logger = logging.getLogger("AI_SUPERVISOR.incident_learning")


async def learning_handler(msg):
    try:
        from engines.rag_engine import get_rag_engine
        from engines.llm_router import get_router
    except ImportError:
        from SERVER.python_ai_core.engines.rag_engine import get_rag_engine
        from SERVER.python_ai_core.engines.llm_router import get_router
    rag = None
    try:
        data = json.loads(msg.data.decode())
        
        # Initialize DB and RAG connection early to load policies
        rag = get_rag_engine()
        rag.connect()
        
        # Default learning gate policy fallback
        confidence_threshold = 0.75
        require_human_confirmation = True
        require_success_verification = True
        try:
            if rag.conn is not None:
                with rag.conn.cursor() as cur:
                    cur.execute("SELECT confidence_threshold, require_human_confirmation, require_success_verification FROM learning_gate_policy LIMIT 1")
                    row = cur.fetchone()
                    if row:
                        confidence_threshold = float(row[0])
                        require_human_confirmation = bool(row[1])
                        require_success_verification = bool(row[2])
        except Exception as policy_err:
            logger.warning(f"Failed to fetch learning gate policy, using default (0.75): {policy_err}")
            try:
                if rag.conn is not None:
                    rag.conn.rollback()
            except:
                import logging; logging.getLogger(__name__).debug('_ = None suppressed')

        # Verified Learning Gate condition evaluation
        verification_status = str(data.get("verification_status", "FAILED")).upper()
        human_confirmed = bool(data.get("human_confirmed", False))
        rollback_needed = bool(data.get("rollback_needed", False))
        confidence = float(data.get("confidence", 0.0))
        
        # Map confidence to 0-1 if it is 0-100 format
        confidence_normalized = confidence / 100.0 if confidence > 1.0 else confidence
        
        # Core learning validation gate using DB thresholds
        learning_allowed = True
        if require_success_verification and verification_status != "SUCCESS":
            learning_allowed = False
        if require_human_confirmation and not human_confirmed:
            learning_allowed = False
        if rollback_needed:
            learning_allowed = False
        if confidence_normalized < confidence_threshold:
            learning_allowed = False
        
        # Strict validation using LearningSchema
        validated_learning = LearningSchema(
            incident_id=str(data.get("incident_id", "")),
            root_cause=str(data.get("human_root_cause", "") or data.get("ai_root_cause", "") or data.get("root_cause", "")),
            successful_action=str(data.get("resolution", "") or data.get("successful_action", "")),
            verification_status=verification_status,
            human_confirmed=human_confirmed,
            confidence=confidence,
            learning_allowed=learning_allowed,
            title=str(data.get("title", "") or "New Resolution"),
            symptoms=str(data.get("symptoms", "")),
            vector_embedding=None
        )
        
        logger.info(f"[LEARNING LOOP] Received learning message for Incident ID: {validated_learning.incident_id}")
        
        # Audit Trail Preservation (Save attempt details to ai_audit_trail)
        if rag.conn:
            try:
                with rag.conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO ai_audit_trail (incident_id, event_id, reasoning_dag, rag_vectors_retrieved, raw_prompt, llm_response, confidence_score, action_executed, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    """, (
                        validated_learning.incident_id,
                        "LEARNING_GATE",
                        json.dumps({
                            "verification_status": verification_status,
                            "human_confirmed": human_confirmed,
                            "rollback_needed": rollback_needed,
                            "confidence_normalized": confidence_normalized,
                            "confidence_threshold": confidence_threshold
                        }),
                        json.dumps({"learning_allowed": learning_allowed}),
                        "RAG dynamic learning ingestion attempt",
                        f"Action: {validated_learning.successful_action} | RCA: {validated_learning.root_cause}",
                        confidence,
                        "LEARNING_ACCEPTED" if learning_allowed else "LEARNING_BLOCKED"
                    ))
                    rag.conn.commit()
                    logger.info(f"[LEARNING GATE] Ingestion audit trail logged to DB.")
            except Exception as audit_err:
                logger.error(f"[LEARNING GATE] Failed to log audit trail: {audit_err}")
        
        # Enforce gate blocking conditions
        if not validated_learning.learning_allowed:
            logger.warning(
                f"[LEARNING BLOCKED] Learning Gate rejected Incident ID: {validated_learning.incident_id}. "
                f"Reason: verification_status={verification_status}, human_confirmed={human_confirmed}, "
                f"rollback_needed={rollback_needed}, confidence={confidence} (threshold={confidence_threshold})"
            )
            await msg.ack()
            return
        
        router = get_router()
        text_to_embed = f"Title: {validated_learning.title} Symptoms: {validated_learning.symptoms} Description: {validated_learning.root_cause} {validated_learning.successful_action}"
        embedding = router.embed_text_768(text_to_embed)

        if not embedding or sum(map(abs, embedding)) == 0.0:
            embedding = rag._local_embedding_fallback(text_to_embed)
            logger.info(f"[LEARNING LOOP] Generated 768-dim local fallback embedding for incident {validated_learning.incident_id}.")

        vector_str = "[" + ",".join(map(str, embedding)) + "]"
        
        if rag.conn is not None:
            with rag.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO knowledge_vectors (incident_id, title, symptoms, root_cause, resolution, embedding, confidence, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (incident_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        symptoms = EXCLUDED.symptoms,
                        root_cause = EXCLUDED.root_cause,
                        resolution = EXCLUDED.resolution,
                        embedding = EXCLUDED.embedding,
                        confidence = EXCLUDED.confidence
                """, (f"KB-LEARN-{validated_learning.incident_id}", validated_learning.title, validated_learning.symptoms, validated_learning.root_cause, validated_learning.successful_action, vector_str, validated_learning.confidence))
                rag.conn.commit()
        
        # Invalidate RAG search cache so new knowledge is immediately searchable
        try:
            from core.cache_manager import get_cache_manager
            cache_mgr = get_cache_manager()
            cleared = cache_mgr.clear_rag_cache()
            logger.info(f"[LEARNING LOOP] Cleared {cleared} cached RAG entries after ingesting {validated_learning.incident_id}.")
        except Exception as cache_err:
            logger.warning(f"[LEARNING LOOP] Failed to clear RAG cache: {cache_err}")

        logger.info(f"[LEARNING LOOP] Successfully vectorized and saved incident {validated_learning.incident_id} to knowledge_vectors.")
    except Exception as e:
        logger.error(f"[LEARNING LOOP] Error processing learning feedback: {e}")
    finally:
        if rag and rag.conn:
            try:
                rag.close()
                logger.info("[LEARNING LOOP] Closed DB connection.")
            except:
                import logging; logging.getLogger(__name__).debug('_ = None suppressed')
