import os
import json
import asyncio
import logging
from typing import Dict, Any, List
from .task_router import TaskRouter
from .consensus_engine_v2 import ConsensusEngineV2

logger = logging.getLogger("ORCHESTRATOR")

class AgentOrchestrator:
    def __init__(self, nats_client=None):
        self.router = TaskRouter()
        self.consensus = ConsensusEngineV2()
        self.active_agents = []
        self.opinions = []
        self.incident = None
        self.nc = nats_client

    def receive_incident(self, incident: Dict[str, Any]):
        self.incident = incident
        agent = self.router.route_task(incident)
        if agent and agent != "UnknownAgent":
            self.assign_agent([agent, "general_ai_agent"])
        else:
            self.assign_agent(["general_ai_agent"])

    def assign_agent(self, agents: List[str]):
        self.active_agents.extend(agents)

    async def collect_opinion(self) -> List[Dict[str, Any]]:
        if not self.nc:
            logger.warning("No NATS client provided. Cannot collect real opinions.")
            return list()

        tasks = []
        for agent in self.active_agents:
            payload = json.dumps({"incident": self.incident}).encode()
            # Send request to specific agent topic
            tasks.append(self.nc.request(f"agent.{agent}.analyze", payload, timeout=10.0))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        self.opinions = []
        for i, res in enumerate(results):
            agent_id = self.active_agents[i]
            if isinstance(res, BaseException):
                logger.error(f"Agent {agent_id} failed to respond: {res}")
                continue
                
            try:
                data = json.loads(res.data.decode())
                self.opinions.append({
                    "agent_id": agent_id,
                    "recommended_action": data.get("recommended_action", "unknown"),
                    "confidence": data.get("confidence", 0.5),
                    "reasoning": data.get("reasoning", "")
                })
            except Exception as e:
                logger.error(f"Failed to parse response from {agent_id}: {e}")
                
        return self.opinions

    def run_consensus(self, opinions: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self.consensus.run_consensus(opinions)

    def resolve_conflict(self, opinions: List[Dict[str, Any]]) -> Dict[str, Any]:
        result = self.run_consensus(opinions)
        if result.get("conflict"):
            logger.warning("[ORCHESTRATOR] Conflict detected during consensus. Applying Confidence-based tie-breaker.")
            # Sort opinions by confidence descending
            sorted_ops = sorted(opinions, key=lambda x: x.get("confidence", 0.0), reverse=True)
            if sorted_ops:
                best_op = sorted_ops[0]
                result["majority"] = [best_op]
                result["conflict"] = False
                result["resolved_by"] = "CONFIDENCE_TIEBREAKER"
                logger.info(f"[ORCHESTRATOR] Conflict resolved. Selected action: {best_op.get('recommended_action')} with confidence {best_op.get('confidence')}")
        return result

    async def recommend_action(self) -> Dict[str, Any]:
        if not self.opinions:
            await self.collect_opinion()
        
        if not self.opinions:
            logger.warning("[ORCHESTRATOR] No opinions collected, cannot recommend action.")
            return dict()
            
        result = self.resolve_conflict(self.opinions)
        if result.get("majority"):
            return result["majority"][0]
        return dict()
