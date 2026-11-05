# 00 — System Baseline Inventory Report

**System**: OSI NOC IT AI — Autonomous Enterprise AI-Driven Incident Analysis Platform  
**Evaluation Standard**: Zero-Assumption & Zero-Mock Runtime Baseline  
**Environment**: Production System Baseline Audit  

---

## 1. System & Hardware Baseline Specs

- **OS / Kernel**: Linux `7.0.0-28-generic` #28-Ubuntu SMP PREEMPT_DYNAMIC x86_64
- **Host Name**: `it-itsm-Vostro-5470`
- **CPU Cores**: 4 Cores (`Intel(R) Core(TM) i5-4210U CPU @ 1.70GHz`)
- **System Memory**: Total: 7.2 GiB | Used: 4.4 GiB | Available: 2.7 GiB | Swap: 8.0 GiB (3.7 GiB Used)
- **Primary Disk Space**: `/dev/sda2` Size: 233 GiB | Used: 74 GiB (34%) | Available: 148 GiB

---

## 2. Container Inventory & Health Status

| Container Name | Status | Port Mappings / Binding | Host Access |
| :--- | :--- | :--- | :--- |
| `osi-nginx` | Up (Healthy) | `80->80/tcp`, `9443->443/tcp` | Public Proxy |
| `osi-dashboard-server` | Up (Healthy) | `9999/tcp` | Internal (Proxied by Nginx) |
| `osi-postgres` | Up (Healthy) | `127.0.0.1:5433->5432/tcp` | Localhost Only |
| `osi-nats` | Up (Healthy) | `4222->4222/tcp`, `127.0.0.1:8222->8222` | Internal / Event Bus |
| `nats-node1` & `nats-node2` | Up (Healthy) | `4223->4223/tcp`, `6223->6223`, `8223->8223` | Cluster Mesh |
| `osi-redis` | Up (Healthy) | `6379/tcp` | Docker Network Only |
| `osi-python-ai-core` | Up (Healthy) | Internal microservice | Docker Network Only |
| `osi-ai-consensus` / `policy` / `critic` | Up (Healthy) | Internal microservices | Docker Network Only |
| `osi-secure-relay` | Up (Healthy) | `9998->9998/tcp` | HMAC Relay |
| `osi-ingestion-server` | Up (Healthy) | `18800->18800/tcp`, `18802->18802/tcp` | Telemetry Collector |
| `osi-telegram-bot` | Up (Healthy) | Internal listener | Outbound HTTP to Telegram |
| `osi-kafka` & `osi-kafka-ui` | Up (Healthy) | `8090->8080/tcp`, `29092->29092` | Stream UI |
| `n8n_workflow_engine` | Up (Healthy) | `5678->5678/tcp` | Automation Engine |

---

## 3. Storage & Database Metrics

- **Database Name**: `osi_system`
- **Engine**: PostgreSQL 16 with `pgvector` extension
- **Total Tables**: **428 Tables** in schema `public`
- **Database Storage Size**: **2.64 GB (2,639 MB)**
- **Event Bus Engine**: NATS JetStream 2.10 (Stream: `telemetry_stream_critical`)

---

## 4. Operational Logging & Artifact Paths

- **System Logs**: `/var/log/syslog`, `docker logs`
- **Dashboard Logs**: `/home/it-itsm/AI/incident-analysis/build/bin/portal`
- **Python AI Core Logs**: `/home/it-itsm/AI/incident-analysis/SERVER/python_ai_core/`
- **Audit Documentation**: `/home/it-itsm/AI/incident-analysis/docs/production-hardening/`

- **Verdict**: **BASELINED (VERIFIED)** — Runtime system inventory captured accurately.
