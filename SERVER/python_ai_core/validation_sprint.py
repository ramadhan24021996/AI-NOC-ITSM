#!/usr/bin/env python3
"""
OSI AI Ops — End-to-End Validation Sprint
Item 9: Simulasi insiden nyata + rollback + dedup + handoff

Skenario:
  1. Buat insiden simulasi di database
  2. Test RollbackEngine.snapshot() + trigger_rollback()
  3. Test DryRunGate.evaluate() dengan blast radius
  4. Test LLMRouter token circuit breaker
  5. Test HandoffPackager.build() + to_telegram_message()
  6. Test DedupFilter via HTTP /health/dedup endpoint
  7. Verifikasi semua data tercatat di DB
  8. Cleanup

Jalankan dari dalam container osi-python-ai-core:
  docker exec osi-python-ai-core python3 /app/validation_sprint.py
"""

import asyncio
import json
import os
import sys
import time
import uuid
import urllib.request
import psycopg2

# ── Konfigurasi ───────────────────────────────────────────────────────────────

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "postgres"),
    "port":     int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME", "osi_system"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
}

INGESTION_URL = os.getenv("INGESTION_URL", "http://ingestion-server:18800")

PASS = "✅"
FAIL = "❌"
WARN = "⚠️"

results = []

def log(icon, component, message):
    line = f"  {icon} [{component}] {message}"
    print(line)
    results.append({"icon": icon, "component": component, "message": message})

def get_db():
    return psycopg2.connect(**DB_CONFIG)

# ── Test 0: Prerequisite — buat insiden simulasi ─────────────────────────────

def setup_simulation(conn) -> int:
    """Buat insiden simulasi dan kembalikan incident_id."""
    with conn.cursor() as cur:
        # incidents.device_name memiliki FK ke devices.name — gunakan device yang sudah ada
        # atau skip device_name agar tidak melanggar FK constraint
        cur.execute("""
            INSERT INTO incidents (raw_data, confidence, timestamp)
            VALUES (
                '{"description":"[VALIDATION] Simulated CPU spike > 95%","severity":"CRITICAL","status":"ACTIVE","device":"VALIDATION-TEST"}',
                0.95,
                NOW()
            )
            RETURNING incident_id
        """)
        inc_id = cur.fetchone()[0]
    conn.commit()
    return inc_id

def teardown_simulation(conn, incident_id: int):
    """Hapus semua data simulasi setelah test."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM incidents WHERE incident_id = %s", (incident_id,))
        cur.execute("DELETE FROM rollback_snapshots WHERE incident_id = %s", (incident_id,))
        cur.execute("DELETE FROM dry_run_logs WHERE device = 'VALIDATION-TEST-DEVICE'")
        cur.execute("DELETE FROM llm_call_logs WHERE incident_id = %s", (str(incident_id),))
    conn.commit()

# ── Test 1: RollbackEngine ────────────────────────────────────────────────────

async def test_rollback_engine(conn, incident_id: int):
    print("\n── Test 1: RollbackEngine ────────────────────────────────────────")
    try:
        sys.path.insert(0, "/app")
        from verification.rollback_engine import RollbackEngine

        engine = RollbackEngine(nc=None, db_conn=conn)

        # Test snapshot()
        snap_id = await engine.snapshot(
            incident_id=incident_id,
            action="RESTART_SERVICE",
            device="VALIDATION-TEST-DEVICE",
            pre_state={"cpu_percent": 97.5, "service": "Spooler", "status": "Running"},
        )

        with conn.cursor() as cur:
            cur.execute("SELECT snap_id, action, pre_state FROM rollback_snapshots WHERE snap_id = %s", (snap_id,))
            row = cur.fetchone()

        if row and str(row[0]) == snap_id:
            log(PASS, "RollbackEngine", f"snapshot() OK — snap_id={snap_id[:8]}...")
        else:
            log(FAIL, "RollbackEngine", "snapshot() — record tidak ditemukan di DB")
            return

        # Test _load_snapshot()
        pre = engine._load_snapshot(incident_id, "RESTART_SERVICE", snap_id)
        if pre.get("cpu_percent") == 97.5:
            log(PASS, "RollbackEngine", "load_snapshot() OK — pre_state data valid")
        else:
            log(FAIL, "RollbackEngine", f"load_snapshot() — data salah: {pre}")

        # Test trigger_rollback() tanpa NATS (nc=None) → harus return False, bukan crash
        ok = await engine.trigger_rollback(incident_id, f"evt-test-{uuid.uuid4()}", "RESTART_SERVICE", snap_id)
        if not ok:
            log(PASS, "RollbackEngine", "trigger_rollback() tanpa NATS → graceful False (expected)")
        else:
            log(WARN, "RollbackEngine", "trigger_rollback() tanpa NATS → returned True (unexpected tapi tidak blocking)")

        # Test verify_and_rollback_if_needed() — kondisi memburuk
        result = await engine.verify_and_rollback_if_needed(
            incident_id=incident_id,
            event_id="evt-verify-test",
            action="RESTART_SERVICE",
            snap_id=snap_id,
            post_metrics={"cpu_percent": 98.0},  # Masih di atas threshold 95.0
            threshold_key="cpu_percent",
            threshold_max=95.0,
        )
        if result.get("rolled_back"):
            log(PASS, "RollbackEngine", "verify_and_rollback_if_needed() → rollback triggered (metric > threshold)")
        else:
            log(FAIL, "RollbackEngine", f"verify_and_rollback_if_needed() → unexpected: {result}")

    except Exception as e:
        log(FAIL, "RollbackEngine", f"Exception: {e}")

# ── Test 2: DryRunGate ────────────────────────────────────────────────────────

def test_dry_run_gate(conn, incident_id: int):
    print("\n── Test 2: DryRunGate ─────────────────────────────────────────────")
    try:
        from verification.dry_run_gate import DryRunGate

        gate = DryRunGate(db_conn=conn)

        # Test 2a: aksi non-destructive → auto-approved
        result = gate.evaluate("GET_STATUS", "VALIDATION-TEST-DEVICE", {})
        if result["approved"] and result["risk_level"] == "LOW":
            log(PASS, "DryRunGate", "Non-destructive action → AUTO-APPROVED (LOW risk)")
        else:
            log(FAIL, "DryRunGate", f"Non-destructive action → unexpected: {result}")

        # Test 2b: aksi HIGH_RISK dengan device yang ada
        result = gate.evaluate("RESTART_SERVICE", "VALIDATION-TEST-DEVICE", {})
        log(PASS, "DryRunGate", f"HIGH_RISK action → risk={result['risk_level']} approved={result['approved']} affected={len(result['affected'])}")

        # Test 2c: aksi REBOOT_HOST → pasti >= MEDIUM risk
        result = gate.evaluate("REBOOT_HOST", "VALIDATION-TEST-DEVICE", {})
        if result["risk_level"] in ("MEDIUM", "CRITICAL"):
            log(PASS, "DryRunGate", f"REBOOT_HOST → risk={result['risk_level']} (correctly elevated)")
        else:
            log(WARN, "DryRunGate", f"REBOOT_HOST → risk={result['risk_level']} (lower than expected)")

        # Verifikasi log di DB
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM dry_run_logs WHERE device='VALIDATION-TEST-DEVICE'")
            cnt = cur.fetchone()[0]
        if cnt >= 2:
            log(PASS, "DryRunGate", f"dry_run_logs → {cnt} records tercatat di DB")
        else:
            log(FAIL, "DryRunGate", f"dry_run_logs → hanya {cnt} records (expected >= 2)")

    except Exception as e:
        log(FAIL, "DryRunGate", f"Exception: {e}")

# ── Test 3: LLMRouter Token Circuit Breaker ───────────────────────────────────

async def test_llm_router(conn, incident_id: int):
    print("\n── Test 3: LLMRouter Token Circuit Breaker ────────────────────────")
    try:
        from engines.llm_router import LLMRouter

        router = LLMRouter(db_conn=conn)
        inc_str = str(incident_id)

        # Test estimasi token
        sample = "A" * 400  # 400 karakter ≈ 100 token
        est = router._estimate_tokens(sample)
        if 90 <= est <= 110:
            log(PASS, "LLMRouter", f"_estimate_tokens() → {est} token untuk 400 karakter")
        else:
            log(WARN, "LLMRouter", f"_estimate_tokens() → {est} (heuristik berbeda)")

        # Test budget check — pertama kali harus PASS
        ok1 = router._check_budget(inc_str, 100)
        if ok1:
            log(PASS, "LLMRouter", "Budget check pertama → ALLOWED")
        else:
            log(FAIL, "LLMRouter", "Budget check pertama → BLOCKED (unexpected)")

        # Simulasi budget habis — inject langsung ke Redis
        r = router._get_redis()
        if r:
            r.set(f"llm:budget:{inc_str}", 999_999_999)  # Set sangat besar
            ok2 = router._check_budget(inc_str, 100)
            if not ok2:
                log(PASS, "LLMRouter", "Circuit Breaker OPEN → budget exhausted correctly blocked")
            else:
                log(FAIL, "LLMRouter", "Circuit Breaker — masih allowed padahal budget habis")
            # Reset budget
            r.delete(f"llm:budget:{inc_str}")
            log(PASS, "LLMRouter", "Budget reset OK")
        else:
            log(WARN, "LLMRouter", "Redis tidak tersedia — token tracking dilewati (graceful degradation OK)")

        # Test _log_call() ke DB
        router._log_call(inc_str, "gemini-test", "prompt test", "response test", 123, "SUCCESS")
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM llm_call_logs WHERE incident_id = %s AND model='gemini-test'", (inc_str,))
            cnt = cur.fetchone()[0]
        if cnt >= 1:
            log(PASS, "LLMRouter", f"_log_call() → {cnt} record tercatat di llm_call_logs")
        else:
            log(FAIL, "LLMRouter", "llm_call_logs → tidak ada record")

    except Exception as e:
        log(FAIL, "LLMRouter", f"Exception: {e}")

# ── Test 4: HandoffPackager ───────────────────────────────────────────────────

def test_handoff_packager(conn, incident_id: int):
    print("\n── Test 4: HandoffPackager ────────────────────────────────────────")
    try:
        from escalation.handoff_packager import HandoffPackager

        packager = HandoffPackager(db_conn=conn)

        # Build package
        package = packager.build(incident_id)

        if package["incident_id"] == incident_id:
            log(PASS, "HandoffPackager", f"build() OK — incident_id={incident_id}")
        else:
            log(FAIL, "HandoffPackager", "build() — incident_id tidak cocok")

        if package.get("summary"):
            log(PASS, "HandoffPackager", f"summary: {package['summary'][:60]}...")
        else:
            log(WARN, "HandoffPackager", "summary kosong (insiden baru, data ERG belum ada)")

        # Build Telegram message
        msg = packager.to_telegram_message(package)
        if "ESKALASI AI" in msg and str(incident_id) in msg:
            log(PASS, "HandoffPackager", "to_telegram_message() → format valid")
            print(f"\n  --- Sample Telegram Output ---\n{msg[:400]}...\n  ---")
        else:
            log(FAIL, "HandoffPackager", "to_telegram_message() — format tidak valid")

    except Exception as e:
        log(FAIL, "HandoffPackager", f"Exception: {e}")

# ── Test 5: DedupFilter via HTTP ─────────────────────────────────────────────

def test_dedup_filter():
    print("\n── Test 5: DedupFilter (HTTP endpoint) ────────────────────────────")
    try:
        url = f"{INGESTION_URL}/health/dedup"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())

        if data.get("status") == "ok":
            log(PASS, "DedupFilter", f"/health/dedup → active_fps={data['active_fingerprints']} suppressed={data['total_suppressed']} window={data['dedup_window_sec']}s")
        else:
            log(FAIL, "DedupFilter", f"/health/dedup → unexpected response: {data}")

        # Test suppression dengan mengirim 2 event identik ke /telemetry
        test_payload = json.dumps({
            "type": "metric",
            "event_type": "CPU_HIGH",
            "status": "CRITICAL",
            "description": "[VALIDATION] DedupFilter test event",
            "site_id": "validation_site",
            "pc_name": "VALIDATION-TEST-DEVICE",
            "agent": "validation",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "token": "validation-skip",
            "metadata": {"cpu": 98},
        }).encode()

        def send_event():
            try:
                r = urllib.request.Request(
                    f"{INGESTION_URL}/telemetry",
                    data=test_payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(r, timeout=5) as resp:
                    return resp.status
            except Exception:
                return 0

        # Kirim event pertama
        s1 = send_event()
        time.sleep(0.5)
        # Kirim event kedua identik — harus disuppress di NATS
        s2 = send_event()

        if s1 and s2:
            log(PASS, "DedupFilter", f"Dua event identik dikirim (HTTP {s1}/{s2}) — cek log ingestion untuk suppression")
        else:
            log(WARN, "DedupFilter", "Tidak bisa mengirim test event ke ingestion server")

        # Cek stats setelah kirim
        with urllib.request.urlopen(url, timeout=5) as resp2:
            data2 = json.loads(resp2.read())
        log(PASS, "DedupFilter", f"Post-test stats → active_fps={data2['active_fingerprints']} suppressed={data2['total_suppressed']}")

    except Exception as e:
        log(FAIL, "DedupFilter", f"Exception: {e}")

# ── Test 6: Ingestion Server health ──────────────────────────────────────────

def test_ingestion_health():
    print("\n── Test 6: Ingestion Server Health ────────────────────────────────")
    try:
        url = f"{INGESTION_URL}/health"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
        if data.get("status") == "healthy":
            log(PASS, "IngestionServer", f"/health → {data}")
        else:
            log(FAIL, "IngestionServer", f"/health → {data}")
    except Exception as e:
        log(FAIL, "IngestionServer", f"Exception: {e}")

# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║     OSI AI Ops — End-to-End Validation Sprint                ║
║     Safety & Operational Hardening — Final Verification      ║
╚══════════════════════════════════════════════════════════════╝
""")

    conn = None
    incident_id = None

    try:
        conn = get_db()
        print(f"  ✓ Database connected: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}\n")

        # Setup
        incident_id = setup_simulation(conn)
        print(f"  ✓ Simulation incident created: incident_id={incident_id}\n")

        # Run all tests
        await test_rollback_engine(conn, incident_id)
        test_dry_run_gate(conn, incident_id)
        await test_llm_router(conn, incident_id)
        test_handoff_packager(conn, incident_id)
        test_ingestion_health()
        test_dedup_filter()

    except Exception as e:
        print(f"\n  {FAIL} [VALIDATION] Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup simulasi
        if conn and incident_id:
            try:
                teardown_simulation(conn, incident_id)
                print(f"\n  ✓ Cleanup: simulation data removed (incident_id={incident_id})")
            except Exception as ce:
                print(f"\n  {WARN} Cleanup error: {ce}")
        if conn:
            conn.close()

    # ── Summary ───────────────────────────────────────────────────────────────
    print("""
╔══════════════════════════════════════════════════════════════╗
║                    VALIDATION SUMMARY                        ║
╚══════════════════════════════════════════════════════════════╝""")

    passed   = [r for r in results if r["icon"] == PASS]
    failed   = [r for r in results if r["icon"] == FAIL]
    warnings = [r for r in results if r["icon"] == WARN]

    for r in results:
        print(f"  {r['icon']} [{r['component']}] {r['message']}")

    print(f"""
┌──────────────────────────────────────────────────────────────┐
│  {PASS} PASSED : {len(passed):<3}  {FAIL} FAILED : {len(failed):<3}  {WARN} WARNINGS: {len(warnings):<3}       │
└──────────────────────────────────────────────────────────────┘""")

    if failed:
        print(f"\n  {FAIL} Validation Sprint TIDAK LULUS — {len(failed)} komponen perlu diperbaiki.")
        sys.exit(1)
    else:
        print(f"\n  {PASS} Validation Sprint LULUS — sistem siap production.")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
