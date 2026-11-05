#!/bin/bash
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT="$(dirname "$DIR")"
echo "[ROLLBACK] Restoring original monolithic index.html..."
cp -p "$DIR/index_monolithic_original.html" "$PARENT/index.html"
echo "[ROLLBACK] Restore complete. index.html size: $(wc -c < "$PARENT/index.html") bytes."
