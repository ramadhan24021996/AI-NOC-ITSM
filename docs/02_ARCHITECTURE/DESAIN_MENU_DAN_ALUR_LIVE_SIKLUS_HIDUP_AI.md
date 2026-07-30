# 🎨 DESAIN MENU & PANEL LIVE SIKLUS HIDUP AI TOPOLOGY (DARK GLASSMORPHISM)
> **Sistem:** Incident Analysis Platform — Autonomous AI Ops & Proactive Root Cause Analysis  
> **Tujuan:** Membuat **Menu & Panel Dedicated "AI Lifecycle & Flow"** pada Dashboard & Overview dengan tampilan visual 9-layer modern, rapi, dan memiliki **Animasi Aliran Data Real-Time (*Live Stream Signal Pulse*)**.

---

## 📍 1. PENEMPATAN MENU & INTEGRASI PANET

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ SIDEBAR NAVIGATION MENU (AI OPS SECTION)                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ 💻 Runtime Engine Monitor                                                  │
│ 🤖 AI Ops Dashboard                                                         │
│ 🧠 AI Lifecycle & Flow  ◄─── [MENU BARU TERDEDIKASI (Live Flowing Signal)]  │
│ 🎓 Training Feedback                                                        │
│ 🧠 AI Decision Logs                                                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🗺️ 2. SKEMA TAMPILAN PANEL VISUAL (`#p-ai_lifecycle_topology`)

Panel ini memiliki 4 area utama:
1. **Live Header Banner:** Menampilkan metrik real-time (*Events/sec, NATS Latency < 5ms, RAG Search < 120ms, HITL Safeguard 100% Enforced*).
2. **Control Bar:** Tombol `[ ⚡ Play Live Motion ]`, `[ ⏸️ Pause ]`, `[ 🔍 Zoom In/Out ]`, `[ 📄 Export SVG/PNG ]`.
3. **Full 9-Layer Flowchart Canvas:** Diagram berestetika *Dark Glassmorphism* dengan blok berwarna presisi (matching gambar):
   - 🟦 **Layer 0 - Client & User:** System Admin, Chrome Assistant, Telegram Gateway
   - 🩵 **Layer 1 - Web Presentation:** Portal Web UI, HITL Queue, Knowledge Base RAG UI
   - 🩵 **Layer 2 - API Gateway:** HTTP REST API Gateway (:8080), WebSocket Stream
   - 🏢 **Layer 3 - Go Core Backend:** Go Server Core (Gin), Secure Encrypted Relay
   - 🟪 **Layer 4 - Python AI Engine:** Active Observer 24/7, Causal DAG, RAG 2.0, Multi-LLM Router (DeepSeek/Gemini/Groq)
   - 🟧 **Layer 5 - Broker & Persistence:** NATS JetStream (:4222), Netdata Collector (:19999), SQLite WAL DBs
   - 🟩 **Layer 6 - Endpoint Agents:** Windows Agent Service, Linux Agent Service
4. **Interactive Component Inspector Modal:** Mengklik box mana pun di kanvas membuka modal statistik live untuk service tersebut.

---

## ✨ 3. EFEK ANIMASI LIVE SIKLUS HIDUP (*LIVE STREAM MOTION*)

- **Glow & Particle Signal Pulse:** Titik-titik sinyal cahaya neon kecil mengalir menyusuri garis konektor SVG dari Agen (`Layer 6`) ➔ NATS (`Layer 5`) ➔ Active Observer (`Layer 4`) ➔ Causal DAG ➔ RAG 2.0 ➔ Multi-LLM Router ➔ HITL Queue (`Layer 1`).
- **Pulsing Active Nodes:** Komponen yang sedang aktif menginferensi data akan berkedip menyala (`animation: pulseNode 1.2s infinite alternate`).

---

## 🚀 4. PERSIAPAN EKSEKUSI PENERAPAN KODE (`portal/templates/index.html`)

1. **Menambahkan Nav Item Sidebar:** `data-panel="ai_lifecycle_topology"`.
2. **Menambahkan HTML Panel:** `<div id="p-ai_lifecycle_topology" class="panel">`.
3. **Menambahkan Engine Renderer & Script Animasi WebSocket Stream.**
