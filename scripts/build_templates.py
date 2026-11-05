#!/usr/bin/env python3
"""
NOC IT AI v3.0 - Template Assembly Script
Compiles HTML partials into master index.html template.
"""

import os, glob

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, 'portal', 'templates')
PARTIALS_DIR = os.path.join(TEMPLATES_DIR, 'partials', 'panels')
INDEX_FILE = os.path.join(TEMPLATES_DIR, 'index.html')

HEADER_PATH = os.path.join(TEMPLATES_DIR, 'partials', 'layout', 'header.html')
FOOTER_PATH = os.path.join(TEMPLATES_DIR, 'partials', 'layout', 'footer.html')

def build_templates():
    if not os.path.exists(HEADER_PATH) or not os.path.exists(FOOTER_PATH):
        print("❌ Header or Footer partial missing!")
        return False
    
    with open(HEADER_PATH, 'r', encoding='utf-8') as f:
        header_content = f.read()

    with open(FOOTER_PATH, 'r', encoding='utf-8') as f:
        footer_content = f.read()

    panel_files = sorted(glob.glob(os.path.join(PARTIALS_DIR, '*.html')))
    print(f"📦 Assembling index.html with {len(panel_files)} panel partials...")

    assembled_html = header_content
    for pf in panel_files:
        with open(pf, 'r', encoding='utf-8') as f:
            assembled_html += f.read() + "\n"

    assembled_html += footer_content

    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        f.write(assembled_html)

    lines = len(assembled_html.splitlines())
    kb = len(assembled_html) // 1024
    print(f"✅ Master index.html successfully built! ({lines} lines, {kb} KB)")
    return True

if __name__ == '__main__':
    build_templates()
