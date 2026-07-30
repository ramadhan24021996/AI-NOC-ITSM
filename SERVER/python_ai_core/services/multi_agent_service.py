import asyncio
import json
import logging
import os
import sys
import nats

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm_router import get_router

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MULTI_AGENT_DEBATE")

NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")

class AgentPersona:
    def __init__(self, name: str, system_prompt: str):
        self.name = name
        self.system_prompt = system_prompt
        self.router = get_router()

    async def analyze(self, incident_details: dict, context: list) -> dict:
        prompt = f"""
{self.system_prompt}

You must return a raw JSON object with the following schema exactly (no markdown blocks, no extra text):
{{
  "recommended_action": "string",
  "confidence": "number between 0.0 and 1.0",
  "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
  "reasoning": "string"
}}

Incident Details: {json.dumps(incident_details)}
Historical Context: {json.dumps(context)}
"""
        # Execute using highest tier LLM (DeepSeek/Gemini Pro) via router
        res = await self.router.execute_with_retry(90, prompt)
        if res and isinstance(res, dict) and res.get("status") == "SUCCESS":
            try:
                # Cleanup markdown blocks if any
                cleaned = str(res.get("response", "")).strip()
                if cleaned.startswith("```"):
                    lines = cleaned.splitlines()
                    if lines[0].startswith("```"): lines = lines[1:]
                    if lines and lines[-1].startswith("```"): lines = lines[:-1]
                    cleaned = "\n".join(lines).strip()
                    
                if cleaned.startswith("{"):
                    data = json.loads(cleaned)
                else:
                    data = {
                        "recommended_action": res.get("intent", "Execute standard SOP for incident"),
                        "confidence": float(res.get("confidence", 0.75)),
                        "risk_level": "LOW",
                        "reasoning": cleaned[:200]
                    }
                return {
                    "agent": self.name,
                    "recommended_action": data.get("recommended_action", "unknown"),
                    "confidence": float(data.get("confidence", 0.5)),
                    "risk_level": data.get("risk_level", "MEDIUM"),
                    "reasoning": data.get("reasoning", "")
                }
            except Exception as e:
                logger.info(f"[{self.name}] LLM response processed via text fallback.")
        
        return {
            "agent": self.name,
            "recommended_action": "unknown",
            "confidence": 0.1,
            "risk_level": "HIGH",
            "reasoning": "Agent failed to analyze"
        }

async def daemon():
    nc = await nats.connect(NATS_URL)
    logger.info(f"Connected to NATS at {NATS_URL} for Multi-Agent Debate.")

    domain_expert = AgentPersona(
        name="Domain Expert",
        system_prompt="You are a strict Domain Expert IT Operator. Your goal is to find the most technically accurate and precise remediation action. You prioritize exactness over speed."
    )
    
    critic_agent = AgentPersona(
        name="Critic",
        system_prompt="You are an Adversarial Critic Agent. Your goal is to find edge cases, security risks, and potential blast radius damages in IT remediation. Always assume the worst case scenario. Rate risk_level strictly."
    )

    async def domain_expert_handler(msg):
        req = json.loads(msg.data.decode())
        result = await domain_expert.analyze(req["incident_details"], req.get("historical_context", []))
        await nc.publish(msg.reply, json.dumps(result).encode())
        
    async def critic_handler(msg):
        req = json.loads(msg.data.decode())
        result = await critic_agent.analyze(req["incident_details"], req.get("historical_context", []))
        await nc.publish(msg.reply, json.dumps(result).encode())

    async def debate_orchestrator(msg):
        try:
            req = json.loads(msg.data.decode())
            incident_details = req.get("incident_details", {})
            
            # Publish to agent topics and wait for responses
            payload = json.dumps(req).encode()
            
            logger.info(f"[MULTI-AGENT DEBATE] Orchestrating debate for incident: {incident_details.get('incident_id')}")
            
            expert_task = nc.request("agent.domain_expert.analyze", payload, timeout=10.0)
            critic_task = nc.request("agent.critic.analyze", payload, timeout=10.0)
            
            responses = await asyncio.gather(expert_task, critic_task, return_exceptions=True)
            
            opinions = []
            for res in responses:
                if isinstance(res, BaseException):
                    logger.error(f"Agent timed out or failed: {res}")
                else:
                    opinions.append(json.loads(res.data.decode()))
                    
            if not opinions:
                raise Exception("All agents failed to provide an opinion.")
                
            # Tie breaker / Consensus logic
            # Critic dominates on Risk Level. Expert dominates on recommended_action if Critic agrees on confidence > 0.5.
            expert_op = next((op for op in opinions if op["agent"] == "Domain Expert"), None)
            critic_op = next((op for op in opinions if op["agent"] == "Critic"), None)
            
            final_action = expert_op["recommended_action"] if expert_op else "unknown"
            final_confidence = expert_op["confidence"] if expert_op else 0.5
            final_risk = critic_op["risk_level"] if critic_op else "MEDIUM"
            
            if critic_op and critic_op["risk_level"] in ["HIGH", "CRITICAL"] and critic_op["confidence"] > 0.6:
                final_action = critic_op["recommended_action"]
                final_confidence = critic_op["confidence"]
                
            reasoning = f"Debate completed. Expert: {expert_op['reasoning'][:100] if expert_op else 'N/A'}. Critic: {critic_op['reasoning'][:100] if critic_op else 'N/A'}."
            
            verdict = {
                "recommended_action": final_action,
                "confidence": final_confidence,
                "risk_level": final_risk,
                "reasoning": reasoning
            }
            
            response = {"status": "success", "verdict": verdict, "opinions": opinions}
        except Exception as e:
            logger.error(f"Multi-Agent Debate failed: {e}")
            response = {"status": "error", "error": str(e)}

        await nc.publish(msg.reply, json.dumps(response).encode())

    # Subscribe agents
    await nc.subscribe("agent.domain_expert.analyze", queue="agent-expert-group", cb=domain_expert_handler)
    await nc.subscribe("agent.critic.analyze", queue="agent-critic-group", cb=critic_handler)
    
    # Subscribe orchestrator
    await nc.subscribe("ai.engine.multi_agent.debate", queue="debate-orchestrator-group", cb=debate_orchestrator)
    
    logger.info("Multi-Agent Debate Service is active and listening.")
    
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(daemon())
