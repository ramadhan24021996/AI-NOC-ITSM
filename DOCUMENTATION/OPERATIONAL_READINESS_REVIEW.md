# OPERATIONAL READINESS REVIEW (ORR)
**Phase:** 2.5.5 (Final Gate before Phase 2.6 Canary Infrastructure)
**Target:** Ingestion Server & Learning Dispatcher

Dokumen ini adalah Syarat Mutlak (Exit Criteria) yang harus dipenuhi 100% sebelum baris kode Agent V6 dan Go Ingestion V6 diproduksi atau di-*deploy*.

## ORR-1: Protocol Certification
Spesifikasi protokol komunikasi harus final dan terkunci.
*   **RFC Version**: Frozen
*   **JSON Schema**: Frozen
*   **Envelope State Machine**: Frozen
*   **ACK State Machine**: Frozen
*   **Error Registry**: Frozen

## ORR-2: Compatibility Certification
Arsitektur pergerakan data dari Agent lama tidak boleh menabrak sistem secara langsung.
*   **MUST**: `V5 ➔ Adapter ➔ Dispatcher ➔ Learning`
*   **MUST NOT**: `V5 ➔ Learning` (Bypass Dispatcher dilarang keras)

## ORR-3: Performance Certification (Budgeting)
Anggaran latensi dan sumber daya yang diperbolehkan.
*   **Go Ingestion Throughput**: ≥ 10.000 event/sec
*   **Go Ingestion Latency**: P95 < 10 ms, P99 < 20 ms
*   **Go Ingestion Resource**: RAM < 300 MB, CPU < 25%
*   **Dispatcher Fan-out Latency**: < 2 ms

## ORR-4: Failure Isolation
Menguji isolasi murni *Shadow Layer*.
*   **Skenario**: `Learning Crash ➔ Dispatcher Menangkap Exception ➔ Tulis ke Log ➔ Incident Engine Tetap Hidup`
*   **Larangan**: `Learning Crash` TIDAK BOLEH menyebabkan *panic()* yang meruntuhkan `Go Ingestion` atau `NATS`.

## ORR-5: Recovery & State Test
Menguji pemulihan otomatis dari mati paksa komponen inti.
*   **Aksi**: *Restart* PostgreSQL, Redis, NATS, AI Core, dan Dispatcher.
*   **Kriteria Lulus**: No Data Loss, No Duplicate Data, Resume processing otomatis.

## ORR-6: Capacity Test (Load Testing)
Skalabilitas bukan asumsi, melainkan bukti uji beban.
*   **Tahapan Beban**: 100, 500, 1.000, 3.000, 5.000, dan 10.000 events/sec.
*   **Metrik Penilaian**: CPU, RAM, Kedalaman Antrean (*Queue Depth*), Retry, dan status ACK.

## ORR-7: Security Review (Anti-Replay)
Pengamanan Kriptografis V6.
*   **Replay Protection**: Token kombinasi `Nonce` + `Timestamp` + `TTL`.
*   **Key Rotation**: Header `KeyID`, server secara dinamis memilih rahasia HMAC.
*   **Signature Expiration**: Pesan dengan selisih waktu `> 5 menit` otomatis *REJECT*.

## ORR-8: Observability Review
Ekspor visibilitas operasional ke *Prometheus/Netdata*.
*   **Dispatcher**: `dispatcher_events_total`, `dispatcher_failed_total`, `dispatcher_latency_ms`, `dispatcher_queue_size`, `dispatcher_drop_total`.
*   **Agent**: `retry_queue_size`, `retry_sent`, `retry_failed`, `clock_drift`, `compression_ratio`.
*   **Ingestion**: `ack_received`, `ack_validated`, `ack_committed`, `schema_rejected`, `auth_failed`.

## ORR-9: Rollback Certification
SOP Pemulihan jika Ingestion V6 membunuh performa *server*.
*   **Langkah**: `V6 Native OFF ➔ Close Port 18806 ➔ 18800 Adapter ON ➔ Dispatcher Passive ➔ Learning OFF ➔ Monitoring Normal`.
*   **Target Rollback**: < 5 Menit.
*   **Catatan**: Rollback harus *scripted* dan dapat diotomatisasi, tidak sekadar mengandalkan `git checkout`.

## ORR-10: Canary Promotion Rules
Aturan penggelaran bertahap agen klien V6 (Tahap demi tahap, bukan *"Big Bang"*).
*   **Fase Rollout**: `1 Agent ➔ 10 Agent ➔ 50 Agent ➔ 100 Agent ➔ 500 Agent ➔ 100% Fleet`.
*   **Syarat Promosi (Per Fase)**: 
    *   CPU < 60%, Memory < 70%.
    *   Error Rate < 0.1%.
    *   No Duplicate, No Panic, No Rollback Triggered.
    *   **Resource Leak Checks**: No Memory Leak, No Goroutine Leak, No Connection Leak.
    *   **Waktu Stabil**: Minimum 24 Jam sebelum promosi ke fase agen berikutnya.

## ORR-11: Data Governance Review (WAJIB)
Kebijakan pengelolaan masa hidup (retention) data untuk skalabilitas jangka panjang miliaran baris.
*   **Feature Store Retention**: 365 hari.
*   **Evidence Retention**: 180 hari.
*   **Telemetry Raw Retention**: 30 hari (Sisanya dipindah ke Cold Storage Archive).
*   **Audit Trail Retention**: Permanent (Tidak boleh dihapus).
*   **Kepatuhan Ekstra**: PII Classification & Checksum Validation pada arsip *Cold Storage*.

## ORR-12: Schema Evolution
Tata kelola evolusi protokol agar tidak merusak versi sebelumnya.
*   **Registry Format**: Semua pembaruan harus `Backward Compatible`.
*   **Deprecated Fields**: Komponen tidak langsung menghapus atribut; harus ada `Migration Window`.
*   **Target Fleksibilitas**: `Agent V6.0` harus tetap dapat melapor ke `Server V6.2` secara mulus tanpa *upgrade client*.

## ORR-13: Learning Safety
Penghalang kualitas (*Quality Threshold*) sebelum data menjadi memori sistem AI.
*   **Confidence < 0.70**: Feature Rejected (Dibuang agar tidak mencemari Feature Store).
*   **Confidence 0.70 - 0.85**: Menunggu Persetujuan Manusia (*Need HITL*).
*   **Confidence > 0.85**: Learning Accepted (Masuk secara *Autonomous*).

## ORR-14: Deployment Gate Automation
Seluruh gerbang ORR tidak dinilai menggunakan daftar centang (*checklist*) manual yang rentan kesalahan (Human Error).
*   **Automasi Pipeline**: Harus ada pengeksekusi kode otomatis (contoh: `deployment_gate.py`).
*   **Execution Flow**: `ORR-1 PASS ➔ ORR-2 PASS ➔ ... ➔ ORR-18 PASS ➔ ALLOW DEPLOYMENT`.

## ORR-15: SLO / Error Budget
Disiplin *Site Reliability Engineering (SRE)* ketat yang mengukur ketersediaan servis nyata.
*   **Service Level Objective (SLO)**: Availability Server `99.95%`, Dispatcher `99.99%`, Learning `99.9%`, ACK `99.999%`.
*   **Error Budget**: `0.05%` per bulan.
*   **Konsekuensi**: Jika *Error Budget* habis ➔ **STOP Feature Development** ➔ Pindah ke status **Bug Fix Only**.

## ORR-16: Disaster Recovery
Parameter waktu pemulihan mutlak jika bencana infrastruktur (*Database Corrupt*) terjadi.
*   **Recovery Point Objective (RPO)**: ≤ 1 menit (Maksimal data tertinggal/hilang).
*   **Recovery Time Objective (RTO)**: ≤ 15 menit (Waktu maksimum sistem harus *online* kembali lewat *Snapshot Restore* & *Replay NATS*).

## ORR-17: Supply Chain Security
Memastikan tidak ada celah kerentanan sejak agen dikompilasi hingga dirilis (*Shift-Left Security*).
*   **Parameter Pengecekan**: SBOM (*Software Bill of Materials*), *Dependency Scan*, *Artifact Signing*, *Binary Checksum*, dan *Container Signature*.

## ORR-18: Configuration Management
*Hardcoding* adalah dosa SRE; segala bentuk kesalahan *setup* harus dapat di-*rollback*.
*   **Kriteria Lulus**: `Config Version ➔ Checksum Validation ➔ Hot Reload ➔ Rollback Config`.
