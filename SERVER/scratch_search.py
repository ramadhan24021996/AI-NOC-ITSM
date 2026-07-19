import os

search_terms = ["raw_results", "stream message", "error processing"]
dirs_to_search = ["server/01_CORE_SERVER", "portal", "server/agents"]

print("--- START SEARCH ---")
for d in dirs_to_search:
    path_d = os.path.join(r"D:\AI-AGEN DRIVEN INTELLIGENT INCIDENT ANALIS", d)
    if not os.path.exists(path_d):
        print(f"Directory {d} does not exist")
        continue
    for root, dirs, files in os.walk(path_d):
        for f in files:
            if f.endswith(".py") or f.endswith(".json") or f.endswith(".txt") or f.endswith(".log"):
                path_f = os.path.join(root, f)
                try:
                    with open(path_f, "r", encoding="utf-8", errors="ignore") as file:
                        for i, line in enumerate(file):
                            for term in search_terms:
                                if term in line.lower():
                                    print(f"FOUND in {os.path.relpath(path_f)} Line {i+1}: {line.strip()}")
                except Exception as e:
                    print(f"Error reading {path_f}: {e}")
print("--- END SEARCH ---")
