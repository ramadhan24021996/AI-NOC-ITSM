#!/bin/bash
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT="$(dirname "$DIR")"
echo "[ROLLBACK] Restoring original dashboard_server.go..."
cp -p "$DIR/dashboard_server_original.go.bak" "$PARENT/dashboard_server.go"
rm -f "$PARENT/server_ws.go" "$PARENT/server_auditor.go" "$PARENT/server_chat.go"
echo "[ROLLBACK] Restore complete. Compiling binary..."
cd "$PARENT/.." && go build -v -o bin/dashboard_server ./portal
