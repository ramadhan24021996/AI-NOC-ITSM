import json
import hmac
import hashlib
import time
import socket
import sys

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


def send_command(ip, cmd, params):
    secret = _load_agent_key()
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

if __name__ == "__main__":
    send_command("10.20.0.70", "CMD", {"cmd": "which sqlite3 || apt-get update && apt-get install -y sqlite3"})

