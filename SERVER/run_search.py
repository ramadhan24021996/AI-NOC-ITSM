import os

root_dir = r"d:\AI-AGEN DRIVEN INTELLIGENT INCIDENT ANALIS"
found = []

for dirpath, dirnames, filenames in os.walk(root_dir):
    if any(x in dirpath.lower() for x in [".git", "__pycache__", "build", "dist", ".gemini", "node_modules", "scratch"]):
        continue
    for fname in filenames:
        if fname.endswith(".py"):
            fpath = os.path.join(dirpath, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    for idx, line in enumerate(f):
                        if "rag_version" in line.lower() or "local_knowledge_base.json" in line.lower():
                            found.append(f"{fpath} | Line {idx+1}: {line.strip()}")
            except:
                import logging; logging.getLogger(__name__).debug('_ = None suppressed')

with open(os.path.abspath("search_results.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(found))

print("Found matches:", len(found))
