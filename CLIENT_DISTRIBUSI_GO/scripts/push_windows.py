import json
import hmac
import hashlib
import time
import socket
import sys

def send_command(ip, cmd, params):
    secret = b"SIAP_DISTRIBUSI_SECRET_KEY"
    ts = int(time.time())
    exec_id = f"exec_{ts}"
    
    msg = f"{cmd}:{ts}"
    token = hmac.new(secret, msg.encode(), hashlib.sha256).hexdigest()
    
    payload = {
        "command": cmd,
        "params": params,
        "execution_id": exec_id,
        "timestamp": ts,
        "token": token
    }
    
    data = json.dumps(payload) + "\n"
    
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10)
    try:
        s.connect((ip, 10001))
        s.sendall(data.encode())
        resp = s.recv(4096)
        print(f"[{ip}] Response: {resp.decode().strip()}")
    except Exception as e:
        print(f"[{ip}] Error: {e}")
    finally:
        s.close()

if __name__ == "__main__":
    target_ip = sys.argv[1]
    host_ip = sys.argv[2]
    
    bat_content = f"""@echo off
timeout /t 3
net stop "OSI AI Agent"
curl -s -o "C:\\Program Files\\Mega Kreasi Tech\\PC Health Agent\\agent.exe" http://{host_ip}:9090/05_SIAP_DISTRIBUSI/agent.exe
net start "OSI AI Agent"
del "%~f0"
"""
    
    # Send POWERSHELL command to create and execute the BAT file asynchronously
    cmd_str = f"""$bat = 'C:\\temp_osi_update.bat'; Set-Content -Path $bat -Value '{bat_content.replace('"', '""').replace("'", "''")}'; Start-Process -FilePath cmd.exe -ArgumentList '/c', $bat -WindowStyle Hidden"""
    
    print(f"Pushing to {target_ip} with host IP {host_ip}...")
    send_command(target_ip, "POWERSHELL", {"cmd": cmd_str})
