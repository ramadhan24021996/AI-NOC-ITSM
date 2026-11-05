#!/usr/bin/env python3
import sys
import os
import time
import urllib.request
import urllib.parse
import json
import threading
import socket
import tkinter as tk
from tkinter import ttk, scrolledtext

# ── Configuration & Colors ───────────────────────────────────────────────────
SERVER_IP = "10.20.0.154"
HOSTNAME = socket.gethostname()

COLOR_BG = "#0f172a"        # Deep slate
COLOR_CARD = "#1e293b"      # Surface slate
COLOR_HEADER = "#090d16"    # Top bar
COLOR_ACCENT = "#0284c7"    # Electric blue
COLOR_CYAN = "#06b6d4"      # Bright cyan
COLOR_TXT = "#f8fafc"       # White text
COLOR_TXT_MUTED = "#94a3b8" # Muted text
COLOR_USER_BUBBLE = "#0369a1"
COLOR_AI_BUBBLE = "#1e293b"

class OSISupportChatUI:
    def __init__(self, root, initial_title=None, initial_msg=None, server_ip=None):
        self.root = root
        self.server_ip = server_ip or SERVER_IP
        self.root.title("OSI AI Support Chat")

        # Set window size & position on top-right of screen (Tray behavior)
        width, height = 440, 640
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        pos_x = max(20, screen_w - width - 40)
        pos_y = 50
        self.root.geometry(f"{width}x{height}+{pos_x}+{pos_y}")
        self.root.configure(bg=COLOR_BG)
        self.root.attributes("-topmost", True)  # Keep on top like Tray App

        # Main Layout
        self._build_header()
        self._build_chat_area()
        self._build_action_buttons()
        self._build_input_bar()

        # Handle initial incident message if provided
        if initial_title or initial_msg:
            welcome_text = f"🚨 **{initial_title or 'Insiden Sistem'}**\n{initial_msg or 'Terdeteksi anomali pada perangkat Anda. Agen AI Siap membantu.'}"
            self._append_message("OSI AI Assistant", welcome_text, is_user=False)
        else:
            self._append_message("OSI AI Assistant", "Selamat datang di **OSI AI Support Chat**.\nBagaimana saya dapat membantu mengatasi kendala perangkat Anda hari ini?", is_user=False)

    def _build_header(self):
        header_frame = tk.Frame(self.root, bg=COLOR_HEADER, height=65)
        header_frame.pack(fill=tk.X, side=tk.TOP)
        header_frame.pack_propagate(False)

        # Title & Subtitle
        title_label = tk.Label(
            header_frame,
            text="🤖 OSI AI Support Chat",
            font=("Helvetica", 13, "bold"),
            bg=COLOR_HEADER,
            fg=COLOR_CYAN,
            anchor="w"
        )
        title_label.pack(side=tk.TOP, fill=tk.X, padx=14, pady=(10, 0))

        sub_label = tk.Label(
            header_frame,
            text=f"🟢 Online • NOC Server ({self.server_ip}) • Host: {HOSTNAME}",
            font=("Helvetica", 9),
            bg=COLOR_HEADER,
            fg=COLOR_TXT_MUTED,
            anchor="w"
        )
        sub_label.pack(side=tk.TOP, fill=tk.X, padx=14, pady=(2, 8))

    def _build_chat_area(self):
        container = tk.Frame(self.root, bg=COLOR_BG)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        self.chat_display = scrolledtext.ScrolledText(
            container,
            wrap=tk.WORD,
            bg=COLOR_BG,
            fg=COLOR_TXT,
            font=("Helvetica", 10),
            bd=0,
            highlightthickness=0,
            padx=8,
            pady=8
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True)

        # Configure Tags for Text Formatting
        self.chat_display.tag_config("user_header", font=("Helvetica", 9, "bold"), foreground=COLOR_CYAN, justify="right")
        self.chat_display.tag_config("user_msg", font=("Helvetica", 10), foreground="#ffffff", justify="right")
        self.chat_display.tag_config("ai_header", font=("Helvetica", 9, "bold"), foreground="#38bdf8", justify="left")
        self.chat_display.tag_config("ai_msg", font=("Helvetica", 10), foreground=COLOR_TXT, justify="left")
        self.chat_display.tag_config("sys_msg", font=("Helvetica", 9, "italic"), foreground=COLOR_TXT_MUTED, justify="center")

    def _build_action_buttons(self):
        btn_frame = tk.Frame(self.root, bg=COLOR_BG)
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 6))

        actions = [
            ("⚡ Cek Jaringan", "Periksa koneksi internet dan ip address"),
            ("🔄 Restart Adapter", "Restart network manager service"),
            ("📞 Hubungi NOC", "Minta bantuan teknisi NOC IT Support"),
        ]

        for label, prompt in actions:
            btn = tk.Button(
                btn_frame,
                text=label,
                font=("Helvetica", 8, "bold"),
                bg=COLOR_CARD,
                fg=COLOR_CYAN,
                activebackground=COLOR_ACCENT,
                activeforeground="#ffffff",
                bd=1,
                relief=tk.FLAT,
                padx=6,
                pady=3,
                command=lambda p=prompt: self._send_preset_query(p)
            )
            btn.pack(side=tk.LEFT, padx=3, expand=True, fill=tk.X)

    def _build_input_bar(self):
        input_frame = tk.Frame(self.root, bg=COLOR_HEADER, height=55)
        input_frame.pack(fill=tk.X, side=tk.BOTTOM)
        input_frame.pack_propagate(False)

        self.entry_msg = tk.Entry(
            input_frame,
            font=("Helvetica", 10),
            bg=COLOR_CARD,
            fg=COLOR_TXT,
            insertbackground=COLOR_TXT,
            bd=1,
            relief=tk.FLAT
        )
        self.entry_msg.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 6), pady=10)
        self.entry_msg.bind("<Return>", lambda event: self._on_send_click())

        send_btn = tk.Button(
            input_frame,
            text="Kirim ➔",
            font=("Helvetica", 9, "bold"),
            bg=COLOR_ACCENT,
            fg="#ffffff",
            activebackground=COLOR_CYAN,
            activeforeground="#000000",
            bd=0,
            padx=12,
            pady=6,
            command=self._on_send_click
        )
        send_btn.pack(side=tk.RIGHT, padx=(0, 10), pady=10)

    def _append_message(self, sender, text, is_user=False):
        self.chat_display.configure(state=tk.NORMAL)
        timestamp = time.strftime("%H:%M")
        
        if is_user:
            self.chat_display.insert(tk.END, f"\nAnda ({timestamp})\n", "user_header")
            self.chat_display.insert(tk.END, f"{text}\n", "user_msg")
        else:
            self.chat_display.insert(tk.END, f"\n🤖 {sender} ({timestamp})\n", "ai_header")
            self.chat_display.insert(tk.END, f"{text}\n", "ai_msg")

        self.chat_display.configure(state=tk.DISABLED)
        self.chat_display.see(tk.END)

    def _send_preset_query(self, query):
        self.entry_msg.delete(0, tk.END)
        self.entry_msg.insert(0, query)
        self._on_send_click()

    def _on_send_click(self):
        query = self.entry_msg.get().strip()
        if not query:
            return

        self.entry_msg.delete(0, tk.END)
        self._append_message("User", query, is_user=True)

        # Start background thread to query OSI AI Chat Engine
        threading.Thread(target=self._query_ai_engine, args=(query,), daemon=True).start()

    def _query_ai_engine(self, query):
        try:
            params = urllib.parse.urlencode({"client_id": HOSTNAME, "query": query})
            url = f"http://{self.server_ip}/api/enterprise/chat/ai_assist?{params}"
            
            req = urllib.request.Request(url, headers={"User-Agent": "OSI-Linux-Tray-Chat/2.1"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                suggestion = data.get("suggestion") or data.get("response") or "Permintaan Anda telah diterima oleh NOC Server."
                
                # Update UI in main thread
                self.root.after(0, lambda: self._append_message("OSI AI Assistant", suggestion, is_user=False))
        except Exception as e:
            err_msg = f"Gagal terhubung ke NOC Server ({self.server_ip}): {e}\nSilakan pastikan jaringan LAN/Wi-Fi terhubung."
            self.root.after(0, lambda: self._append_message("OSI System", err_msg, is_user=False))

def main():
    title = None
    msg = None
    server_ip = SERVER_IP

    # Parse CLI arguments if passed by notification trigger
    for i, arg in enumerate(sys.argv):
        if arg == "--title" and i + 1 < len(sys.argv):
            title = sys.argv[i + 1]
        elif arg == "--msg" and i + 1 < len(sys.argv):
            msg = sys.argv[i + 1]
        elif arg == "--server" and i + 1 < len(sys.argv):
            server_ip = sys.argv[i + 1]

    root = tk.Tk()
    app = OSISupportChatUI(root, initial_title=title, initial_msg=msg, server_ip=server_ip)
    root.mainloop()

if __name__ == "__main__":
    main()
