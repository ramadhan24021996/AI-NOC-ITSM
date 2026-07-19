import asyncio
import json
import logging
import os
import psycopg2

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm_router import get_router
import nats

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("LEARNING_PLANE")

NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")
DB_NAME = os.environ.get("DB_NAME", "osi_system")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASS = os.environ.get("DB_PASSWORD", "SecurePassword_123!")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5433")

def get_db():
    return psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT)

class LearningPlane:
    """
    Tahap 8: Learning Plane
    Modul otonom kurikulum AI yang secara proaktif mengevaluasi kelemahan 
    diagnostik mandirinya dari post-mortems yang gagal atau HITL.
    """
    def __init__(self):
        self.router = get_router()
        self._init_db()

    def _init_db(self):
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ai_learning_curriculum (
                    id SERIAL PRIMARY KEY,
                    post_mortem_id VARCHAR(255),
                    incident_id VARCHAR(255),
                    identified_weakness TEXT,
                    new_diagnostic_rule TEXT,
                    status VARCHAR(50) DEFAULT 'LEARNED',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
        conn.commit()
        conn.close()

    async def run_reflection_cycle(self):
        logger.info("[LEARNING_PLANE] Starting autonomous post-mortem self-reflection cycle...")
        conn = get_db()
        try:
            with conn.cursor() as cur:
                # Find post-mortems where AI didn't solve it perfectly, or wasn't processed yet
                cur.execute("""
                    SELECT pm.post_mortem_id, pm.incident_id, pm.rca_summary, i.status
                    FROM incident_post_mortems pm
                    JOIN fleet_incidents i ON pm.incident_id = i.incident_id
                    WHERE pm.post_mortem_id::text NOT IN (SELECT post_mortem_id FROM ai_learning_curriculum)
                    LIMIT 5
                """)
                rows = cur.fetchall()
                
            for pm_id, inc_id, rca, status in rows:
                logger.info(f"[LEARNING_PLANE] Evaluating Post-Mortem: {pm_id} for Incident: {inc_id}")
                
                prompt = f"""
You are the AI Ops Learning Plane.
Analyze this Post-Mortem summary of a recent incident. Identify any diagnostic weakness the AI might have had, and define a new rule or learning point to avoid this weakness in the future.

Post-Mortem:
{rca}

Return ONLY valid JSON matching this schema:
{{
  "identified_weakness": "Explanation of what the AI missed or did wrong",
  "new_diagnostic_rule": "Actionable rule for the AI to follow next time"
}}
"""
                res = await self.router.execute_with_retry(85, prompt)
                if res.get("status") == "SUCCESS":
                    try:
                        cleaned = str(res.get("response", "")).strip()
                        if not cleaned:
                            logger.warning(f"[LEARNING_PLANE] Empty LLM response for post-mortem {pm_id}, skipping.")
                            continue
                        if cleaned.startswith("```"):
                            lines = cleaned.splitlines()
                            if lines[0].startswith("```"): lines = lines[1:]
                            if lines and lines[-1].startswith("```"): lines = lines[:-1]
                            cleaned = "\n".join(lines).strip()
                            
                        lesson = json.loads(cleaned)
                        weakness = lesson.get("identified_weakness", "")
                        rule = lesson.get("new_diagnostic_rule", "")
                        
                        with conn.cursor() as cur:
                            cur.execute("""
                                INSERT INTO ai_learning_curriculum (post_mortem_id, incident_id, identified_weakness, new_diagnostic_rule)
                                VALUES (%s, %s, %s, %s)
                            """, (pm_id, inc_id, weakness, rule))
                        conn.commit()
                        logger.info(f"[LEARNING_PLANE] Successfully learned from {inc_id}. Rule: {rule}")
                    except Exception as e:
                        conn.rollback()
                        logger.error(f"[LEARNING_PLANE] Failed to parse lesson: {e}")
                else:
                    logger.warning(f"[LEARNING_PLANE] LLM request failed for post-mortem {pm_id}, status={res.get('status')}. Skipping.")
        except Exception as e:
            logger.error(f"[LEARNING_PLANE] DB Error: {e}")
        finally:
            conn.close()

    async def run_revalidation_cycle(self):
        """
        Tahap Learning Plane v2: Knowledge Lifecycle Re-validation.
        Evaluates stale knowledge vectors and determines if they are still valid.
        """
        logger.info("[LEARNING_PLANE v2] Starting Knowledge Re-validation cycle...")
        conn = get_db()
        try:
            with conn.cursor() as cur:
                # Find stale golden vectors
                cur.execute("""
                    SELECT incident_id, title, root_cause, resolution, freshness_score
                    FROM knowledge_vectors
                    WHERE status = 'GOLDEN' AND freshness_score < 0.5
                    LIMIT 3
                """)
                rows = cur.fetchall()
                
            for vec_id, title, rc, res_text, freshness in rows:
                prompt = f"""
You are the AI Ops Learning Plane.
Re-validate the following stale IT knowledge. Is this resolution still considered modern best practice?
Title: {title}
Root Cause: {rc}
Resolution: {res_text}

Return ONLY valid JSON:
{{
  "is_still_valid": true,
  "updated_resolution": "If invalid, provide modern alternative here. Else keep original.",
  "confidence_boost": 0.5
}}
"""
                res = await self.router.execute_with_retry(85, prompt)
                if res.get("status") == "SUCCESS":
                    try:
                        cleaned = str(res.get("response", "")).strip()
                        if cleaned.startswith("```"):
                            lines = cleaned.splitlines()
                            if lines[0].startswith("```"): lines = lines[1:]
                            if lines and lines[-1].startswith("```"): lines = lines[:-1]
                            cleaned = "\n".join(lines).strip()
                            
                        validation = json.loads(cleaned)
                        is_valid = validation.get("is_still_valid", True)
                        updated_res = validation.get("updated_resolution", res_text)
                        
                        with conn.cursor() as cur:
                            if is_valid:
                                # Boost freshness
                                cur.execute("""
                                    UPDATE knowledge_vectors 
                                    SET freshness_score = 1.0, last_validated = NOW()
                                    WHERE incident_id = %s
                                """, (vec_id,))
                                logger.info(f"[LEARNING_PLANE v2] Re-validated '{title}' -> Confirmed Valid.")
                            else:
                                # Update to modern resolution
                                cur.execute("""
                                    UPDATE knowledge_vectors 
                                    SET resolution = %s, freshness_score = 1.0, last_validated = NOW()
                                    WHERE incident_id = %s
                                """, (updated_res, vec_id))
                                logger.info(f"[LEARNING_PLANE v2] Re-validated '{title}' -> Updated Resolution.")
                        conn.commit()
                    except Exception as e:
                        conn.rollback()
                        logger.error(f"[LEARNING_PLANE v2] Failed to parse re-validation: {e}")
        except Exception as e:
            logger.error(f"[LEARNING_PLANE v2] Re-validation DB Error: {e}")
        finally:
            conn.close()

async def daemon(interval_hours: int = 12):
    logger.info("[LEARNING_PLANE] Daemon started.")
    plane = LearningPlane()
    while True:
        await plane.run_reflection_cycle()
        await plane.run_revalidation_cycle()
        await asyncio.sleep(interval_hours * 3600)

if __name__ == '__main__':
    asyncio.run(daemon(interval_hours=2))
