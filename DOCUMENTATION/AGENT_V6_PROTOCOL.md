# AGENT V6 COMMUNICATION PROTOCOL & CONTRACT
**Version:** 6.0.0
**Status:** DRAFT (Under Review)
**Target Layer:** Ingress & Ingestion Layer
**Integration Target:** LF-1 to LF-5 Continuous Learning Foundation

## 1. PHILOSOPHY & OBJECTIVE
Protokol V6 dirancang secara mutlak untuk menghubungkan *Raw Telemetry* dari Agen Klien (Windows/Linux) menuju *Continuous Learning Foundation (LF-1 s/d LF-5)*. Tidak ada lagi data mentah tanpa asal-usul (lineage), dimensi waktu yang ambigu, atau umpan balik eksekusi yang dangkal. V6 mengunci jaminan kualitas data sejak agen memulai koneksi.

## 2. MESSAGE ENVELOPE (STANDARD HEADER)
Semua komunikasi (Telemetry, Command, Feedback, Handshake) dibungkus dalam *Envelope* standar. Sistem secara instan menolak *(Drop)* segala bentuk *payload* yang tidak mematuhi skema dasar ini.

```json
{
  "envelope": {
    "protocol_version": "v6.0",
    "schema_version": "1.0",
    "capability_version": "1.2",
    "message_type": "TELEMETRY | COMMAND | FEEDBACK | HANDSHAKE",
    "correlation_id": "uuid-v4-string",
    "trace_id": "otel-trace-id",
    "tenant_id": "tenant-01",
    "device_id": "host-xyz",
    "timestamp": "2026-07-22T14:30:00Z",
    "timezone": "Asia/Jakarta",
    "clock_offset_ms": 15,
    "signature": "hmac-sha256-hash"
  },
  "payload": { ... }
}
```

## 3. CAPABILITY NEGOTIATION (HANDSHAKE)
Mekanisme krusial untuk skalabilitas masa depan (Phase 3). Saat Agen terhubung, terjadi negosiasi kemampuan (Capability Handshake).

**Langkah 1: Agent Mengirim HELLO**
```json
{
  "envelope": { "message_type": "HANDSHAKE" },
  "payload": {
    "action": "HELLO",
    "supports": [
      "remediation_v2",
      "ebpf_sensor",
      "dry_run",
      "timeout_enforcement",
      "rollback_engine",
      "feature_hash",
      "temporal_sync"
    ]
  }
}
```

**Langkah 2: Server Menjawab WELCOME**
```json
{
  "envelope": { "message_type": "HANDSHAKE" },
  "payload": {
    "action": "WELCOME",
    "enable": [
      "remediation_v2",
      "feature_store",
      "temporal_sync"
    ],
    "disable": [
      "prediction_pack"
    ]
  }
}
```
*Catatan: Fitur yang dinonaktifkan *(disabled)* oleh server wajib dimatikan oleh agen klien untuk menghemat memori dan bandwidth.*

## 4. TELEMETRY PAYLOAD (Suplai Feature Store & Infra Learning)
Data metrik dari agen ke server. Berisi bobot kualitas dan hash unik.

```json
{
  "envelope": { "message_type": "TELEMETRY" },
  "payload": {
    "metric_class": "CPU_USAGE",
    "value": 85.5,
    "unit": "percent",
    "sample_interval_ms": 1000,
    "quality_score": 0.95,
    "feature_checksum": "sha256-hash",
    "metadata": {
      "process_count": 145,
      "sensor_source": "procfs"
    }
  }
}
```

## 5. COMMAND PAYLOAD (Server ➔ Agent)
Perintah perbaikan dari AI (Konsensus) untuk agen klien. Memperkenalkan pembatasan *Blast Radius*.

```json
{
  "envelope": {
    "message_type": "COMMAND",
    "correlation_id": "incident-12345"
  },
  "payload": {
    "command_id": "remediation-777",
    "action": "RESTART_SERVICE",
    "target": "nginx",
    "parameters": {},
    "safety_controls": {
      "dry_run": false,
      "timeout_ms": 15000,
      "max_cpu_percent": 30,
      "allow_rollback": true
    }
  }
}
```

## 6. FEEDBACK PAYLOAD (Umpan Balik LF-3 Remediation Learning)
Tanggapan dari agen setelah skrip mitigasi selesai (atau gagal).

```json
{
  "envelope": {
    "message_type": "FEEDBACK",
    "correlation_id": "incident-12345"
  },
  "payload": {
    "command_id": "remediation-777",
    "execution_status": "SUCCESS | FAILED | TIMEOUT | ROLLED_BACK",
    "resolution_time_ms": 4500,
    "error_count": 0,
    "service_restored": true,
    "evidence_log": "Service nginx restarted successfully. Process ID 45521."
  }
}
```

## 7. SECURITY & RETRY POLICY
*   **Security Signature**: Agen harus menghitung `HMAC-SHA256` dari `payload` menggunakan `OSI_SECURITY_KEY` dan menaruhnya di atribut `signature`. 
*   **Retry Policy (Offline Handling)**: Jika koneksi Server (TCP 18800) terputus:
    *   Agen dilarang membuang log ke /dev/null. 
    *   Log disimpan dalam antrean lokal `Retry Queue` (Maks 50MB / 1 jam).
    *   Agen membungkus ulang (Re-envelope) saat terkoneksi dengan menyertakan `timestamp` asli kejadian dan `clock_offset_ms` saat terhubung, sehingga LF-5 Temporal Engine tidak bingung dengan data lama yang terlambat datang.
*   **Compression Policy**: Payload harus dikompresi menggunakan *Zstandard (zstd)* apabila ukuran batch `payload` melebihi 16KB.
