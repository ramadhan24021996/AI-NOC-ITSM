#!/bin/bash
# -----------------------------------------------------------------------------
# OSI AI AGENT LINUX - UNINSTALL & FRESH CLEAN REINSTALL SCRIPT
# Server IP: 10.20.0.154
# -----------------------------------------------------------------------------

set -e

SERVER_IP="${1:-10.20.0.154}"
INSTALL_DIR="/opt/osi-agent"

echo "============================================================"
echo "   OSI AI AGENT LINUX - CLEAN UNINSTALL & FRESH REINSTALL"
echo "   Server NOC Target: ${SERVER_IP}"
echo "============================================================"

echo "[1/5] Hentikan semua proses & service agen lama..."
systemctl stop osi-agent 2>/dev/null || true
systemctl disable osi-agent 2>/dev/null || true
pkill -9 -f osi-agent 2>/dev/null || true
pkill -9 -f linux_agent 2>/dev/null || true
pkill -9 -f linux_tray_agent 2>/dev/null || true
pkill -9 -f linux_chat_ui 2>/dev/null || true

echo "[2/5] Hapus folder & file instalasi lama secara total..."
rm -rf /opt/osi-agent
rm -rf ~/.config/osi-agent
rm -f /tmp/osi-agent /tmp/linux_agent /tmp/linux_chat_ui.py /tmp/linux_tray_agent.py /tmp/osi_agent_update.bin

echo "[3/5] Buat folder instalasi bersih..."
mkdir -p "${INSTALL_DIR}"
mkdir -p ~/.config/osi-agent

echo "[4/5] Mengunduh biner agen & skrip GUI Tray Chat terbaru dari server..."
curl -sSL "http://${SERVER_IP}:9090/linux_agent/osi-agent" -o "${INSTALL_DIR}/agent"
chmod +x "${INSTALL_DIR}/agent"

curl -sSL "http://${SERVER_IP}:9090/linux_agent/linux_chat_ui.py" -o "${INSTALL_DIR}/linux_chat_ui.py"
chmod +x "${INSTALL_DIR}/linux_chat_ui.py"

curl -sSL "http://${SERVER_IP}:9090/linux_agent/linux_tray_agent.py" -o "${INSTALL_DIR}/linux_tray_agent.py"
chmod +x "${INSTALL_DIR}/linux_tray_agent.py"

echo "[5/5] Menjalankan Service & Tray Agent..."
nohup python3 "${INSTALL_DIR}/linux_tray_agent.py" >/dev/null 2>&1 &
nohup "${INSTALL_DIR}/agent" >/dev/null 2>&1 &

echo "============================================================"
echo "   RE-INSTALLATION SELESAI & AKTIF (v2.1.1-Go BERSIH)"
echo "============================================================"
