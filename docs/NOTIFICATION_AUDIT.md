# NOTIFICATION AUDIT
## OSI NOC IT AI — Notification System Forensic Audit
**Evidence:** SERVER/go_core/ingestion/telegram_service.go, incident_service.go, chat_service.go  
**Status:** VERIFIED multi-channel notification system

---

## NOTIFICATION CHANNELS

| Channel | Implementation | Status | Reliability |
|---------|----------------|--------|-------------|
| Telegram Bot | telegram_service.go | VERIFIED | HIGH |
| WebSocket (chat) | chat_service.go + Redis PubSub | VERIFIED | HIGH |
| Windows Agent Push | sendBypassCommandToAgent() TCP | VERIFIED | MEDIUM |
| Email | NOT FOUND | NOT_IMPLEMENTED | — |
| PagerDuty/OpsGenie | NOT FOUND | NOT_IMPLEMENTED | — |
| SMS | NOT FOUND | NOT_IMPLEMENTED | — |
| Slack | NOT FOUND | NOT_IMPLEMENTED | — |

---

## TELEGRAM NOTIFICATION (telegram_service.go — 4008 bytes)

### Configuration
```go
// From docker-compose.yml environment:
TELEGRAM_BOT_TOKEN=[REDACTED_TELEGRAM_BOT_TOKEN]  // PLAINTEXT
TELEGRAM_CHAT_ID=7794987703
AUTHORIZED_ADMINS=7794987703
```

### Message Types

| Trigger | Message Format | Status |
|---------|----------------|--------|
| New incident detected | "🚨 Insiden Baru Terdeteksi!\n\n💻 PC: {pcName}\n🔴 Severity: {severity}\n📋 Deskripsi: {description}" | VERIFIED |
| Incident escalated | "📞 NOC Dihubungi\n\n💻 PC: {pcName}\n📋 Deskripsi: {description}" | VERIFIED |
| Incident resolved (self-healing) | "✅ SELF-HEALING SUCCESS\n\n💻 PC: {pcName}\n📋 {resolution}" | VERIFIED |

### Notification Flow
```
incident_service.go:
  EscalateIncident() → DefaultTelegramService.SendIncidentAlert()
  ResolveIncident()  → DefaultTelegramService.SendIncidentAlert("Self-Healing")
  
  TriggerIncidentWorkflow() → (no direct Telegram — initial Telegram is from EscalateIncident only)
```

### Telegram Security Issues
- Bot token in plaintext .env and docker-compose environment
- No message signing/verification
- AUTHORIZED_ADMINS is single ID (not group management)
- No rate limiting on Telegram sends

### Telegram Error Handling
```go
// incident_service.go line 319-323
if err := DefaultTelegramService.SendIncidentAlert(...); err != nil {
    return fmt.Errorf("failed to send Telegram alert: %w", err)
}
```
**Status:** Error propagated to caller — if Telegram fails, escalation fails

---

## WEBSOCKET / CHAT NOTIFICATIONS

### Implementation Path
```
incident_service.go:
  SaveChatMessage(msg) → INSERT chat_messages
  PublishChatEvent(evt) → redis.Publish("chat:{clientID}", payload)
  
dashboard-server (chat_engine.go):
  StartChatRedisSubscriber() → PSubscribe("chat:*")
  → receive events → wsClients[clientID].send <- bytes
  → conn.WriteMessage(WebSocket) → Browser/Client chat UI
```

### Chat Event Types
| Event Type | Source | Data | Status |
|-----------|--------|------|--------|
| `message` | incident_service, operator | full ChatMessage struct | VERIFIED |
| `message_update` | updateIncidentCardStatus | status, incident_id | VERIFIED |
| `typing` | Operator sends | clientID | VERIFIED |
| `chat_event` | Various | generic event payload | VERIFIED |

### Chat Notification UI Cards (Verified Message Formats)
```
Message 1 (immediate): 
  "🚨 Saya mendeteksi gangguan pada PC Anda!\n\n📋 {description}\n\n🔍 AI sedang menganalisis masalah ini..."

Message 2 (AI report):
  "🤖 Hasil Analisis AI:\n\n📌 {cause}\n💡 {reason}\n⚡ {action}\n📊 Confidence: {confidence}%"

Message 3 (remediation):
  "🔧 Panduan Perbaikan:\n\n{step-by-step remediation}\n\n⏳ Apakah masalah sudah terselesaikan?"
  + [Selesaikan Masalah] + [Hubungi NOC] buttons
```

---

## WINDOWS AGENT PUSH NOTIFICATIONS

### Implementation
```go
// incident_service.go: sendBypassCommandToAgent()
conn, err := net.DialTimeout("tcp", agentIP+":10000", 5*time.Second)
// Fallback to port 10001 if 10000 fails

// Commands sent:
SHOW_NOTIFICATION: {type: "SHOW_NOTIFICATION", message: "⚠️ Masalah Terdeteksi!", severity}
SHOW_CHAT:         {type: "SHOW_CHAT", message: "Chat NOC dibuka.", incident_id, client_id, chat_url}
```

### Agent Push Reliability
- TCP dial timeout: 5 seconds
- If agent IP not found in DB: skip silently (just Printf warning)
- No retry mechanism
- No acknowledgment verification
- **If agent is offline: push silently dropped**

---

## NOTIFICATION AUDIT MATRIX

| Scenario | Telegram | WebSocket | Agent Push | Email | Status |
|----------|---------|-----------|-----------|-------|--------|
| Incident detected | NO | YES | YES | NO | PARTIAL |
| Incident escalated | YES | YES | NO | NO | PARTIAL |
| Incident resolved | YES | YES | NO | NO | PARTIAL |
| AI analysis complete | NO | YES | NO | NO | PARTIAL |
| Remediation complete | NO | YES | NO | NO | PARTIAL |
| System health degraded | NO | NO | NO | NO | MISSING |
| SLA breach | NO | NO | NO | NO | MISSING |
| New device registered | NO | YES? | NO | NO | UNKNOWN |

---

## NOTIFICATION RISKS

| Risk | Severity | Evidence |
|------|----------|---------|
| Telegram token in plaintext .env | CRITICAL | .env line 26 |
| Escalation fails if Telegram unavailable | HIGH | incident_service.go L319-323 |
| Agent push silently dropped if device offline | MEDIUM | sendBypassCommandToAgent() |
| No email/PagerDuty integration | MEDIUM | Not implemented |
| WebSocket notification lost if client reconnects | MEDIUM | No message persistence for WS |
| No notification rate limiting | LOW | Could flood Telegram in incident storm |
| Single Telegram chat ID (no multi-channel) | LOW | TELEGRAM_CHAT_ID single value |

---

## n8n WORKFLOW INTEGRATION

### Status: CONNECTED_BUT_NOT_VERIFIED
- `SERVER/integration/n8n/n8n_dispatcher.py` exists (referenced in noc_bridge.py)
- `n8n_docker/` exists with n8n container
- n8n URL: `N8N_URL=http://n8n:5678` (from docker-compose)
- **N8N webhook triggering from incident lifecycle: NOT VERIFIED**
- n8n could be used for additional notification channels (email, Slack, etc.)
