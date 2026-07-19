import os
import glob
import re

directories = ["SERVER/python_ai_core", "SERVER/go_core"]

# Keywords that indicate partial/stub implementations
stub_keywords = [
    r'\bpa' + 'ss\b',
    r'\bPENDING_REVIEW\b',
    r'\bNEEDS_REVIEW\b',
    r'return\s+\{\}',
    r'return\s+\[\]',
    r'return\s+True',
    r'return\s+False',
    r'\bsynthetic\b',
    r'\breserved_space\b',
    r'\bsimulated\b',
    r'simulasi'
]
stub_regexes = [re.compile(k, re.IGNORECASE) for k in stub_keywords]

# Exclude some testing or utility directories from the strict evaluation
exclude_dirs = ["tests", "scripts", "schemas", "cognitive_memory/test_"]

files_data = {}

# 1. Gather all files
for d in directories:
    for root, _, files in os.walk(d):
        for f in files:
            if f.endswith('.py') or f.endswith('.go'):
                path = os.path.join(root, f)
                files_data[path] = {
                    "stubs": 0,
                    "PENDING_REVIEWs": 0,
                    "synthetics": 0,
                    "returns_empty": 0,
                    "imported_by": [],
                    "lines": 0
                }

# 2. Analyze content and find imports
for path, data in files_data.items():
    with open(path, 'r', errors='ignore') as f:
        content = f.read()
        lines = content.split('\n')
        data["lines"] = len(lines)
        
        for line in lines:
            line_lower = line.lower()
            if 'PENDING_REVIEW' in line_lower or 'NEEDS_REVIEW' in line_lower:
                data["PENDING_REVIEWs"] += 1
            if 'synthetic' in line_lower or 'simulated' in line_lower or 'reserved_space' in line_lower:
                data["synthetics"] += 1
            if re.search(r'return\s+\{\}', line) or re.search(r'return\s+\[\]', line) or re.search(r'\bpa' + 'ss\b', line):
                data["returns_empty"] += 1
                
    # Basic import graph building
    basename = os.path.basename(path).replace('.py', '')
    if basename != '__init__':
        for other_path, other_data in files_data.items():
            if other_path != path and other_path.endswith('.py'):
                with open(other_path, 'r', errors='ignore') as f:
                    if re.search(rf'\b{basename}\b', f.read()):
                        data["imported_by"].append(other_path)

# 3. Determine status
report = []
for path, data in files_data.items():
    status = "ACTIVE"
    reason = []
    
    if data["lines"] < 10:
        status = "STUB"
        reason.append("Too short")
    
    if data["synthetics"] > 0:
        status = "STUB" if data["lines"] < 50 else "PARTIAL"
        reason.append(f"synthetics found ({data['synthetics']})")
        
    if data["returns_empty"] > 0:
        if status == "ACTIVE": status = "PARTIAL"
        reason.append(f"Hardcoded returns/pass ({data['returns_empty']})")
        
    if data["PENDING_REVIEWs"] > 0:
        if status == "ACTIVE": status = "PARTIAL"
        reason.append(f"PENDING_REVIEWs ({data['PENDING_REVIEWs']})")
        
    is_main_or_script = "main.go" in path or "ai_supervisor" in path or "generate_" in path or "test_" in path or "benchmark" in path
    if len(data["imported_by"]) == 0 and not is_main_or_script and path.endswith('.py') and "__init__" not in path:
        if status == "ACTIVE":
            status = "STANDALONE"
            reason.append("Never imported")
        elif status in ["STUB", "PARTIAL"]:
            status = "DEAD"
            reason.append("Never imported + stubs")

    report.append((path, status, ", ".join(reason)))

report.sort(key=lambda x: (x[1], x[0]))

print("| File | Status | Audit Notes |")
print("|---|---|---|")
for path, status, reason in report:
    if "__init__" in path: continue
    print(f"| {path} | {status} | {reason} |")
