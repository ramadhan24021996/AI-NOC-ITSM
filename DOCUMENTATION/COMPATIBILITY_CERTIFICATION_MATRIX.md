# COMPATIBILITY CERTIFICATION MATRIX
**Phase:** 2.5.5 Operational Readiness Review
**Component:** Telemetry Agent & Ingestion Router

Dokumen ini mendefinisikan matriks kesesuaian operasional *(Operational Compatibility Matrix)* antara versi Agen di lapangan, mesin Router Ingestion (Go Core), dan status subsistem Pembelajaran *(Learning Dispatcher)*.

Artefak ini adalah syarat mutlak sebelum melakukan *Canary Rollout* Agen V6 ke jaringan produksi. Jika suatu konfigurasi bertanda ❌, penggelaran (*deployment*) wajib dibatalkan untuk mencegah *Split-Brain Data* atau insiden ganda.

## 1. Compatibility Matrix

| Client Agent Version | Ingestion Server Router | Dispatcher Status | Certification Result | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **V5 (Legacy)** | **V5 (Legacy)** | Aktif (Pasif) | ✅ **SUPPORTED** | Konfigurasi stabil saat ini. Dispatcher membungkus payload menggunakan `V5ProtocolAdapter`. |
| **V5 (Legacy)** | **V6 Adapter (Port 18800)** | Aktif | ✅ **SUPPORTED** | **Fase Transisi (Canary)**. Ingestion V6 membungkus (wrap) payload V5 menjadi amplop V6 sebelum dikirim ke NATS. |
| **V6 (Native)** | **V6 Native (Port 18806)** | Aktif | ⏳ **PENDING TEST** | Tujuan akhir. Jalur asli *Zero-Copy* ke *Feature Store*. |
| **V6 (Native)** | **V5 (Legacy)** | Aktif / Inaktif | ❌ **UNSUPPORTED** | **BAHAYA.** Agen V6 akan ditolak oleh Ingestion V5 karena ketidakcocokan skema dan *Envelope Isolator*. |
| **V5 (Legacy)** | **V6 Native (Port 18806)**| Aktif | ❌ **UNSUPPORTED** | Kegagalan skema mutlak. Ingestion V6 Native tidak akan melayani *payload* V5. |

## 2. Feature Capability Matrix

| Feature | Agent V5 | Agent V6 | Ingestion V5 | Ingestion V6 |
| :--- | :---: | :---: | :---: | :---: |
| **HMAC Signature Auth** | ✅ | ✅ | ✅ | ✅ |
| **Timestamp ISO-8601** | ❌ (Unix/Lokal) | ✅ | ❌ | ✅ |
| **Timezone & Clock Drift** | ❌ | ✅ | ❌ | ✅ |
| **Schema Registry Verification**| ❌ | ✅ | ❌ | ✅ |
| **Idempotency Key** | ❌ | ✅ | ❌ | ✅ |
| **Event ID (W3C Trace)** | ❌ | ✅ | ❌ | ✅ |
| **Feature Extraction Lineage** | ❌ | ✅ | ❌ | ✅ |
| **Dry Run & Timeout Limits** | ❌ | ✅ | ❌ | ✅ |
| **Resource Snapshot Feedback** | ❌ | ✅ | ❌ | ✅ |

## 3. Degradation Strategy (Rollback)

Apabila Ingestion V6 atau Agen V6 Canary mengalami galat (*Panic/Crash*) atau menimbulkan lonjakan *CPU > 80%* selama uji kapasitas:
1.  **Hentikan Canary**: Pindahkan beban kembali ke `Port 18800` (V5 Adapter).
2.  **Dispatcher Shutdown**: *Learning Dispatcher* boleh dinonaktifkan sepenuhnya. Ini tidak akan memblokir *Incident Engine* (Validasi `Gate F - Non Blocking`).
3.  **Tahan Promosi**: Matriks konfigurasi **V6 Native** tetap berstatus ⏳ hingga ORR-6 (Capacity Test) menyatakan stabil di 10.000 events/sec.

---
**Dokumen ini dibekukan sebagai acuan operasional rilis V6.**
