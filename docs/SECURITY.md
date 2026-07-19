# Security

## Mechanisms
1. **API Keys:** Encrypted at rest in DB using Fernet (`OSI_SECURITY_KEY`).
2. **Internal Auth:** NATS and Redis require `OSI_SECURITY_KEY` for connection.
3. **Web Auth:** JWT for dashboard API access. Nginx uses basic auth (`.htpasswd`).
4. **Agent Execution:** Commands sent to agents are signed via HMAC (Secure Relay).
5. **RBAC:** Database tables control user roles and permissions.
6. **Audit Logs:** Tamper-proof `immutable_audit_log` tracks critical changes.
