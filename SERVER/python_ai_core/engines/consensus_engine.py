import logging
import asyncio
import json
import os
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
        """Invokes Model A (Gemini)."""
        if not self.router.gemini_ready or not self.router.gemini_client:
            logger.warning("Gemini not ready, simulating Model A response.")
            return self._simulated_verdict("gemini", prompt)

        model_name = self.router.route_incident(severity_score)
        try:
            response = await asyncio.to_thread(
                self.router.gemini_client.models.generate_content,
                model=model_name,
                contents=prompt
            )
            return self._parse_verdict("gemini", response.text)
        except Exception as e:
            logger.error("Gemini invocation failed: %s. Falling back to simulation.", e)
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

    def _simulated_verdict(self, model_name: str, prompt: str) -> dict:
        prompt_lower = prompt.lower()
        if "cpu" in prompt_lower:
            action = "restart Service Winmgmt via Command Relay"
            confidence = 0.92 if model_name == "gemini" else (0.88 if model_name == "deepseek" else 0.85)
            risk = "LOW"
        elif "ram" in prompt_lower or "memory" in prompt_lower:
            action = "force restart client process"
            confidence = 0.85 if model_name == "gemini" else (0.80 if model_name == "deepseek" else 0.78)
            risk = "MEDIUM"
        elif "disk" in prompt_lower:
            action = "clean temp files and IIS logs"
            confidence = 0.95 if model_name == "gemini" else (0.90 if model_name == "deepseek" else 0.88)
            risk = "LOW"
        else:
            action = "restart service Spooler"
            confidence = 0.80 if model_name == "gemini" else (0.75 if model_name == "deepseek" else 0.72)
            risk = "MEDIUM"

        return {
            "model": model_name,
            "recommended_action": action,
            "confidence": confidence,
            "risk_level": risk,
            "reasoning": "Simulated backup logic"
        }

    async def get_consensus_verdict(self, incident_details: dict, historical_context: list, severity_score: int, pattern: str = "WEIGHTED CONFIDENCE") -> dict:
        """
        Runs Consensus Models, merges confidence, resolves conflicts, and checks risk override constraints.
        """
        # Inject Sprint K Foundation Knowledge
        from knowledge.foundation_knowledge_engine import FoundationKnowledgeEngine
        foundation = FoundationKnowledgeEngine()
        
        system_prompt = foundation.inject_system_prompt()
        output_schema = json.dumps(foundation.generate_output_schema(), indent=2)
        
        # Connect to DB for historical learning context
        import os
        import psycopg2
        db_conn = None
        try:
            db_conn = psycopg2.connect(
                host=os.environ.get("DB_HOST", "postgres"),
                port=os.environ.get("DB_PORT", "5432"),
                dbname=os.environ.get("DB_NAME", "osi_system"),
                user=os.environ.get("DB_USER", "postgres"),
                password=os.environ.get("DB_PASSWORD", "postgres")
            )
        except Exception as e:
            logger.error(f"Failed to connect to DB for Foundation Knowledge: {e}")
            
        # Augment Learning Context (Bagian 8)
        augmented_context = foundation.augment_learning_context(incident_details, db_conn)
        historical_context.append(augmented_context)
        
        if db_conn:
            db_conn.close()
        
        prompt = f"""
{system_prompt}

Analyze this incident based on your Foundation Knowledge.
Incident details: {json.dumps(incident_details)}
Historical context: {json.dumps(historical_context)}

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

        verdicts = [verdict_a, verdict_b, verdict_c, verdict_d]
        logger.info("Consensus Engine inputs: %s", verdicts)

        # Merge Confidence (Weighted average of all models)
        merged_confidence = (
            (verdict_a["confidence"] * self.weights["gemini"]) +
            (verdict_b["confidence"] * self.weights["deepseek"]) +
            (verdict_c["confidence"] * self.weights["groq"]) +
            (verdict_d["confidence"] * self.weights["rule_engine"])
        ) / (self.weights["gemini"] + self.weights["deepseek"] + self.weights["groq"] + self.weights["rule_engine"])

        # Conflict Resolution & Consensus Pattern application
        chosen_action = verdict_a["recommended_action"]
        chosen_reason = verdict_a["reasoning"]
        chosen_risk = verdict_a["risk_level"]

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
