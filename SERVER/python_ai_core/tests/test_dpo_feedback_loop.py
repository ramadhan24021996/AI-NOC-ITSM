#!/usr/bin/env python3
"""
Automated Test Suite for Pilar 3: Continuous Learning DPO Feedback Loop
- Tests recording operator Approve / Reject decisions as preference pairs
- Tests daily JSONL DPO dataset synthesis (dpo_dataset_YYYY-MM-DD.jsonl)
- Validates JSONL structure compatibility with HuggingFace TRL DPOTrainer
"""

import sys
import os
import time
import json
import logging
from datetime import datetime, UTC

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from learning.dpo_dataset_synthesizer import DPODatasetSynthesizer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("TEST_DPO_LOOP")

def run_dpo_feedback_loop_tests():
    logger.info("==================================================================")
    logger.info("🚀 STARTING PILAR 3: CONTINUOUS LEARNING DPO FEEDBACK LOOP TESTS")
    logger.info("==================================================================")

    start_time = time.time()
    synth = DPODatasetSynthesizer()

    # 1. Test Recording APPROVED decision
    logger.info("\n[TEST 1] Testing APPROVED Operator Decision Recording...")
    res_app = synth.record_operator_decision(
        incident_id=f"INC-TEST-{int(time.time())}-1",
        action_proposed="systemctl restart postgresql",
        decision="APPROVED",
        prompt_context="Database connection pool exhausted on SERVER-DB-01",
        operator_id="SUPERADMIN",
        intent="DB_POOL_EXHAUSTED",
        device_id="SERVER-DB-01"
    )
    assert res_app == True, "Failed to record APPROVED decision"
    logger.info("✅ TEST 1 PASSED: APPROVED decision recorded as DPO pair.")

    # 2. Test Recording REJECTED decision
    logger.info("\n[TEST 2] Testing REJECTED Operator Decision Recording...")
    res_rej = synth.record_operator_decision(
        incident_id=f"INC-TEST-{int(time.time())}-2",
        action_proposed="rm -rf /var/log/*",
        decision="REJECTED",
        prompt_context="Disk space 95% full on WEB-SERVER-02",
        operator_id="NOC_ENGINEER",
        intent="DISK_SPACE_CRITICAL",
        device_id="WEB-SERVER-02",
        alternative_recommendation="Rotate Nginx logs and compress old archives"
    )
    assert res_rej == True, "Failed to record REJECTED decision"
    logger.info("✅ TEST 2 PASSED: REJECTED decision recorded as DPO pair.")

    # 3. Test Daily Dataset Synthesizer (JSONL Generation)
    logger.info("\n[TEST 3] Testing Daily JSONL DPO Dataset Synthesis...")
    synth_res = synth.synthesize_daily_dataset()
    logger.info(f"Synthesis Output: Status: {synth_res.get('status')}, File: {synth_res.get('output_file')}, Count: {synth_res.get('record_count')}")
    
    rec_count = int(synth_res.get("record_count") or 0)
    out_file = str(synth_res.get("output_file") or "")
    assert synth_res.get("status") == "SUCCESS", "Failed to synthesize daily DPO dataset"
    assert rec_count >= 2, "Expected at least 2 DPO records in daily export"
    assert out_file and os.path.exists(out_file), "JSONL dataset file does not exist on disk"

    # Verify JSONL lines validity
    with open(out_file, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]
        assert len(lines) >= 2, "JSONL line count mismatch"
        first = lines[0]
        assert "prompt" in first and "chosen" in first and "rejected" in first
        logger.info(f"Sample JSONL Entry: Prompt='{first['prompt'][:30]}...' -> Chosen='{first['chosen'][:30]}...'")

    logger.info("✅ TEST 3 PASSED: Daily JSONL DPO dataset synthesis 100% verified.")

    elapsed = time.time() - start_time
    logger.info("\n==================================================================")
    logger.info(f"🎉 ALL PILAR 3 DPO FEEDBACK LOOP TESTS PASSED SUCCESSFULLY! ({elapsed:.2f}s)")
    logger.info("==================================================================")

if __name__ == "__main__":
    run_dpo_feedback_loop_tests()
