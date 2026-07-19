# PRD — Full System Reverse Engineering & Documentation

## Objective

Lakukan analisis menyeluruh terhadap seluruh isi folder `incident-analis`.

Anggap tidak ada dokumentasi yang tersedia dan jangan membuat asumsi apa pun mengenai arsitektur, teknologi, atau tujuan sistem sebelum ditemukan bukti di source code.

Seluruh hasil harus berdasarkan fakta yang ditemukan pada project.

---

# Primary Goals

- Memahami keseluruhan sistem.
- Mengidentifikasi seluruh komponen.
- Mendokumentasikan arsitektur.
- Menjelaskan hubungan antar modul.
- Menjelaskan alur data.
- Mengidentifikasi entry point.
- Menjelaskan dependency.
- Menghasilkan dokumentasi lengkap yang dapat digunakan developer baru.

---

# Analysis Rules

- Jangan mengarang informasi.
- Jangan berasumsi.
- Verifikasi setiap kesimpulan menggunakan source code.
- Sertakan lokasi file sebagai referensi.
- Jika informasi tidak ditemukan tulis **Unknown**.
- Jangan mengubah source code.
- Jangan menghapus file.
- Fokus hanya pada analisis dan dokumentasi.

---

# Scope

Analisis seluruh folder tanpa pengecualian, termasuk:

- source code
- configuration
- documentation
- scripts
- tests
- docker
- deployment
- database
- assets
- prompts
- workflow
- AI components
- MCP servers
- plugins
- integrations

---

# Required Analysis

## 1. Project Overview

Jelaskan:

- tujuan sistem
- fungsi utama
- domain aplikasi
- fitur utama

---

## 2. Directory Analysis

Dokumentasikan seluruh struktur folder.

Jelaskan fungsi setiap folder.

---

## 3. Entry Points

Temukan seluruh entry point.

Misalnya:

- main
- app
- server
- cli
- startup
- bootstrap

---

## 4. Tech Stack

Identifikasi:

- bahasa pemrograman
- framework
- runtime
- package manager
- dependency
- library utama

---

## 5. Architecture

Buat penjelasan mengenai:

- architecture pattern
- module
- service
- package
- layer
- dependency graph

---

## 6. Data Flow

Jelaskan:

User

↓

API

↓

Business Logic

↓

AI

↓

Database

↓

Response

---

## 7. AI Components

Jika ada AI.

Identifikasi:

- Agent
- Prompt
- Memory
- RAG
- MCP
- Tool Calling
- Planner
- Reflection
- Evaluation
- Embedding
- Vector Database

---

## 8. API Analysis

Dokumentasikan seluruh endpoint.

Untuk setiap endpoint tampilkan:

- URL
- Method
- Request
- Response
- Authentication
- Source File

---

## 9. Database

Identifikasi:

- database
- ORM
- migration
- schema
- model
- relationship

Buat ERD jika memungkinkan.

---

## 10. Configuration

Analisis:

- .env
- yaml
- json
- toml
- ini
- config

---

## 11. External Services

Cari integrasi:

- OpenAI
- Claude
- Gemini
- Ollama
- Redis
- PostgreSQL
- Qdrant
- Elasticsearch
- Slack
- Discord
- Telegram
- WhatsApp
- GitHub
- Email
- REST API

---

## 12. Security

Identifikasi:

- JWT
- OAuth
- RBAC
- Permission
- Encryption
- Secret Management

---

## 13. Automation

Cari:

- scheduler
- cron
- queue
- worker
- webhook
- event

---

## 14. Deployment

Analisis:

- Dockerfile
- Docker Compose
- Kubernetes
- Nginx
- CI/CD
- GitHub Actions

---

## 15. Testing

Identifikasi:

- Unit Test
- Integration Test
- E2E Test

---

## 16. Code Quality

Evaluasi:

- struktur project
- modularitas
- coupling
- cohesion
- technical debt
- duplicate code
- dead code
- unused dependency

Berikan rekomendasi perbaikan.

---

# Deliverables

Hasilkan folder `docs/` dengan minimal file berikut:

docs/
├── README.md
├── SYSTEM_OVERVIEW.md
├── ARCHITECTURE.md
├── DIRECTORY_TREE.md
├── MODULES.md
├── DATA_FLOW.md
├── API_REFERENCE.md
├── DATABASE.md
├── AI_SYSTEM.md
├── PROMPTS.md
├── MCP.md
├── MEMORY.md
├── CONFIGURATION.md
├── DEPLOYMENT.md
├── SECURITY.md
├── AUTOMATION.md
├── DEPENDENCIES.md
├── CODE_QUALITY.md
├── IMPROVEMENT_PLAN.md
└── GLOSSARY.md

---

# Evidence Requirement

Setiap temuan wajib menyertakan:

- lokasi file
- nama file
- fungsi komponen
- hubungan dengan komponen lain
- bukti potongan kode (ringkas)
- tingkat keyakinan (High/Medium/Low)

---

# Final Success Criteria

Dokumentasi harus cukup lengkap sehingga seorang developer yang belum pernah melihat proyek `incident-analis` dapat:

- memahami tujuan sistem,
- memahami arsitektur,
- mengetahui alur data,
- memahami setiap modul,
- mengetahui dependensi,
- menjalankan sistem,
- mengembangkan fitur baru,
- melakukan debugging,
- dan melakukan deployment,

tanpa harus membaca seluruh source code dari awal.s