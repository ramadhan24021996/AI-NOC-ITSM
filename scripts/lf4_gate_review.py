#!/usr/bin/env python3
import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../SERVER/python_ai_core/learning')))

def print_hdr(msg):
    print(f"\n==================================================")
    print(f" {msg}")
    print(f"==================================================")

def run_gate_review():
    print_hdr("LF-4 MANDATORY GATE REVIEW (INFRASTRUCTURE LEARNING)")
    passed = 0
    total = 5
    
    DB_CONFIG = {
        "host": "localhost",
        "port": 5433,
        "database": "osi_system",
        "user": "postgres",
        "password": "SecurePassword_123!"
    }
    
    from infrastructure.services.manager import InfrastructureLearningManager
    manager = InfrastructureLearningManager(DB_CONFIG)
    
    dev_id = "rt-core-01"

    # Clean DB
    cur = manager.conn.cursor()
    cur.execute("DELETE FROM infra_audit WHERE device_id = %s", (dev_id,))
    cur.execute("DELETE FROM infra_degradation_history WHERE device_id = %s", (dev_id,))
    cur.execute("DELETE FROM infra_patterns WHERE device_id = %s", (dev_id,))
    cur.execute("DELETE FROM infra_baseline WHERE device_id = %s", (dev_id,))
    cur.execute("DELETE FROM infra_registry WHERE device_id = %s", (dev_id,))
    cur.close()

    # 1. Infrastructure Registry Test
    print("\n--- 1. Infrastructure Registry Test ---")
    try:
        manager.register_device(dev_id, "Core-Router-Jkt", "Cisco", "Router")
        print("✅ PASS: Infrastructure device successfully registered.")
        passed += 1
    except Exception as e:
        print(f"❌ FAIL: {e}")

    # 2. Baseline Calculation Test
    print("\n--- 2. Mathematical Baseline Test ---")
    try:
        cpu_metrics = [10.5, 12.0, 11.2, 15.0, 45.0, 10.1, 9.8, 12.5, 14.1, 13.0]
        manager.update_baseline(dev_id, "CPU_USAGE", cpu_metrics)
        
        cur = manager.conn.cursor()
        cur.execute("SELECT avg_value, p95_value FROM infra_baseline WHERE device_id = %s AND metric_name = %s", (dev_id, "CPU_USAGE"))
        avg_val, p95_val = cur.fetchone()
        cur.close()
        
        if avg_val > 10 and p95_val >= 15.0:
            print(f"✅ PASS: Baseline built properly. Avg={avg_val:.2f}, P95={p95_val:.2f}.")
            passed += 1
        else:
            print(f"❌ FAIL: Baseline calculation wrong. Avg={avg_val}, P95={p95_val}")
    except Exception as e:
        print(f"❌ FAIL: {e}")

    # 3. Pattern Recognition Test (Trend/Seasonality/Correlation)
    print("\n--- 3. Pattern Recognition Logging Test ---")
    try:
        manager.log_pattern(dev_id, "CORRELATION", "CPU spikes when BGP Interface Errors > 5", 0.92)
        manager.log_pattern(dev_id, "SEASONALITY", "Backup load causes CPU > 80% at 02:00 AM daily", 0.99)
        manager.log_pattern(dev_id, "TREND", "Memory usage increasing by 2% daily (Memory Leak)", 0.85)
        
        cur = manager.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM infra_patterns WHERE device_id = %s", (dev_id,))
        count = cur.fetchone()[0]
        cur.close()
        
        if count == 3:
            print("✅ PASS: Trend, Seasonality, and Correlation patterns successfully stored.")
            passed += 1
        else:
            print(f"❌ FAIL: Expected 3 patterns, got {count}.")
    except Exception as e:
        print(f"❌ FAIL: {e}")

    # 4. Degradation History & Timeline Test
    print("\n--- 4. Degradation Timeline Test ---")
    try:
        now = datetime.now()
        manager.log_degradation(dev_id, "LATENCY", now - timedelta(minutes=15), now, "CRITICAL", 450.5)
        
        cur = manager.conn.cursor()
        cur.execute("SELECT severity, peak_value FROM infra_degradation_history WHERE device_id = %s", (dev_id,))
        sev, peak = cur.fetchone()
        cur.close()
        
        if sev == "CRITICAL" and peak == 450.5:
            print("✅ PASS: Degradation event added to infrastructure timeline.")
            passed += 1
        else:
            print("❌ FAIL: Degradation mismatch.")
    except Exception as e:
        print(f"❌ FAIL: {e}")

    # 5. Audit & Health Metrics
    print("\n--- 5. Audit Persistence Test ---")
    try:
        cur = manager.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM infra_audit WHERE device_id = %s", (dev_id,))
        count = cur.fetchone()[0]
        cur.close()
        if count >= 2:
            print(f"✅ PASS: Infrastructure learning audited properly ({count} events).")
            passed += 1
        else:
            print(f"❌ FAIL: Audit events missing.")
    except Exception as e:
        print(f"❌ FAIL: {e}")

    print_hdr(f"GATE REVIEW RESULT: {passed}/{total} PASSED")
    if passed == total:
        print("🚀 STATUS: GO. LF-4 is formally CLOSED. Infrastructure Learning active.")
    else:
        print("🛑 STATUS: HOLD. LF-4 Gate Review Failed.")

if __name__ == "__main__":
    run_gate_review()
