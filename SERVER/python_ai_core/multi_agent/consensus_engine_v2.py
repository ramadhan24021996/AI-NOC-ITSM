from typing import Dict, Any, List

class ConsensusEngineV2:
    def __init__(self):
        import logging; logging.getLogger(__name__).debug('_ = None suppressed')

    def run_consensus(self, opinions: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not opinions:
            return {"majority": [], "minority": [], "confidence": 0.0, "conflict": False}

        votes = {}
        for op in opinions:
            action = op.get("recommended_action", "unknown")
            votes[action] = votes.get(action, 0) + 1
        
        sorted_votes = sorted(votes.items(), key=lambda x: x[1], reverse=True)
        majority_action = sorted_votes[0][0]
        
        majority = [op for op in opinions if op.get("recommended_action") == majority_action]
        minority = [op for op in opinions if op.get("recommended_action") != majority_action]
        
        conflict = len(minority) > 0
        confidence = float(len(majority)) / float(len(opinions))

        return {
            "majority": majority,
            "minority": minority,
            "confidence": confidence,
            "conflict": conflict
        }

    def explain_conflict(self, agent1_opinion: Dict[str, Any], agent2_opinion: Dict[str, Any]) -> str:
        return f"Agent 1 suggests {agent1_opinion.get('recommended_action')} while Agent 2 suggests {agent2_opinion.get('recommended_action')}."
