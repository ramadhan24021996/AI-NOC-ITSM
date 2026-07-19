import re

with open('portal/templates/index.html', 'r') as f:
    content = f.read()

# Replace any occurrence of 'dag', 'decision_dag', 'evidence_dag' in the panels list arrays
content = re.sub(r"'dag'\s*,\s*", "", content)
content = re.sub(r"'decision_dag'\s*,\s*", "", content)
content = re.sub(r"'evidence_dag'\s*,\s*", "", content)
# Since I did a replace earlier for "dag: 'AI Root Cause" this is fine. Let's make sure it's clean.
# I already see 'unified_dag' is in the array from the previous output:
# 'incident', 'rca', 'unified_dag', 'approval_queue',

with open('portal/templates/index.html', 'w') as f:
    f.write(content)
