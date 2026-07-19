import socket, json, sys

ip = "100.100.10.98"
port = 10001

print(f"Testing socket connection to {ip}:{port}...")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(15.0)
    sock.connect((ip, port))
    print("Connected successfully!")
    
    payload = {"command": "DEEP_DIAGNOSTICS"}
    data = json.dumps(payload).encode('utf-8')
    print(f"Sending: {data}")
    sock.sendall(data)
    
    response_data = []
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break
        response_data.append(chunk)
        print(f"Received chunk: {len(chunk)} bytes")
    
    response_str = b"".join(response_data).decode('utf-8', errors='ignore')
    print(f"\nTotal response length: {len(response_str)}")
    print(f"Raw response (first 500 chars): {response_str[:500]}")
    
    sock.close()
    
    if response_str:
        try:
            parsed = json.loads(response_str)
            print(f"\nParsed JSON keys: {list(parsed.keys())}")
            print(f"Network length: {len(str(parsed.get('network', '')))}")
            print(f"Apps count: {len(parsed.get('apps', []))}")
            print(f"Webs count: {len(parsed.get('webs', []))}")
            print(f"Printers keys: {list(parsed.get('printers', {}).keys())}")
        except json.JSONDecodeError as e:
            print(f"\nJSON parse error: {e}")
    else:
        print("\nResponse was EMPTY!")
        
except Exception as e:
    print(f"Socket error: {type(e).__name__}: {e}")

# Also test with 127.0.0.1
print(f"\n\n--- Testing with 127.0.0.1:{port} ---")
try:
    sock2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock2.settimeout(15.0)
    sock2.connect(("127.0.0.1", port))
    print("Connected successfully!")
    
    payload = {"command": "DEEP_DIAGNOSTICS"}
    sock2.sendall(json.dumps(payload).encode('utf-8'))
    
    response_data = []
    while True:
        chunk = sock2.recv(4096)
        if not chunk:
            break
        response_data.append(chunk)
    
    response_str = b"".join(response_data).decode('utf-8', errors='ignore')
    print(f"Total response length: {len(response_str)}")
    print(f"Raw response (first 500 chars): {response_str[:500]}")
    sock2.close()
    
except Exception as e:
    print(f"Socket error: {type(e).__name__}: {e}")
