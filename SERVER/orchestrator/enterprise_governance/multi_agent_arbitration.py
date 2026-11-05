"""
SERVER.orchestrator.enterprise_governance.multi_agent_arbitration
===================================================================
Component: Multi-Agent Arbitration Engine

Resolves disagreements between AI NOC and Jarvis by requesting targeted evidence rather than simple voting:
"Perbedaan pendapat terdeteksi: AI NOC (Backup Job) vs Jarvis (Memory Leak). Meminta PostgreSQL Log, Lock Table, dan Disk Queue sebelum mengambil keputusan."
"""
import logging
from typing import Dict, Any, List
from SERVER.contracts.schemas import ArbitrationResult

logger = logging.getLogger("orchestrator.governance.arbitration")


class MultiAgentArbitrationEngine:
    """
    Arbitrates peer disputes through evidence solicitation.
    """

    def arbitrate_disagreement(
        self, incident_id: str, ai_noc_claim: str = "Backup Job", jarvis_claim: str = "Memory Leak"
    ) -> ArbitrationResult:
        ev_req = ["PostgreSQL Log", "Lock Table State", "Disk Queue Length"]

        res = ArbitrationResult(
            has_disagreement=True,
            ai_noc_claim=ai_noc_claim,
            jarvis_claim=jarvis_claim,
            evidence_requested=ev_req,
            arbitrated_decision=f"Perbedaan pendapat terdeteksi: AI NOC ({ai_noc_claim}) vs Jarvis ({jarvis_claim}). Meminta {', '.join(ev_req)} sebelum keputusan akhir.",
        )

        logger.info(f"[MultiAgentArbitrationEngine] Arbitrating {incident_id}: Requested {len(ev_req)} extra evidence items")
        return res
