# Deployment

## Docker Compose
The system is deployed using `docker-compose.yml` comprising 13+ services:
1. `osi-nginx`: Reverse proxy.
2. `osi-postgres`: DB + pgvector.
3. `osi-redis`: Cache.
4. `osi-nats`: Message broker.
5. `osi-ingestion-server`: Go telemetry receiver.
6. `osi-dashboard-server`: Go UI backend.
7. `osi-secure-relay`: HMAC command relay.
8. `osi-python-ai-core`: Main supervisor.
9. `osi-ai-*`: Various AI microservices (consensus, critic, policy, rag, daemons).
10. `osi-telegram-bot`: Notification listener.
11. `osi-portainer`: Docker UI.

## Networks
- `osi-frontend`
- `osi-backend`
