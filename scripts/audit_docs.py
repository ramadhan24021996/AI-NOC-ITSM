import os
import shutil

doc_dir = "/home/it-itsm/AI/incident-analysis/DOCUMENTATION"
diterapkan_dir = os.path.join(doc_dir, "DITERAPKAN")
belum_diterapkan_dir = os.path.join(doc_dir, "BELUM_DITERAPKAN")

os.makedirs(diterapkan_dir, exist_ok=True)
os.makedirs(belum_diterapkan_dir, exist_ok=True)

# List of files identified as raw instructions, notes, or pending implementation
belum_diterapkan_files = [
    "GEMINI.MD", "GOVERENCE.MD", "allsite.md", "chalive.md", 
    "cloude&gemini.md ", "cloude.md", "cloudeinsinyur.md", "eksekusi2.md", 
    "eksekusiintruksi.md", "geminiku.md", "geminiku1.md", "intruksi.md", 
    "intruksi1.md", "intruksigemini.md", "main.md", "production.md", 
    "system audit ui dan ux.md", "taks.md", "task.md", "walkthrough.md", 
    "backup linuk ubuntu.txt", "untuk backup ke pc lain atau server.txt",
    "enterprise_ai_reliability_engineering.md", "implementation_plan.md"
]

for item in os.listdir(doc_dir):
    item_path = os.path.join(doc_dir, item)
    if os.path.isfile(item_path):
        if item.endswith(".md") or item.endswith(".txt"):
            if item.strip() in belum_diterapkan_files or item.startswith("cloude") or item.startswith("gemini") or item.startswith("intruksi") or item.startswith("task"):
                shutil.move(item_path, os.path.join(belum_diterapkan_dir, item))
            else:
                shutil.move(item_path, os.path.join(diterapkan_dir, item))

print("Audit and move completed!")
