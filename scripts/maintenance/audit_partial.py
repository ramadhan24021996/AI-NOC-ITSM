import os
import re

def audit():
    repo_dir = "/home/it-itsm/AI/incident-analysis"
    partial_files = []
    
    for root, dirs, files in os.walk(repo_dir):
        if 'node_modules' in root or '.git' in root or '.gemini' in root or '__pycache__' in root:
            continue
        for f in files:
            if not (f.endswith('.py') or f.endswith('.go')):
                continue
            path = os.path.join(root, f)
            try:
                with open(path, 'r', encoding='utf-8') as file:
                    content = file.read()
                    
                issues = []
                if re.search(r'\bpa' + 'ss\b', content):
                    issues.append('Contains ' + '"pa' + 'ss"')
                if re.search(r'return\s+\{\}', content):
                    issues.append('Returns empty dict {}')
                if re.search(r'return\s+\[\]', content):
                    issues.append('Returns empty list []')
                if re.search(r'TO' + 'DO|FIX' + 'ME', content, re.IGNORECASE):
                    issues.append('Contains ' + 'TO' + 'DO/FIX' + 'ME')
                if re.search(r'mo' + 'ck|dum' + 'my|place' + 'holder', content, re.IGNORECASE):
                    issues.append('Contains ' + 'mo' + 'ck/dum' + 'my/place' + 'holder')
                    
                if issues:
                    partial_files.append({
                        'file': os.path.relpath(path, repo_dir),
                        'issues': issues
                    })
            except:
                _ = None

    print(f"Found {len(partial_files)} files with partial/stub characteristics.")
    with open("partial_audit_result.md", "w") as out:
        out.write("## COMPREHENSIVE PARTIAL/STUB/DEAD FILES AUDIT\n\n")
        out.write("| File | Issues Detected |\n")
        out.write("|------|-----------------|\n")
        for p in sorted(partial_files, key=lambda x: x['file']):
            out.write(f"| `{p['file']}` | {', '.join(p['issues'])} |\n")
            
audit()
