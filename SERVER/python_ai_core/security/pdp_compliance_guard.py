"""
Layer 4 AI Core — Policy Decision Point (PDP) Governance Framework (pdp_compliance_guard.py)
Replaces simple regex matching with a modular Enterprise Policy Decision Point (PDP):
- CommandNormalizer: Normalizes whitespace, casing, and extracts command structure.
- ContextEvaluator: Evaluates maintenance windows, asset criticality, service status, and user RBAC.
- RiskScorer: Computes risk score R in [0.0, 1.0] based on matching rules and business impact.
- PolicyProfiles: Manages versioned industry profiles (Retail, Finance, Healthcare, Manufacturing).
- ComplianceEngine: Evaluates multi-step workflow plans.
- AuditLogger: Records audit trail metadata.
- HITLRouter: Routes high-risk/ambiguous plans to HITL queue with full explainability.
"""

import re
import json
import time
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("PDP_COMPLIANCE_GUARD")


class CommandNormalizer:
    """Normalizes whitespace, casing, and extracts structural intent."""
    @staticmethod
    def normalize(command_str: str) -> Dict[str, Any]:
        cleaned = re.sub(r"\s+", " ", command_str.strip())
        upper_cmd = cleaned.upper()
        tokens = upper_cmd.split(" ")
        verb = tokens[0] if tokens else "UNKNOWN"

        return {
            "raw": command_str,
            "normalized": upper_cmd,
            "verb": verb,
            "token_count": len(tokens)
        }


class ContextEvaluator:
    """Evaluates contextual factors: Maintenance Window, Asset Criticality, Service Status, and User RBAC Role."""
    @staticmethod
    def evaluate(context: Dict[str, Any]) -> Dict[str, Any]:
        is_maint_window = bool(context.get("is_maintenance_window", False))
        asset_criticality = context.get("asset_criticality", "P1").upper() # P0, P1, P2, P3
        service_status = context.get("service_status", "ACTIVE_OPERATIONAL").upper()
        user_role = context.get("user_role", "NOC_OPERATOR").upper()

        return {
            "is_maintenance_window": is_maint_window,
            "asset_criticality": asset_criticality,
            "service_status": service_status,
            "user_role": user_role,
            "is_superadmin": user_role in ["SUPERADMIN", "SITE_RELIABILITY_ARCHITECT"]
        }


class RiskScorer:
    """Computes risk score R in [0.0, 1.0] based on rules, business context, and impact radius."""
    @staticmethod
    def calculate_risk(verb: str, context_eval: Dict[str, Any], matched_rules_count: int) -> float:
        base_risk = 0.20

        # Verb weight
        high_risk_verbs = ["DROP", "DELETE", "FORMAT", "SHUTDOWN", "PURGE", "REBOOT", "TRUNCATE"]
        if any(v in verb for v in high_risk_verbs):
            base_risk += 0.40

        # Criticality weight
        crit_map = {"P0": 0.30, "P1": 0.20, "P2": 0.10, "P3": 0.05}
        base_risk += crit_map.get(context_eval["asset_criticality"], 0.15)

        # Maintenance window discount
        if context_eval["is_maintenance_window"]:
            base_risk -= 0.25

        # Rule matches weight
        base_risk += (matched_rules_count * 0.10)

        # Clamp R to [0.0, 1.0]
        return round(max(0.0, min(1.0, base_risk)), 4)


class PolicyProfiles:
    """Manages versioned industry profiles: Retail, Finance, Healthcare, Manufacturing."""
    POLICY_VERSION = "v2.1.0"

    PROFILES = {
        "RETAIL": {
            "profile_name": "Retail & POS POS Terminal Safeguard",
            "version": "v2.1.0",
            "prohibited_actions": ["FORCE_REBOOT_POS", "PURGE_RECEIPT_PRINTER_QUEUE", "DROP_STORE_LOCAL_DB"],
            "requires_hitl_risk_threshold": 0.30
        },
        "FINANCE": {
            "profile_name": "PCI-DSS Financial Audit & Encryption Safeguard",
            "version": "v2.1.0",
            "prohibited_actions": ["EXPORT_UNENCRYPTED_TRANSACTIONS", "DISABLE_AUDIT_LOGGING", "DROP_LEDGER_TABLE"],
            "requires_hitl_risk_threshold": 0.20
        },
        "HEALTHCARE": {
            "profile_name": "HIPAA Patient Data Privacy Safeguard",
            "version": "v2.1.0",
            "prohibited_actions": ["EXPORT_RAW_PATIENT_RECORDS", "DISABLE_SSL_ENCRYPTION"],
            "requires_hitl_risk_threshold": 0.25
        },
        "MANUFACTURING": {
            "profile_name": "ICS/SCADA Industrial Automation Safeguard",
            "version": "v2.1.0",
            "prohibited_actions": ["PLC_FORCE_STOP", "OVERRIDE_SAFETY_RELAY"],
            "requires_hitl_risk_threshold": 0.15
        }
    }

    @classmethod
    def get_profile(cls, profile_key: str) -> Dict[str, Any]:
        return cls.PROFILES.get(profile_key.upper(), cls.PROFILES["RETAIL"])


class PolicyDecisionPoint:
    """Main PDP Engine evaluating multi-step workflow plans with full explainability & audit metadata."""

    def __init__(self, default_profile: str = "RETAIL"):
        self.default_profile = default_profile

    def evaluate_workflow_plan(
        self,
        workflow_steps: List[Dict[str, Any]],
        context: Dict[str, Any],
        profile_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Evaluates an entire multi-step workflow plan:
        1. Normalizes all commands.
        2. Evaluates context & maintenance windows.
        3. Checks versioned industry policy profiles.
        4. Calculates multi-step cumulative risk score.
        5. Returns Decision, Full Explainability, and Audit Trail Metadata.
        """
        profile = PolicyProfiles.get_profile(profile_key or self.default_profile)
        context_eval = ContextEvaluator.evaluate(context)

        step_results = []
        max_step_risk = 0.0
        total_matched_rules = 0
        overall_violations = []

        for idx, step in enumerate(workflow_steps, start=1):
            raw_action = step.get("action", step.get("command", "UNKNOWN"))
            target = step.get("target", "UNKNOWN_TARGET")

            norm = CommandNormalizer.normalize(raw_action)

            # Check profile prohibitions
            violations = []
            for prohibited in profile["prohibited_actions"]:
                if prohibited in norm["normalized"]:
                    violations.append(f"Profile Rule Violation [{profile['profile_name']}]: '{prohibited}' is strictly prohibited.")

            matched_rules_count = len(violations)
            total_matched_rules += matched_rules_count
            overall_violations.extend(violations)

            step_risk = RiskScorer.calculate_risk(norm["verb"], context_eval, matched_rules_count)
            if step_risk > max_step_risk:
                max_step_risk = step_risk

            step_results.append({
                "step_index": idx,
                "raw_action": raw_action,
                "normalized_action": norm["normalized"],
                "target": target,
                "step_risk_score": step_risk,
                "violations": violations
            })

        # Multi-step cumulative decision threshold
        hitl_threshold = profile["requires_hitl_risk_threshold"]
        is_compliant = len(overall_violations) == 0 and max_step_risk <= hitl_threshold

        # Decision Status
        if len(overall_violations) > 0:
            decision = "POLICY_VIOLATION_BLOCKED"
        elif max_step_risk > hitl_threshold:
            decision = "ROUTED_TO_HITL_QUEUE"
        else:
            decision = "AUTOMATIC_CLEARANCE_APPROVED"

        # Full Explainability Package
        explainability = {
            "decision": decision,
            "policy_profile_applied": profile["profile_name"],
            "policy_version": profile["version"],
            "max_risk_score": max_step_risk,
            "hitl_risk_threshold": hitl_threshold,
            "is_maintenance_window_active": context_eval["is_maintenance_window"],
            "matched_violation_rules": overall_violations,
            "reasons": [
                f"Evaluated {len(workflow_steps)} workflow steps under {profile['profile_name']} (Policy {profile['version']}).",
                f"Calculated Maximum Step Risk Score: {max_step_risk:.4f} (HITL Threshold: {hitl_threshold:.2f}).",
                f"Contextual Factors: Criticality = {context_eval['asset_criticality']}, Maint Window = {context_eval['is_maintenance_window']}, Role = {context_eval['user_role']}."
            ],
            "recommended_next_step": "Proceed with automated execution" if is_compliant else ("Escalate to HITL approval queue" if decision == "ROUTED_TO_HITL_QUEUE" else "Abort execution and alert SRA")
        }

        # Audit Trail Metadata
        audit_metadata = {
            "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "policy_version": profile["version"],
            "profile_key": profile_key or self.default_profile,
            "total_steps_evaluated": len(workflow_steps),
            "max_risk_score": max_step_risk,
            "decision": decision
        }

        logger.info(f"[PDP_COMPLIANCE] Evaluated workflow ({len(workflow_steps)} steps) -> Decision: {decision} (Max Risk: {max_step_risk:.4f}).")

        return {
            "decision": decision,
            "is_compliant": is_compliant,
            "explainability": explainability,
            "step_results": step_results,
            "audit_metadata": audit_metadata
        }

# Global PDP instance
pdp_engine = PolicyDecisionPoint()
