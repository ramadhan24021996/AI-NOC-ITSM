# REALTIME / WEBSOCKET AUDIT
## OSI NOC IT AI — WebSocket & Real-time Communication Audit
**Evidence:** portal/server_ws.go, portal/chat_engine.go, ingestion_server.go (Redis PubSub)  
**Status:** VERIFIED from source code analysis

---

## REALTIME ARCHITECTURE

```mermaid
flowchart TD
    subgraph Server
        IS[Ingestion Server\nGo go_core]
        RD[(Redis\nPubSub)]
        DS[Dashboard Server\nportal/]
    end

    subgraph Clients
        CLIENT_APP[Windows Agent Chat\nchat_sessions client]
        NOC_DASH[NOC Dashboard\nBrowser WebSocket]
    end

    IS -->|SaveChatMessage| PG[(PostgreSQL)]
    IS -->|PUBLISH chat:{clientID}| RD
    RD -->|SUBSCRIBE| DS
    DS -->|WebSocket push| NOC_DASH
    DS -->|WebSocket push| CLIENT_APP
    CLIENT_APP -->|WS message| DS
    NOC_DASH -->|WS message| DS
```

---

## WEBSOCKET IMPLEMENTATION (portal/server_ws.go)

### WebSocket Endpoints

| Path | Purpose | Auth | Status |
|------|---------|------|--------|
| `/ws/chat/:clientID` | Client chat WebSocket (agent-side) | None (token in query?) | VERIFIED |
| `/ws/dashboard` | Dashboard real-time events | JWT cookie/query | VERIFIED |
| `/ws/telemetry` | Live telemetry stream | JWT | VERIFIED |
| `/jarvis/voice/duplex` | JARVIS voice duplex | JWT | VERIFIED |

### WebSocket Lifecycle (Verified from server_ws.go)
```go
var upgrader = websocket.Upgrader{
    ReadBufferSize:  1024,
    WriteBufferSize: 1024,
    CheckOrigin: func(r *http.Request) bool { return true },  // SECURITY RISK: AllowAllOrigins
}
```

**CRITICAL SECURITY FINDING:**
```go
CheckOrigin: func(r *http.Request) bool { return true }
```
This disables CORS/origin checking for WebSocket connections — allows cross-origin WS hijacking.

### WebSocket Connection Map (server_ws.go)
```go
type WSClient struct {
    conn     *websocket.Conn
    clientID string     // maps to chat_sessions.client_id
    role     string     // CLIENT / OPERATOR / SYSTEM
    send     chan []byte
}

var wsClients   = make(map[string]*WSClient)  // clientID → client
var wsClientsMu sync.RWMutex
```

---

## REDIS PUB/SUB FOR REAL-TIME CHAT

### Publisher (ingestion_server.go / chat_service.go)
```go
// chat_service.go — PublishChatEvent()
redisClient.Publish(ctx, "chat:"+clientID, jsonPayload)
```

### Subscriber (dashboard server / chat_engine.go)
```go
// chat_engine.go — StartChatRedisSubscriber()
pubsub := redisClient.PSubscribe(ctx, "chat:*")
for msg := range pubsub.Channel() {
    // parse chatID from channel name
    // find matching WSClient
    // push to WSClient.send channel
}
```

### Real-time Chat Event Flow (VERIFIED)
```
[Incident detected by ingestion server]
  ↓
incident_service.go: SaveChatMessage() → INSERT chat_messages
  ↓
chat_service.go: PublishChatEvent(ChatEvent{Type:"message", ClientID, Data})
  ↓
redis.Publish("chat:{clientID}", eventJSON)
  ↓
portal/chat_engine.go: StartChatRedisSubscriber() picks up
  ↓
wsClients[clientID].send <- eventBytes
  ↓
goroutine: conn.WriteMessage(websocket.TextMessage, bytes)
  ↓
[Client WebSocket receives JSON event]
```
**Status:** VERIFIED — full path traced

---

## SCREENSHOT VIA WEBSOCKET

```go
// incident_service.go line 239
_ = DefaultChatService.SendWSCommand(clientID, "capture_screenshot", map[string]interface{}{
    "incident_id": incidentID,
})
```

**Server → Agent flow:**
1. Server sends WS command `capture_screenshot` to agent's WebSocket connection
2. Agent captures screenshot
3. Agent uploads screenshot via POST /screenshot/upload
4. `RegisterScreenshotCallback()` signals the waiting channel
5. 4-second timeout if no response

**Status:** VERIFIED — command send verified, callback mechanism verified

---

## DASHBOARD REAL-TIME EVENTS (server_ws.go)

### Event Types Published to Dashboard WebSocket
| Event | Source | Consumer | Status |
|-------|--------|---------|--------|
| `message` | Chat service | Client chat UI + NOC dashboard | VERIFIED |
| `message_update` | updateIncidentCardStatus | Client chat UI | VERIFIED |
| `chat_event` | incident_service | Dashboard | VERIFIED |
| `telemetry_stream` | PostgreSQL NOTIFY trigger | Dashboard live metrics | VERIFIED |
| `device_status` | Heartbeat monitor | Dashboard device list | CONNECTED_BUT_NOT_VERIFIED |
| `incident_update` | Incident service | Dashboard incident panel | CONNECTED_BUT_NOT_VERIFIED |

### PostgreSQL NOTIFY → WebSocket Path
```sql
-- schema.go: trigger on telemetry_logs INSERT
notify_telemetry_insert() → pg_notify('telemetry_stream', payload)
```
```go
// ingestion_server.go or dashboard_server.go:
// LISTEN telemetry_stream → receives pg_notify
// → push to connected dashboard WebSocket clients
```
**Status:** TRIGGER VERIFIED in schema.go; Go LISTEN subscription CONNECTED_BUT_NOT_VERIFIED

---

## HEARTBEAT / KEEPALIVE

| Component | Heartbeat | Implementation | Status |
|-----------|-----------|----------------|--------|
| Windows Agent | Sends telemetry every interval | Agent periodic sender | VERIFIED |
| WebSocket Client | Ping/Pong (gorilla/websocket default) | server_ws.go | PARTIALLY_IMPLEMENTED |
| Dashboard WS | Reconnect logic | Frontend JS (unverified) | UNKNOWN |
| JARVIS Voice WS | Duplex heartbeat | jarvis/runtime/ | UNKNOWN |

---

## REALTIME RISKS

| Risk | Severity | Evidence |
|------|----------|---------|
| WebSocket CheckOrigin returns true (no CORS validation) | HIGH | server_ws.go upgrader |
| Redis nil check may not be everywhere in chat flow | MEDIUM | If Redis down, events silently dropped |
| No WebSocket message size limit | MEDIUM | Potential memory exhaustion |
| No reconnect logic verified in browser client | MEDIUM | Frontend JS not audited |
| Dashboard WS connection count unbounded | LOW | No max client limit |
| Screenshot 4s timeout too short for slow networks | LOW | incident_service.go L249 |

---

## VERIFICATION MATRIX

| Feature | Implemented | Tested | Production-Ready |
|---------|------------|--------|-----------------|
| Client chat WebSocket | YES | PARTIALLY | MOSTLY |
| NOC dashboard WebSocket | YES | UNKNOWN | MOSTLY |
| Redis PubSub broadcast | YES | UNKNOWN | YES |
| Screenshot via WS | YES | UNKNOWN | PARTIALLY |
| pg_notify telemetry stream | TRIGGER_YES / LISTEN_UNKNOWN | NO | PARTIALLY |
| Reconnection handling | UNKNOWN | NO | NO |
| CORS/Origin validation | NO (disabled) | NO | NO |
