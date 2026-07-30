import re

with open('portal/templates/index.html', 'r') as f:
    content = f.read()

content = content.replace("{ key: 'dag', label: 'Causal DAG' },", "{ key: 'unified_dag', label: 'Unified Graphs' },")
content = content.replace("{ key: 'decision_dag', label: 'Decision Graph' },", "")
content = content.replace("{ key: 'evidence_dag', label: 'Evidence DAG' },", "")

with open('portal/templates/index.html', 'w') as f:
    f.write(content)
print("RBAC options fixed.")
