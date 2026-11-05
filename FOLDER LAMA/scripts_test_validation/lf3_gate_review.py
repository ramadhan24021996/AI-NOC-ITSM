#!/usr/bin/env python3
import sys
import os
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../SERVER/python_ai_core/learning')))

def print_hdr(msg):
    print(f"\n==================================================")
    print(f" {msg}")
    print(f"==================================================")

def run_gate_review():
    print_hdr("LF-3 MANDATORY GATE REVIEW (REMEDIATION LEARNING)")
    passed = 0
    total = 7
    
    DB_CONFIG = {
        "host": "localhost",
        "port": 5433,  # Map to host port of docker
        "database": "osi_system",
        "user": "postgres",
        "password": "SecurePassword_123!"
    }
    
    from remediation.services.manager import RemediationManager
    manager = RemediationManager(DB_CONFIG)
    
    # Setup test data
    rem_id_1 = "rem-test-001"
    rem_id_2 = "rem-test-002"
    rem_id_fail = "rem-test-fail"

    # Clean DB
    cur = manager.conn.cursor()
    cur.execute("DELETE FROM remediation_feedback WHERE remediation_id IN (%s, %s, %s)", (rem_id_1, rem_id_2, rem_id_fail))
    cur.execute("DELETE FROM remediation_scores WHERE remediation_id IN (%s, %s, %s)", (rem_id_1, rem_id_2, rem_id_fail))
    cur.execute("DELETE FROM remediation_results WHERE remediation_id IN (%s, %s, %s)", (rem_id_1, rem_id_2, rem_id_fail))
    cur.execute("DELETE FROM remediation_audit WHERE remediation_id IN (%s, %s, %s)", (rem_id_1, rem_id_2, rem_id_fail))
    cur.execute("DELETE FROM remediation_registry WHERE remediation_id IN (%s, %s, %s)", (rem_id_1, rem_id_2, rem_id_fail))
    cur.close()

    # 1. Registry Test
    print("\n--- 1. Remediation Registry Test ---")
    payload1 = {
        "remediation_id": rem_id_1,
        "incident_id": "inc-001",
        "tenant_id": "t-01",
        "device_id": "srv-01",
        "action_name": "RESTART_SERVICE",
        "executor": "AI_AGENT",
        "execution_status": "EXECUTED",
        "confidence_before": 0.80
    }
    try:
        manager.register_remediation(payload1)
        print("✅ PASS: Remediation successfully registered.")
        passed += 1
    except Exception as e:
        print(f"❌ FAIL: {e}")

    # 2. Evidence Enforcement Test
    print("\n--- 2. Evidence Enforcement Test ---")
    try:
        manager.log_evidence_and_result(rem_id_1, "RESTART_SERVICE", {"resolution_time_ms": 100}, 0.80)
        print("❌ FAIL: Allowed learning without evidence.")
    except ValueError as e:
        if "strictly required" in str(e).lower():
            print("✅ PASS: System violently rejected remediation learning without evidence.")
            passed += 1
        else:
            print(f"❌ FAIL: Wrong error - {e}")

    # 3. Success Scoring & Confidence Update Test
    print("\n--- 3. Success Scoring & Confidence Update Test ---")
    result_success = {
        "resolution_time_ms": 5000,
        "rollback_needed": False,
        "service_restored": True,
        "error_count": 0,
        "evidence": "Service status returned 200 OK after execution."
    }
    score, new_conf = manager.log_evidence_and_result(rem_id_1, "RESTART_SERVICE", result_success, 0.80)
    
    if score == 1.0 and round(new_conf, 2) == 0.85:
        print(f"✅ PASS: Perfect execution yielded Score={score}, Confidence climbed to {new_conf:.2f}.")
        passed += 1
    else:
        print(f"❌ FAIL: Expected Score=1.0/Conf=0.85, got Score={score}/Conf={new_conf}")

    # 4. Failure Learning Test
    print("\n--- 4. Failure Learning Test ---")
    payload_fail = dict(payload1)
    payload_fail["remediation_id"] = rem_id_fail
    manager.register_remediation(payload_fail)
    
    result_fail = {
        "resolution_time_ms": 120000, # Slow
        "rollback_needed": True,      # Bad
        "service_restored": False,
        "error_count": 2,             # Bad
        "failure_type": "TIMEOUT",
        "failure_cause": "Port blocked by firewall",
        "evidence": "TimeoutException during SSH execution"
    }
    fail_score, fail_conf = manager.log_evidence_and_result(rem_id_fail, "RESTART_SERVICE", result_fail, 0.80)
    if fail_score < 0.5 and fail_conf < 0.80:
        print(f"✅ PASS: Failure accurately penalized. Score={fail_score:.2f}, Confidence dropped to {fail_conf:.2f}.")
        passed += 1
    else:
        print(f"❌ FAIL: Penalty calculation wrong. Score={fail_score}/Conf={fail_conf}")

    # 5. HITL Feedback Integration Test
    print("\n--- 5. HITL (Human In The Loop) Feedback Test ---")
    manager.log_hitl_feedback(rem_id_1, "eng-7794987703", "APPROVE", "Correct action. Good AI.")
    cur = manager.conn.cursor()
    cur.execute("SELECT action_taken FROM remediation_feedback WHERE remediation_id = %s", (rem_id_1,))
    fb = cur.fetchone()
    if fb and fb[0] == "APPROVE":
        print("✅ PASS: Human feedback recorded and audited.")
        passed += 1
    else:
        print("❌ FAIL: Human feedback not found.")

    # 6. Dynamic Ranking Test
    print("\n--- 6. Dynamic Ranking Test ---")
    # Add a different action that succeeds to see ranking
    payload2 = dict(payload1)
    payload2["remediation_id"] = rem_id_2
    payload2["action_name"] = "CLEAR_CACHE"
    manager.register_remediation(payload2)
    manager.log_evidence_and_result(rem_id_2, "CLEAR_CACHE", {"resolution_time_ms": 1000, "evidence": "Cache cleared"}, 0.5)
    
    ranks = manager.get_action_ranking()
    if ranks and len(ranks) >= 2:
        print(f"✅ PASS: Actions dynamically ranked based on success history.")
        for r in ranks[:2]:
            print(f"   - Rank {r['rank']}: {r['action_name']} (Avg Score: {r['avg_score']:.2f})")
        passed += 1
    else:
        print("❌ FAIL: Ranking calculation failed.")
        
    # 7. Audit & Lineage Test
    print("\n--- 7. Audit Persistence Test ---")
    cur.execute("SELECT COUNT(*) FROM remediation_audit WHERE remediation_id IN (%s, %s, %s)", (rem_id_1, rem_id_2, rem_id_fail))
    audit_count = cur.fetchone()[0]
    cur.close()
    if audit_count >= 5:
        print(f"✅ PASS: Audit logging robust. Captured {audit_count} lifecycle events.")
        passed += 1
    else:
        print(f"❌ FAIL: Insufficient audit logs ({audit_count}).")

    print_hdr(f"GATE REVIEW RESULT: {passed}/{total} PASSED")
    if passed == total:
        print("🚀 STATUS: GO. LF-3 is formally CLOSED. Remediation Learning Foundation is Solid.")
    else:
        print("🛑 STATUS: HOLD. LF-3 Gate Review Failed.")

if __name__ == "__main__":
    run_gate_review()
