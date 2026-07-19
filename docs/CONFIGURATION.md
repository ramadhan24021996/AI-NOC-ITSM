# Configuration

## Environment Variables (`.env`)
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_PASSWORD`: PostgreSQL connection.
- `REDIS_HOST`, `REDIS_PORT`: Redis connection.
- `NATS_HOST`, `NATS_PORT`: NATS connection.
- `JWT_SECRET_KEY`: Auth signing.
- `OSI_SECURITY_KEY`: Fernet encryption and internal service auth.
- `GEMINI_API_KEY`: Google AI access.
- `TELEGRAM_BOT_TOKEN`: Alerting bot.

## Dynamic Configs
- `ai_config.json`: Loaded by dashboard and AI core (model selection, budgets).
- `remote_settings.json`: Hot-reload settings for the dashboard.
