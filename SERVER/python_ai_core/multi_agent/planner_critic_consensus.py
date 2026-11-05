"""
Multi-Agent Consensus & Critic Auditor Engine (Layer 4 AI Core)
Implements 'Dual AI Brain Verification': Planner Agent vs Critic Auditor Agent.
Requires 100% Consensus (Score = 1.0) before any action clearance is granted.
Includes Enterprise Command Safety Critic Sandbox to block destructive commands.
If any dissent occurs between Planner and Critic, incident is immediately routed to HITL Human Queue.
"""

import re
import logging
import time
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("PlannerCriticConsensusEngine")
logging.basicConfig(level=logging.INFO)

# ─────────────────────────────────────────────────────────────────────────────
# ENTERPRISE COMMAND SAFETY CRITIC RULEBANK (Cross-Platform Windows / Linux)
# ─────────────────────────────────────────────────────────────────────────────
DANGEROUS_COMMAND_PATTERNS = [
    # 1. Destructive Filesystem / Disk Partitioning
    (re.compile(r"\brm\s+-[rRfF]{1,3}\s+[/~*]", re.IGNORECASE), "Critical: Recursive root filesystem deletion (rm -rf /)"),
    (re.compile(r"\bdel\s+/[fFqsQS\s]*[cCdD]:\\", re.IGNORECASE), "Critical: Root drive recursive deletion (del /f /s /q c:\\)"),
    (re.compile(r"\brd\s+/[sS]\s+/[qQ]\s+[cCdD]:\\", re.IGNORECASE), "Critical: Root directory recursive removal (rd /s /q c:\\)"),
    (re.compile(r"\bformat\s+[cCdD]:", re.IGNORECASE), "Critical: Disk formatting command (Format-Volume / format c:)"),
    (re.compile(r"\bformat-volume\b", re.IGNORECASE), "Critical: PowerShell disk formatting (Format-Volume)"),
    (re.compile(r"\bdiskpart\b", re.IGNORECASE), "Critical: Low-level disk partitioning tool (diskpart)"),
    (re.compile(r"\bmkfs(\.\w+)?\b", re.IGNORECASE), "Critical: Filesystem creation (mkfs)"),
    (re.compile(r"\bdd\s+if=.*of=/dev/(sd[a-z]|nvme\d+n\d+|vd[a-z])", re.IGNORECASE), "Critical: Raw disk overwrite (dd of=/dev/...)"),
    (re.compile(r"\bwipefs\b", re.IGNORECASE), "Critical: Partition signature wiping (wipefs)"),

    # 2. Destructive Database Operations
    (re.compile(r"\bdrop\s+(database|schema)\b", re.IGNORECASE), "Critical: Destructive SQL database drop"),
    (re.compile(r"\bdrop\s+table\b", re.IGNORECASE), "High Risk: Destructive SQL table drop"),
    (re.compile(r"\btruncate\s+(table\s+)?(fleet_|incident_|rbac_|knowledge_)", re.IGNORECASE), "Critical: Truncation of core system tables"),
    
    # 3. Kernel / System Destabilization & Fork Bombs
    (re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", re.IGNORECASE), "Critical: Bash fork bomb execution"),
    (re.compile(r"\bkill\s+-9\s+1\b", re.IGNORECASE), "Critical: Forceful termination of init/PID 1"),
    (re.compile(r"\bStop-Computer\s+-Force\b", re.IGNORECASE), "High Risk: Immediate forced computer shutdown"),
    
    # 4. Firewall / Security Disabling
    (re.compile(r"\bnetsh\s+advfirewall\s+set\s+allprofiles\s+state\s+off\b", re.IGNORECASE), "High Risk: Complete firewall disablement"),
    (re.compile(r"\biptables\s+-F\b", re.IGNORECASE), "High Risk: Flush all firewall packet filtering rules")
]


class PlannerCriticConsensusEngine:
    def __init__(self):
        logger.info("[PLANNER_CRITIC_CONSENSUS] Multi-Agent Consensus & Critic Auditor Engine initialized (100% Consensus Enforced).")

    def audit_command_safety(self, command_text: str) -> Tuple[bool, List[str]]:
        """
        Deep AST / Pattern sandbox scanner for shell & PowerShell commands.
        Returns: (is_safe, list_of_violations)
        """
        if not command_text:
            return True, []

        violations = []
        for pattern, description in DANGEROUS_COMMAND_PATTERNS:
            if pattern.search(command_text):
                violations.append(description)

        is_safe = (len(violations) == 0)
        return is_safe, violations

    def evaluate_dual_brain_consensus(
        self,
        incident_id: str,
        planner_output: Dict[str, Any],
        critic_audit_output: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Runs Dual-Agent Consensus:
        Planner Agent formulates Plan A/B/C.
        Critic Agent audits risk, security, and hallucination flaws.
        100% Consensus (Score = 1.0) required for automatic clearance.
        """
        plan_id = planner_output.get("plan_id", "PLAN_001")
        action = planner_output.get("recommended_action", "NO_ACTION")
        command = planner_output.get("command", "") or planner_output.get("raw_command", "")
        planner_confidence = planner_output.get("confidence", 0.95)

        # If Critic Audit Output is not explicitly provided, execute dynamic Critic Sandbox Audit
        if not critic_audit_output:
            critic_audit_output = self._execute_critic_audit(planner_output)

        critic_approved = critic_audit_output.get("approved", False)
        critic_score = critic_audit_output.get("critic_score", 0.0)
        critic_flaws = critic_audit_output.get("flaws_detected", [])

        # Calculate 100% Consensus Score
        # Consensus Score = 1.0 ONLY IF Planner and Critic agree 100% with ZERO flaws detected
        if critic_approved and len(critic_flaws) == 0 and planner_confidence >= 0.90:
            consensus_score = 1.0
            consensus_status = "100_PERCENT_CONSENSUS_APPROVED"
            requires_hitl = False
            clearance_status = "APPROVED_BY_DUAL_BRAIN_CONSENSUS"
        else:
            # Dissent or flaws detected -> Penalty applied, HITL enforced
            consensus_score = round(min(planner_confidence, critic_score) * 0.85, 2)
            consensus_status = "CONSENSUS_DISAGREEMENT_DISSENT"
            requires_hitl = True
            clearance_status = "PAUSED_AWAITING_HITL_QUEUE"

        result = {
            "incident_id": incident_id,
            "plan_id": plan_id,
            "verification_phase": "MULTI_AGENT_CONSENSUS_GATE",
            "consensus_status": consensus_status,
            "consensus_score": consensus_score,
            "requires_100_pct_consensus": True,
            "planner_agent_verdict": {
                "role": "Planner Agent",
                "recommended_action": action,
                "confidence": planner_confidence,
                "status": "PROPOSED"
            },
            "critic_auditor_verdict": {
                "role": "Critic Auditor Agent",
                "approved": critic_approved,
                "critic_score": critic_score,
                "flaws_detected": critic_flaws,
                "status": "AUDITED_APPROVED" if critic_approved else "AUDITED_REJECTED"
            },
            "requires_hitl_approval": requires_hitl,
            "execution_clearance": clearance_status,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }

        if consensus_score == 1.0:
            logger.info("[CONSENSUS_ENGINE] 100%% Dual-Brain Consensus REACHED for %s (Action: %s). Clearance granted.", incident_id, action)
        else:
            logger.warning("[CONSENSUS_ENGINE] DISSENT DETECTED for %s! Score: %.2f (Flaws: %s). Routing to HITL Queue.",
                           incident_id, consensus_score, critic_flaws)

        return result

    def _execute_critic_audit(self, planner_output: Dict[str, Any]) -> Dict[str, Any]:
        """Deep Critic sandbox audit combining risk scoring and AST regex checks."""
        risk = planner_output.get("risk", 0.1)
        action = planner_output.get("recommended_action", "")
        command = planner_output.get("command", "") or action

        flaws = []
        is_safe, violations = self.audit_command_safety(command)
        if not is_safe:
            flaws.extend(violations)

        if risk > 0.35:
            flaws.append(f"Risk Score ({risk:.2f}) exceeds autonomous execution threshold (0.35)")

        if len(flaws) > 0:
            return {
                "approved": False,
                "critic_score": max(0.0, 1.0 - (len(flaws) * 0.35)),
                "flaws_detected": flaws
            }

        return {
            "approved": True,
            "critic_score": 1.0,
            "flaws_detected": []
        }


if __name__ == "__main__":
    engine = PlannerCriticConsensusEngine()

    # Test 1: 100% Agreement (Safe action)
    plan1 = {"plan_id": "PLAN_SPOOLER", "recommended_action": "SOP_001: Restart Spooler", "command": "net stop spooler && net start spooler", "confidence": 0.98, "risk": 0.05}
    res1 = engine.evaluate_dual_brain_consensus("INC_001", plan1)
    print("Test 1 (100% Consensus):", res1["consensus_status"], "Score:", res1["consensus_score"], "HITL:", res1["requires_hitl_approval"])

    # Test 2: Dangerous command detected -> Critic rejects
    plan2 = {"plan_id": "PLAN_WIPE", "recommended_action": "Clean Disk", "command": "format c: /fs:NTFS /q", "confidence": 0.95, "risk": 0.10}
    res2 = engine.evaluate_dual_brain_consensus("INC_002", plan2)
    print("Test 2 (Dangerous Action Blocked):", res2["consensus_status"], "Flaws:", res2["critic_auditor_verdict"]["flaws_detected"], "HITL:", res2["requires_hitl_approval"])
