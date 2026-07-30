#!/bin/bash
# ==============================================================================
# AUTOMATED OTA BINARY BUILD & CI/CD PIPELINE SCRIPT
# Automatically compiles Linux & Windows client agents and generates SHA-256 manifest.
# ==============================================================================

set -e

WORKSPACE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${WORKSPACE_DIR}/portal/ota_binaries"

echo "[OTA BUILD] Target Directory: ${OUTPUT_DIR}"
mkdir -p "${OUTPUT_DIR}"

# 1. Compile Linux Agent
echo "[OTA BUILD] Compiling Linux Agent (linux/amd64)..."
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o "${OUTPUT_DIR}/linux_agent" "${WORKSPACE_DIR}/CLIENT_DISTRIBUSI_GO/linux_agent"
chmod +x "${OUTPUT_DIR}/linux_agent"

# 2. Compile Windows Agent
echo "[OTA BUILD] Compiling Windows Agent (windows/amd64)..."
CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -ldflags="-s -w" -o "${OUTPUT_DIR}/windows_agent.exe" "${WORKSPACE_DIR}/CLIENT_DISTRIBUSI_GO/agent"

# 3. Compute SHA-256 Checksums
LINUX_HASH=$(sha256sum "${OUTPUT_DIR}/linux_agent" | awk '{print $1}')
WIN_HASH=$(sha256sum "${OUTPUT_DIR}/windows_agent.exe" | awk '{print $1}')
BUILD_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# 4. Generate JSON Release Manifest
cat <<EOF > "${OUTPUT_DIR}/manifest.json"
{
  "version": "v1.1.0",
  "build_time": "${BUILD_TIME}",
  "platforms": {
    "linux": {
      "filename": "linux_agent",
      "sha256": "${LINUX_HASH}",
      "download_url": "/api/fleet/ota/download?platform=linux"
    },
    "windows": {
      "filename": "windows_agent.exe",
      "sha256": "${WIN_HASH}",
      "download_url": "/api/fleet/ota/download?platform=windows"
    }
  }
}
EOF

echo "[OTA BUILD] SUCCESS! OTA Binaries & Manifest generated successfully:"
echo "            - Linux SHA256  : ${LINUX_HASH}"
echo "            - Windows SHA256: ${WIN_HASH}"
