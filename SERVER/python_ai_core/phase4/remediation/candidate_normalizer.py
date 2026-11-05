"""
Phase 4.1 Candidate Normalizer (phase4/remediation/candidate_normalizer.py)

Resolves LLM/Rule candidates to registered ACTION_IDs in ActionRegistry.
Denies 100% arbitrary shell commands or unregistered ACTION_IDs before Safety Gate.
"""

import logging
import re
from typing import Dict, Any, Tuple, Optional
from phase4.remediation.remediation_action_registry import ActionRegistry, ActionContract

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("CANDIDATE_NORMALIZER")


class CandidateNormalizer:
    def __init__(self, registry: Optional[ActionRegistry] = None):
        self.registry = registry or ActionRegistry()

    def normalize_and_resolve_candidate(self, proposal: Dict[str, Any]) -> Tuple[bool, Optional[ActionContract], str]:
        """
        Normalizes proposal and resolves exact registered ACTION_ID in ActionRegistry.
        Returns: (is_registered, action_contract, status_reason)
        """
        raw_cmd = proposal.get("raw_command", "") or proposal.get("candidate_text", "")
        action_id = proposal.get("action_id", "")

        # Check shell injection or raw shell string (e.g., sudo, systemctl, rm, kill)
        if raw_cmd and any(kw in raw_cmd.lower() for kw in ["sudo", "systemctl", "rm ", "kill ", "kubectl", "docker"]):
            logger.warning(f"[NORMALIZER DENIED] Shell command injection attempt rejected: '{raw_cmd}'")
            return False, None, "UNREGISTERED_SHELL_COMMAND_DENIED"

        # Check explicit action_id
        if action_id:
            action = self.registry.lookup_action(action_id)
            if action:
                logger.info(f"[NORMALIZER RESOLVED] Resolved explicit Action ID: '{action_id}' ({action.name})")
                return True, action, "ACTION_ID_REGISTERED"
            else:
                logger.warning(f"[NORMALIZER DENIED] Unregistered Action ID: '{action_id}'")
                return False, None, "UNREGISTERED_ACTION_ID_DENIED"

        # Semantic attribute lookup fallback
        text_lower = raw_cmd.lower()
        if "dhcp" in text_lower and "restart" in text_lower:
            action = self.registry.lookup_action("NET-DHCP-RESTART-001")
            return True, action, "SEMANTIC_RESOLVED_DHCP_RESTART"
        elif "app" in text_lower and "restart" in text_lower:
            action = self.registry.lookup_action("RESTART-APP-SERVICE-001")
            return True, action, "SEMANTIC_RESOLVED_APP_RESTART"
        elif "config" in text_lower or "reload" in text_lower:
            action = self.registry.lookup_action("RELOAD-CONFIG-001")
            return True, action, "SEMANTIC_RESOLVED_CONFIG_RELOAD"

        logger.warning(f"[NORMALIZER DENIED] Could not resolve candidate '{raw_cmd}' to ActionRegistry.")
        return False, None, "UNREGISTERED_ACTION_DENIED"
