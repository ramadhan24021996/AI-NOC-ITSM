#!/bin/bash
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT="$(dirname "$DIR")"
echo "[ROLLBACK] Restoring original noc_integration_gateway.py..."
cp -p "$DIR/noc_integration_gateway_original.py.bak" "$PARENT/noc_integration_gateway.py"
rm -rf "$PARENT/providers"
echo "[ROLLBACK] Restore complete. Testing import..."
cd "$PARENT/../../.." && PYTHONPATH=. python3 -c "from SERVER.integration.gateway.noc_integration_gateway import NOCIntegrationGateway; print('Restored OK')"
