import logging
import json
import re
import os
from typing import Any, Dict, List, Optional, Tuple
from .policy_memory import PolicyMemoryManager
from .knowledge_memory import KnowledgeMemoryManager

logger = logging.getLogger("KNOWLEDGE_VALIDATION_ENGINE")

class KnowledgeValidationEngine:
    """
    Knowledge Validation Engine for Jarvis AI:
    Positioned IN FRONT of Knowledge Memory.
    Verifies new knowledge before it enters the persistent knowledge base:
      1. Schema & Format Validation
      2. Policy Validation Against Policy Memory (Layer 5 Governance Rules)
         Example: Detects if solution "Reboot router" violates NO_UNAPPROVED_ROUTER_REBOOT.
      3. Conflict Detection with Existing Knowledge (detects opposing instructions)
      4. Metadata Completeness Scoring (0.0 to 1.0)
      5. Human-In-The-Loop (HITL) Gate Triggering for high-risk / policy-conflicting knowledge.
    """

    def __init__(
        self,
        policy_mgr: Optional[PolicyMemoryManager] = None,
        knowledge_mgr: Optional[KnowledgeMemoryManager] = None
    ):
        self.policy_mgr = policy_mgr or PolicyMemoryManager()
        self.knowledge_mgr = knowledge_mgr or KnowledgeMemoryManager()

    def validate_new_knowledge(
        self,
        title: str,
        solution: str,
        category: str = "NETWORK",
        symptoms: str = "",
        root_cause: str = "",
        tags: Optional[List[str]] = None,
        severity: str = "MEDIUM",
        confidence: float = 1.0,
        author: str = "OPERATOR"
    ) -> Dict[str, Any]:
        """
        Runs comprehensive pre-ingestion validation pipeline for proposed knowledge.
        """
        title_clean = title.strip()
        solution_clean = solution.strip()
        category_clean = category.upper().strip()
        severity_clean = severity.upper().strip()
        tags_arr = tags or []

        # 1. Format & Schema Check
        if not title_clean or not solution_clean:
            return {
                "is_valid": False,
                "validation_status": "REJECTED_FORMAT",
                "reason": "Judul dan Solusi wajib diisi.",
                "completeness_score": 0.0,
                "requires_hitl": False
            }

        # 2. Metadata Completeness Score (0.0 - 1.0)
        score_components = [
            bool(title_clean),
            bool(solution_clean),
            bool(symptoms),
            bool(root_cause),
            len(tags_arr) > 0,
            severity_clean in ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
            category_clean in ["NETWORK", "SERVER", "SECURITY", "STORAGE", "DATABASE", "MIKROTIK", "CISCO", "LINUX", "SOP", "RUNBOOK", "LESSON_LEARNED"]
        ]
        completeness_score = round(sum(score_components) / len(score_components), 2)

        # 3. Policy Validation Against Layer 5 Policy Memory
        combined_text = f"{title_clean} {solution_clean} {root_cause}"
        policy_eval = self.policy_mgr.evaluate_command_against_policies(
            command_str=combined_text,
            risk_level=severity_clean
        )

        triggered_policies = policy_eval.get("triggered_policies", [])
        policy_effect = policy_eval.get("final_effect", "ALLOW")

        if policy_effect in ["DENY", "REQUIRE_APPROVAL", "FORCE_HITL"] and len(triggered_policies) > 0:
            policy_names = ", ".join([p["policy_code"] for p in triggered_policies])
            hitl_reason = f"Pengetahuan bertentangan dengan Kebijakan Keamanan: [{policy_names}]. Memerlukan persetujuan Human-In-The-Loop (HITL)."
            logger.warning(f"[KNOWLEDGE_VALIDATION_ENGINE] {hitl_reason}")
            return {
                "is_valid": False,
                "validation_status": "REJECTED_BY_POLICY" if policy_effect == "DENY" else "PENDING_HITL_APPROVAL",
                "reason": hitl_reason,
                "completeness_score": completeness_score,
                "requires_hitl": True,
                "triggered_policies": triggered_policies,
                "policy_evaluation": policy_eval
            }

        # 4. Conflict Detection with Existing Knowledge
        existing_matches = self.knowledge_mgr.hybrid_search(
            query_text=f"{title_clean} {symptoms}",
            category_filter=category_clean,
            limit=3
        )

        has_conflict = False
        conflict_details = ""
        for match in existing_matches:
            ex_solution = match.get("solution", "").lower()
            ex_title = match.get("title", "")
            # Check direct contradiction (e.g. "enable vs disable", "restart vs stop")
            if ("reboot" in solution_clean.lower() and "no reboot" in ex_solution) or \
               ("disable" in solution_clean.lower() and "enable" in ex_solution) or \
               ("stop" in solution_clean.lower() and "start" in ex_solution):
                has_conflict = True
                conflict_details = f"Pengetahuan bertentangan dengan entri eksisting '{ex_title}' (UUID: {match.get('uuid')})"
                break

        if has_conflict:
            logger.warning(f"[KNOWLEDGE_VALIDATION_ENGINE] Conflict detected: {conflict_details}")
            return {
                "is_valid": False,
                "validation_status": "REQUIRES_HUMAN_REVIEW",
                "reason": conflict_details,
                "completeness_score": completeness_score,
                "requires_hitl": True,
                "conflicting_entry": existing_matches[0] if existing_matches else None
            }

        # 5. Validation Passed Cleanly
        return {
            "is_valid": True,
            "validation_status": "VALIDATED",
            "reason": "Pengetahuan memenuhi seluruh standar format, metadata, dan kebijakan keamanan.",
            "completeness_score": completeness_score,
            "requires_hitl": False
        }
