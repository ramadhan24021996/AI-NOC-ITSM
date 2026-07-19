#!/usr/bin/env python3
"""
OSI AI Agent - Mass OTA Update Pusher
Mengirim perintah update ke semua agent aktif via port 10000 (HMAC-secured)

Usage:
  python3 push_all.py [host_ip]   # host_ip = IP server (default: 10.20.0.163)
"""

import json
import hmac
import hashlib
import time
import socket
import sys
import threading

SECRET  = b"SIAP_DISTRIBUSI_SECRET_KEY"
HOST_IP = sys.argv[1] if len(sys.argv) > 1 else "10.20.0.163"
HOST_PORT = 9090   # Port file server (osi-agent-dist container)

# ─── Daftar agent terdaftar ─────────────────────────────────────────────────
# Format: (ip, type, device_name)
# Update IPs sesuai network scan / DHCP lease
AGENTS = [
    # Linux agents (NUC dan Vostro)
    ("10.20.0.70",  "linux",   "LINUX-it-mkt-NUC12WSH-B"),
    # Windows agents - tambahkan IP saat online
    # ("10.20.0.XX", "windows", "PC-MKT-NUC"),
]

# ─── Commands ────────────────────────────────────────────────────────────────
LINUX_UPDATE_CMD = (
    f"wget -q -O /tmp/osi-agent http://{HOST_IP}:{HOST_PORT}/linux_agent/osi-agent "
    f"&& chmod +x /tmp/osi-agent "
    f"&& mv /tmp/osi-agent /opt/osi-agent/agent "
    f"&& systemctl restart osi-agent.service "
    f"&& echo 'OSI AGENT UPDATE OK'"
)

WINDOWS_UPDATE_CMD = (
    f"""$url='http://{HOST_IP}:{HOST_PORT}/05_SIAP_DISTRIBUSI/agent.exe'; """
    f"""$dest='C:\\Program Files\\Mega Kreasi Tech\\PC Health Agent\\agent.exe'; """
    f"""net stop 'OSI AI Agent'; """
    f"""Invoke-WebRequest -Uri $url -OutFile $dest; """
    f"""net start 'OSI AI Agent'; """
    f"""echo 'OSI AGENT UPDATE OK'"""
)

# ─── Core send function ───────────────────────────────────────────────────────
def send_command(ip, command_type, params, timeout=15):
    ts       = int(time.time())
    msg      = f"{command_type}:{ts}"
    token    = hmac.new(SECRET, msg.encode(), hashlib.sha256).hexdigest()
    payload  = {
        "command":      command_type,
        "params":       params,
        "execution_id": f"push_{ts}_{ip.replace('.','_')}",
        "timestamp":    ts,
        "token":        token,
    }
    data = json.dumps(payload) + "\n"

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((ip, 10000))
        s.sendall(data.encode())
        resp = s.recv(4096).decode("utf-8", errors="replace").strip()
        return True, resp
    except Exception as e:
        return False, str(e)
    finally:
        s.close()

# ─── Push logic per agent ─────────────────────────────────────────────────────
def push_agent(ip, agent_type, device_name):
    print(f"\n{'='*60}")
    print(f"[PUSH] {device_name} ({agent_type.upper()}) @ {ip}")
    print(f"{'='*60}")

    # 1. Ping (health check)
    ok, resp = send_command(ip, "CMD", {"cmd": "echo PING_OK"})
    if not ok:
        print(f"  ✗ Unreachable: {resp}")
        return False
    print(f"  ✓ Agent reachable: {resp}")

    # 2. Send update command
    if agent_type == "linux":
        ok, resp = send_command(ip, "CMD", {"cmd": LINUX_UPDATE_CMD}, timeout=30)
    elif agent_type == "windows":
        ok, resp = send_command(ip, "POWERSHELL", {"cmd": WINDOWS_UPDATE_CMD}, timeout=30)
    else:
        print(f"  ✗ Unknown agent type: {agent_type}")
        return False

    if ok:
        print(f"  ✓ Update command sent: {resp}")
    else:
        print(f"  ✗ Update failed: {resp}")
    return ok

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║       OSI AI AGENT - MASS OTA UPDATE PUSHER                  ║
║  Server: {HOST_IP}:{HOST_PORT:<50}║
╚══════════════════════════════════════════════════════════════╝
""")

    results = []
    threads = []

    def worker(ip, atype, name):
        success = push_agent(ip, atype, name)
        results.append((name, ip, "OK" if success else "FAILED"))

    for ip, atype, name in AGENTS:
        t = threading.Thread(target=worker, args=(ip, atype, name))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    print(f"\n{'='*60}")
    print("SUMMARY:")
    print(f"{'='*60}")
    for name, ip, status in results:
        icon = "✓" if status == "OK" else "✗"
        print(f"  {icon} {name} ({ip}): {status}")

    ok_count = sum(1 for _, _, s in results if s == "OK")
    print(f"\nTotal: {ok_count}/{len(results)} agent berhasil diupdate.")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
