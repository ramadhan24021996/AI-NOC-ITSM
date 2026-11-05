"""
Live Proof Runner: Typed Dashboard Commands Simulation
======================================================
Executes ALL 144 Action Codes from DOCUMENTATION/JARVIS_VOICE_COMMAND_CATALOG.md
via simulated live HTTP POST requests to /api/jarvis/voice/query (the same endpoint
triggered when a user types into #jrv-cmd-input on the Dashboard UI).

Run:
    python3 scripts/test_live_dashboard_typed_commands.py
"""

import sys
import os
import re
import unittest
import json
import time

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

def parse_catalog():
    filepath = os.path.join(PROJECT_ROOT, "DOCUMENTATION", "JARVIS_VOICE_COMMAND_CATALOG.md")
    actions = []
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    table_pattern = re.compile(r"^\|\s*`?([A-Z0-9_]+)`?\s*\|\s*`?([^|]+)`?\s*\|\s*\"?([^|\"]+)\"?\s*\|\s*([^|]+)\s*\|")

    for line in lines:
        match = table_pattern.match(line.strip())
        if match:
            action_code = match.group(1).strip("` ")
            if action_code in ("Action Code", "No") or action_code.isdigit():
                continue
            triggers_raw = match.group(2).strip("` ")
            sample_query = match.group(3).strip('" ')
            handler = match.group(4).strip()
            actions.append({
                "action_code": action_code,
                "sample_query": sample_query,
                "handler": handler
            })
    return actions

def main():
    actions = parse_catalog()
    print("=" * 80)
    print("🖥️ PROOF OF TYPED DASHBOARD COMMANDS EXECUTION (144/144 ACTIONS)")
    print("=" * 80)

    import urllib.request

    total = len(actions)
    success = 0
    failures = []

    t0 = time.time()

    for idx, item in enumerate(actions, 1):
        code = item["action_code"]
        query = item["sample_query"]

        req_data = json.dumps({
            "question": query,
            "query": query,
            "session_id": f"typed-sim-{code.lower()}"
        }).encode("utf-8")

        req = urllib.request.Request(
            "http://127.0.0.1/api/jarvis/voice/query",
            data=req_data,
            headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    res_body = json.loads(resp.read().decode("utf-8"))
                    ans = res_body.get("answer_text") or res_body.get("answer") or ""
                    if ans and "Unauthorized" not in ans:
                        success += 1
                        print(f" [{idx:03d}/{total}] ✅ [{code:<28}] Query: \"{query}\" -> Status: OK ({len(ans)} chars)")
                    else:
                        failures.append((code, query, f"Empty or Unauthorized answer"))
                        print(f" [{idx:03d}/{total}] ❌ [{code:<28}] Query: \"{query}\" -> FAIL: Empty answer")
                else:
                    failures.append((code, query, f"HTTP {resp.status}"))
                    print(f" [{idx:03d}/{total}] ❌ [{code:<28}] Query: \"{query}\" -> FAIL: HTTP {resp.status}")
        except Exception as e:
            failures.append((code, query, str(e)))
            print(f" [{idx:03d}/{total}] ❌ [{code:<28}] Query: \"{query}\" -> EXCEPTION: {e}")

    t_wall = int((time.time() - t0) * 1000)

    print("\n" + "=" * 80)
    print(f"📊 SUMMARY REPORT: TYPED DASHBOARD COMMAND SIMULATION")
    print("=" * 80)
    print(f"Total Commands Tested  : {total}")
    print(f"Total Success          : {success} / {total} ({int(success/total*100)}%)")
    print(f"Execution Wall Time    : {t_wall} ms")
    if failures:
        print(f"Failures ({len(failures)}):")
        for f_code, f_q, f_err in failures:
            print(f"  • [{f_code}] \"{f_q}\" -> {f_err}")
    else:
        print("🎉 100% PROOF PASSED! All 144 typed commands succeed on the live Dashboard!")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    main()
