#!/usr/bin/env python3
"""
Comprehensive Frontend, Dashboard, Menu, Icon, and Unicode Audit Tool
For Mega Kreasi Tech NOC IT AI Incident Analysis Portal
"""

import os
import re
import sys
import json
import glob
import subprocess
from html.parser import HTMLParser

BASE_DIR = "/home/it-itsm/AI/incident-analysis"
PORTAL_DIR = os.path.join(BASE_DIR, "portal")
TEMPLATES_DIR = os.path.join(PORTAL_DIR, "templates")
STATIC_DIR = os.path.join(PORTAL_DIR, "static")
JS_DIR = os.path.join(STATIC_DIR, "js")
CSS_DIR = os.path.join(STATIC_DIR, "css")

results = {
    "menus": {"total": 0, "valid": 0, "broken": [], "details": []},
    "panels": {"dom_panels": [], "orphaned": [], "missing_dom": []},
    "icons": {"total_fa": 0, "fa_classes": set(), "suspicious_icons": [], "svg_count": 0, "svg_errors": []},
    "unicode": {"total_files_scanned": 0, "mojibake_found": [], "invalid_utf8": [], "special_chars_stats": {}},
    "onclick_handlers": {"total": 0, "missing_functions": [], "found_functions": set()},
    "js_syntax": {"errors": [], "files_checked": 0},
    "css_audit": {"errors": [], "missing_vars": []},
    "extension_audit": {"errors": []}
}

print("=" * 80)
print("1. COMPILING / CHECKING index.html ASSEMBLY")
print("=" * 80)

# Check assemble.sh
assemble_sh = os.path.join(TEMPLATES_DIR, "assemble.sh")
index_html = os.path.join(TEMPLATES_DIR, "index.html")

if os.path.exists(assemble_sh):
    res = subprocess.run(["bash", assemble_sh], cwd=TEMPLATES_DIR, capture_output=True, text=True)
    print(f"assemble.sh output: {res.stdout.strip()}")
    if res.returncode != 0:
        print(f"assemble.sh ERROR: {res.stderr}")

if os.path.exists(index_html):
    print(f"index.html exists: {os.path.getsize(index_html)} bytes")
else:
    print("CRITICAL: index.html not found!")

index_content = ""
with open(index_html, "r", encoding="utf-8", errors="replace") as f:
    index_content = f.read()

# Extract all panels in index.html: <div class="panel..." id="p-...">
dom_panel_ids = re.findall(r'<div[^>]*class="[^"]*panel[^"]*"[^>]*id="p-([^"]+)"', index_content)
dom_panel_ids += re.findall(r'<div[^>]*id="p-([^"]+)"[^>]*class="[^"]*panel[^"]*"', index_content)
dom_panel_ids = sorted(list(set(dom_panel_ids)))
results["panels"]["dom_panels"] = dom_panel_ids
print(f"Found {len(dom_panel_ids)} DOM panels in index.html: {dom_panel_ids}")

# Extract sidebar menus
sidebar_html_path = os.path.join(TEMPLATES_DIR, "layouts", "sidebar.html")
with open(sidebar_html_path, "r", encoding="utf-8") as f:
    sidebar_content = f.read()

# Find all data-panel="..."
sidebar_panels = re.findall(r'data-panel="([^"]+)"', sidebar_content)
# Also find all Nav.go('...') calls
nav_go_calls = re.findall(r"Nav\.go\('([^']+)'", index_content)
nav_go_calls += re.findall(r'Nav\.go\("([^"]+)"', index_content)
nav_go_calls = sorted(list(set(nav_go_calls)))

print(f"\nSidebar items ({len(sidebar_panels)}): {sidebar_panels}")
print(f"All Nav.go calls across codebase ({len(nav_go_calls)}): {nav_go_calls}")

# Check navigation consistency
for sp in sidebar_panels:
    results["menus"]["total"] += 1
    if sp in dom_panel_ids:
        results["menus"]["valid"] += 1
        results["menus"]["details"].append({"panel": sp, "status": "OK", "has_dom": True})
    else:
        results["menus"]["broken"].append(sp)
        results["menus"]["details"].append({"panel": sp, "status": "MISSING_DOM", "has_dom": False})

for ng in nav_go_calls:
    if ng not in dom_panel_ids and ng not in ["dashboard", "overview"]: # dashboard is alias of overview
        results["panels"]["missing_dom"].append(ng)

# Check orphaned DOM panels
for dp in dom_panel_ids:
    if dp not in sidebar_panels and dp not in nav_go_calls:
        results["panels"]["orphaned"].append(dp)

print(f"\nMenu Audit: {results['menus']['valid']}/{results['menus']['total']} sidebar menu items match DOM panels.")
if results["menus"]["broken"]:
    print(f"WARNING: Broken sidebar menu items: {results['menus']['broken']}")
if results["panels"]["missing_dom"]:
    print(f"WARNING: Nav.go targets missing DOM #p-...: {set(results['panels']['missing_dom'])}")

# Check nav.js titles and subs
nav_js_path = os.path.join(JS_DIR, "core", "nav.js")
with open(nav_js_path, "r", encoding="utf-8") as f:
    nav_js_content = f.read()

nav_titles = re.findall(r'([a-zA-Z0-9_-]+)\s*:\s*\'<i class="', nav_js_content)
nav_subs = re.findall(r'([a-zA-Z0-9_-]+)\s*:\s*\'[^\']+\'', nav_js_content)

print(f"nav.js defined titles for {len(nav_titles)} panels.")

# ==============================================================================
# 2. ICON AUDIT
# ==============================================================================
print("\n" + "=" * 80)
print("2. FONT AWESOME & SVG ICON AUDIT")
print("=" * 80)

# Extract all font awesome classes
fa_matches = re.findall(r'<i[^>]*class="([^"]*fa-[^"]*)"', index_content)
for fam in fa_matches:
    results["icons"]["total_fa"] += 1
    classes = fam.split()
    for c in classes:
        if c.startswith("fa-") and not c in ["fa-solid", "fa-regular", "fa-brands", "fa-xs", "fa-sm", "fa-lg", "fa-xl", "fa-2x", "fa-3x", "fa-spin", "fa-pulse", "fa-fw"]:
            results["icons"]["fa_classes"].add(c)

print(f"Total FontAwesome <i> usages: {results['icons']['total_fa']}")
print(f"Unique FontAwesome icon classes: {len(results['icons']['fa_classes'])}")

# Check against Font Awesome 6 free icon database or verify standard names
# Let's inspect some potentially uncommon icon names
print("Unique FA icon names sample:")
print(sorted(list(results["icons"]["fa_classes"])))

# Check SVG elements
svg_matches = re.findall(r'<svg[^>]*>.*?</svg>', index_content, re.DOTALL)
results["icons"]["svg_count"] = len(svg_matches)
print(f"Inline SVG count: {len(svg_matches)}")

for i, svg in enumerate(svg_matches):
    if 'viewBox="' not in svg and "viewbox=" not in svg and "width=" not in svg:
        results["icons"]["svg_errors"].append(f"SVG #{i} missing viewBox or width")

# ==============================================================================
# 3. UNICODE & CHARACTER ENCODING AUDIT
# ==============================================================================
print("\n" + "=" * 80)
print("3. UNICODE, ENCODING & MOJIBAKE AUDIT")
print("=" * 80)

# Mojibake regex patterns (UTF-8 decoded as Latin-1/Windows-1252)
mojibake_pattern = re.compile(r'(?:Ã[\x80-\xbf]|â€[\x98-\x9f\x90-\x95]|â€”|â€“|Â©|Â®|Â°|Ã©|Ã¨|Ã¡|Ã±|Ã§|\ufffd)')

files_to_scan = []
for root, dirs, files in os.walk(PORTAL_DIR):
    for file in files:
        if file.endswith((".html", ".js", ".css", ".json", ".md")):
            files_to_scan.append(os.path.join(root, file))

for root, dirs, files in os.walk(os.path.join(BASE_DIR, "CLIENT_DISTRIBUSI_GO", "browser_extension")):
    for file in files:
        if file.endswith((".html", ".js", ".css", ".json")):
            files_to_scan.append(os.path.join(root, file))

results["unicode"]["total_files_scanned"] = len(files_to_scan)

special_chars = {
    "emojis": 0,
    "arrows": 0,
    "bullets_dots": 0,
    "dashes": 0,
    "quotes": 0
}

for filepath in files_to_scan:
    # 1. Test binary utf-8 decoding
    try:
        with open(filepath, "rb") as bf:
            raw_bytes = bf.read()
            raw_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as e:
        results["unicode"]["invalid_utf8"].append({"file": filepath, "error": str(e)})
        continue

    # 2. Search for mojibake
    mojibake_matches = mojibake_pattern.findall(raw_text)
    if mojibake_matches:
        results["unicode"]["mojibake_found"].append({"file": filepath, "matches": mojibake_matches[:5], "count": len(mojibake_matches)})

    # Count unicode usage
    special_chars["emojis"] += len(re.findall(r'[\U00010000-\U0010ffff]', raw_text))
    special_chars["arrows"] += len(re.findall(r'[→←↑↓↔↕➔➜➤►▼▲◄]', raw_text))
    special_chars["bullets_dots"] += len(re.findall(r'[·•●○■□▪▫]', raw_text))
    special_chars["dashes"] += len(re.findall(r'[—–―]', raw_text))

results["unicode"]["special_chars_stats"] = special_chars
print(f"Scanned {len(files_to_scan)} files for UTF-8 and Unicode validity.")
print(f"Invalid UTF-8 files: {len(results['unicode']['invalid_utf8'])}")
print(f"Mojibake artifacts found in: {len(results['unicode']['mojibake_found'])} files")
if results["unicode"]["mojibake_found"]:
    for m in results["unicode"]["mojibake_found"]:
        print(f"  - {m['file']} ({m['count']} matches: {m['matches']})")

print(f"Unicode character statistics across frontend: {special_chars}")

# ==============================================================================
# 4. JAVASCRIPT SYNTAX & EVENT HANDLER AUDIT
# ==============================================================================
print("\n" + "=" * 80)
print("4. JAVASCRIPT SYNTAX & EVENT HANDLERS")
print("=" * 80)

# Check JS syntax with node --check
js_files = glob.glob(f"{JS_DIR}/**/*.js", recursive=True)
results["js_syntax"]["files_checked"] = len(js_files)

for jsf in js_files:
    res = subprocess.run(["node", "--check", jsf], capture_output=True, text=True)
    if res.returncode != 0:
        results["js_syntax"]["errors"].append({"file": jsf, "error": res.stderr.strip()})

print(f"Checked {len(js_files)} JS files with node --check.")
print(f"JS syntax errors: {len(results['js_syntax']['errors'])}")
if results["js_syntax"]["errors"]:
    for err in results["js_syntax"]["errors"]:
        print(f"  - {err['file']}: {err['error']}")

# Find all inline event handlers in index.html (onclick, onchange, onsubmit, onkeyup, etc.)
event_handlers = re.findall(r'\s(on[a-z]+)="([^"]+)"', index_content)
results["onclick_handlers"]["total"] = len(event_handlers)
print(f"Total inline event handlers in index.html: {len(event_handlers)}")

# Extract function names from handlers
all_js_code = ""
for jsf in js_files:
    with open(jsf, "r", encoding="utf-8", errors="replace") as f:
        all_js_code += "\n" + f.read()

# Also include scripts in index.html
inline_scripts = re.findall(r'<script>(.*?)</script>', index_content, re.DOTALL)
all_js_code += "\n".join(inline_scripts)

# Extract declared function names in JS
declared_functions = set(re.findall(r'function\s+([a-zA-Z0-9_$]+)\s*\(', all_js_code))
declared_functions.update(re.findall(r'window\.([a-zA-Z0-9_$]+)\s*=', all_js_code))
declared_functions.update(re.findall(r'var\s+([a-zA-Z0-9_$]+)\s*=', all_js_code))
declared_functions.update(re.findall(r'let\s+([a-zA-Z0-9_$]+)\s*=', all_js_code))
declared_functions.update(re.findall(r'const\s+([a-zA-Z0-9_$]+)\s*=', all_js_code))

print(f"Identified {len(declared_functions)} declared global functions/variables in frontend scripts.")

# Check common event handlers
tested_handlers = set()
for attr, handler_code in event_handlers:
    # Match function call like funcName(...) or Obj.funcName(...)
    fn_matches = re.findall(r'([a-zA-Z0-9_$]+(?:\.[a-zA-Z0-9_$]+)?)\s*\(', handler_code)
    for fn in fn_matches:
        tested_handlers.add(fn)

print(f"Unique functions called from HTML event handlers: {len(tested_handlers)}")
for fn in sorted(list(tested_handlers)):
    root_fn = fn.split('.')[0]
    if root_fn in ["event", "this", "console", "alert", "document", "window", "sessionStorage", "localStorage", "JSON", "parseInt", "parseFloat"]:
        continue
    if root_fn not in declared_functions and fn not in declared_functions:
        # Check if defined inside object literals like Panels.pchealth.showDetail
        results["onclick_handlers"]["found_functions"].add(fn)

# ==============================================================================
# 5. CSS AUDIT
# ==============================================================================
print("\n" + "=" * 80)
print("5. CSS & DESIGN TOKENS AUDIT")
print("=" * 80)

css_files = glob.glob(f"{CSS_DIR}/**/*.css", recursive=True)
for cssf in css_files:
    with open(cssf, "r", encoding="utf-8") as f:
        ccontent = f.read()
        # Check for unclosed braces
        open_b = ccontent.count('{')
        close_b = ccontent.count('}')
        if open_b != close_b:
            results["css_audit"]["errors"].append(f"{cssf}: Unmatched braces: {open_b} open vs {close_b} closed")

print(f"Checked {len(css_files)} CSS files.")
print(f"CSS syntax balance errors: {len(results['css_audit']['errors'])}")

# Save results JSON
with open("/home/it-itsm/AI/incident-analysis/artifacts/frontend_audit_report.json", "w", encoding="utf-8") as f:
    json_export = {
        "menus": results["menus"],
        "panels": {
            "dom_panels": results["panels"]["dom_panels"],
            "orphaned": results["panels"]["orphaned"],
            "missing_dom": list(set(results["panels"]["missing_dom"]))
        },
        "icons": {
            "total_fa": results["icons"]["total_fa"],
            "fa_classes": sorted(list(results["icons"]["fa_classes"])),
            "svg_count": results["icons"]["svg_count"],
            "svg_errors": results["icons"]["svg_errors"]
        },
        "unicode": results["unicode"],
        "js_syntax": results["js_syntax"],
        "css_audit": results["css_audit"]
    }
    json.dump(json_export, f, indent=2)

print(f"\nFull audit written to artifacts/frontend_audit_report.json")
