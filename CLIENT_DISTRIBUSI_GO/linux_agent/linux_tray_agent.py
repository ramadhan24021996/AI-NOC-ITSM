#!/usr/bin/env python3
import socket
import json
import threading
import webbrowser
import logging
import subprocess
import time
import os

# Set up simple logging
logging.basicConfig(level=logging.INFO, format='[LINUX TRAY] %(message)s')

def open_chat_window(server_ip="10.20.0.154", title="", message=""):
    gui_paths = [
        "/tmp/linux_chat_ui.py",
        "/opt/osi-agent/linux_chat_ui.py",
        os.path.expanduser("~/.config/osi-agent/linux_chat_ui.py"),
        "/home/it-itsm/AI/incident-analysis/CLIENT_DISTRIBUSI_GO/linux_agent/linux_chat_ui.py",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "linux_chat_ui.py")
    ]
    for gui_path in gui_paths:
        if os.path.exists(gui_path):
            try:
                logging.info(f"Launching Native Linux Desktop Tray Chat GUI: {gui_path}")
                cmd = ["python3", gui_path, "--server", server_ip]
                if title:
                    cmd.extend(["--title", title])
                if message:
                    cmd.extend(["--msg", message])
                subprocess.Popen(cmd)
                return
            except Exception as e:
                logging.error(f"Failed to launch native chat GUI: {e}")

    url = f"http://{server_ip}/?mode=chat#live-chat"
    logging.info(f"Launching OSI AI Support Chat Browser UI: {url}")
    browsers = ["google-chrome", "chromium-browser", "chromium", "microsoft-edge", "msedge"]
    launched = False
    for b in browsers:
        try:
            subprocess.Popen([b, f"--app={url}"])
            launched = True
            break
        except Exception:
            continue
    if not launched:
        webbrowser.open(url, new=1, autoraise=True)

def handle_client(client_socket):
    try:
        data = client_socket.recv(4096).decode('utf-8').strip()
        if not data:
            return
        
        payload = json.loads(data)
        cmd = payload.get("command", "")
        
        if cmd == "SHOW_CHAT":
            params = payload.get("params", {})
            server_ip = params.get("server_ip") or payload.get("server_ip") or "10.20.0.154"
            open_chat_window(server_ip)
            
        elif cmd == "SHOW_NOTIFICATION":
            title = payload.get("title") or (payload.get("params", {}).get("title")) or "🚨 OSI AI - Peringatan Sistem"
            message = payload.get("message") or (payload.get("params", {}).get("message")) or "Terdapat masalah pada komputer Anda. Silakan buka chat."
            params = payload.get("params", {})
            server_ip = params.get("server_ip") or payload.get("server_ip") or "10.20.0.154"
            logging.info(f"Showing Notification: {title}")
            try:
                icon_path = "/opt/osi-agent/agent.ico" if os.path.exists("/opt/osi-agent/agent.ico") else "dialog-warning"
                subprocess.run(["notify-send", "--urgency=critical", f"--icon={icon_path}", "--expire-time=10000", "-A", "chat=Buka Chat", title, message], capture_output=True, text=True)
                open_chat_window(server_ip, title, message)
            except Exception as e:
                logging.error(f"Failed to run notify-send: {e}")
                open_chat_window(server_ip, title, message)
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
