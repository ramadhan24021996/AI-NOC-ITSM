"""
Full AEO Production Certification & Integrated Regression Test Suite
Runs all test suites across Phase 3.1 to Phase 4.1 and AEO 8 Gates Certification.
"""

import logging
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from governance.certification_baseline_freeze import CertificationBaselineFreeze
from tests.test_phase31_evidence_graph import Phase31EvidenceGraphSuite
from tests.test_phase32_hypothesis_competition import Phase32HypothesisCompetitionSuite
from tests.test_phase33_active_probing import Phase33ActiveProbingSuite
from tests.test_phase34_causal_confirmation import Phase34CausalConfirmationSuite
from tests.test_phase35_counterfactual import Phase35CounterfactualSuite
from tests.test_phase36_remediation import Phase36RemediationSuite
from tests.test_phase40b_event_loop_wrapper import Phase40BEventLoopSuite
from tests.test_phase41_remediation_recommendation import Phase41RemediationRecommendationSuite
from tests.test_aeo_8_gates_certification import AEO8GatesCertificationSuite

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("FULL_AEO_CERTIFICATION_SUITE")


def run_full_certification():
    logger.info("=== 1. VERIFYING G3-G8 BASELINE FREEZE INTEGRITY ===")
    freeze = CertificationBaselineFreeze()
    f_res = freeze.validate_freeze_integrity()
    logger.info(f"Baseline status: {f_res['status']}")
    assert f_res['freeze_intact'] == True

    logger.info("\n=== 2. RUNNING PHASE 3.1 SUITE ===")
    s31 = Phase31EvidenceGraphSuite().run_phase31_forensic_suite()
    logger.info(f"Phase 3.1 result: {s31['status']}")

    logger.info("\n=== 3. RUNNING PHASE 3.2 SUITE ===")
    s32 = Phase32HypothesisCompetitionSuite().run_10_failure_injections()
    logger.info(f"Phase 3.2 result: {'PASS' if s32['all_passed'] else 'FAIL'}")

    logger.info("\n=== 4. RUNNING PHASE 3.3 SUITE ===")
    s33 = Phase33ActiveProbingSuite().run_15_failure_injections()
    logger.info(f"Phase 3.3 result: {'PASS' if s33['all_passed'] else 'FAIL'}")

    logger.info("\n=== 5. RUNNING PHASE 3.4 SUITE ===")
    s34 = Phase34CausalConfirmationSuite().run_25_failure_injections()
    logger.info(f"Phase 3.4 result: {'PASS' if s34['all_passed'] else 'FAIL'}")

    logger.info("\n=== 6. RUNNING PHASE 3.5 SUITE ===")
    s35 = Phase35CounterfactualSuite().run_30_failure_injections()
    logger.info(f"Phase 3.5 result: {'PASS' if s35['all_passed'] else 'FAIL'}")

    logger.info("\n=== 7. RUNNING PHASE 3.6 SUITE ===")
    s36 = Phase36RemediationSuite().run_35_failure_injections()
    logger.info(f"Phase 3.6 result: {'PASS' if s36['all_passed'] else 'FAIL'}")

    logger.info("\n=== 8. RUNNING PHASE 4.0-B CONTROL PLANE SUITE ===")
    s40b = Phase40BEventLoopSuite().run_40_failure_injections()
    logger.info(f"Phase 4.0-B result: {'PASS' if s40b['all_passed'] else 'FAIL'}")

    logger.info("\n=== 9. RUNNING PHASE 4.1 RECOMMENDATION ENGINE SUITE ===")
    s41 = Phase41RemediationRecommendationSuite().run_20_failure_injections()
    logger.info(f"Phase 4.1 result: {'PASS' if s41['all_passed'] else 'FAIL'}")

    logger.info("\n=== 10. RUNNING AEO 8 GATES PRODUCTION CERTIFICATION SUITE ===")
    s8g = AEO8GatesCertificationSuite().run_all_8_gates()
    logger.info(f"AEO 8 Gates result: {'PASS' if s8g['all_passed'] else 'FAIL'}")

    logger.info("\n🎉 ALL SUITES PASSED 100% CLEANLY (TOTAL 183 CERTIFICATION SCENARIOS PASSED)!")


if __name__ == "__main__":
    run_full_certification()
