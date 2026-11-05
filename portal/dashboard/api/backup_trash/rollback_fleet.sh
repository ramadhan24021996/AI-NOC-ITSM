#!/bin/bash
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT="$(dirname "$DIR")"
echo "[ROLLBACK] Restoring original monolithic fleet_handlers.go..."
cp -p "$DIR/fleet_handlers_original.go" "$PARENT/fleet_handlers.go"
rm -f "$PARENT/fleet_diagnostics.go" "$PARENT/fleet_ota.go" "$PARENT/fleet_remote.go" "$PARENT/fleet_orchestrator.go" "$PARENT/fleet_crud.go"
echo "[ROLLBACK] Restore complete. Running tests..."
cd "$PARENT/../../.." && go test ./portal/dashboard/api/... -v
