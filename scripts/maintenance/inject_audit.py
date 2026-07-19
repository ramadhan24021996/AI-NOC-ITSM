import os

audit_file = "/home/it-itsm/.gemini/antigravity/brain/a60184be-3998-4fd5-91ae-e17f55b01419/FULL_SYSTEM_AUDIT_2026.md"
partial_file = "partial_audit_result.md"

with open(audit_file, "r") as f:
    content = f.read()

with open(partial_file, "r") as f:
    partial_content = f.read()

# Insert before "## SUMMARY STATISTICS"
parts = content.split("## SUMMARY STATISTICS")
if len(parts) == 2:
    new_content = parts[0] + partial_content + "\n\n---\n\n## SUMMARY STATISTICS" + parts[1]
    with open(audit_file, "w") as f:
        f.write(new_content)
    print("Successfully injected the partial audit results into FULL_SYSTEM_AUDIT_2026.md")
else:
    print("Could not find '## SUMMARY STATISTICS' in the audit file.")
