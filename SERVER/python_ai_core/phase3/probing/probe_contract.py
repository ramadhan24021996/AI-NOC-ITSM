"""
Phase 3.3 Probe Contract & Registry (phase3/probing/probe_contract.py)

1. ProbeContract: Standardized contract defining registered diagnostic probes.
2. ProbeRegistry: Whitelisted registry enforcing Invariant #7 (Registered Probe Only) and Invariant #8 (Read-Only Default-DENY).
"""

import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional

logger = logging.getLogger("PROBE_CONTRACT")

MUTATING_TOKENS_BLACKLIST = [
    "rm ", "rm -", "reset", "mv ", "cp ", "chmod ", "chown ", "kill ", "kill -", "pkill",
    "systemctl restart", "systemctl stop", "systemctl disable",
    "service stop", "service restart", "reboot", "shutdown", "poweroff",
    "bash -c", "sh -c", "sudo ", "su ", "exec ", "python -c", "perl -e",
    "iptables", "ip route", "/ip route", "/ip firewall", "/ip address", "/ip nat",
    "kubectl delete", "kubectl apply", "docker stop", "docker rm", "docker system prune",
    "docker volume rm", "docker network rm", "virsh destroy", "qm destroy", "terraform destroy",
    "DELETE FROM", "DROP DATABASE", "TRUNCATE TABLE", "ALTER TABLE",
    ">", ">>", "tee "
]


@dataclass
class ProbeContract:
    probe_id: str
    name: str
    description: str
    command_template: str
    allowed_targets: List[str]
    readonly: bool = True
    timeout_seconds: int = 5
    risk_class: str = "READ_ONLY_LOW"
    cost: float = 0.01
    risk_score: float = 0.01
    operational_impact: float = 0.01
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ProbeRegistry:
    """
    Whitelisted registry enforcing Invariant #7 (Unregistered -> DENIED)
    and Invariant #8 (Read-Only Enforcement).
    """
    def __init__(self):
        self._registry: Dict[str, ProbeContract] = {}
        self._register_default_whitelisted_probes()

    def _register_default_whitelisted_probes(self):
        defaults = [
            ProbeContract("P-CPU-001", "CPU Process Inspection", "Inspects top CPU process consumption", "ps aux", ["host", "server", "srv-prod-db-01"]),
            ProbeContract("P-MEM-001", "Memory Pressure Inspection", "Inspects memory utilization and swap", "free -m", ["host", "server", "srv-prod-db-01"]),
            ProbeContract("P-NET-001", "Network Connectivity Inspection", "Inspects interface errors and RTT ping", "ping -c 3 127.0.0.1", ["host", "router", "ROUTER-E2E-01"]),
            ProbeContract("P-SPOOLER-001", "Print Spooler Inspection", "Inspects print spooler status and queue count", "lpstat -p", ["host", "server", "DEV-01"]),
            ProbeContract("P-DB-001", "DB Connection Pool Inspection", "Queries active connection count in PostgreSQL", "SELECT count(*) FROM pg_stat_activity;", ["database", "postgres", "osi_system"])
        ]
        for p in defaults:
            self.register_probe(p)

    def register_probe(self, probe: ProbeContract) -> bool:
        # Validate read-only command template against mutating blacklist
        cmd_lower = probe.command_template.lower()
        for token in MUTATING_TOKENS_BLACKLIST:
            if token in cmd_lower:
                logger.error(f"[PROBE REGISTRY DENIED] Probe '{probe.probe_id}' contains mutating token '{token}'! Registration DENIED.")
                return False

        if not probe.readonly:
            logger.error(f"[PROBE REGISTRY DENIED] Probe '{probe.probe_id}' is marked readonly=False! Registration DENIED.")
            return False

        self._registry[probe.probe_id] = probe
        logger.info(f"[PROBE REGISTRY] Registered safe read-only probe '{probe.probe_id}' ({probe.name})")
        return True

    def get_probe(self, probe_id: str) -> Optional[ProbeContract]:
        """
        Invariant #7 Enforcement: Probe not in Registry -> Returns None (DENIED / FAIL-CLOSED).
        """
        probe = self._registry.get(probe_id)
        if not probe:
            logger.warning(f"[INVARIANT 7 VIOLATION] Probe ID '{probe_id}' NOT in Registry! Execution DENIED.")
        return probe

    def is_target_allowed(self, probe_id: str, target: str) -> bool:
        probe = self.get_probe(probe_id)
        if not probe:
            return False
        return any(t.lower() in target.lower() for t in probe.allowed_targets)
