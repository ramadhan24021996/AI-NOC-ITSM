# 🛡️ PANDUAN PORT NETWORK & ATO FIREWALL TOPOLOGY ENTERPRISE

**Dokumen Kepatuhan Jaringan & Keamanan:** `v3.0.0-PROD-HA`  
**Target Pembaca:** `Tim Network Engineer, SecOps, SysAdmin, & DevOps Enterprise`

---

## 📊 Matriks Alokasi Port Jaringan Enterprise

Tabel berikut menentukan aturan pembukaan port firewall (iptables/ufw/firewalld) dan Load Balancer enterprise:

```
+----------------------------------------------------------------------------------------------------------------------------------+
|                                    MATRIKS ALOKASI PORT & FIREWALL RULES ENTERPRISE                                              |
+----------------------------------------------------------------------------------------------------------------------------------+
| Port  | Protokol | Direction | Source Scope           | Target Service             | Deskripsi & Garansi Keamanan                 |
+-------+----------+-----------+------------------------+----------------------------+----------------------------------------------+
| 8099  | TCP      | INBOUND   | Admin / NOC Subnet     | OSI NGINX Reverse Proxy    | Portal Web Dashboard HTTP Unencrypted        |
| 9443  | TCP      | INBOUND   | Admin / NOC Subnet     | OSI NGINX Reverse Proxy    | Portal Web Dashboard HTTPS TLS 1.3           |
| 4222  | TCP      | INBOUND   | Local Subnet & Agents  | NATS JetStream Client      | Telemetry Stream & Command Channel           |
| 6222  | TCP      | INTERNAL  | NATS Cluster Pods Only | NATS Cluster Mesh Node 1   | Komunikasi Internal Mesh Quorum Node 1       |
| 6223  | TCP      | INTERNAL  | NATS Cluster Pods Only | NATS Cluster Mesh Node 2   | Komunikasi Internal Mesh Quorum Node 2       |
| 6224  | TCP      | INTERNAL  | NATS Cluster Pods Only | NATS Cluster Mesh Node 3   | Komunikasi Internal Mesh Quorum Node 3       |
| 8222  | TCP      | INTERNAL  | Internal Monitoring    | NATS Monitoring HTTP API   | Monitoring Quorum & Metrics Stream           |
| 5432  | TCP      | INTERNAL  | Go Core & Python AI    | PostgreSQL Primary DB      | Write Host Utama (Master Database)           |
| 5433  | TCP      | INTERNAL  | Go Core & Refresher    | PostgreSQL Read Replica    | Read Host Replica (Streaming Replication)    |
| 6379  | TCP      | INTERNAL  | Core Services Only     | Redis Hybrid Cache & Lock  | Pub/Sub Reload & Distributed Locks           |
| 18800 | TCP      | INBOUND   | Client Agents (Go/Win) | Go Ingestion Server        | Direct Agent Telemetry Receiver (Port Utama) |
| 18802 | TCP      | INBOUND   | Client Agents (Go/Win) | Go Ingestion Server        | Direct Agent Telemetry Receiver (Port Cad)   |
| 9998  | TCP      | INBOUND   | Client Agents / Relay  | Secure Encrypted Relay     | Remote Encrypted Action Relay (AES-256)      |
+----------------------------------------------------------------------------------------------------------------------------------+
```

---

## 🔒 Aturan Konfigurasi UFW / IPTables

Jalankan perintah berikut di Server Production:

```bash
# 1. Definisikan Default Policy (Zero-Trust)
sudo ufw default deny incoming
sudo ufw default allow outgoing

# 2. Port Akses Operator NOC & Dashboard (Nginx)
sudo ufw allow 8099/tcp comment 'OSI Dashboard HTTP'
sudo ufw allow 9443/tcp comment 'OSI Dashboard HTTPS'

# 3. Port Koneksi Agen Telemetri Endpoint (NATS & Ingestion)
sudo ufw allow 4222/tcp comment 'NATS JetStream Agent Client Port'
sudo ufw allow 18800/tcp comment 'Go Ingestion Agent Primary'
sudo ufw allow 18802/tcp comment 'Go Ingestion Agent Backup'
sudo ufw allow 9998/tcp comment 'Secure Encrypted Relay'

# 4. Port Internal NATS Mesh Cluster (Hanya antar IP Server Cluster)
sudo ufw allow from 10.0.0.0/8 to any port 6222 proto tcp comment 'NATS Cluster Route 1'
sudo ufw allow from 10.0.0.0/8 to any port 6223 proto tcp comment 'NATS Cluster Route 2'
sudo ufw allow from 10.0.0.0/8 to any port 6224 proto tcp comment 'NATS Cluster Route 3'

# 5. Reload UFW Firewall
sudo ufw reload
```
