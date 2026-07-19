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
    
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10)
    try:
        s.connect((ip, 10000))
        s.sendall((json.dumps(payload) + "\n").encode())
        resp = s.recv(4096)
        print(f"[{ip}] Response: {resp.decode().strip()}")
    except Exception as e:
        print(f"[{ip}] Error: {e}")
    finally:
        s.close()

send_command("10.20.0.70", "CMD", {"cmd": "for d in :0 :1; do export DISPLAY=$d; wmctrl -l 2>/dev/null && break; done"})
