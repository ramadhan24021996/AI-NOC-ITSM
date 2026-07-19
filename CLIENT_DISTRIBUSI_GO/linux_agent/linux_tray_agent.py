#!/usr/bin/env python3
import socket
import json
import threading
import webbrowser
import logging
import time
import os

# Set up simple logging
logging.basicConfig(level=logging.INFO, format='[LINUX TRAY] %(message)s')

def handle_client(client_socket):
    try:
        data = client_socket.recv(4096).decode('utf-8').strip()
        if not data:
            return
        
        payload = json.loads(data)
        cmd = payload.get("command", "")
        
        if cmd == "SHOW_CHAT":
            url = payload.get("url", "http://127.0.0.1")
            logging.info(f"Opening Chat UI: {url}")
            # This safely runs in the user-space and launches the default Desktop Browser
            webbrowser.open(url, new=1, autoraise=True)
    except Exception as e:
        logging.error(f"Error handling request: {e}")
    finally:
        client_socket.close()

def start_server():
    host = '127.0.0.1'
    port = 10001
    
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind((host, port))
        server.listen(5)
        logging.info(f"OSI AI Linux UI Agent running on {host}:{port}")
        logging.info(f"User Display Env: {os.environ.get('DISPLAY', 'Not Set')}")
    except Exception as e:
        logging.error(f"Failed to bind port {port}: {e}")
        return

    while True:
        try:
            client_socket, addr = server.accept()
            client_handler = threading.Thread(target=handle_client, args=(client_socket,))
            client_handler.daemon = True
            client_handler.start()
        except KeyboardInterrupt:
            logging.info("Shutting down UI Agent.")
            break
        except Exception as e:
            logging.error(f"Accept error: {e}")
            time.sleep(1)

if __name__ == '__main__':
    start_server()
