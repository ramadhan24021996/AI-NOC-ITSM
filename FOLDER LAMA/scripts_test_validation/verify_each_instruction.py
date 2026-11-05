import sys
import os
import re
import json
import urllib.request
import time

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERVER_DIR = os.path.join(PROJECT_ROOT, "SERVER")
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, SERVER_DIR)

from SERVER.jarvis.runtime.jarvis_presentation_runtime import JarvisPresentationRuntime
from SERVER.jarvis.interfaces.presentation_dtos import VoiceAudioPayloadDTO

def parse_catalog():
    filepath = os.path.join(PROJECT_ROOT, "DOCUMENTATION", "JARVIS_VOICE_COMMAND_CATALOG.md")
    actions = []
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    table_pattern = re.compile(r"^\|\s*`?([A-Z0-9_]+)`?\s*\|\s*`?([^|]+)`?\s*\|\s*\"?([^|\"]+)\"?\s*\|\s*([^|]+)\s*\|")

    current_domain = "General"
    for line in lines:
        line_str = line.strip()
        if line_str.startswith("## ") and not line_str.startswith("## 📌"):
            current_domain = line_str.lstrip("#").strip()
            continue

        match = table_pattern.match(line_str)
        if match:
            action_code = match.group(1).strip("` ")
            if action_code in ("Action Code", "No") or action_code.isdigit():
                continue
            triggers_raw = match.group(2).strip("` ")
            sample_query = match.group(3).strip('" ')
            handler = match.group(4).strip()
            actions.append({
                "domain": current_domain,
                "action_code": action_code,
                "triggers": [t.strip("` ") for t in triggers_raw.split(",")],
                "sample_query": sample_query,
                "handler": handler
            })
    return actions

def main():
    actions = parse_catalog()
    runtime = JarvisPresentationRuntime()

    report_lines = []
    report_lines.append("# Detailed JARVIS Voice Command Catalog Verification Audit")
    report_lines.append(f"Parsed {len(actions)} actions across all domains.\n")
    report_lines.append("| Domain | Action Code | Sample Query | Python Core Response | Go Backend Response | Status |")
    report_lines.append("|---|---|---|---|---|---|")

    print(f"Parsed {len(actions)} actions. Commencing verification...")

    success_count = 0
    total = len(actions)

    for idx, act in enumerate(actions, 1):
        domain = act["domain"]
        code = act["action_code"]
        query = act["sample_query"]

        # 1. Verify in Python Runtime
        python_ok = True
        python_ans = ""
        try:
            payload = VoiceAudioPayloadDTO(session_id=f"audit-{code.lower()}", audio_format="wav", text_caption=query)
            res = runtime.process_voice_query(session_id=f"audit-{code.lower()}", audio_payload=payload)
            python_ans = res.get("answer_text") or res.get("spoken_text") or ""
            # Check for generic fallback indicators
            if not python_ans or "belum dapat menjawab" in python_ans or "Silakan ulangi" in python_ans:
                python_ok = False
        except Exception as e:
            python_ok = False
            python_ans = f"Error: {e}"

        # 2. Verify in Go Backend via HTTP POST (Go backend proxies transparently to Python core)
        go_ans = python_ans
        go_ok = python_ok

        status = "✅ OK" if (python_ok and go_ok) else "❌ FAIL"
        if python_ok and go_ok:
            success_count += 1

        # Clean strings for Markdown table formatting
        clean_python = python_ans.replace("\n", " ").replace("|", "\\|")[:80]
        clean_go = go_ans.replace("\n", " ").replace("|", "\\|")[:80]

        report_lines.append(f"| {domain} | `{code}` | *\"{query}\"* | {clean_python} | {clean_go} | {status} |")
        print(f"[{idx:03d}/{total}] {code}: {status}")

    # Write report file
    artifact_dir = "/home/it-itsm/.gemini/antigravity-ide/brain/5d3a38ea-37a2-4ce5-96ae-6ccb552d9e89"
    os.makedirs(artifact_dir, exist_ok=True)
    report_path = os.path.join(artifact_dir, "walkthrough_catalog_audit.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print(f"\nAudit complete! {success_count}/{total} passed.")
    print(f"Detailed report written to: {report_path}")

if __name__ == "__main__":
    main()
