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

import subprocess

def _load_agent_key() -> bytes:
    """[K-01] Agent HMAC key from AGENT_HMAC_KEY env or repo .key file. No literal."""
    import os, pathlib
    k = os.environ.get("AGENT_HMAC_KEY", "").strip()
    if not k:
        f = pathlib.Path(__file__).resolve().parents[2] / ".key"
        k = f.read_text().strip().strip("\"'") if f.exists() else ""
    if not k:
        raise SystemExit("AGENT_HMAC_KEY not set and .key not found; refusing to sign (fail-closed).")
    return k.encode()


SECRET  = _load_agent_key()
HOST_IP = sys.argv[1] if len(sys.argv) > 1 else "10.20.0.163"
HOST_PORT = 9090   # Port file server (osi-agent-dist container)

def get_registered_agents():
    server_ips = {"10.20.0.163", "10.20.0.154", "127.0.0.1"}
    try:
        cmd = ["docker", "exec", "osi-postgres", "psql", "-U", "postgres", "-d", "osi_system", "-t", "-A", "-F", ",", "-c", "SELECT name, ip FROM devices WHERE ip IS NOT NULL AND ip != '';"]
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
        agents = []
        seen_ips = set()
        for line in out.strip().splitlines():
            parts = line.split(",")
            if len(parts) == 2:
                name, ip = parts[0].strip(), parts[1].strip()
                if ip and ip not in server_ips and not ip.startswith("172.") and ip not in seen_ips:
                    seen_ips.add(ip)
                    atype = "windows" if ("pc" in name.lower() or "win" in name.lower() or "desktop" in name.lower()) else "linux"
                    agents.append((ip, atype, name))
        if agents:
            return agents
    except Exception:
        pass
    
    return [
        ("10.20.0.46",  "linux",   "LINUX-it-mkt-NUC12WSH-B"),
        ("10.20.0.44",  "windows", "PC-MKT-NUC"),
        ("10.20.0.120", "linux",   "LINUX-PC-TMS"),
    ]

AGENTS = get_registered_agents()

# ─── Commands ────────────────────────────────────────────────────────────────
LINUX_UPDATE_CMD = (
    f"wget -q -O /tmp/osi-agent http://{HOST_IP}:{HOST_PORT}/linux_agent/osi-agent "
    f"|| wget -q -O /tmp/osi-agent http://{HOST_IP}:{HOST_PORT}/linux_agent/linux_agent "
    f"&& chmod +x /tmp/osi-agent "
    f"&& mv /tmp/osi-agent /opt/osi-agent/agent "
    f"&& systemctl restart osi-agent.service "
    f"&& echo 'OSI AGENT UPDATE OK'"
)

WINDOWS_TRAY_UPDATE_BAT = f"""@echo off
set CSC_PATH=C:\\Windows\\Microsoft.NET\\Framework64\\v4.0.30319\\csc.exe
cd "C:\\Program Files\\Mega Kreasi Tech\\PC Health Agent"
curl -s -o ChatForm.cs http://{HOST_IP}:{HOST_PORT}/agent/ChatForm.cs
curl -s -o tray.cs http://{HOST_IP}:{HOST_PORT}/agent/tray.cs
if exist "%CSC_PATH%" (
    "%CSC_PATH%" /target:winexe /out:agent_tray.exe /win32icon:agent.ico /r:System.Web.Extensions.dll /r:System.Management.dll tray.cs ChatForm.cs
    taskkill /F /IM agent_tray.exe
    start "" "agent_tray.exe"
)
"""
WINDOWS_UPDATE_CMD = f"""$bat = 'C:\\temp_osi_tray_update.bat'; Set-Content -Path $bat -Value '{WINDOWS_TRAY_UPDATE_BAT.replace('"', '""').replace("'", "''")}'; Start-Process -FilePath cmd.exe -ArgumentList '/c', $bat -WindowStyle Hidden"""

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

    last_err = ""
    for port in [10000, 10001]:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            s.connect((ip, port))
            s.sendall(data.encode())
            resp = s.recv(4096).decode("utf-8", errors="replace").strip()
            s.close()
            return True, resp
        except Exception as e:
            last_err = str(e)
            s.close()
    return False, last_err

LINUX_BIN_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "linux_agent", "osi-agent")
try:
    with open(LINUX_BIN_PATH, "rb") as _f:
        LINUX_SHA256 = hashlib.sha256(_f.read()).hexdigest()
except Exception:
    LINUX_SHA256 = ""

# ─── Push logic per agent ─────────────────────────────────────────────────────
def push_agent(ip, agent_type, device_name):
    print(f"\n{'='*60}")
    print(f"[PUSH] {device_name} ({agent_type.upper()}) @ {ip}")
    print(f"{'='*60}")

    # 1. Ping (health check)
    ok, resp = send_command(ip, "PING", {})
    if not ok:
        print(f"  ✗ Unreachable: {resp}")
        return False
    print(f"  ✓ Agent reachable: {resp}")

    # 2. Send update command
    if agent_type == "linux":
        ok, resp = send_command(ip, "UPDATE_AGENT", {
            "download_url": f"http://{HOST_IP}:{HOST_PORT}/linux_agent/osi-agent",
            "sha256": LINUX_SHA256
        }, timeout=30)
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
