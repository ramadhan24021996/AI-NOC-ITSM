package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net"
	"strings"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/go-redis/redis/v8"
	"github.com/gorilla/websocket"
	"github.com/nats-io/nats.go"
	"gorm.io/gorm"

	"go_incident_analysis/SERVER/go_core/database"
	"go_incident_analysis/portal/dashboard/core"
	wsPkg "go_incident_analysis/portal/dashboard/websocket"
)

// Shared Globals for Server Hub
var (
	dashboardRedisClient *redis.Client
	dashboardNatsConn    *nats.Conn
	dashboardCtx         = context.Background()
)

// WebSocket upgrader (shared with chat_engine.go)
var upgrader = websocket.Upgrader{
	CheckOrigin:  wsPkg.CheckSameOrigin, // [WS-1/T-06]
	Subprotocols: []string{"bearer"},
}

// Legacy WebSocket chat structures
type DashboardChatEvent struct {
	Type     string      `json:"type"` // message, typing, operator_status, read_receipt
	ClientID string      `json:"client_id"`
	Sender   string      `json:"sender,omitempty"`
	Data     interface{} `json:"data,omitempty"`
}

var (
	wsChatDashboardClients   = make(map[*websocket.Conn]bool)
	wsChatDashboardClientsMu sync.Mutex
)

// Helpers mapping to modular package
func addInternalLog(logType, category, message string) {
	wsPkg.AddInternalLog(logType, category, message)
}

func broadcastWSEvent(event string, data interface{}) {
	wsPkg.BroadcastWSEvent(event, data)
}

func writeAuditLog(db *gorm.DB, actionType, actor, target string, payload interface{}) error {
	return core.WriteAuditLog(db, actionType, actor, target, payload)
}

func cleanSiteID(siteID string) string {
	return core.CleanSiteID(siteID)
}

func checkTCP(addr string) string {
	conn, err := net.DialTimeout("tcp", addr, 2*time.Second)
	if err != nil {
		return "DOWN"
	}
	conn.Close()
	return "OK"
}

func fileExists(path string) bool {
	return core.FileExists(path)
}

func invalidateIncidentCache() {
	if dashboardRedisClient != nil {
		dashboardRedisClient.Del(context.Background(), "cache:incidents")
	}
}

// StartDashboardChatRedisSubscriber listens to Redis chat_channel and forwards events to WebSocket clients.
func StartDashboardChatRedisSubscriber() {
	if dashboardRedisClient == nil {
		return
	}
	// Register operator presence in Redis with TTL so client agents know operator is online
	go func() {
		for {
			if presErr := dashboardRedisClient.Set(dashboardCtx, "presence:operator", "1", 15*time.Second).Err(); presErr != nil {
				fmt.Printf("[WS] Redis presence update failed: %v\n", presErr)
			}
			time.Sleep(10 * time.Second)
		}
	}()

	go func() {
		pubsub := dashboardRedisClient.Subscribe(dashboardCtx, "chat_channel")
		ch := pubsub.Channel()
		fmt.Println(" [CHAT] Dashboard Server listening to Redis chat_channel")
		for msg := range ch {
			var event DashboardChatEvent
			if err := json.Unmarshal([]byte(msg.Payload), &event); err != nil {
				continue
			}

			// Broadcast to all active dashboard WebSocket connections
			wsChatDashboardClientsMu.Lock()
			for conn := range wsChatDashboardClients {
				_ = conn.WriteJSON(event)
			}
			wsChatDashboardClientsMu.Unlock()
		}
	}()
}

// StartTelemetryRedisSubscriber listens to telemetry_channel and pushes live telemetry events to WebSocket clients.
func StartTelemetryRedisSubscriber() {
	if dashboardRedisClient == nil {
		return
	}
	go func() {
		pubsub := dashboardRedisClient.Subscribe(dashboardCtx, "telemetry_channel")
		ch := pubsub.Channel()
		fmt.Println(" [TELEMETRY] Dashboard Server listening to Redis telemetry_channel")
		for msg := range ch {
			var event struct {
				Event string                 `json:"event"`
				Data  map[string]interface{} `json:"data"`
				Path  string                 `json:"path"`
			}
			if err := json.Unmarshal([]byte(msg.Payload), &event); err != nil {
				continue
			}

			typeStr := "telemetry"
			if strings.Contains(event.Path, "activity") {
				typeStr = "activity"
			} else if strings.Contains(event.Path, "issues") || strings.Contains(event.Path, "watchdog") {
				typeStr = "issue"
			} else if strings.Contains(event.Path, "browser-events") {
				typeStr = "web_activity"
			}

			dev, _ := event.Data["pc_name"].(string)
			if dev == "" {
				dev, _ = event.Data["agent_id"].(string)
			}
			if dev == "" {
				dev = "unknown-device"
			}

			wsPkg.BroadcastWSEvent("live_telemetry", map[string]interface{}{
				"device": dev,
				"type":   typeStr,
				"data":   event.Data,
			})
		}
	}()
}

// handleDashboardWebSocket manages dashboard operator WebSocket lifecycles.
func handleDashboardWebSocket(c *gin.Context, db *gorm.DB) {
	conn, err := upgrader.Upgrade(c.Writer, c.Request, nil)
	if err != nil {
		fmt.Printf(" [CHAT ERROR] Failed to upgrade dashboard socket: %v\n", err)
		return
	}

	wsChatDashboardClientsMu.Lock()
	wsChatDashboardClients[conn] = true
	wsChatDashboardClientsMu.Unlock()

	defer func() {
		wsChatDashboardClientsMu.Lock()
		delete(wsChatDashboardClients, conn)
		wsChatDashboardClientsMu.Unlock()
		conn.Close()
	}()

	for {
		var event DashboardChatEvent
		if err := conn.ReadJSON(&event); err != nil {
			break
		}

		switch event.Type {
		case "typing":
			publishDashboardChatEvent(event)
		case "message":
			if dataMap, ok := event.Data.(map[string]interface{}); ok {
				clientID, _ := dataMap["client_id"].(string)
				text, _ := dataMap["message"].(string)
				attachment, _ := dataMap["attachment_path"].(string)

				if clientID == "" {
					continue
				}

				msg := database.ChatMessage{
					ClientID:       clientID,
					Sender:         "OPERATOR",
					Message:        text,
					AttachmentPath: attachment,
					ReadStatus:     "SENT",
				}
				db.Create(&msg)

				db.Model(&database.ChatSession{}).Where("client_id = ?", clientID).Updates(map[string]interface{}{
					"status":     "ACTIVE",
					"updated_at": time.Now(),
				})

				event.ClientID = clientID
				event.Sender = "OPERATOR"
				event.Data = msg

				publishDashboardChatEvent(event)
			}
		}
	}
}

func publishDashboardChatEvent(event DashboardChatEvent) {
	if dashboardRedisClient == nil {
		return
	}
	payloadBytes, _ := json.Marshal(event)
	if pubErr := dashboardRedisClient.Publish(dashboardCtx, "chat_channel", string(payloadBytes)).Err(); pubErr != nil {
		fmt.Printf("[WS] Redis chat_channel publish failed: %v\n", pubErr)
	}
}
