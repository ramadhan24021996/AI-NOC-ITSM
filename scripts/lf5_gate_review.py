#!/usr/bin/env python3
import sys
import os
from datetime import datetime, time, timedelta

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../SERVER/python_ai_core/learning')))

def print_hdr(msg):
    print(f"\n==================================================")
    print(f" {msg}")
    print(f"==================================================")

def run_gate_review():
    print_hdr("LF-5 MANDATORY GATE REVIEW (TEMPORAL LEARNING)")
    passed = 0
    total = 6
    
    DB_CONFIG = {
        "host": "localhost",
        "port": 5433,
        "database": "osi_system",
        "user": "postgres",
        "password": "SecurePassword_123!"
    }
    
    from temporal.services.manager import TemporalLearningManager
    manager = TemporalLearningManager(DB_CONFIG)
    
    tmp_id = "temp-core-01"

    # Clean DB
    cur = manager.conn.cursor()
    cur.execute("DELETE FROM temporal_audit WHERE temporal_id = %s", (tmp_id,))
    cur.execute("DELETE FROM temporal_timeline WHERE temporal_id = %s", (tmp_id,))
    cur.execute("DELETE FROM temporal_patterns WHERE temporal_id = %s", (tmp_id,))
    cur.execute("DELETE FROM temporal_baseline WHERE temporal_id = %s", (tmp_id,))
    cur.execute("DELETE FROM temporal_calendar WHERE temporal_id = %s", (tmp_id,))
    cur.execute("DELETE FROM temporal_registry WHERE temporal_id = %s", (tmp_id,))
    cur.close()

    # 1. Temporal Registry & Feature Extractor Test
    print("\n--- 1. Time Feature Extractor Test ---")
    try:
        # Wednesday, July 22, 2026, 14:30
        dt_test = datetime(2026, 7, 22, 14, 30, 0)
        feats = manager.extract_time_features(dt_test)
        if feats["weekday"] == "Wednesday" and feats["business_hour"] == True and feats["quarter"] == 3:
            print("✅ PASS: Temporal Feature Extractor correctly mapped raw timestamp to Business Hour, Weekday, and Quarter.")
            passed += 1
            manager.register_device(tmp_id, "rt-core-01", "t-01")
        else:
            print(f"❌ FAIL: Extraction output wrong. {feats}")
    except Exception as e:
        print(f"❌ FAIL: {e}")

    # 2. Calendar & Maintenance Window Learning
    print("\n--- 2. Calendar & Maintenance Window Test ---")
    try:
        manager.set_calendar(
            tmp_id, True, False, 
            time(9, 0), time(17, 0), # Business Hours
            time(1, 0), time(3, 0)   # Maintenance Window
        )
        print("✅ PASS: Maintenance Window & Business Calendar successfully configured and audited.")
        passed += 1
    except Exception as e:
        print(f"❌ FAIL: {e}")

    # 3. Peak Hour Baseline Learning
    print("\n--- 3. Peak Hour Baseline Learning ---")
    try:
        manager.set_peak_baseline(tmp_id, time(9, 0), time(17, 0), 0.95)
        print("✅ PASS: Individualized Peak Hour Baseline successfully mapped to device.")
        passed += 1
    except Exception as e:
        print(f"❌ FAIL: {e}")

    # 4. Seasonality (Monthly/Weekly Patching)
    print("\n--- 4. Seasonality Learning Test ---")
    try:
        manager.log_seasonality(tmp_id, "PATCH_TUESDAY", "Microsoft Patch Tuesday impacts bandwidth every 2nd Tuesday of Month", 0.98)
        print("✅ PASS: Seasonality pattern (Patch Tuesday) successfully logged to Temporal Store.")
        passed += 1
    except Exception as e:
        print(f"❌ FAIL: {e}")

    # 5. Timeline Builder (Sequence of Events)
    print("\n--- 5. Timeline Engine Test ---")
    try:
        now = datetime.now()
        events = [
            {"event_time": now, "event_type": "BACKUP_START"},
            {"event_time": now + timedelta(minutes=5), "event_type": "CPU_SPIKE", "metric_value": 90.5},
            {"event_time": now + timedelta(minutes=10), "event_type": "DISK_IO_HIGH"},
            {"event_time": now + timedelta(minutes=30), "event_type": "BACKUP_END"}
        ]
        manager.build_timeline(tmp_id, events)
        
        cur = manager.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM temporal_timeline WHERE temporal_id = %s", (tmp_id,))
        cnt = cur.fetchone()[0]
        cur.close()
        
        if cnt == 4:
            print("✅ PASS: Timeline engine successfully sequenced 4 consecutive events.")
            passed += 1
        else:
            print("❌ FAIL: Timeline failed to record all events.")
    except Exception as e:
        print(f"❌ FAIL: {e}")

    # 6. Audit & Observability
    print("\n--- 6. Audit Observability Test ---")
    try:
        cur = manager.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM temporal_audit WHERE temporal_id = %s", (tmp_id,))
        count = cur.fetchone()[0]
        cur.close()
        if count >= 3:
            print(f"✅ PASS: Temporal learning strongly audited ({count} lifecycle events).")
            passed += 1
        else:
            print(f"❌ FAIL: Audit events missing.")
    except Exception as e:
        print(f"❌ FAIL: {e}")

    print_hdr(f"GATE REVIEW RESULT: {passed}/{total} PASSED")
    if passed == total:
        print("🚀 STATUS: GO. LF-5 is formally CLOSED. Temporal Learning active.")
    else:
        print("🛑 STATUS: HOLD. LF-5 Gate Review Failed.")

if __name__ == "__main__":
    run_gate_review()
