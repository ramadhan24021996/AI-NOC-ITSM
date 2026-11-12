import logging
import asyncio
import json
import os
try:
    from .llm_router import get_router
except ImportError:
    from engines.llm_router import get_router

logger = logging.getLogger("CONSENSUS_ENGINE")

class ConsensusEngine:
    def __init__(self):
        self.router = get_router()
        # Model weights
        self.weights = {
            "gemini": 0.4,
            "deepseek": 0.3,
            "groq": 0.2,
            "rule_engine": 0.1
        }
        logger.info("Consensus Engine initialized with weights: %s", self.weights)

    async def execute_model_a_gemini(self, prompt: str, severity_score: int) -> dict:
        """Invokes Model A (Gemini) with multi-key rotation via LLMRouter._execute_gemini."""
        if not self.router.gemini_ready:
            logger.warning("Gemini not ready — marking Model A unavailable (honest degradation).")
            return self._simulated_verdict("gemini", prompt)

        model_name = self.router.route_incident(severity_score)
        try:
            res = await asyncio.to_thread(self.router._execute_gemini, model_name, prompt)
            if res and isinstance(res, dict) and res.get("status") == "SUCCESS" and res.get("response"):
                return self._parse_verdict("gemini", str(res["response"]))
            logger.warning("Gemini returned non-success: %s", res.get("error") if isinstance(res, dict) else res)
            return self._simulated_verdict("gemini", prompt)
        except Exception as e:
            logger.error("Gemini invocation failed: %s.", e)
            return self._simulated_verdict("gemini", prompt)

    async def execute_model_b_deepseek(self, prompt: str) -> dict:
        """Invokes Model B (DeepSeek), with Groq as fallback."""
        if not self.router.deepseek_ready:
            logger.warning("DeepSeek not ready, trying Groq fallback for Model B.")
            if self.router.groq_ready:
                try:
                    res = await asyncio.to_thread(self.router.execute_groq, prompt, "llama-3.1-70b-versatile")
                    if res and isinstance(res, dict) and res.get("status") == "SUCCESS":
                        # Return Groq answer but label model as deepseek for consensus processing
                        return self._parse_verdict("deepseek", str(res.get("response", "")))
                except Exception as e:
                    logger.error("Groq fallback for DeepSeek failed: %s", e)
            logger.warning("DeepSeek & Groq not ready, simulating Model B response.")
            return self._simulated_verdict("deepseek", prompt)

        try:
            res = await asyncio.to_thread(self.router.execute_deepseek, prompt)
            if res and isinstance(res, dict) and res.get("status") == "SUCCESS":
                return self._parse_verdict("deepseek", str(res.get("response", "")))
            else:
                logger.warning("DeepSeek call failed, trying Groq fallback.")
                if self.router.groq_ready:
                    res_fallback = await asyncio.to_thread(self.router.execute_groq, prompt, "llama-3.1-70b-versatile")
                    if res_fallback and isinstance(res_fallback, dict) and res_fallback.get("status") == "SUCCESS":
                        return self._parse_verdict("deepseek", str(res_fallback.get("response", "")))
                return self._simulated_verdict("deepseek", prompt)
        except Exception as e:
            logger.error("DeepSeek invocation failed: %s. Falling back to simulation.", e)
            return self._simulated_verdict("deepseek", prompt)

    async def execute_model_c_groq(self, prompt: str) -> dict:
        """Invokes Model C (Groq/Llama-3.1)."""
        if not self.router.groq_ready:
            logger.warning("Groq not ready, simulating Model C response.")
            return self._simulated_verdict("groq", prompt)

        try:
            res = await asyncio.to_thread(self.router.execute_groq, prompt)
            if res and isinstance(res, dict) and res.get("status") == "SUCCESS":
                return self._parse_verdict("groq", str(res.get("response", "")))
            else:
                logger.warning("Groq call failed, simulating Model C response.")
                return self._simulated_verdict("groq", prompt)
        except Exception as e:
            logger.error("Groq invocation failed: %s. Falling back to simulation.", e)
            return self._simulated_verdict("groq", prompt)

    def execute_model_d_rule_engine(self, prompt: str) -> dict:
        """Invokes Model D (Offline Rule Engine as tie-breaker)."""
        res = self.router.rule_engine_fallback(prompt)
        action = res.get("response", "RULE_ENGINE_FALLBACK: general warning")
        return {
            "model": "rule_engine",
            "recommended_action": action,
            "confidence": 0.50,
            "risk_level": "LOW",
            "reasoning": "Rule engine static matching"
        }

    def _parse_verdict(self, model_name: str, response_text: str) -> dict:
        try:
            cleaned = response_text.strip()
            if cleaned.startswith("```"):
                lines = cleaned.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                cleaned = "\n".join(lines).strip()

            data = json.loads(cleaned)
            
            # Map Sprint K Foundation Schema to Consensus Legacy Schema
            action = data.get("immediate_action") or data.get("recommended_action", "unknown")
            risk = str(data.get("severity") or data.get("risk_level", "MEDIUM")).upper()
            
            reasoning = data.get("root_cause", "")
            if "executive_summary" in data:
                reasoning = data["executive_summary"] + "\nRoot Cause: " + reasoning
            if not reasoning:
                reasoning = data.get("reasoning", "")

            confidence_val = data.get("confidence", 70)
            if isinstance(confidence_val, int) and confidence_val > 1:
                confidence_val = confidence_val / 100.0 # Convert 0-100 to 0.0-1.0 expected by consensus
            else:
                confidence_val = float(confidence_val)

            return {
                "model": model_name,
                "recommended_action": action,
                "confidence": confidence_val,
                "risk_level": risk,
                "reasoning": reasoning,
                "raw_schema": data # Pass full schema for downstream use
            }
        except Exception as e:
            logger.error("Failed to parse JSON from model %s: %s", model_name, e)
            return {
                "model": model_name,
                "recommended_action": "unknown",
                "confidence": 0.5,
                "risk_level": "MEDIUM",
                "reasoning": f"Failed parsing: {response_text}"
            }

    def _simulated_verdict(self, model_name: str, prompt: str, reason: str = "") -> dict:
        """[WS-IA3] Honest Confidence Degradation:
        Never fabricate high-confidence (0.80-0.92) Winmgmt/Spooler restart commands when an LLM provider fails.
        Mark the provider verdict as unavailable so ConsensusEngine excludes it from weighted voting
        or degrades gracefully to HITL if all cloud providers are unreachable.
        """
        _ = prompt
        detail = f" ({reason})" if reason else ""
        return {
            "model": model_name,
            "recommended_action": "MANUAL_TRIAGE_REQUIRED",
            "confidence": 0.0,
            "risk_level": "HIGH",
            "reasoning": f"Provider '{model_name}' unavailable or rate-limited{detail} (honest degradation — zero hallucination).",
            "unavailable": True,
        }

    async def get_consensus_verdict(self, incident_details: dict, historical_context: list, severity_score: int = 50, pattern: str = "WEIGHTED CONFIDENCE") -> dict:
        """
        Runs Consensus Models, merges confidence across live responding models only,
        resolves conflicts, and checks risk override constraints.
        """
        # Inject Sprint K Foundation Knowledge
        try:
            from knowledge.foundation_knowledge_engine import FoundationKnowledgeEngine
        except ImportError:
            from SERVER.python_ai_core.knowledge.foundation_knowledge_engine import FoundationKnowledgeEngine
        foundation = FoundationKnowledgeEngine()
        
        system_prompt = foundation.inject_system_prompt()
        output_schema = json.dumps(foundation.generate_output_schema(), indent=2)
        
        # Connect to DB for historical learning context via shared pool (with fast fallback)
        db_conn = None
        try:
            try:
                from shared.db_pool import get_db_connection
            except ImportError:
                from SERVER.shared.db_pool import get_db_connection
            db_conn = get_db_connection()
        except Exception as e:
            logger.error(f"Failed to connect to DB for Foundation Knowledge: {e}")

        # Augment Learning Context without mutating caller's historical_context list
        try:
            augmented_context = foundation.augment_learning_context(incident_details, db_conn)
            local_history = list(historical_context) + ([augmented_context] if augmented_context else [])
        finally:
            if db_conn:
                try:
                    db_conn.close()
                except Exception:
                    pass
        
        prompt = f"""
{system_prompt}

Analyze this incident based on your Foundation Knowledge.
Incident details: {json.dumps(incident_details)}
Historical context: {json.dumps(local_history)}

Return ONLY a raw JSON mapping exactly to this JSON Schema. Do NOT use markdown blocks:
{output_schema}
"""
        # Run Model A, Model B and Model C in parallel
        verdict_a, verdict_b, verdict_c = await asyncio.gather(
            self.execute_model_a_gemini(prompt, severity_score),
            self.execute_model_b_deepseek(prompt),
            self.execute_model_c_groq(prompt)
        )
        verdict_d = self.execute_model_d_rule_engine(prompt)

        all_verdicts = [verdict_a, verdict_b, verdict_c, verdict_d]
        live_cloud_verdicts = [
            v for v in (verdict_a, verdict_b, verdict_c)
            if not v.get("unavailable") and v.get("recommended_action") not in ("unknown", "MANUAL_TRIAGE_REQUIRED")
        ]
        active_verdicts = live_cloud_verdicts + [verdict_d] if live_cloud_verdicts else [verdict_d]
        logger.info("Consensus Engine inputs (live_cloud=%d): %s", len(live_cloud_verdicts), all_verdicts)

        # Merge Confidence across active (non-unavailable) models only
        active_weight_sum = sum(self.weights.get(v["model"], 0.1) for v in active_verdicts) or 1.0
        merged_confidence = sum(
            v["confidence"] * self.weights.get(v["model"], 0.1) for v in active_verdicts
        ) / active_weight_sum

        if not live_cloud_verdicts:
            # All cloud LLM providers failed/unavailable -> cap confidence at 0.45 and force HIGH risk (HITL)
            merged_confidence = min(0.45, merged_confidence)
            chosen_action = verdict_d["recommended_action"]
            chosen_reason = f"All cloud LLM providers unavailable; using deterministic offline rule engine ({verdict_d['reasoning']})."
            chosen_risk = "HIGH"
            return {
                "recommended_action": chosen_action,
                "confidence": merged_confidence,
                "risk_level": chosen_risk,
                "reasoning": f"Consensus Pattern: {pattern} (Offline Fallback). {chosen_reason}",
                "verdicts": all_verdicts,
            }

        verdicts = active_verdicts
        chosen_action = live_cloud_verdicts[0]["recommended_action"]
        chosen_reason = live_cloud_verdicts[0]["reasoning"]
        chosen_risk = live_cloud_verdicts[0]["risk_level"]

        if pattern == "MAJORITY":
            votes = {}
            for v in verdicts:
                action = v["recommended_action"].lower().strip()
                votes[action] = votes.get(action, 0) + 1
            
            majority_action = max(votes, key=lambda k: votes.get(k, 0))
            if votes[majority_action] >= 2:
                for v in verdicts:
                    if v["recommended_action"].lower().strip() == majority_action:
                        chosen_action = v["recommended_action"]
                        chosen_reason = v["reasoning"]
                        chosen_risk = v["risk_level"]
                        break
            else:
                highest = max(verdicts, key=lambda x: x["confidence"])
                chosen_action = highest["recommended_action"]
                chosen_reason = highest["reasoning"]
                chosen_risk = highest["risk_level"]

        elif pattern == "WEIGHTED CONFIDENCE":
            scores = {}
            for v in verdicts:
                action = v["recommended_action"].lower().strip()
                weight = self.weights[v["model"]]
                score = v["confidence"] * weight
                scores[action] = scores.get(action, 0.0) + score
            
            best_action = max(scores, key=lambda k: scores.get(k, 0.0))
            for v in verdicts:
                if v["recommended_action"].lower().strip() == best_action:
                    chosen_action = v["recommended_action"]
                    chosen_reason = v["reasoning"]
                    chosen_risk = v["risk_level"]
                    break

        elif pattern == "RISK OVERRIDE":
            # Prioritize the verdict with highest risk rating
            risk_map = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
            highest_risk_verdict = max(verdicts, key=lambda x: risk_map.get(x["risk_level"], 1))
            chosen_action = highest_risk_verdict["recommended_action"]
            chosen_reason = f"Risk Override active. Selected action from model {highest_risk_verdict['model']} to mitigate risk. reasoning: {highest_risk_verdict['reasoning']}"
            chosen_risk = highest_risk_verdict["risk_level"]

        # RISK OVERRIDE Constraint (Safety Envelope)
        any_high_risk = any(v["risk_level"] in ("HIGH", "CRITICAL") for v in verdicts)
        if any_high_risk:
            logger.warning("RISK OVERRIDE active: At least one model flagged high risk remediation!")
            chosen_risk = "HIGH"

        result = {
            "recommended_action": chosen_action,
            "confidence": merged_confidence,
            "risk_level": chosen_risk,
            "reasoning": f"Consensus Pattern: {pattern}. {chosen_reason}",
            "verdicts": verdicts
        }
        logger.info("Consensus Engine output: %s", result)
        return result
