#!/bin/bash
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT="$(dirname "$DIR")"
echo "[ROLLBACK] Restoring original incident_handler.py..."
cp -p "$DIR/incident_handler_original.py.bak" "$PARENT/incident_handler.py"
rm -f "$PARENT/incident_triage.py" "$PARENT/incident_learning.py" "$PARENT/incident_retry.py" "$PARENT/incident_reanalyze.py"
echo "[ROLLBACK] Restore complete. Running tests..."
cd "$PARENT/../../../.." && python3 -m unittest discover -s tests/unit
