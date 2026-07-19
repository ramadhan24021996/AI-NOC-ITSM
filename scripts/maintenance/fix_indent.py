with open("SERVER/python_ai_core/ai_supervisor.py", "r") as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1

for i, line in enumerate(lines):
    if "# 5. Isolated Agent Calls & Schema Validation" in line:
        start_idx = i
    if "# 6. Dynamic OPA-Style Policy Engine via NATS request" in line:
        end_idx = i
        break

if start_idx != -1 and end_idx != -1:
    for i in range(start_idx, end_idx):
        if lines[i].strip():
            lines[i] = "    " + lines[i]
            
    with open("SERVER/python_ai_core/ai_supervisor.py", "w") as f:
        f.writelines(lines)
    print(f"Indented lines {start_idx} to {end_idx}")
else:
    print("Could not find bounds")
