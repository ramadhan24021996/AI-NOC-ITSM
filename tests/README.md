# Unified Testing Framework

Direktori ini didedikasikan untuk melakukan *Automated Testing* pada seluruh infrastruktur **OSI AIOps Enterprise**.

## Struktur Direktori

- **`unit/`**: Tempat untuk menguji fungsi/modul secara terisolasi tanpa memerlukan *database* atau layanan eksternal.
  - `go_core/`: *Unit tests* untuk Golang Ingestion Server dan Edge Agents (`_test.go`).
  - `python_ai/`: *Unit tests* untuk Python AI Supervisor dan Causal DAG Engine menggunakan `pytest`.

- **`integration/`**: Tempat untuk menguji perpaduan antar-komponen (membutuhkan NATS, PostgreSQL, atau Redis).
  - `go_core/`: *Integration tests* untuk alur dari Agen ke NATS.
  - `python_ai/`: *Integration tests* untuk siklus Multi-Agent Debate dan Database Pgvector.

## Menjalankan Tes
- Untuk Python: Jalankan `pytest tests/unit/python_ai` dari direktori *root*.
- Untuk Go: Jalankan `go test ./tests/unit/go_core/...` dari direktori *root*.
