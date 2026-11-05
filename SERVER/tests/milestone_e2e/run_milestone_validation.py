#!/usr/bin/env python3
"""
Milestone E2E Validation Runner
================================
Executes all milestone validation categories and writes a machine-readable
JSON report to milestone_report.json for independent verification.

Categories:
  M0-FC  Functional Correctness
  M1-BC  Backward Compatibility
  M2-RL  Reliability & Resilience
  M3-SEC Security
  M4-OBS Observability & Decision Trace
  M5-INT Integration Validation
  M6-PERF Performance & Latency Budget
  M7-REC Recovery & Resilience

Exit code: 0 = all pass, 1 = one or more failures.
Usage:
  python3 SERVER/tests/milestone_e2e/run_milestone_validation.py
"""
import unittest
import json
import sys
import os
import time
import datetime
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

SUITE_DIR = os.path.dirname(__file__)
REPORT_PATH = os.path.join(PROJECT_ROOT, "SERVER", "tests",
                           "milestone_e2e", "milestone_report.json")

CATEGORIES = [
    ("M0-FC",  "m0_fc_functional_correctness",    "Functional Correctness"),
    ("M1-BC",  "m1_bc_backward_compatibility",     "Backward Compatibility"),
    ("M2-RL",  "m2_rl_reliability",                "Reliability & Resilience"),
    ("M3-SEC", "m3_sec_security",                  "Security"),
    ("M4-OBS", "m4_obs_observability",             "Observability & Decision Trace"),
    ("M5-INT", "m5_int_integration",               "Integration Validation"),
    ("M6-PERF","m6_perf_performance",              "Performance & Latency Budget"),
    ("M7-REC", "m7_rec_recovery",                  "Recovery & Resilience"),
]

@dataclass
class CategoryResult:
    tests_run: int
    failures: int
    errors: int
    skipped: int
    passed: int
    duration_ms: float
    failure_details: List[Tuple[str, str]] = field(default_factory=list)
    error_details: List[Tuple[str, str]] = field(default_factory=list)

def run_category(module_name: str) -> CategoryResult:
    import importlib.util
    mod_path = os.path.join(SUITE_DIR, f"{module_name}.py")
    spec = importlib.util.spec_from_file_location(module_name, mod_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module spec for: {module_name}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(mod)

    stream = open(os.devnull, "w")
    runner = unittest.TextTestRunner(stream=stream, verbosity=0)
    t0 = time.monotonic()
    result = runner.run(suite)
    duration_ms = round((time.monotonic() - t0) * 1000, 2)
    stream.close()

    failures: List[Tuple[str, str]] = [(f"{tc}", f"{tb}") for tc, tb in result.failures]
    errors: List[Tuple[str, str]] = [(f"{tc}", f"{tb}") for tc, tb in result.errors]

    return CategoryResult(
        tests_run=result.testsRun,
        failures=len(result.failures),
        errors=len(result.errors),
        skipped=len(result.skipped),
        passed=result.testsRun - len(result.failures) - len(result.errors),
        duration_ms=duration_ms,
        failure_details=failures,
        error_details=errors,
    )

def main() -> int:
    print("=" * 65)
    print("  MILESTONE: End-to-End System Validation")
    print(f"  Run at: {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
    print("=" * 65)

    report: Dict[str, Any] = {
        "milestone": "End-to-End System Validation",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "python_version": sys.version,
        "project_root": PROJECT_ROOT,
        "categories": {},
        "summary": {},
    }

    total_tests = 0
    total_passed = 0
    total_failed = 0

    for code, module, label in CATEGORIES:
        print(f"\n▶  {code}: {label}")
        try:
            res = run_category(module)
        except Exception as exc:
            res = CategoryResult(
                tests_run=0,
                failures=0,
                errors=1,
                skipped=0,
                passed=0,
                duration_ms=0.0,
                failure_details=[],
                error_details=[("loader", f"{exc}")],
            )

        status = "PASS" if res.failures == 0 and res.errors == 0 else "FAIL"
        bar = "✅" if status == "PASS" else "❌"
        print(f"   {bar} {status}  {res.passed}/{res.tests_run} passed  ({res.duration_ms} ms)")

        combined_details = res.failure_details + res.error_details
        if combined_details:
            for tc, tb in combined_details:
                short = "\n".join(tb.strip().splitlines()[-3:])
                print(f"      ⚠  {tc}\n         {short}")

        cat_dict: Dict[str, Any] = {
            "label": label,
            "status": status,
            "tests_run": res.tests_run,
            "failures": res.failures,
            "errors": res.errors,
            "skipped": res.skipped,
            "passed": res.passed,
            "duration_ms": res.duration_ms,
            "failure_details": res.failure_details,
            "error_details": res.error_details,
        }
        report["categories"][code] = cat_dict

        total_tests += res.tests_run
        total_passed += res.passed
        total_failed += res.failures + res.errors

    pass_rate = round((total_passed / total_tests * 100), 1) if total_tests else 0.0
    exit_status = "PASS" if total_failed == 0 else "FAIL"

    report["summary"] = {
        "total_tests": total_tests,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "pass_rate_pct": pass_rate,
        "exit_status": exit_status,
        "dod_exit_criteria_met": total_failed == 0,
    }

    print("\n" + "=" * 65)
    print(f"  TOTAL: {total_passed}/{total_tests} passed  ({pass_rate}%)")
    print(f"  STATUS: {'✅ MILESTONE PASS' if exit_status == 'PASS' else '❌ MILESTONE FAIL'}")
    print("=" * 65)

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n  📄 Full report saved to:\n     {REPORT_PATH}")

    return 0 if exit_status == "PASS" else 1

if __name__ == "__main__":
    sys.exit(main())
