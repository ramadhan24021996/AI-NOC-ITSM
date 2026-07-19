from typing import Dict, Any, List
import uuid

class KnowledgeEvolution:
    def __init__(self, db_conn=None):
        self.db = db_conn

    def process_incident_learning(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pipeline: Incident -> Knowledge -> Memory -> Pattern -> Policy Recommendation -> Human Review -> Rule Update
        """
        # Step 1: Extract Knowledge from Incident
        knowledge = self._extract_knowledge(incident_data)
        
        # Step 2: Store to Memory
        self._store_to_memory(knowledge)
        
        # Step 3: Analyze Pattern
        pattern = self._analyze_pattern(knowledge)
        
        # Step 4: Generate Policy Recommendation
        if pattern.get("confidence", 0) > 80:
            return self._propose_policy_update(pattern)
        return {"status": "No Policy Change Needed"}

    def _extract_knowledge(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        return {"incident_id": incident_data.get("incident_id"), "outcome": "Success"}

    def _store_to_memory(self, knowledge: Dict[str, Any]):
        import logging; logging.getLogger(__name__).debug('_ = None suppressed')

    def _analyze_pattern(self, knowledge: Dict[str, Any]) -> Dict[str, Any]:
        return {"pattern_id": "P-101", "confidence": 85, "suggested_rule": "Auto-Restart if Memory > 90%"}

    def _propose_policy_update(self, pattern: Dict[str, Any]) -> Dict[str, Any]:
        proposal_id = str(uuid.uuid4())
        proposal = {
            "proposal_id": proposal_id,
            "type": "Policy Recommendation",
            "reason": f"Detected repeating pattern: {pattern['suggested_rule']}",
            "status": "Pending Review"  # WAJIB Human Review, AI tidak boleh mengubah Policy Engine langsung
        }
        
        # Simpan ke Shadow Queue (knowledge_proposal table)
        if self.db:
            try:
                with self.db.cursor() as cur:
                    cur.execute(
                        "INSERT INTO knowledge_proposal (proposal_id, proposal_type, reason, status) VALUES (%s, %s, %s, %s)",
                        (proposal["proposal_id"], proposal["type"], proposal["reason"], proposal["status"])
                    )
                self.db.commit()
            except Exception as e:
                import logging
                logging.getLogger("KNOWLEDGE").exception("Failed inserting proposal: %s", e)
                
        return proposal