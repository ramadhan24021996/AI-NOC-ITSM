# CONFIGURATION AUDIT
## OSI NOC IT AI — Environment Variables & Configuration Audit
**Evidence:** .env, docker-compose.yml, SERVER/go_core/config/config.go  
**Status:** VERIFIED — configuration analyzed

---

## ENVIRONMENT VARIABLES

### Database Configuration
| Variable | Current Value | Risk |
|----------|--------------|------|
| DB_HOST | postgres (Docker service name) | OK |
| DB_PORT | 5432 | OK |
| DB_NAME | osi_system | OK |
| DB_PASSWORD | [REDACTED_HISTORICAL_PASSWORD] | MEDIUM — use Vault |
| DB_USER | (not set — defaults to postgres) | LOW |
| DB_READ_HOST | (not set — read replica disabled) | INFO |

### Redis Configuration
| Variable | Current Value | Risk |
|----------|--------------|------|
| REDIS_HOST | redis | OK |
| REDIS_PORT | 6379 | OK |
| REDIS_PASSWORD | OSI_SECURITY_KEY | MEDIUM — reuse |

### NATS Configuration
| Variable | Current Value | Risk |
|----------|--------------|------|
| NATS_HOST | nats | OK |
| NATS_PORT | 4222 | OK |
| NATS_TOKEN | OSI_SECURITY_KEY | MEDIUM — reuse |

### Security Variables
| Variable | Current Value | Risk | Action |
|----------|--------------|------|--------|
| JWT_SECRET_KEY | 94c86bf4f85e... (64-char hex) | CRITICAL — in .env plaintext | Rotate + Vault |
| OSI_SECURITY_KEY | [REDACTED_HISTORICAL_KEY] | CRITICAL — shared 4 ways | Separate + Vault |
| GEMINI_API_KEY | AQ.Ab8RN6KQeV... (3 keys) | CRITICAL — exposed | Rotate + Vault |
| OPENAI_API_KEY | sk-proj-UTb5B32_... | CRITICAL — exposed | Rotate + Vault |
| TELEGRAM_BOT_TOKEN | [REDACTED_TELEGRAM_ID]:AAH... | CRITICAL — exposed | Rotate + Vault |
| TELEGRAM_CHAT_ID | 7794987703 | MEDIUM | Consider env |
| AUTHORIZED_ADMINS | 7794987703 | LOW | OK |

### External Services
| Variable | Current Value | Risk |
|----------|--------------|------|
| ENTERPRISE_DNS_PRIMARY | 192.168.1.1 | OK for internal |
| ENTERPRISE_LDAP_BIND_PASSWORD | changeme_ldap_password_2026 | HIGH — default |

### Application Config
| Variable | Current Value | Risk |
|----------|--------------|------|
| DEV_MODE | true | MEDIUM — disable in production |
| PROXY_HTTP_PORT | 80 | OK |
| PROXY_HTTPS_PORT | 9443 | OK |
| MIGRATE_DB | (not in .env — defaults to false) | INFO — add explicitly |

---

## MISSING CONFIGURATION

| Variable | Needed For | Risk if Missing |
|----------|-----------|----------------|
| MIGRATE_DB=false | DB migration gate | MEDIUM — schema not updated |
| GROQ_API_KEY | LLM router groq provider | CONFIG_DEPENDENT |
| DEEPSEEK_API_KEY | LLM router deepseek | CONFIG_DEPENDENT |
| ANTHROPIC_API_KEY | LLM router anthropic | CONFIG_DEPENDENT |
| N8N_URL | n8n integration | CONFIG_DEPENDENT |
| SMTP_HOST/USER/PASS | Email notifications (not implemented) | NOT_NEEDED_YET |
| VAULT_ADDR / VAULT_TOKEN | Secret management | HIGH — must have |

---

## config.go LOADING ANALYSIS

**File:** SERVER/go_core/config/config.go (9,770 bytes)

```go
// Config struct fields loaded from env:
type Config struct {
    DBHost     string  // DB_HOST
    DBPort     int     // DB_PORT
    DBName     string  // DB_NAME
    RedisHost  string  // REDIS_HOST
    RedisPort  int     // REDIS_PORT
    RedisPass  string  // REDIS_PASS or OSI_SECURITY_KEY
    NatsHost   string  // NATS_HOST
    NatsPort   int     // NATS_PORT
    NatsToken  string  // NATS_TOKEN
    JWTSecret  string  // JWT_SECRET_KEY
    SecurityKey string // OSI_SECURITY_KEY
    GeminiKey  string  // GEMINI_API_KEY
    TelegramToken string // TELEGRAM_BOT_TOKEN
}
```

**Config also loads from:** PostgreSQL `system_config` table (hot-reload feature)  
**Status:** Dual-source config — env vars + DB — sophisticated but complex to audit

---

## CONFIGURATION RECOMMENDATIONS

1. Create separate `.env.production` and `.env.development`
2. Use Docker secrets or HashiCorp Vault for all sensitive values
3. Add `MIGRATE_DB=false` explicitly to production .env
4. Set `DEV_MODE=false` in production
5. Enable `sslmode=require` via `DB_SSLMODE=require` env var
6. Add `LLM_MAX_TOKENS_PER_INCIDENT=50000` explicitly (currently only in llm_router.py)
7. Add provider API keys for Groq/DeepSeek as fallback (CONFIG_DEPENDENT)
