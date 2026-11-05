#!/usr/bin/env python3
"""
Test script untuk menguji dan menerapkan Linux System Toast Notification (notify-send / libnotify)
untuk Agent Distribusi OSI AI.
"""

import os
import sys
import json
import logging
import subprocess

logging.basicConfig(level=logging.INFO, format='[NOTIFY-TEST] %(levelname)s: %(message)s')

def send_linux_toast(title, message, urgency="critical", icon=None, actions=None):
    """
    Mengirimkan notifikasi Toast ke Desktop Linux via Freedesktop D-Bus (notify-send).
    """
    if not icon:
        icon = "/opt/osi-agent/agent.ico" if os.path.exists("/opt/osi-agent/agent.ico") else "dialog-warning"

    cmd = [
        "notify-send",
        f"--urgency={urgency}",
        f"--icon={icon}",
        "--expire-time=10000",
        title,
        message
    ]

    # Menambahkan action buttons jika didukung oleh D-Bus / notify-send
    if actions:
        for action_key, action_label in actions.items():
            cmd.extend(["-A", f"{action_key}={action_label}"])

    logging.info(f"Executing command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        logging.info(f"Exit Code: {result.returncode}")
        if result.stdout:
            logging.info(f"User Action Selected: {result.stdout.strip()}")
        if result.stderr:
            logging.warning(f"Stderr: {result.stderr.strip()}")
        return True, result.stdout.strip()
    except Exception as e:
        logging.error(f"Gagal mengeksekusi notify-send: {e}")
        return False, str(e)

if __name__ == '__main__':
    print("==================================================")
    print("   TESTING LINUX SYSTEM POPUP (NOTIFY-SEND / LIBNOTIFY)   ")
    print("==================================================")
    
    title = "🚨 OSI AI - Peringatan Sistem"
    message = "Terdeteksi insiden keamanan pada sistem. Silakan buka Support Chat untuk verifikasi."
    actions = {
        "chat": "Buka Chat",
        "dismiss": "Abaikan"
    }

    success, action_res = send_linux_toast(title, message, urgency="critical", actions=actions)
    if success:
        print("✅ Success: Notifikasi Toast berhasil dikirim ke D-Bus Desktop Notification System!")
    else:
        print("❌ Error: Gagal mengirimkan notifikasi.")
