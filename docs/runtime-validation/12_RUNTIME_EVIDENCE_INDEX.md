# Runtime Evidence Index

Comprehensive index of empirical command execution outputs, test logs, database queries, and network proofs.

---

## 1. Environment & Pre-Flight System Evidence

- **OS**: Linux Ubuntu 26.04 LTS (Kernel 7.0.0-28-generic x86_64)
- **Container Engine**: Docker Compose (`osi-postgres`, `osi-nats`, `osi-redis`, `osi-python-ai-core`, `osi-ingestion-server`, `osi-dashboard-server`, `osi-nginx`, `osi-secure-relay`, `osi-telegram-bot`)
- **Listening Ports**: `80` (HTTP), `9443` (HTTPS), `4222` (NATS), `5433` (PostgreSQL), `8222` (NATS Monitoring), `8090` (Kafka UI), `5050`/`5051` (pgAdmin), `9000` (Portainer), `9998` (Relay)

---

## 2. Evidence Log File Index

1. **Docker Container Discovery Log**: `docker ps -a` output (All containers active & healthy).
2. **NATS JetStream Status Log**: `http://localhost:8222/jsz` (2 streams, 11 consumers, 26,631 messages, 21 MB storage).
3. **JetStream ACK Test Log**: Sequence `26630` published & acknowledged on `telemetry_stream_critical`.
4. **AI Engine Go Unit Test Log**: `go test -v ./SERVER/go_core/ai/...` (12/12 signature rules passed in 0.016s).
5. **PostgreSQL Password Hash Audit Log**: All 6 `rbac_users` verified with `$2b$12$...` / `$2a$10$...` bcrypt hashes.
6. **AuthGuard Zero-Trust Log**: Unauthenticated HTTP request blocked with `HTTP 401 | INVALID_TOKEN_FORMAT`; HMAC authenticated call authorized (`HTTP 200 OK`).
7. **Remediation Execution Audit Log**: `VerificationEngine` persisted `OUTCOME-RESTART_SERVICE-1786843056` to PostgreSQL table `remediation_results`.
8. **Dashboard UI Log**: Nginx HTTP port 80 / HTTPS port 9443 serving live HTML `<title>NOC IT AI – Command Center v3.0</title>`.
