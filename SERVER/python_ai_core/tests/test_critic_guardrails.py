#!/usr/bin/env python3
"""
Automated Production Readiness Test Suite for Guardrails & Dual-Layer AI Critic:
- Automatic Hallucination Detection (CLI/Bash/PowerShell/SQL command safety scanner)
- Dynamic Confidence Threshold Tiers:
  - Confidence >= 0.92: AUTO_EXECUTE (Low-Risk Action)
  - Confidence 0.70 - 0.91: HITL_APPROVAL (Human-In-The-Loop)
  - Confidence < 0.70: GUIDANCE_ONLY (AI Advice Mode)
"""

import sys
import os
import time
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from critic_engine import AdversarialCriticEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("TEST_CRITIC")

def run_critic_guardrail_tests():
    logger.info("==================================================================")
    logger.info("🚀 STARTING AI CRITIC GUARDRAILS & CONFIDENCE TIER TEST SUITE")
    logger.info("==================================================================")

    start_time = time.time()
    critic = AdversarialCriticEngine()

    # 1. Test Dangerous Command Hallucination Detection
    logger.info("\n[TEST 1] Testing Dangerous Command Hallucination Detection...")
    dangerous_cmds = [
        "rm -rf /",
        "mkfs.ext4 /dev/sda1",
        "DROP DATABASE osi_system;",
        "format c: /fs:ntfs",
        "chmod -R 777 /",
        "dd if=/dev/zero of=/dev/sda"
    ]

    for cmd in dangerous_cmds:
        res = critic.validate_command_hallucination(cmd)
        assert res.get("is_hallucination") == True, f"Failed to detect hallucination/danger in: {cmd}"
        assert res.get("valid") == False, f"Dangerous command marked valid: {cmd}"
        logger.info(f"  - Detected dangerous command: '{cmd[:35]}...' -> {res.get('reason')}")

    logger.info("✅ TEST 1 PASSED: All 6 dangerous commands correctly blocked by AI Guardrails.")

    # 2. Test Unmatched Quotation Mark Hallucination
    logger.info("\n[TEST 2] Testing Syntax Quotation Mark Sanity Check...")
    bad_quote_cmd = "echo \"Hello World"
    res_quote = critic.validate_command_hallucination(bad_quote_cmd)
    assert res_quote.get("is_hallucination") == True
    logger.info(f"  - Detected bad quote syntax: '{bad_quote_cmd}' -> {res_quote.get('reason')}")
    logger.info("✅ TEST 2 PASSED: Unmatched quotation mark syntax correctly caught.")

    # 3. Test Safe SOP Command Validation
    logger.info("\n[TEST 3] Testing Safe SOP Command Validation...")
    safe_cmds = [
        "systemctl restart nginx",
        "service postgresql restart",
        "systemctl status osi-dashboard-server"
    ]
    for cmd in safe_cmds:
        res_safe = critic.validate_command_hallucination(cmd)
        assert res_safe.get("is_hallucination") == False
        assert res_safe.get("valid") == True
        logger.info(f"  - Validated safe SOP command: '{cmd}' -> Valid: True")
    logger.info("✅ TEST 3 PASSED: Safe SOP commands correctly approved.")

    # 4. Test Dynamic Confidence Threshold Classification Tiers
    logger.info("\n[TEST 4] Testing Dynamic Confidence Threshold Tiers...")
    
    # Tier 1: Confidence >= 92% -> AUTO_EXECUTE
    t1 = critic.evaluate_confidence_tier(0.95, is_hallucination=False, critic_score=20)
    assert t1.get("execution_mode") == "AUTO_EXECUTE", f"Expected AUTO_EXECUTE, got {t1.get('execution_mode')}"
    assert t1.get("auto_execute") == True
    logger.info(f"  - Conf 95%: {t1.get('execution_mode')} ({t1.get('tier_name')}) -> Auto: True")

    # Tier 2: Confidence 70% - 91% -> HITL_APPROVAL
    t2 = critic.evaluate_confidence_tier(0.85, is_hallucination=False, critic_score=30)
    assert t2.get("execution_mode") == "HITL_APPROVAL", f"Expected HITL_APPROVAL, got {t2.get('execution_mode')}"
    assert t2.get("requires_hitl") == True
    logger.info(f"  - Conf 85%: {t2.get('execution_mode')} ({t2.get('tier_name')}) -> Requires HITL: True")

    # Tier 3: Confidence < 70% -> GUIDANCE_ONLY
    t3 = critic.evaluate_confidence_tier(0.55, is_hallucination=False, critic_score=40)
    assert t3.get("execution_mode") == "GUIDANCE_ONLY", f"Expected GUIDANCE_ONLY, got {t3.get('execution_mode')}"
    logger.info(f"  - Conf 55%: {t3.get('execution_mode')} ({t3.get('tier_name')}) -> Guidance Mode")

    # Tier 3 Fallback on Hallucination despite High Confidence
    t4 = critic.evaluate_confidence_tier(0.98, is_hallucination=True, critic_score=10)
    assert t4.get("execution_mode") == "GUIDANCE_ONLY", "Hallucination must force GUIDANCE_ONLY"
    logger.info(f"  - Conf 98% + Hallucination: Forced to {t4.get('execution_mode')}")

    logger.info("✅ TEST 4 PASSED: Dynamic Confidence Threshold Tiers 100% verified.")

    # 5. End-to-End Critic Audit Pipeline Test
    logger.info("\n[TEST 5] Testing End-to-End Critic Audit Pipeline...")
    import asyncio
    audit_res = asyncio.run(critic.evaluate_action(
        action="check system status",
        severity="LOW",
        confidence=0.95,
        incident_details={"pc_name": "LINUX-SERVER-01", "description": "Routine status check"}
    ))
    logger.info(f"End-to-End Audit Result: Execution Mode: {audit_res.get('execution_mode')} | Critic Score: {audit_res.get('critic_score')}")
    assert "confidence_tier" in audit_res
    assert audit_res.get("execution_mode") == "AUTO_EXECUTE"
    logger.info("✅ TEST 5 PASSED: End-to-End Critic Audit Pipeline executed successfully.")

    elapsed = time.time() - start_time
    logger.info("\n==================================================================")
    logger.info(f"🎉 ALL 5 AI CRITIC GUARDRAIL TESTS PASSED SUCCESSFULLY! ({elapsed:.2f}s)")
    logger.info("==================================================================")

if __name__ == "__main__":
    run_critic_guardrail_tests()
