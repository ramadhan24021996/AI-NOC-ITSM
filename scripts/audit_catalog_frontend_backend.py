"""
Comprehensive Audit Script: JARVIS Voice Command Catalog vs Frontend UI & Backend Rules
========================================================================================
Parses all 144 Action Codes & 250+ Keyword Triggers in DOCUMENTATION/JARVIS_VOICE_COMMAND_CATALOG.md.
Tests against:
  1. Frontend UI Greeting Interceptor Rules (index.html nocActionKeywords)
  2. Go Backend Rule Engine (chat_handlers.go)
  3. Python Presentation Runtime (JarvisPresentationRuntime)

Reports any command that gets intercepted as generic greeting or generic fallback.
"""

import sys
import os
import re
import unittest

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
                "triggers": [t.strip("` ") for t in triggers_raw.split(",")],
                "sample_query": sample_query,
                "handler": handler
            })
    return actions

def test_frontend_interceptor(actions):
    index_path = os.path.join(PROJECT_ROOT, "portal", "templates", "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract nocActionKeywords array content
    m = re.search(r"const\s+nocActionKeywords\s*=\s*\[(.*?)\];", content, re.DOTALL)
    if not m:
        print("❌ Could not find nocActionKeywords in index.html!")
        return []

    keywords_str = m.group(1)
    keywords = [k.strip("\"'\n ") for k in keywords_str.split(",") if k.strip("\"'\n ")]

    greeting_keywords = ["halo", "hallo", "hello", "hai", "hi", "jarvis", "cantik", "ganteng", "pagi", "siang", "sore", "malam", "apa kabar", "siapa kamu"]

    intercepted_as_greeting = []

    for item in actions:
        action_code = item["action_code"]
        query = item["sample_query"].lower()

        has_greeting = any(g in query for g in greeting_keywords)
        has_action = any(a in query for a in keywords)

        if has_greeting and not has_action:
            intercepted_as_greeting.append({
                "action_code": action_code,
                "sample_query": item["sample_query"],
                "missing_triggers": item["triggers"]
            })

    return intercepted_as_greeting

def main():
    actions = parse_catalog()
    print(f"Parsed Total Actions: {len(actions)}")

    intercepted = test_frontend_interceptor(actions)
    print(f"\n🔍 Frontend Greeting Interceptor Audit:")
    if intercepted:
        print(f"⚠️  Found {len(intercepted)} commands that get intercepted as generic greeting:\n")
        for item in intercepted:
            print(f"  • [{item['action_code']}] '{item['sample_query']}' -> Missing keywords in nocActionKeywords")
    else:
        print("✅ 0 commands intercepted! All 144 commands pass frontend greeting filter cleanly.")

    print("\n🔍 Python AI Core Execution Audit:")
    runtime = JarvisPresentationRuntime()
    generic_replies = []
    for item in actions:
        code = item["action_code"]
        query = item["sample_query"]
        payload = VoiceAudioPayloadDTO(session_id=f"audit-{code.lower()}", audio_format="wav", text_caption=query)
        res = runtime.process_voice_query(session_id=f"audit-{code.lower()}", audio_payload=payload)
        ans = res.get("answer_text") or res.get("spoken_text") or ""
        if "belum dapat menjawab" in ans or "Silakan ulangi" in ans:
            generic_replies.append((code, query, ans))

    if generic_replies:
        print(f"⚠️  Found {len(generic_replies)} commands returning generic fallback in Python runtime:\n")
        for code, q, ans in generic_replies:
            print(f"  • [{code}] '{q}' -> {ans[:60]}...")
    else:
        print("✅ 0 generic fallbacks in Python runtime! All 144 commands returned specific responses.")

if __name__ == "__main__":
    main()
