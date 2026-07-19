import re

with open('SERVER/go_core/database/schema.go', 'r') as f:
    content = f.read()

# Find the start and end of tableDDLs map
start_idx = content.find('tableDDLs := map[string]string{')
end_idx = content.find('	for tbl, ddl := range tableDDLs {')

if start_idx == -1 or end_idx == -1:
    print("Could not find tableDDLs block")
    exit(1)

map_block = content[start_idx:end_idx]

# Extract all tables and DDLs
pattern = re.compile(r'"([^"]+)":\s*`([^`]+)`', re.DOTALL)
matches = pattern.findall(map_block)

tables = {}
for name, ddl in matches:
    tables[name] = ddl

# Dependency graph
deps = {name: [] for name in tables}
for name, ddl in tables.items():
    # Find REFERENCES table_name
    ref_pattern = re.compile(r'REFERENCES\s+([a-zA-Z0-9_]+)\s*\(')
    refs = ref_pattern.findall(ddl)
    for ref in refs:
        if ref in tables:
            deps[name].append(ref)

# Topological sort
ordered_tables = []
visited = set()
temp_mark = set()

def visit(n):
    if n in temp_mark:
        return # circular
    if n not in visited:
        temp_mark.add(n)
        for m in deps[n]:
            visit(m)
        temp_mark.remove(n)
        visited.add(n)
        ordered_tables.append(n)

for n in tables:
    visit(n)

# Build the new struct slice
new_block = "tableDDLs := []struct{ Name string; DDL string }{\n"
for name in ordered_tables:
    new_block += f'\t\t{{"{name}", `{tables[name]}`}},\n'
new_block += "\t}\n\n"

# Replace map_block with new_block
new_content = content[:start_idx] + new_block + content[end_idx:]

# Replace the for loop
new_content = new_content.replace('for tbl, ddl := range tableDDLs {', 'for _, item := range tableDDLs {\n\t\ttbl := item.Name\n\t\tddl := item.DDL')

with open('SERVER/go_core/database/schema.go', 'w') as f:
    f.write(new_content)

print("Fixed schema.go")
