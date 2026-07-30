# NOC & AI Observability - Phase 3 Audit Matrix
**Tanggal Audit:** 20 Juli 2026

Berdasarkan permintaan *deep-dive audit* terhadap 10 pilar observabilitas tingkat lanjut, berikut adalah evaluasi kondisi sistem saat ini secara riil pada *production codebase*.

---

### 1. AI Evidence Grounding (Status: ⚠️ PARTIAL)
*   **Kondisi Saat Ini:** Modul `evidence_reasoning_graph.py` telah membuat DAG (Directed Acyclic Graph) untuk menyimpan jejak *reasoning* dari *Evidence* ke *Hypothesis*. Namun, *Active Cognitive Engine* (pada `_active_root_cause_analysis`) hanya melakukan pencocokan string sederhana (`"cpu" in desc`, `"disk" in desc`) untuk menetapkan *Root Cause*.
*   **Risiko:** AI rentan mengalami *hallucination* (halusinasi) karena *confidence score* sering kali dimanipulasi secara *hardcoded* (ditambah 20 jika event >= 5) tanpa benar-benar menimbang bobot kualitas dari bukti forensik tersebut.

### 2. Observability Pipeline SLA (Status: ❌ MISSING)
*   **Kondisi Saat Ini:** Baik di Golang (`ingestion_server.go`) maupun Python (`ai_supervisor.py`), tidak ada injeksi *monotonic timestamp* saat event masuk, sehingga kita tidak bisa menghitung `ingestion latency` atau `event processing latency` secara akurat.
*   **Risiko:** Tidak ada visibilitas operasional terhadap SLA (apakah peringatan insiden tiba di NOC di bawah 3 detik?). Kemacetan pada NATS atau PostgreSQL tidak akan terdeteksi hingga terjadi kegagalan sistem.

### 3. Agent Self-Healing (Status: ✅ PRODUCTION-READY)
*   **Kondisi Saat Ini:** Pada Windows Agent (`main.go`), fungsi `runWatchdog()` secara aktif memantau kondisi sub-modul (AI Engine, Telemetry Collector, Heartbeat). Apabila ada modul yang *crash*, watchdog otomatis me-restart modul tersebut dengan implementasi *backoff delay*.
*   **Catatan:** Meskipun restart internal berfungsi, agent belum memiliki kemampuan *Self-Update/Rollback* biner secara otomatis tanpa campur tangan *Remote Launcher*.

### 4. Dependency Mapping & 5. Service Dependency Graph (Status: ❌ MISSING)
*   **Kondisi Saat Ini:** AI melakukan observasi per-node (per PC). Tidak ada graf relasional yang memetakan bahwa "Browser pada PC-A" bergantung pada "NATS di Server B" dan "Database di Server C".
*   **Risiko:** Jika NATS mati, agen tidak dapat melaporkan data. Namun, dashboard tidak bisa menampilkan *Root Cause* yang menunjukkan bahwa "Agent gagal karena Broker Down", melainkan hanya melihat "Agent Offline".

### 6. OpenTelemetry Compatibility (Status: ❌ MISSING)
*   **Kondisi Saat Ini:** Skema *telemetry_logs* (`schema.go`) menggunakan format *proprietary* (Agent, IP, Timestamp, Metadata). Tidak ada konsep `Trace ID` murni, `Span ID`, maupun eksportir standar (OTLP).
*   **Risiko:** Vendor lock-in. Sulit untuk mengintegrasikan metrik dengan *tools* standar industri seperti Jaeger, Prometheus, atau Datadog di masa depan.

### 7. Time Synchronization (Status: ⚠️ PARTIAL)
*   **Kondisi Saat Ini:** Backend (Ingestion Server) dan AI Supervisor sama-sama mengambil waktu dari OS lokal masing-masing (`time.Now().Unix()`). Namun, tidak ada protokol NTP yang dipaksakan atau deteksi *clock skew* antara Agent (di PC klien) dan Server.
*   **Risiko:** Event dari agen yang jam PC-nya tertinggal 5 menit bisa dianggap sebagai data usang dan ditolak oleh AI, atau merusak alur kronologi (Timeline) di Dashboard RCA.

### 8. AI Auditability (Status: ⚠️ PARTIAL)
*   **Kondisi Saat Ini:** Ada `log_ai_pipeline()` di `ai_supervisor.py` yang menyimpan *prompt*, *LLM response*, dan *confidence* ke dalam tabel `ai_audit_trail`. 
*   **Risiko:** Versi model LLM sering kali tidak dicatat dengan presisi, dan korelasi deterministik dari DAG tidak di-render ke UI. Hasil audit hanya bisa dibaca oleh *Database Administrator*.

### 9. Resource Forecasting (Status: ✅ PRODUCTION-READY)
*   **Kondisi Saat Ini:** Di dalam `active_cognitive_engine.py`, fungsi `_active_prediction()` sudah mampu memprediksi tren *Disk Exhaustion* dan *CPU Saturation* berbasis historis (time-series). AI dapat mengirim pesan *Early Warning* ke NOC sebelum masalah berdampak.
*   **Catatan:** Fokus metrik masih terbatas pada CPU dan Disk. Forecasting Queue NATS dan Memory DB belum ada.

### 10. AI Hallucination Guard (Status: ❌ MISSING)
*   **Kondisi Saat Ini:** AI Engine akan *selalu* mengeluarkan Root Cause, meskipun buktinya sangat minim atau tidak ada (misalnya: *root_cause = "Unknown (No Evidence)"* dipaksa masuk). Tidak ada blokir deterministik yang secara vokal mengatakan *"Bukti tidak mencukupi untuk menentukan akar penyebab."*
*   **Risiko:** Operator NOC dapat diarahkan untuk memecahkan masalah menggunakan RCA palsu dari AI (membuang MTTR dan tenaga).

---

### Kesimpulan Prioritas Perbaikan (Berdasarkan Impact)
1. **[CRITICAL] AI Hallucination Guard & Evidence Grounding:** Modifikasi AI Supervisor agar berani me-reject incident jika bobot bukti forensik di bawah ambang batas (Threshold).
2. **[HIGH] OpenTelemetry & SLA Pipeline:** Suntikkan *TraceID* standar (UUID v7) dari hulu (Agent) ke hilir (Dashboard) untuk perhitungan latensi P99 yang presisi.
3. **[MEDIUM] Service Dependency Graph:** Integrasikan tabel `fleet_topology` (jika ada) ke dalam `KnowledgeGraph` agar AI memahami topologi jaringan.
