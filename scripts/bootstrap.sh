#!/usr/bin/env bash
# ==============================================================================
# AI-NOC-ITSM Environment Bootstrap Script
# Safely initializes configuration and credentials from .example templates
# without overwriting existing production or customized configs.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "🚀 [Bootstrap] Initializing AI-NOC-ITSM configuration..."

# 1. Root .env
if [ ! -f "${ROOT_DIR}/.env" ]; then
    echo "  -> Copying .env.example to .env..."
    cp "${ROOT_DIR}/.env.example" "${ROOT_DIR}/.env"
    echo "     ⚠️ Please review and fill all required secrets in .env before running docker compose up!"
else
    echo "  -> .env already exists (preserving)."
fi

# 2. Portal ai_config.json
mkdir -p "${ROOT_DIR}/portal"
if [ ! -f "${ROOT_DIR}/portal/ai_config.json" ]; then
    echo "  -> Creating portal/ai_config.json from template..."
    cp "${ROOT_DIR}/portal/ai_config.example.json" "${ROOT_DIR}/portal/ai_config.json"
else
    echo "  -> portal/ai_config.json already exists (preserving)."
fi

# 3. Nginx .htpasswd
mkdir -p "${ROOT_DIR}/docker/nginx"
if [ ! -f "${ROOT_DIR}/docker/nginx/.htpasswd" ]; then
    echo "  -> Creating docker/nginx/.htpasswd from template..."
    cp "${ROOT_DIR}/docker/nginx/.htpasswd.example" "${ROOT_DIR}/docker/nginx/.htpasswd"
else
    echo "  -> docker/nginx/.htpasswd already exists (preserving)."
fi

echo "✅ [Bootstrap] Environment files verified successfully."
