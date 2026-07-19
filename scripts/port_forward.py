import socket
import threading
import sys
import time

def forward(src, dst):
    try:
        while True:
            data = src.recv(4096)
            if not data:
                break
            dst.sendall(data)
    except Exception:
        _ = None
    finally:
        try:
            src.close()
        except:
            _ = None
        try:
            dst.close()
        except:
            _ = None

def handle_client(client_socket, target_port):
    try:
        target_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        target_socket.connect(('127.0.0.1', target_port))
        
        # Start bidirectional forwarding
        threading.Thread(target=forward, args=(client_socket, target_socket), daemon=True).start()
        threading.Thread(target=forward, args=(target_socket, client_socket), daemon=True).start()
    except Exception as e:
        client_socket.close()

def start_proxy(listen_ip, port):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((listen_ip, port))
        server.listen(100)
        print(f"[OK] Proxy listening on {listen_ip}:{port} -> 127.0.0.1:{port}", flush=True)
    except Exception as e:
        print(f"[ERR] Failed to bind proxy on {listen_ip}:{port}: {e}", flush=True)
        return

    while True:
        try:
            client_sock, addr = server.accept()
            threading.Thread(target=handle_client, args=(client_sock, port), daemon=True).start()
        except Exception:
            break

def main():
    listen_ip = sys.argv[1] if len(sys.argv) > 1 else '0.0.0.0'
    ports = [8099, 9443, 18800, 9998, 44600]
    print(f"[*] Starting OSI NOC Proxy on IP {listen_ip}...", flush=True)
    
    threads = []
    for port in ports:
        t = threading.Thread(target=start_proxy, args=(listen_ip, port), daemon=True)
        t.start()
        threads.append(t)
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[*] Proxy shutting down...", flush=True)

if __name__ == '__main__':
    main()
