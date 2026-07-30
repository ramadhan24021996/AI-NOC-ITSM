import logging
import json
import datetime

from engines.blast_radius_engine import BlastRadiusEngine
from engines.policy_engine import get_policy_engine

logger = logging.getLogger("AI_SAFETY_LAYER")

class RiskAnalyzer:
    """
    Determines the risk of an action deterministically without an LLM.
    Uses keyword matching and action taxonomy.
    """
    async def analyze(self, action: str, target: str, context: dict = None) -> dict:
        """
        Tahap AI Safety v2: Multi-Factor Risk Scoring
        Menggunakan kombinasi penilaian LLM, Blast Radius, dan Konteks Waktu untuk menghasilkan
        Skor Risiko (0.0 - 1.0).
        """
        if not action:
            return {"risk_level": "LOW", "risk_score": 0.1, "factors": {}}
            
        import json
        from engines.llm_router import get_router
        
        # Factor 1: LLM Destructiveness Assessment
        router = get_router()
        prompt = f"""
        You are an AI Safety Core. Assess the destructiveness of this action on this target.
        Action: {action}
        Target: {target}
        
        Return ONLY valid JSON:
        {{
            "destructiveness_score": 0.9, 
            "reason": "explanation"
        }}
        """
        
        destructiveness_score = 0.5
        try:
            res = await router.execute_with_retry(85, prompt)
            if res and isinstance(res, dict) and res.get("status") == "SUCCESS":
                cleaned = str(res.get("response", "")).strip()
                if cleaned.startswith("```"):
                    lines = cleaned.splitlines()
                    if lines[0].startswith("```"): lines = lines[1:]
                    if lines and lines[-1].startswith("```"): lines = lines[:-1]
                    cleaned = "\n".join(lines).strip()
                data = json.loads(cleaned)
                destructiveness_score = float(data.get("destructiveness_score", 0.5))
        except Exception as e:
            logger.warning(f"[SAFETY v2] LLM Destructiveness evaluation failed: {e}")
            
        # Factor 2: Blast Radius (from context)
        blast_score = 0.0
        if context and "blast_score" in context:
            blast_score = float(context["blast_score"])
            
        # Factor 3: Time-of-Day Penalty (e.g., Friday night deployments are riskier)
        time_penalty = 0.0
        now = datetime.datetime.now()
        if now.weekday() == 4 and now.hour > 17: # Friday evening
            time_penalty = 0.3
        elif now.weekday() >= 5: # Weekend
            time_penalty = 0.2
            
        # Factor 4: Site Criticality (from context)
        crit_multiplier = 1.0
        site_crit = context.get("site_criticality", "MEDIUM") if context else "MEDIUM"
        if site_crit == "HIGH": crit_multiplier = 1.5
        elif site_crit == "CRITICAL": crit_multiplier = 2.0
        elif site_crit == "LOW": crit_multiplier = 0.8
        
        # Calculate Final Risk Score
        raw_score = (destructiveness_score * 0.5) + (blast_score * 0.3) + time_penalty
        final_risk_score = min(1.0, max(0.0, raw_score * crit_multiplier))
        
        risk_level = "LOW"
        if final_risk_score >= 0.75:
            risk_level = "HIGH"
        elif final_risk_score >= 0.4:
            risk_level = "MEDIUM"
            
        return {
            "risk_level": risk_level,
            "risk_score": final_risk_score,
            "factors": {
                "destructiveness": destructiveness_score,
                "blast_score": blast_score,
                "time_penalty": time_penalty,
                "criticality_multiplier": crit_multiplier
            }
        }


class AISafetyLayer:
    """
    Orchestrates the deterministic safety pipeline:
    Candidate Action -> Risk Analyzer -> Blast Radius -> Policy -> Approval -> Execution
    """
    def __init__(self, db_conn=None):
        self.db = db_conn
        self.risk_analyzer = RiskAnalyzer()
        self.policy_engine = get_policy_engine()
        self.blast_engine = BlastRadiusEngine()
        
    def evaluate_action(
        self,
        incident_id: int,
        device_id: str,
        candidate_action: str,
        llm_confidence: float,
        action_target: str = ""
    ) -> dict:
        """
        Evaluates a candidate action and returns the execution decision and audit trail.
        """
        logger.info(f"[SAFETY LAYER] Evaluating candidate action '{candidate_action}' for incident {incident_id} on {device_id}")

        # 1. Blast Radius Calculation
        blast_radius_size = 1
        blast_score = 0.0
        try:
            res = self.blast_engine.calculate_blast_radius(incident_id, device_id)
            if res and isinstance(res, dict):
                blast_radius_size = len(res.get("affected_nodes", [device_id]))
                blast_score = res.get("blast_score", 0.0)
            logger.info(f"[SAFETY LAYER] Blast Radius computed: {blast_radius_size} nodes affected (Score: {blast_score})")
        except Exception as e:
            logger.warning(f"[SAFETY LAYER] Failed to compute blast radius: {e}. Defaulting to 1.")
            
        # 3. Contextual Data Fetch (Severity & Trust Score & Site Criticality)
        severity = "LOW"
        trust_score = 100.0
        site_criticality = "MEDIUM"
        
        if self.db:
            try:
                with self.db.cursor() as cur:
                    cur.execute("SELECT severity, site_id FROM fleet_incidents WHERE incident_id = %s", (incident_id,))
                    row = cur.fetchone()
                    if row:
                        severity = row[0]
                        site_id = row[1]
                        
                        # Get site criticality
                        cur.execute("SELECT criticality FROM fleet_sites WHERE site_id = %s", (site_id,))
                        s_row = cur.fetchone()
                        if s_row and s_row[0]:
                            site_criticality = s_row[0]
                        
                    cur.execute("SELECT trust_score FROM agent_trust_scores WHERE agent_name = %s", (device_id,))
                    t_row = cur.fetchone()
                    if t_row:
                        trust_score = float(t_row[0])
            except Exception as e:
                logger.warning(f"[SAFETY LAYER] DB error fetching contextual data: {e}")
                
        # 3. Risk Analyzer (v2) - Requires context
        safety_context = {
            "blast_score": blast_score,
            "site_criticality": site_criticality
        }
        # Since evaluate_action() is a sync method called from an async context,
        # we cannot use asyncio.run() or loop.run_until_complete() here.
        # Use a thread-based sync wrapper instead.
        import asyncio
        import concurrent.futures
        try:
            loop = asyncio.get_running_loop()
            # We're inside an async context — submit to a thread pool to avoid deadlock
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, self.risk_analyzer.analyze(candidate_action, action_target, safety_context))
                risk_data = future.result(timeout=10)
        except RuntimeError:
            # No running loop — safe to use asyncio.run()
            risk_data = asyncio.run(self.risk_analyzer.analyze(candidate_action, action_target, safety_context))
        except Exception as e:
            logger.warning(f"[SAFETY LAYER] Risk analyzer failed: {e}. Using default HIGH risk.")
            risk_data = {"risk_level": "HIGH", "risk_score": 1.0, "factors": {}}
            
        risk_level = risk_data.get("risk_level", "HIGH")
        risk_score = risk_data.get("risk_score", 1.0)
        logger.info(f"[SAFETY LAYER] Risk Level v2 determined: {risk_level} (Score: {risk_score})")
                
        # 4. Policy Engine Evaluation
        policy_effect = self.policy_engine.evaluate_policy(
            conn=self.db,
            confidence=llm_confidence,
            risk=risk_level,
            severity=severity,
            action_type=candidate_action,
            incident_id=incident_id,
            trust_score=trust_score,
            blast_radius=blast_radius_size,
            site_criticality=site_criticality,
            agent_name=device_id
        )
        logger.info(f"[SAFETY LAYER] Policy Engine returned effect: {policy_effect}")

        # 5. Deterministic Approval Logic
        is_approved = (policy_effect == "AUTO_EXECUTE")
        requires_hitl = policy_effect in ["FORCE_HITL", "REQUIRE_APPROVAL"]

        decision = {
            "incident_id": incident_id,
            "device": device_id,
            "candidate_action": candidate_action,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "risk_factors": risk_data.get("factors", {}),
            "blast_radius_size": blast_radius_size,
            "blast_score": blast_score,
            "llm_confidence": llm_confidence,
            "policy_effect": policy_effect,
            "is_approved": is_approved,
            "requires_hitl": requires_hitl,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "context": {
                "severity": severity,
                "trust_score": trust_score,
                "site_criticality": site_criticality
            }
        }
        
        return decision

def get_safety_layer(db_conn=None):
    return AISafetyLayer(db_conn)
