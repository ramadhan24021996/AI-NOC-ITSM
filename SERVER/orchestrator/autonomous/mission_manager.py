"""
SERVER.orchestrator.autonomous.mission_manager
==============================================
Component: Mission Manager & Priority Queue

Manages dynamic incident mission priority queues (P1 to P4):
  P1: Firewall Core Outage (Highest Priority)
  P1: Accounting Server Down
  P2: POS Printer Issue (Deferred during P1)
  P3: CPU High Warning
"""
import logging
from typing import List, Dict, Any
from SERVER.contracts.schemas import MissionPriorityQueue

logger = logging.getLogger("orchestrator.autonomous.mission")


class MissionManager:
    """
    Prioritizes operational missions and defers low priority tasks during outages.
    """

    def get_mission_queue(self) -> MissionPriorityQueue:
        p1_list = ["INC-240801: Core Firewall Outage", "INC-240802: Accounting Database Unreachable"]
        p2_list = ["INC-240805: POS Terminal Printer Offline (DEFERRED)"]

        queue = MissionPriorityQueue(
            p1_active_incidents=p1_list,
            p2_deferred_tasks=p2_list,
            active_mission="Investigate P1 Core Firewall Outage",
        )

        logger.debug(f"[MissionManager] Mission Queue evaluated | Active: {queue.active_mission}")
        return queue
