#!/bin/bash
# -----------------------------------------------------------------------------
# OSI AI AGENT LINUX - AUTOMATIC UPDATE & INSTALLER SCRIPT
# Server IP: 10.20.0.154
# -----------------------------------------------------------------------------

set -e

SERVER_IP="${1:-10.20.0.154}"
INSTALL_DIR="/opt/osi-agent"

echo "============================================================"
echo "   OSI AI AGENT LINUX - SKRIP PEMBAHARUAN OTOMATIS"
echo "   Server NOC Target: ${SERVER_IP}"
echo "============================================================"

# Ensure directories exist
mkdir -p "${INSTALL_DIR}" 2>/dev/null || true
mkdir -p ~/.config/osi-agent 2>/dev/null || true

echo "[1/4] Mengunduh biner agen terbaru (osi-agent)..."
curl -sSL "http://${SERVER_IP}:9090/linux_agent/osi-agent" -o "${INSTALL_DIR}/agent.tmp" 2>/dev/null || true
if [ -s "${INSTALL_DIR}/agent.tmp" ]; then
    mv -f "${INSTALL_DIR}/agent.tmp" "${INSTALL_DIR}/agent"
    chmod 0755 "${INSTALL_DIR}/agent"
fi

echo "[2/4] Mengunduh skrip GUI Native Tray Chat (linux_chat_ui.py)..."
curl -sSL "http://${SERVER_IP}:9090/linux_agent/linux_chat_ui.py" -o "${INSTALL_DIR}/linux_chat_ui.py"
cp "${INSTALL_DIR}/linux_chat_ui.py" ~/.config/osi-agent/linux_chat_ui.py 2>/dev/null || true
chmod 0755 "${INSTALL_DIR}/linux_chat_ui.py" ~/.config/osi-agent/linux_chat_ui.py 2>/dev/null || true

echo "[3/4] Mengunduh daemon Tray Agent (linux_tray_agent.py)..."
curl -sSL "http://${SERVER_IP}:9090/linux_agent/linux_tray_agent.py" -o "${INSTALL_DIR}/linux_tray_agent.py"
cp "${INSTALL_DIR}/linux_tray_agent.py" ~/.config/osi-agent/linux_tray_agent.py 2>/dev/null || true
chmod 0755 "${INSTALL_DIR}/linux_tray_agent.py" ~/.config/osi-agent/linux_tray_agent.py 2>/dev/null || true

echo "[4/4] Merestart daemon Tray Agent..."
pkill -f linux_tray_agent || true
nohup python3 "${INSTALL_DIR}/linux_tray_agent.py" >/dev/null 2>&1 &

if systemctl is-active --quiet osi-agent 2>/dev/null; then
    systemctl restart osi-agent 2>/dev/null || true
fi

echo "============================================================"
echo "   PEMBAHARUAN AGENT LINUX SELESAI & AKTIF (v2.1.1-Go)"
echo "============================================================"
