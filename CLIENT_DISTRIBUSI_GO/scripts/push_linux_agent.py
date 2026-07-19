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
    
    params_json = json.dumps(params, separators=(',', ':')) if params else "{}"
    if params is None:
        params_json = "null"
        
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
        s.connect((ip, 10000))
        s.sendall(data.encode())
        resp = s.recv(4096)
        print(f"[{ip}] Response: {resp.decode().strip()}")
    except Exception as e:
        print(f"[{ip}] Error: {e}")
    finally:
        s.close()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 push.py <IP> <HOST_IP>")
        sys.exit(1)
        
    target_ip = sys.argv[1]
    host_ip = sys.argv[2]
    
    cmd_str = f"wget -O /tmp/osi-agent http://{host_ip}:8001/osi-agent && chmod +x /tmp/osi-agent && mv /tmp/osi-agent /opt/osi-agent/agent && systemctl restart osi-agent.service"
    
    print(f"Pushing to {target_ip} with host IP {host_ip}...")
    send_command(target_ip, "CMD", {"cmd": cmd_str})
