import re

file_path = "SERVER/go_core/ingestion/ingestion_server.go"
with open(file_path, "r") as f:
    content = f.read()

# Replace if natsConn != nil { ... err := natsConn.Publish(...)
content = re.sub(r'if natsConn != nil \{\s+err := natsConn\.Publish\(', 'if natsJS != nil {\n\t\t_, err := natsJS.Publish(', content)

# Replace if natsConn != nil { ... _ = natsConn.Publish(...)
content = re.sub(r'if natsConn != nil \{\s+_\s*=\s*natsConn\.Publish\(', 'if natsJS != nil {\n\t\t\t\t\t\t_, _ = natsJS.Publish(', content)
# But we need to handle different indentations properly.
# A safer regex: replace natsConn != nil with natsJS != nil if it guards a publish
content = content.replace("if natsConn != nil {\n\t\terr := natsConn.Publish(", "if natsJS != nil {\n\t\t_, err := natsJS.Publish(")

# General replace of natsConn.Publish
def replace_publish(match):
    prefix = match.group(1)
    return prefix + "_, " + match.group(2) + "natsJS.Publish("

# For assignments like err = natsConn.Publish(
content = re.sub(r'([ \t]*)err\s*=\s*natsConn\.Publish\(', r'\1_, err = natsJS.Publish(', content)
# For ignores like _ = natsConn.Publish(
content = re.sub(r'([ \t]*)_\s*=\s*natsConn\.Publish\(', r'\1_, _ = natsJS.Publish(', content)
# For err := natsConn.Publish(
content = re.sub(r'([ \t]*)err\s*:=\s*natsConn\.Publish\(', r'\1_, err := natsJS.Publish(', content)

# Replace natsConn != nil with natsJS != nil where it guards a publish
# Since we only replaced natsConn.Publish, some if natsConn != nil {} remain for these publishes. We can just replace those specific ones.
content = content.replace("if natsConn != nil {\n\t\t\t\t\t\t_, _ = natsJS.Publish", "if natsJS != nil {\n\t\t\t\t\t\t_, _ = natsJS.Publish")
content = content.replace("if natsConn != nil {\n\t\t\t\t\t_, _ = natsJS.Publish", "if natsJS != nil {\n\t\t\t\t\t_, _ = natsJS.Publish")
content = content.replace("if natsConn != nil {\n\t\t\t_, _ = natsJS.Publish", "if natsJS != nil {\n\t\t\t_, _ = natsJS.Publish")
content = content.replace("if natsConn != nil {\n\t\t_, _ = natsJS.Publish", "if natsJS != nil {\n\t\t_, _ = natsJS.Publish")
content = content.replace("if natsConn != nil {\n\t\t_, err := natsJS.Publish", "if natsJS != nil {\n\t\t_, err := natsJS.Publish")
content = content.replace("if natsConn != nil {\n\t\t_, err = natsJS.Publish", "if natsJS != nil {\n\t\t_, err = natsJS.Publish")
content = content.replace("and natsConn != nil {\n\t\t\t\t\t_, _ = natsJS.Publish", "and natsJS != nil {\n\t\t\t\t\t_, _ = natsJS.Publish")

# Edge cases without if wrapper
content = content.replace("fmt.Printf(\"[WATCHDOG] Publishing agent.watchdog.failed: %s\\n\", string(payloadBytes))\n\t\t_, _ = natsJS.Publish(", "fmt.Printf(\"[WATCHDOG] Publishing agent.watchdog.failed: %s\\n\", string(payloadBytes))\n\t\tif natsJS != nil {\n\t\t\t_, _ = natsJS.Publish(\"agent.watchdog.failed\", payloadBytes)\n\t\t}")

with open(file_path, "w") as f:
    f.write(content)

