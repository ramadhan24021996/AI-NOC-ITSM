import os
import shutil

doc_dir = "/home/it-itsm/AI/incident-analysis/DOCUMENTATION"
diterapkan_dir = os.path.join(doc_dir, "DITERAPKAN")
belum_diterapkan_dir = os.path.join(doc_dir, "BELUM_DITERAPKAN")

belum_diterapkan_files_upper = [
    "GEMINI.MD", "GOVERENCE.MD", "SPRINT.MD", "SPRINT_M_AUDIT.MD",
    "SPRINT_O.MD", "SPRINT_P1.MD"
]

for item in os.listdir(doc_dir):
    item_path = os.path.join(doc_dir, item)
    if os.path.isfile(item_path):
        if item.upper().endswith(".MD") or item.upper().endswith(".TXT"):
            if item.strip() in belum_diterapkan_files_upper or "GEMINI" in item.upper() or "CLOUDE" in item.upper():
                shutil.move(item_path, os.path.join(belum_diterapkan_dir, item))
            else:
                shutil.move(item_path, os.path.join(diterapkan_dir, item))

print("Audit and move (case-insensitive) completed!")
