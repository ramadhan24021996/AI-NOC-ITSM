#!/bin/bash
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT="$(dirname "$DIR")"
echo "[ROLLBACK] Restoring original jarvis_presentation_runtime.py..."
cp -p "$DIR/jarvis_presentation_runtime_original.py.bak" "$PARENT/jarvis_presentation_runtime.py"
rm -f "$PARENT/intent_query_handler.py" "$PARENT/intent_action_handler.py" "$PARENT/intent_chat_handler.py"
echo "[ROLLBACK] Restore complete. Testing import..."
python3 -c "from jarvis.runtime.jarvis_presentation_runtime import JarvisPresentationRuntime; print('Restored OK')"
