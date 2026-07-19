package main

import (
	"context"
	"encoding/json"
	"fmt"
	"mime/multipart"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/go-redis/redis/v8"
	"github.com/google/uuid"
	"github.com/gorilla/websocket"
	"github.com/nats-io/nats.go"
	"gorm.io/gorm"

	"go_incident_analysis/SERVER/go_core/ai"
	"go_incident_analysis/SERVER/go_core/database"
)

// ============================================================
// ENTERPRISE LIVE CHAT ENGINE (cloude.md)
// WhatsApp-style: session-based, real-time, HITL AI-assist
// ============================================================

var chatCtx = context.Background()

// --- MODELS ---

type OperatorPresence struct {
	OperatorID string    `gorm:"primaryKey;column:operator_id" json:"operator_id"`
	Status     string    `gorm:"column:status" json:"status"` // ONLINE, OFFLINE, BUSY, TYPING
	LastSeen   time.Time `gorm:"column:last_seen" json:"last_seen"`
	TypingTo   string    `gorm:"column:typing_to" json:"typing_to"`
}

func (OperatorPresence) TableName() string { return "operator_presence" }

type ChatFeedback struct {
	ID                    uint      `gorm:"primaryKey;autoIncrement" json:"id"`
	SessionClientID       string    `gorm:"column:session_client_id" json:"session_client_id"`
	ResolutionStatus      string    `gorm:"column:resolution_status" json:"resolution_status"`
	OperatorNotes         string    `gorm:"column:operator_notes" json:"operator_notes"`
	AIRecommendationUsed  bool      `gorm:"column:ai_recommendation_used" json:"ai_recommendation_used"`
	Successful            bool      `gorm:"column:successful" json:"successful"`
	EscalationLevel       string    `gorm:"column:escalation_level" json:"escalation_level"`
	CreatedAt             time.Time `gorm:"column:created_at;autoCreateTime" json:"created_at"`
}

func (ChatFeedback) TableName() string { return "chat_feedback" }

// P7: Live Thread Message representation for NATS
type LiveThreadMessage struct {
	MessageID   string                 `json:"message_id,omitempty"`
	ID          int64                  `json:"id"`
	IncidentID  int                    `json:"incident_id"`
	ClientID    string                 `json:"client_id"`
	SenderType  string                 `json:"sender_type"` // CLIENT, OPERATOR, SYSTEM, AI
	Message     string                 `json:"message"`
	Attachment  string                 `json:"attachment,omitempty"`
	Timestamp   string                 `json:"timestamp"`
	IsSystemMsg bool                   `json:"is_system_msg"`
	ThreadType  string                 `json:"thread_type"` // SUPPORT, INCIDENT, ESCALATION
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
}

var (
	processedNatsMessages sync.Map
)

func isDuplicateNatsMessage(messageID string) bool {
	if messageID == "" {
		return false
	}
	_, loaded := processedNatsMessages.LoadOrStore(messageID, time.Now())
	return loaded
}

// --- WEBSOCKET HUB ---

type ChatHub struct {
	mu          sync.RWMutex
	operators   map[string]*websocket.Conn // operatorID -> conn
	clients     map[string]*websocket.Conn // clientID -> conn
	sessions    map[string]string          // clientID -> assignedOperatorID
	redis       *redis.Client
	db          *gorm.DB
	supervisor  *ai.AISupervisor
}

var globalChatHub *ChatHub

func InitChatHub(rc *redis.Client, db *gorm.DB, sup *ai.AISupervisor) {
	globalChatHub = &ChatHub{
		operators:  make(map[string]*websocket.Conn),
		clients:    make(map[string]*websocket.Conn),
		sessions:   make(map[string]string),
		redis:      rc,
		db:         db,
		supervisor: sup,
	}
	go globalChatHub.runRedisSubscriber()
	go globalChatHub.runNatsSubscriber()
	go globalChatHub.runPresenceHeartbeat()
	fmt.Println("[CHAT-ENGINE] Enterprise Live Chat Hub initialized with NATS Live Sync")
}

// --- NATS SUBSCRIBER (P7 Live Sync) ---

func (h *ChatHub) runNatsSubscriber() {
	if dashboardNatsConn == nil {
		fmt.Println("[CHAT-ENGINE] Warning: dashboardNatsConn is nil, skipping NATS thread subscription")
		return
	}
	_, err := dashboardNatsConn.QueueSubscribe("chat.site.*.thread.*", "dashboard-chat-group", func(m *nats.Msg) {
		var msg LiveThreadMessage
		if err := json.Unmarshal(m.Data, &msg); err != nil {
			return
		}

		if isDuplicateNatsMessage(msg.MessageID) {
			return
		}

		h.mu.RLock()
		defer h.mu.RUnlock()

		// Broadcast to all operators (Dashboard mirror)
		for _, conn := range h.operators {
			_ = conn.WriteJSON(ChatEvent{
				Type:       "RECEIVE_MESSAGE",
				ClientID:   msg.ClientID,
				OperatorID: "",
				SenderType: msg.SenderType,
				Data: map[string]interface{}{
					"message_id":      msg.ID,
					"message":         msg.Message,
					"attachment_url":  msg.Attachment,
					"timestamp":       msg.Timestamp,
					"is_system_msg":   msg.IsSystemMsg,
					"thread_type":     msg.ThreadType,
					"incident_id":     msg.IncidentID,
					"metadata":        msg.Metadata,
				},
			})
		}

		// Also send to client WS if client is active
		if msg.ClientID != "" {
			if conn, ok := h.clients[msg.ClientID]; ok {
				_ = conn.WriteJSON(ChatEvent{
					Type:       "RECEIVE_MESSAGE",
					ClientID:   msg.ClientID,
					SenderType: msg.SenderType,
					Data: map[string]interface{}{
						"message_id":      msg.ID,
						"message":         msg.Message,
						"attachment_url":  msg.Attachment,
						"timestamp":       msg.Timestamp,
						"incident_id":     msg.IncidentID,
					},
				})
			}
		}
	})
	if err != nil {
		fmt.Printf("[CHAT-ENGINE] NATS thread subscription failed: %v\n", err)
	} else {
		fmt.Println("[CHAT-ENGINE] Subscribed to NATS 'incident.thread.*' for Live Sync")
	}
}

// --- REDIS SUBSCRIBER ---

type ChatEvent struct {
	Type       string      `json:"type"`
	ClientID   string      `json:"client_id,omitempty"`
	OperatorID string      `json:"operator_id,omitempty"`
	SenderType string      `json:"sender_type,omitempty"` // CLIENT, OPERATOR, SYSTEM, AI
	Data       interface{} `json:"data,omitempty"`
}

type IngestorChatEvent struct {
	Type     string      `json:"type"`
	ClientID string      `json:"client_id"`
	Sender   string      `json:"sender,omitempty"`
	Data     interface{} `json:"data,omitempty"`
}

func (h *ChatHub) runRedisSubscriber() {
	if h.redis == nil {
		return
	}
	pubsub := h.redis.Subscribe(chatCtx, "enterprise_chat", "chat_channel")
	ch := pubsub.Channel()
	for msg := range ch {
		if msg.Channel == "enterprise_chat" {
			var event ChatEvent
			if err := json.Unmarshal([]byte(msg.Payload), &event); err != nil {
				continue
			}
			h.routeEvent(event)
		} else if msg.Channel == "chat_channel" {
			var event IngestorChatEvent
			if err := json.Unmarshal([]byte(msg.Payload), &event); err != nil {
				continue
			}

			if event.ClientID == "" {
				continue
			}

			h.mu.RLock()
			assignedOp := h.sessions[event.ClientID]
			h.mu.RUnlock()

			if assignedOp == "" {
				var session struct {
					AssignedOperator string
				}
				h.db.Table("chat_sessions").Select("assigned_operator").Where("client_id = ?", event.ClientID).Scan(&session)
				assignedOp = session.AssignedOperator
				if assignedOp != "" {
					h.mu.Lock()
					h.sessions[event.ClientID] = assignedOp
					h.mu.Unlock()
				}
			}

			var opEvent ChatEvent
			switch event.Type {
			case "message":
				var msgID float64
				var messageText string
				var attachmentPath string
				var createdAtStr string
				var senderVal string

				if dataMap, ok := event.Data.(map[string]interface{}); ok {
					if idVal, ok := dataMap["id"].(float64); ok {
						msgID = idVal
					}
					if msgVal, ok := dataMap["message"].(string); ok {
						messageText = msgVal
					}
					if attachVal, ok := dataMap["attachment_path"].(string); ok {
						attachmentPath = attachVal
					}
					if createdVal, ok := dataMap["created_at"].(string); ok {
						createdAtStr = createdVal
					}
					if sender, ok := dataMap["sender"].(string); ok {
						senderVal = sender
					}
				}

				if senderVal == "" {
					senderVal = event.Sender
				}
				if senderVal == "" {
					senderVal = "CLIENT"
				}

				if senderVal == "OPERATOR" {
					continue
				}

				if createdAtStr == "" {
					createdAtStr = time.Now().Format(time.RFC3339)
				}

				opEvent = ChatEvent{
					Type:       "RECEIVE_MESSAGE",
					ClientID:   event.ClientID,
					OperatorID: assignedOp,
					SenderType: senderVal,
					Data: map[string]interface{}{
						"message_id":      msgID,
						"message":         messageText,
						"attachment_url":  attachmentPath,
						"timestamp":       createdAtStr,
					},
				}

				if h.supervisor != nil && assignedOp != "" && senderVal == "CLIENT" {
					go func(q string, opID string, clientID string) {
						_, report := h.supervisor.DiagnoseIncident(q, "")
						h.publishEvent(ChatEvent{
							Type: "AI_SUGGESTION", ClientID: clientID, OperatorID: opID,
							SenderType: "AI",
							Data: map[string]interface{}{
								"summary":     report[:min(len(report), 800)],
								"client_id":   clientID,
								"hitl_notice": "AI ASSIST ONLY - Human operator controls final response",
							},
						})
					}(messageText, assignedOp, event.ClientID)
				}
			case "typing":
				isTyping := false
				if dataMap, ok := event.Data.(map[string]interface{}); ok {
					if tVal, ok := dataMap["typing"].(bool); ok {
						isTyping = tVal
					}
				}

				if event.Sender == "OPERATOR" {
					continue
				}

				opType := "STOP_TYPING"
				if isTyping {
					opType = "START_TYPING"
				}

				opEvent = ChatEvent{
					Type:       opType,
					ClientID:   event.ClientID,
					OperatorID: assignedOp,
					SenderType: "CLIENT",
				}
			case "read_receipt":
				opEvent = ChatEvent{
					Type:       "MESSAGE_READ",
					ClientID:   event.ClientID,
					OperatorID: assignedOp,
					SenderType: "CLIENT",
					Data:       event.Data,
				}
			default:
				continue
			}

			h.routeEvent(opEvent)
		}
	}
}

func (h *ChatHub) publishEvent(event ChatEvent) {
	if h.redis == nil {
		return
	}
	b, _ := json.Marshal(event)
	h.redis.Publish(chatCtx, "enterprise_chat", string(b))
}

func (h *ChatHub) routeEvent(event ChatEvent) {
	h.mu.RLock()
	defer h.mu.RUnlock()

	switch event.Type {
	case "RECEIVE_MESSAGE", "MESSAGE_DELIVERED", "MESSAGE_READ",
		"START_TYPING", "STOP_TYPING", "SESSION_ASSIGNED",
		"SESSION_SOLVED", "SESSION_CLOSED", "AI_SUGGESTION":

		// Send to target operator
		if event.OperatorID != "" && event.Type != "RECEIVE_MESSAGE" {
			if conn, ok := h.operators[event.OperatorID]; ok {
				_ = conn.WriteJSON(event)
			}
		}
		// Also fan-out to all operators for session list updates and incoming messages
		if event.Type == "SESSION_ASSIGNED" || event.Type == "SESSION_SOLVED" || event.Type == "RECEIVE_MESSAGE" {
			for _, conn := range h.operators {
				_ = conn.WriteJSON(event)
			}
		}
		// Send ack to client
		if event.ClientID != "" {
			if conn, ok := h.clients[event.ClientID]; ok {
				_ = conn.WriteJSON(event)
			}
		}
	}
}

// --- PRESENCE ENGINE ---

func (h *ChatHub) runPresenceHeartbeat() {
	if h.redis == nil {
		return
	}
	for {
		h.mu.RLock()
		for opID := range h.operators {
			key := fmt.Sprintf("presence:operator:%s", opID)
			h.redis.Set(chatCtx, key, "ONLINE", 30*time.Second)
		}
		for clID := range h.clients {
			key := fmt.Sprintf("presence:client:%s", clID)
			h.redis.Set(chatCtx, key, "ONLINE", 30*time.Second)
		}
		h.mu.RUnlock()
		time.Sleep(20 * time.Second)
	}
}

func (h *ChatHub) setOperatorPresence(operatorID, status string) {
	if h.redis != nil {
		key := fmt.Sprintf("presence:operator:%s", operatorID)
		h.redis.Set(chatCtx, key, status, 30*time.Second)
	}
	h.db.Exec(`
		INSERT INTO operator_presence (operator_id, status, last_seen)
		VALUES (?, ?, NOW())
		ON CONFLICT (operator_id) DO UPDATE
		  SET status = EXCLUDED.status, last_seen = EXCLUDED.last_seen
	`, operatorID, status)
}

// --- SESSION ASSIGNMENT LOGIC ---

func assignSession(db *gorm.DB, clientID, issueCategory string) string {
	// Find operator with fewest active sessions
	var presence []OperatorPresence
	db.Where("status IN ?", []string{"ONLINE", "BUSY"}).Find(&presence)
	if len(presence) == 0 {
		return "unassigned"
	}

	bestOp := ""
	var minLoad int64 = 999999
	for _, op := range presence {
		var count int64
		db.Table("chat_sessions").Where("assigned_operator = ? AND status IN ?", op.OperatorID, []string{"OPEN", "ACTIVE", "PENDING"}).Count(&count)
		if count < minLoad {
			minLoad = count
			bestOp = op.OperatorID
		}
	}

	if bestOp != "" {
		db.Exec(`UPDATE chat_sessions SET assigned_operator = ?, status = 'ACTIVE', updated_at = NOW() WHERE client_id = ?`, bestOp, clientID)
	}

	// Escalation level based on category
	level := "L1"
	switch strings.ToLower(issueCategory) {
	case "network", "gateway", "outage":
		level = "L2"
	case "database", "security", "data_loss":
		level = "L3"
	case "critical", "server_down":
		level = "SYSADMIN"
	}
	db.Exec(`UPDATE chat_sessions SET escalation_level = ? WHERE client_id = ?`, level, clientID)

	return bestOp
}

// --- OPERATOR WEBSOCKET HANDLER ---

func handleOperatorChatWS(c *gin.Context, db *gorm.DB) {
	if globalChatHub == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "Chat hub not initialized"})
		return
	}

	operatorID := c.Query("operator_id")
	if operatorID == "" {
		operatorID = "NOC_OPERATOR"
	}

	conn, err := upgrader.Upgrade(c.Writer, c.Request, nil)
	if err != nil {
		fmt.Printf("[CHAT-ENGINE] Operator WS upgrade failed: %v\n", err)
		return
	}

	globalChatHub.mu.Lock()
	globalChatHub.operators[operatorID] = conn
	globalChatHub.mu.Unlock()
	globalChatHub.setOperatorPresence(operatorID, "ONLINE")

	defer func() {
		globalChatHub.mu.Lock()
		delete(globalChatHub.operators, operatorID)
		globalChatHub.mu.Unlock()
		globalChatHub.setOperatorPresence(operatorID, "OFFLINE")
		conn.Close()
	}()

	// Announce operator online
	globalChatHub.publishEvent(ChatEvent{
		Type: "CONNECT", OperatorID: operatorID, SenderType: "SYSTEM",
		Data: map[string]string{"status": "ONLINE"},
	})

	for {
		var event ChatEvent
		if err := conn.ReadJSON(&event); err != nil {
			break
		}
		event.OperatorID = operatorID
		event.SenderType = "OPERATOR"

		switch event.Type {
		case "SEND_MESSAGE":
			handleOperatorSendMessage(event, db)
		case "START_TYPING":
			globalChatHub.setOperatorPresence(operatorID, "TYPING")
			db.Exec(`UPDATE operator_presence SET typing_to = ? WHERE operator_id = ?`, event.ClientID, operatorID)
			globalChatHub.publishEvent(event)
		case "STOP_TYPING":
			globalChatHub.setOperatorPresence(operatorID, "ONLINE")
			db.Exec(`UPDATE operator_presence SET typing_to = '' WHERE operator_id = ?`, operatorID)
			globalChatHub.publishEvent(event)
		case "MESSAGE_READ":
			markMessagesRead(event.ClientID, "OPERATOR", db)
			globalChatHub.publishEvent(event)
		case "SESSION_SOLVED":
			db.Exec(`UPDATE chat_sessions SET status = 'SOLVED', closed_at = NOW(), updated_at = NOW() WHERE client_id = ?`, event.ClientID)
			globalChatHub.publishEvent(event)
		case "SESSION_CLOSED":
			db.Exec(`UPDATE chat_sessions SET status = 'CLOSED', closed_at = NOW(), updated_at = NOW() WHERE client_id = ?`, event.ClientID)
			globalChatHub.publishEvent(event)
		}
	}

	globalChatHub.publishEvent(ChatEvent{
		Type: "DISCONNECT", OperatorID: operatorID, SenderType: "SYSTEM",
	})
}

// --- CLIENT WEBSOCKET HANDLER ---

func handleClientChatWS(c *gin.Context, db *gorm.DB) {
	if globalChatHub == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "Chat hub not initialized"})
		return
	}

	clientID := c.Query("client_id")
	if clientID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "client_id required"})
		return
	}
	pcName := c.Query("pc_name")

	conn, err := upgrader.Upgrade(c.Writer, c.Request, nil)
	if err != nil {
		return
	}

	globalChatHub.mu.Lock()
	globalChatHub.clients[clientID] = conn
	globalChatHub.mu.Unlock()

	// Upsert session
	var count int64
	db.Table("chat_sessions").Where("client_id = ?", clientID).Count(&count)
	if count == 0 {
		db.Exec(`
			INSERT INTO chat_sessions (client_id, pc_name, status, created_at, updated_at)
			VALUES (?, ?, 'OPEN', NOW(), NOW())
			ON CONFLICT (client_id) DO UPDATE SET status = 'OPEN', updated_at = NOW()
		`, clientID, pcName)
		// Auto-assign operator
		assigned := assignSession(db, clientID, "general")
		globalChatHub.mu.Lock()
		globalChatHub.sessions[clientID] = assigned
		globalChatHub.mu.Unlock()

		// Notify operator
		globalChatHub.publishEvent(ChatEvent{
			Type: "SESSION_ASSIGNED", ClientID: clientID, OperatorID: assigned, SenderType: "SYSTEM",
			Data: map[string]string{"pc_name": pcName, "status": "OPEN"},
		})
	}

	// Set presence
	if globalChatHub.redis != nil {
		globalChatHub.redis.Set(chatCtx, fmt.Sprintf("presence:client:%s", clientID), "ONLINE", 30*time.Second)
	}

	defer func() {
		globalChatHub.mu.Lock()
		delete(globalChatHub.clients, clientID)
		globalChatHub.mu.Unlock()
		if globalChatHub.redis != nil {
			globalChatHub.redis.Del(chatCtx, fmt.Sprintf("presence:client:%s", clientID))
		}
		conn.Close()
	}()

	for {
		var event ChatEvent
		if err := conn.ReadJSON(&event); err != nil {
			break
		}
		event.ClientID = clientID
		event.SenderType = "CLIENT"

		switch event.Type {
		case "SEND_MESSAGE":
			handleClientSendMessage(event, db)
		case "START_TYPING":
			globalChatHub.publishEvent(event)
		case "STOP_TYPING":
			globalChatHub.publishEvent(event)
		case "MESSAGE_READ":
			markMessagesRead(clientID, "CLIENT", db)
			globalChatHub.publishEvent(event)
		}
	}
}

// --- MESSAGE HANDLING ---


func handleClientSendMessage(event ChatEvent, db *gorm.DB) {
	dataMap, ok := event.Data.(map[string]interface{})
	if !ok {
		return
	}
	text, _ := dataMap["message"].(string)
	attachURL, _ := dataMap["attachment_url"].(string)
	attachType, _ := dataMap["attachment_type"].(string)

	// Get pc_name from chat_sessions using ClientID (which is a UUID)
	var session struct {
		PCName string
	}
	db.Table("chat_sessions").Select("pc_name").Where("client_id = ?", event.ClientID).Scan(&session)

	// Look up active incident and its site_id using the actual pc_name
	var incident struct {
		IncidentID int
		SiteID     string
	}
	
	lookupName := event.ClientID
	if session.PCName != "" {
		lookupName = session.PCName
	}

	db.Table("fleet_incidents").
		Select("incident_id, site_id").
		Where("pc_name = ? AND status NOT IN ('RESOLVED', 'CLOSED', 'DLQ', 'FAILED')", lookupName).
		Order("created_at desc").
		Limit(1).
		Scan(&incident)

	msg := database.ChatMessage{
		ClientID:       event.ClientID,
		Sender:         "CLIENT",
		Message:        text,
		AttachmentPath: attachURL,
		ReadStatus:     "SENT",
		IncidentID:     incident.IncidentID,
		ThreadType:     "SUPPORT",
		IsSystemMsg:    false,
	}
	db.Create(&msg)
	triggerChatCompactionIfNeeded(db, incident.IncidentID)

	db.Exec(`UPDATE chat_messages SET delivered_at = NOW(), read_status = 'DELIVERED' WHERE id = ?`, msg.ID)
	db.Exec(`UPDATE chat_sessions SET updated_at = NOW(), unread_count = unread_count + 1 WHERE client_id = ?`, event.ClientID)
	invalidateChatSessionsCache()

	// Get assigned operator
	globalChatHub.mu.RLock()
	operatorID := globalChatHub.sessions[event.ClientID]
	globalChatHub.mu.RUnlock()

	// Immutable audit logging
	_ = writeAuditLog(db, "CHAT_MESSAGE_SENT", "client_"+event.ClientID, fmt.Sprintf("incident_%d", incident.IncidentID), map[string]interface{}{
		"message_id": msg.ID,
		"text":       text,
	})

	// Publish to NATS thread for Live Sync
	if dashboardNatsConn != nil && incident.IncidentID > 0 {
		threadMsg := LiveThreadMessage{
			MessageID:   uuid.New().String(),
			ID:          int64(msg.ID),
			IncidentID:  incident.IncidentID,
			ClientID:    event.ClientID,
			SenderType:  "CLIENT",
			Message:     text,
			Attachment:  attachURL,
			Timestamp:   time.Now().Format(time.RFC3339),
			IsSystemMsg: false,
			ThreadType:  "SUPPORT",
		}
		b, _ := json.Marshal(threadMsg)
		site := cleanSiteID(incident.SiteID)
		_ = dashboardNatsConn.Publish(fmt.Sprintf("chat.site.%s.thread.%d", site, incident.IncidentID), b)
	} else {
		// Fallback to legacy publish
		globalChatHub.publishEvent(ChatEvent{
			Type: "RECEIVE_MESSAGE", ClientID: event.ClientID, OperatorID: operatorID,
			SenderType: "CLIENT",
			Data: map[string]interface{}{
				"message_id":      msg.ID,
				"message":         text,
				"attachment_url":  attachURL,
				"attachment_type": attachType,
				"timestamp":       time.Now().Format(time.RFC3339),
			},
		})
	}

	// Delivered ack back to client
	globalChatHub.publishEvent(ChatEvent{
		Type: "MESSAGE_DELIVERED", ClientID: event.ClientID, SenderType: "SYSTEM",
		Data: map[string]interface{}{"message_id": msg.ID, "delivered_at": time.Now()},
	})

	// AI Assist: async suggestion to operator
	if globalChatHub.supervisor != nil && operatorID != "" {
		go func(q string, opID string) {
			res, _ := globalChatHub.supervisor.DiagnoseIncident(q, "")
			
			var suggestion strings.Builder
			
			if res.ConfidenceScore < 50 || res.PrimaryCause == "Unrecognized Telemetry Signature" || res.Insufficient {
				suggestion.WriteString("Data belum cukup untuk memastikan penyebab masalah. Silakan lakukan langkah pemeriksaan berikut.\n\n")
				suggestion.WriteString("🛠 Cara Penanganan\n\n")
				suggestion.WriteString("1. Pastikan perangkat/klien terhubung ke jaringan.\n")
				suggestion.WriteString("2. Tanyakan detail kendala atau gejala spesifik kepada user.\n")
				suggestion.WriteString("3. Periksa status indikator pada perangkat (jika ada).\n")
				suggestion.WriteString("4. Lakukan pengecekan log sistem secara manual jika diperlukan.\n\n")
				suggestion.WriteString("✅ Verifikasi\n\n")
				suggestion.WriteString("□ User memberikan respons/detail tambahan.\n")
				suggestion.WriteString("□ Status perangkat dapat dipastikan (Online/Offline).\n")
			} else {
				suggestion.WriteString("🛠 Cara Penanganan\n\n")
				
				// Action as step 1
				fmt.Fprintf(&suggestion, "1. %s\n", res.Action)
				
				// Rollback or additional steps if any
				if res.RollbackProcedure != "" {
					fmt.Fprintf(&suggestion, "2. Jika kendala berlanjut, %s\n", strings.ToLower(res.RollbackProcedure))
				} else {
					suggestion.WriteString("2. Lakukan pengujian ulang pada sistem.\n")
				}
				
				if res.EscalationRequired {
					suggestion.WriteString(fmt.Sprintf("3. Jika tetap gagal, eskalasikan ke %s (%s).\n", res.EscalationLevel, res.EscalationReason))
				}
				
				suggestion.WriteString("\n✅ Verifikasi\n\n")
				
				if res.ExpectedResult != "" {
					fmt.Fprintf(&suggestion, "□ %s.\n", res.ExpectedResult)
				}
				if res.RollbackValidation != "" {
					fmt.Fprintf(&suggestion, "□ %s.\n", res.RollbackValidation)
				}
				suggestion.WriteString("□ Tidak ada error baru pada log.\n")
			}

			globalChatHub.publishEvent(ChatEvent{
				Type: "AI_SUGGESTION", ClientID: event.ClientID, OperatorID: opID,
				SenderType: "AI",
				Data: map[string]interface{}{
					"summary":     suggestion.String(),
					"client_id":   event.ClientID,
					"hitl_notice": "AI ASSIST ONLY - Human operator controls final response",
				},
			})
		}(text, operatorID)
	}
}

func handleOperatorSendMessage(event ChatEvent, db *gorm.DB) {
	dataMap, ok := event.Data.(map[string]interface{})
	if !ok {
		return
	}
	text, _ := dataMap["message"].(string)
	attachURL, _ := dataMap["attachment_url"].(string)

	// Look up active incident and its site_id
	var incident struct {
		IncidentID int
		SiteID     string
	}
	db.Table("fleet_incidents").
		Select("incident_id, site_id").
		Where("pc_name = ? AND status NOT IN ('RESOLVED', 'CLOSED', 'DLQ', 'FAILED')", event.ClientID).
		Order("created_at desc").
		Limit(1).
		Scan(&incident)

	msg := database.ChatMessage{
		ClientID:       event.ClientID,
		Sender:         "OPERATOR",
		Message:        text,
		AttachmentPath: attachURL,
		ReadStatus:     "SENT",
		IncidentID:     incident.IncidentID,
		ThreadType:     "SUPPORT",
		IsSystemMsg:    false,
	}
	db.Create(&msg)
	triggerChatCompactionIfNeeded(db, incident.IncidentID)
	db.Exec(`UPDATE chat_messages SET delivered_at = NOW() WHERE id = ?`, msg.ID)
	db.Exec(`UPDATE chat_sessions SET updated_at = NOW(), unread_count = 0 WHERE client_id = ?`, event.ClientID)
	invalidateChatSessionsCache()

	// Immutable audit logging
	_ = writeAuditLog(db, "CHAT_MESSAGE_SENT", event.OperatorID, fmt.Sprintf("incident_%d", incident.IncidentID), map[string]interface{}{
		"message_id": msg.ID,
		"text":       text,
	})

	// Publish to NATS thread for Live Sync
	if dashboardNatsConn != nil && incident.IncidentID > 0 {
		threadMsg := LiveThreadMessage{
			MessageID:   uuid.New().String(),
			ID:          int64(msg.ID),
			IncidentID:  incident.IncidentID,
			ClientID:    event.ClientID,
			SenderType:  "OPERATOR",
			Message:     text,
			Attachment:  attachURL,
			Timestamp:   time.Now().Format(time.RFC3339),
			IsSystemMsg: false,
			ThreadType:  "SUPPORT",
		}
		b, _ := json.Marshal(threadMsg)
		site := cleanSiteID(incident.SiteID)
		_ = dashboardNatsConn.Publish(fmt.Sprintf("chat.site.%s.thread.%d", site, incident.IncidentID), b)
	}
	
	// ALWAYS publish to globalChatHub so ingestion_server (Client WS) and Dashboard UI receive the echo
	globalChatHub.publishEvent(ChatEvent{
		Type: "RECEIVE_MESSAGE", ClientID: event.ClientID, OperatorID: event.OperatorID,
		SenderType: "OPERATOR",
		Data: map[string]interface{}{
			"message_id": msg.ID,
			"message":    text,
			"attachment_url": attachURL,
			"timestamp":  time.Now().Format(time.RFC3339),
		},
	})
}

func markMessagesRead(clientID, readerType string, db *gorm.DB) {
	sender := "CLIENT"
	if readerType == "OPERATOR" {
		sender = "CLIENT" // operator reads client messages
	} else {
		sender = "OPERATOR" // client reads operator messages
	}
	db.Exec(`
		UPDATE chat_messages
		SET read_status = 'READ', read_at = NOW()
		WHERE client_id = ? AND sender = ? AND read_status != 'READ'
	`, clientID, sender)
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

// --- ATTACHMENT UPLOAD ---

func handleChatAttachmentUpload(c *gin.Context) {
	clientID := c.PostForm("client_id")
	if clientID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "client_id required"})
		return
	}

	file, header, err := c.Request.FormFile("file")
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "No file uploaded"})
		return
	}
	defer file.Close()

	// Validate file type
	allowedTypes := map[string]bool{
		".jpg": true, ".jpeg": true, ".png": true, ".gif": true,
		".pdf": true, ".txt": true, ".log": true, ".zip": true,
	}
	ext := strings.ToLower(filepath.Ext(header.Filename))
	if !allowedTypes[ext] {
		c.JSON(http.StatusBadRequest, gin.H{"error": "File type not allowed"})
		return
	}

	// Max 10MB
	if header.Size > 10*1024*1024 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "File exceeds 10MB limit"})
		return
	}

	uploadDir := "/app/uploads/chat"
	if _, err := os.Stat("/app"); os.IsNotExist(err) {
		uploadDir = "./uploads/chat"
	}
	os.MkdirAll(uploadDir, 0755)

	filename := fmt.Sprintf("%s_%d%s", clientID, time.Now().UnixNano(), ext)
	destPath := filepath.Join(uploadDir, filename)
	destFile, err := os.Create(destPath)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to save file"})
		return
	}
	defer destFile.Close()

	buf := make([]byte, 32*1024)
	copyFile(file, destFile, buf)

	attachType := "file"
	if ext == ".jpg" || ext == ".jpeg" || ext == ".png" || ext == ".gif" {
		attachType = "image"
	}

	c.JSON(http.StatusOK, gin.H{
		"url":             fmt.Sprintf("/uploads/chat/%s", filename),
		"attachment_type": attachType,
		"filename":        header.Filename,
	})
}

func copyFile(src multipart.File, dst *os.File, buf []byte) {
	for {
		n, err := src.Read(buf)
		if n > 0 {
			dst.Write(buf[:n])
		}
		if err != nil {
			break
		}
	}
}

// --- REST API HANDLERS ---

// Helper to invalidate active sessions cache
func invalidateChatSessionsCache() {
	if globalChatHub != nil && globalChatHub.redis != nil {
		keys, err := globalChatHub.redis.Keys(chatCtx, "cache:chat_sessions:*").Result()
		if err == nil && len(keys) > 0 {
			globalChatHub.redis.Del(chatCtx, keys...)
		}
	}
}

// GET /api/enterprise/chat/sessions
func handleEnterpriseChatSessions(c *gin.Context, db *gorm.DB) {
	status := c.Query("status")
	operator := c.Query("operator")

	cacheKey := fmt.Sprintf("cache:chat_sessions:%s:%s", status, operator)
	if globalChatHub != nil && globalChatHub.redis != nil {
		if cachedVal, err := globalChatHub.redis.Get(chatCtx, cacheKey).Result(); err == nil && cachedVal != "" {
			var cachedSessions []map[string]interface{}
			if errJson := json.Unmarshal([]byte(cachedVal), &cachedSessions); errJson == nil {
				c.JSON(http.StatusOK, cachedSessions)
				return
			}
		}
	}

	query := db.Table("chat_sessions").Order("updated_at desc")
	if status != "" {
		query = query.Where("status = ?", status)
	}
	if operator != "" {
		query = query.Where("assigned_operator = ?", operator)
	}

	var sessions []map[string]interface{}
	query.Limit(100).Find(&sessions)

	// Add unread + presence info
	for i, s := range sessions {
		clientID, _ := s["client_id"].(string)
		if globalChatHub != nil && globalChatHub.redis != nil {
			presKey := fmt.Sprintf("presence:client:%s", clientID)
			val, _ := globalChatHub.redis.Get(chatCtx, presKey).Result()
			if val != "" {
				sessions[i]["client_online"] = true
			} else {
				sessions[i]["client_online"] = false
			}
		}
	}

	if globalChatHub != nil && globalChatHub.redis != nil && len(sessions) > 0 {
		if bytesVal, errJson := json.Marshal(sessions); errJson == nil {
			globalChatHub.redis.Set(chatCtx, cacheKey, string(bytesVal), 0)
		}
	}

	c.JSON(http.StatusOK, sessions)
}

// GET /api/enterprise/chat/presence
func handleGetPresence(c *gin.Context, db *gorm.DB) {
	if globalChatHub != nil && globalChatHub.redis != nil {
		if cachedVal, err := globalChatHub.redis.Get(chatCtx, "cache:presence").Result(); err == nil && cachedVal != "" {
			var cachedOps []OperatorPresence
			if errJson := json.Unmarshal([]byte(cachedVal), &cachedOps); errJson == nil {
				c.JSON(http.StatusOK, cachedOps)
				return
			}
		}
	}

	var ops []OperatorPresence
	db.Find(&ops)

	if globalChatHub != nil && globalChatHub.redis != nil {
		for i, op := range ops {
			key := fmt.Sprintf("presence:operator:%s", op.OperatorID)
			val, err := globalChatHub.redis.Get(chatCtx, key).Result()
			if err == nil && val != "" {
				ops[i].Status = val
			} else {
				ops[i].Status = "OFFLINE"
			}
		}
	}

	if globalChatHub != nil && globalChatHub.redis != nil && len(ops) > 0 {
		if bytesVal, errJson := json.Marshal(ops); errJson == nil {
			globalChatHub.redis.Set(chatCtx, "cache:presence", string(bytesVal), 60*time.Second)
		}
	}

	c.JSON(http.StatusOK, ops)
}

// POST /api/enterprise/chat/presence
func handleSetPresence(c *gin.Context, db *gorm.DB) {
	_ = db
	var req struct {
		OperatorID string `json:"operator_id"`
		Status     string `json:"status"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if globalChatHub != nil {
		globalChatHub.setOperatorPresence(req.OperatorID, req.Status)
		if globalChatHub.redis != nil {
			globalChatHub.redis.Del(chatCtx, "cache:presence")
		}
	}
	c.JSON(http.StatusOK, gin.H{"status": "updated"})
}

// POST /api/enterprise/chat/feedback
func handleChatFeedback(c *gin.Context, db *gorm.DB) {
	var fb ChatFeedback
	if err := c.ShouldBindJSON(&fb); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	db.Create(&fb)
	// Mark session closed
	db.Exec(`UPDATE chat_sessions SET status = 'CLOSED', closed_at = NOW() WHERE client_id = ?`, fb.SessionClientID)
	invalidateChatSessionsCache()
	c.JSON(http.StatusOK, gin.H{"id": fb.ID, "status": "recorded"})
}

// GET /api/enterprise/chat/ai_assist?client_id=xxx
func handleAIAssist(c *gin.Context, db *gorm.DB, sup *ai.AISupervisor) {
	clientID := c.Query("client_id")
	if clientID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "client_id required"})
		return
	}

	// Get last 50 client messages as context (Sprint M P4 fix)
	var messages []database.ChatMessage
	db.Where("client_id = ? AND sender = 'CLIENT'", clientID).
		Order("id desc").Limit(50).Find(&messages)

	var combined strings.Builder
	for i := len(messages) - 1; i >= 0; i-- {
		combined.WriteString(messages[i].Message)
		combined.WriteString(" ")
	}
	query := strings.TrimSpace(combined.String())
	if query == "" {
		c.JSON(http.StatusOK, gin.H{"suggestion": "No client messages to analyze yet."})
		return
	}

	res, _ := sup.DiagnoseIncident(query, "")
	
	var suggestion strings.Builder
			
	if res.ConfidenceScore < 50 || res.PrimaryCause == "Unrecognized Telemetry Signature" || res.Insufficient {
		suggestion.WriteString("Data belum cukup untuk memastikan penyebab masalah. Silakan lakukan langkah pemeriksaan berikut.\n\n")
		suggestion.WriteString("🛠 Cara Penanganan\n\n")
		suggestion.WriteString("1. Pastikan perangkat/klien terhubung ke jaringan.\n")
		suggestion.WriteString("2. Tanyakan detail kendala atau gejala spesifik kepada user.\n")
		suggestion.WriteString("3. Periksa status indikator pada perangkat (jika ada).\n")
		suggestion.WriteString("4. Lakukan pengecekan log sistem secara manual jika diperlukan.\n\n")
		suggestion.WriteString("✅ Verifikasi\n\n")
		suggestion.WriteString("□ User memberikan respons/detail tambahan.\n")
		suggestion.WriteString("□ Status perangkat dapat dipastikan (Online/Offline).\n")
	} else {
		suggestion.WriteString("🛠 Cara Penanganan\n\n")
		
		fmt.Fprintf(&suggestion, "1. %s\n", res.Action)
		
		if res.RollbackProcedure != "" {
			fmt.Fprintf(&suggestion, "2. Jika kendala berlanjut, %s\n", strings.ToLower(res.RollbackProcedure))
		} else {
			suggestion.WriteString("2. Lakukan pengujian ulang pada sistem.\n")
		}
		
		if res.EscalationRequired {
			suggestion.WriteString(fmt.Sprintf("3. Jika tetap gagal, eskalasikan ke %s (%s).\n", res.EscalationLevel, res.EscalationReason))
		}
		
		suggestion.WriteString("\n✅ Verifikasi\n\n")
		
		if res.ExpectedResult != "" {
			fmt.Fprintf(&suggestion, "□ %s.\n", res.ExpectedResult)
		}
		if res.RollbackValidation != "" {
			fmt.Fprintf(&suggestion, "□ %s.\n", res.RollbackValidation)
		}
		suggestion.WriteString("□ Tidak ada error baru pada log.\n")
	}

	// HITL enforcement: AI only suggests, never acts
	c.JSON(http.StatusOK, gin.H{
		"hitl_mode":   true,
		"ai_role":     "ASSISTANT_ONLY",
		"client_id":   clientID,
		"query":       query,
		"suggestion":  suggestion.String(),
		"warning":     "AI ASSIST ONLY. Human operator controls all actions.",
	})
}

// GET /api/enterprise/chat/unread_counts
func handleUnreadCounts(c *gin.Context, db *gorm.DB) {
	operatorID := c.Query("operator_id")
	type UnreadRow struct {
		ClientID    string `json:"client_id"`
		UnreadCount int    `json:"unread_count"`
	}
	var rows []UnreadRow
	query := db.Table("chat_sessions").Select("client_id, unread_count").
		Where("status IN ?", []string{"OPEN", "ACTIVE", "PENDING"})
	if operatorID != "" {
		query = query.Where("assigned_operator = ?", operatorID)
	}
	query.Scan(&rows)
	c.JSON(http.StatusOK, rows)
}

// --- ENTERPRISE CHAT HISTORY ---

// GET /api/enterprise/chat/history/:client_id
// Returns full chat history for a session, including attachment_url field
func handleEnterpriseChatHistory(c *gin.Context, db *gorm.DB) {
	clientID := c.Param("client_id")
	limit := 200

	type MsgRow struct {
		ID             uint      `json:"id"`
		ClientID       string    `json:"client_id"`
		Sender         string    `json:"sender"`
		Message        string    `json:"message"`
		AttachmentPath string    `json:"attachment_path"`
		AttachmentURL  string    `json:"attachment_url"`
		ReadStatus     string    `json:"read_status"`
		IncidentID     int       `json:"incident_id"`
		ThreadType     string    `json:"thread_type"`
		IsSystemMsg    bool      `json:"is_system_msg"`
		CreatedAt      time.Time `json:"created_at"`
		DeliveredAt    *time.Time `json:"delivered_at,omitempty"`
		ReadAt         *time.Time `json:"read_at,omitempty"`
	}

	var rows []MsgRow
	db.Raw(`
		SELECT id, client_id, sender, message,
		       COALESCE(attachment_url, attachment_path, '') AS attachment_url,
		       COALESCE(attachment_path, '') AS attachment_path,
		       read_status, incident_id, thread_type, is_system_msg, created_at,
		       delivered_at, read_at
		FROM chat_messages
		WHERE client_id = ?
		ORDER BY created_at ASC
		LIMIT ?
	`, clientID, limit).Scan(&rows)

	if rows == nil {
		rows = []MsgRow{}
	}
	c.JSON(http.StatusOK, rows)
}

// --- AI ISSUE DETECTION REPORT ---

type AIIssueReport struct {
	IssueName         string                 `json:"issue_name"`
	Severity          string                 `json:"severity"` // CRITICAL, HIGH, MEDIUM, LOW
	DetectedAt        string                 `json:"detected_at"`
	AffectedModules   []string               `json:"affected_modules"`
	PossibleCauses    []string               `json:"possible_causes"`
	AIAnalysis        string                 `json:"ai_analysis"`
	SystemImpact      string                 `json:"system_impact"`
	Recommendations   []string               `json:"recommendations"`
	RemediationSteps  []string               `json:"remediation_steps"`
	HandlingStatus    string                 `json:"handling_status"`
	Progress          int                    `json:"progress"`
	ErrorLogs         []string               `json:"error_logs"`
	Timeline          []map[string]interface{} `json:"timeline"`
	// Per-platform payloads
	DashboardPayload  map[string]interface{} `json:"dashboard_payload"`
	TelegramPayload   string                 `json:"telegram_payload"`
	OperatorPayload   map[string]interface{} `json:"operator_payload"` // for OSI AI Support Chat
}

// GET /api/enterprise/chat/issue_report/:client_id
// Returns a structured AI issue report for the active incident linked to this client
func handleAIIssueReport(c *gin.Context, db *gorm.DB, sup *ai.AISupervisor) {
	clientID := c.Param("client_id")
	platform := c.Query("platform") // "dashboard", "telegram", "operator"
	if platform == "" {
		platform = "dashboard"
	}

	// Get last 50 client messages for context (Sprint M P4 fix)
	var messages []database.ChatMessage
	db.Where("client_id = ? AND sender = 'CLIENT'", clientID).
		Order("id desc").Limit(50).Find(&messages)

	var combined strings.Builder
	for i := len(messages) - 1; i >= 0; i-- {
		combined.WriteString(messages[i].Message)
		combined.WriteString(" ")
	}
	query := strings.TrimSpace(combined.String())

	// Get active incident
	var inc struct {
		IncidentID  int    `gorm:"column:incident_id"`
		SiteID      string `gorm:"column:site_id"`
		Severity    string `gorm:"column:severity"`
		Description string `gorm:"column:description"`
		Status      string `gorm:"column:status"`
	}
	db.Table("fleet_incidents").
		Select("incident_id, site_id, severity, description, status").
		Where("pc_name = ? AND status NOT IN ('RESOLVED', 'CLOSED', 'DLQ', 'FAILED')", clientID).
		Order("created_at desc").Limit(1).Scan(&inc)

	severity := inc.Severity
	if severity == "" {
		severity = "MEDIUM"
	}
	issueName := inc.Description
	if issueName == "" {
		issueName = "Issue terdeteksi dari laporan client"
	}

	aiAnalysis := "Tidak ada analisis tersedia."
	if sup != nil && query != "" {
		_, report := sup.DiagnoseIncident(query, "")
		if len(report) > 0 {
			l := len(report)
			if l > 1500 {
				l = 1500
			}
			aiAnalysis = report[:l]
		}
	}

	report := AIIssueReport{
		IssueName:  issueName,
		Severity:   severity,
		DetectedAt: time.Now().Format(time.RFC3339),
		AffectedModules: []string{"Chat System", "OSI AI Support Chat", "Dashboard Live Chat"},
		PossibleCauses: []string{
			"WebSocket disconnected",
			"Event listener tidak aktif",
			"Queue message gagal diproses",
			"API sinkronisasi gagal",
			"Database insert gagal",
		},
		AIAnalysis:   aiAnalysis,
		SystemImpact: "Komunikasi dua arah antara client dan operator terganggu.",
		Recommendations: []string{
			"Periksa koneksi WebSocket",
			"Verifikasi endpoint API",
			"Validasi event broadcast",
			"Restart message queue bila diperlukan",
			"Sinkronisasi ulang data yang gagal",
		},
		RemediationSteps: []string{
			"1. Periksa apakah koneksi jaringan normal",
			"2. Klik tombol Reconnect pada aplikasi",
			"3. Tunggu proses sinkronisasi selesai",
			"4. Jika masalah berlanjut, hubungi Administrator",
		},
		HandlingStatus: "IN_PROGRESS",
		Progress:       0,
		ErrorLogs:      []string{},
		Timeline: []map[string]interface{}{
			{"time": time.Now().Format(time.RFC3339), "event": "Issue terdeteksi oleh AI", "actor": "AI_SYSTEM"},
		},
	}

	// Build per-platform payloads
	report.DashboardPayload = map[string]interface{}{
		"issue_name":         report.IssueName,
		"severity":           report.Severity,
		"detected_at":        report.DetectedAt,
		"affected_modules":   report.AffectedModules,
		"possible_causes":    report.PossibleCauses,
		"ai_analysis":        report.AIAnalysis,
		"system_impact":      report.SystemImpact,
		"recommendations":    report.Recommendations,
		"remediation_steps":  report.RemediationSteps,
		"handling_status":    report.HandlingStatus,
		"progress":           report.Progress,
		"error_logs":         report.ErrorLogs,
		"timeline":           report.Timeline,
	}
	report.TelegramPayload = fmt.Sprintf(
		"🚨 <b>%s ALERT: %s</b>\n\n"+
			"⏰ <b>Waktu:</b> %s\n"+
			"📊 <b>AI Analisis:</b> %s\n\n"+
			"💡 <b>Langkah Penanganan:</b>\n1. Periksa koneksi jaringan\n2. Verifikasi endpoint API\n3. Restart message queue bila diperlukan",
		report.Severity, report.IssueName, report.DetectedAt, aiAnalysis,
	)
	report.OperatorPayload = map[string]interface{}{
		"detail_issue":    issueName,
		"cara_penanganan": report.RemediationSteps,
	}

	// Return full report or platform-specific
	switch platform {
	case "telegram":
		c.JSON(http.StatusOK, gin.H{"telegram_text": report.TelegramPayload})
	case "operator":
		c.JSON(http.StatusOK, report.OperatorPayload)
	default:
		c.JSON(http.StatusOK, report)
	}

	// Async: Push report to all operators via WebSocket (Dashboard) and Telegram via NATS
	if inc.IncidentID > 0 {
		go func() {
			if globalChatHub != nil {
				globalChatHub.mu.RLock()
				for _, conn := range globalChatHub.operators {
					_ = conn.WriteJSON(ChatEvent{
						Type:       "AI_ISSUE_REPORT",
						ClientID:   clientID,
						SenderType: "AI",
						Data:       report.DashboardPayload,
					})
				}
				globalChatHub.mu.RUnlock()
			}
			// Publish to Telegram via NATS
			if dashboardNatsConn != nil {
				b, _ := json.Marshal(LiveThreadMessage{
					MessageID:   uuid.New().String(),
					IncidentID:  inc.IncidentID,
					ClientID:    clientID,
					SenderType:  "SYSTEM",
					Message:     report.TelegramPayload,
					Timestamp:   time.Now().Format(time.RFC3339),
					IsSystemMsg: true,
					ThreadType:  "SUPPORT",
				})
				site := cleanSiteID(inc.SiteID)
				_ = dashboardNatsConn.Publish(
					fmt.Sprintf("chat.site.%s.thread.%d", site, inc.IncidentID), b,
				)
			}
		}()
	}
}

// --- ROUTE REGISTRATION ---

// POST /api/enterprise/chat/sessions/status/:client_id
func handleEnterpriseSessionStatus(c *gin.Context, db *gorm.DB) {
	clientID := c.Param("client_id")
	var req struct {
		Status string `json:"status"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	err := db.Exec(`UPDATE chat_sessions SET status = ?, updated_at = NOW() WHERE client_id = ?`, req.Status, clientID).Error
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	invalidateChatSessionsCache()
	// Broadcast status change
	if globalChatHub != nil {
		globalChatHub.publishEvent(ChatEvent{
			Type:       "SESSION_ASSIGNED",
			ClientID:   clientID,
			SenderType: "SYSTEM",
			Data: map[string]interface{}{
				"status": req.Status,
			},
		})
	}
	c.JSON(http.StatusOK, gin.H{"status": "updated", "new_status": req.Status})
}

// GET /api/enterprise/chat/device_context/:client_id
// Returns incident history, remote sessions, and screenshots linked to this client
func handleEnterpriseDeviceContext(c *gin.Context, db *gorm.DB) {
	clientID := c.Param("client_id")

	// Get active incidents for this client (linked by pc_name = client_id convention)
	type IncidentRow struct {
		IncidentID  int    `json:"incident_id" gorm:"column:incident_id"`
		Severity    string `json:"severity" gorm:"column:severity"`
		Status      string `json:"status" gorm:"column:status"`
		Description string `json:"description" gorm:"column:description"`
		CreatedAt   string `json:"created_at" gorm:"column:created_at"`
	}
	var incidents []IncidentRow
	db.Raw(`
		SELECT incident_id, COALESCE(severity, 'MEDIUM') as severity,
		       COALESCE(status, 'ACTIVE') as status,
		       COALESCE(description, '') as description,
		       created_at::text
		FROM fleet_incidents
		WHERE pc_name = ?
		ORDER BY created_at DESC
		LIMIT 5
	`, clientID).Scan(&incidents)
	if incidents == nil {
		incidents = []IncidentRow{}
	}

	// Get remote sessions
	type RemoteRow struct {
		Operator  string `json:"operator" gorm:"column:operator"`
		Status    string `json:"status" gorm:"column:status"`
		Reason    string `json:"reason" gorm:"column:reason"`
		StartTime string `json:"start_time" gorm:"column:start_time"`
	}
	var remoteSessions []RemoteRow
	db.Raw(`
		SELECT COALESCE(requested_by, '') as operator,
		       COALESCE(status, 'ENDED') as status,
		       COALESCE(reason, 'Remote Access') as reason,
		       created_at::text as start_time
		FROM remote_access_logs
		WHERE device_name = ? OR target_device = ?
		ORDER BY created_at DESC
		LIMIT 3
	`, clientID, clientID).Scan(&remoteSessions)
	if remoteSessions == nil {
		remoteSessions = []RemoteRow{}
	}

	// Get screenshots from chat_messages
	type ScreenshotRow struct {
		AttachmentPath string `json:"attachment_path" gorm:"column:attachment_path"`
	}
	var screenshots []ScreenshotRow
	db.Raw(`
		SELECT attachment_path
		FROM chat_messages
		WHERE client_id = ? AND attachment_path != '' AND (
			attachment_path LIKE '%.png' OR attachment_path LIKE '%.jpg' OR
			attachment_path LIKE '%.jpeg' OR attachment_path LIKE '%.gif'
		)
		ORDER BY created_at DESC
		LIMIT 10
	`, clientID).Scan(&screenshots)
	if screenshots == nil {
		screenshots = []ScreenshotRow{}
	}

	c.JSON(http.StatusOK, gin.H{
		"client_id":       clientID,
		"incidents":       incidents,
		"remote_sessions": remoteSessions,
		"screenshots":     screenshots,
	})
}


func RegisterChatEngineRoutes(r interface {
	GET(string, ...gin.HandlerFunc) gin.IRoutes
	POST(string, ...gin.HandlerFunc) gin.IRoutes
}, db *gorm.DB, rc *redis.Client, sup *ai.AISupervisor) {

	// Init hub
	InitChatHub(rc, db, sup)

	// Operator WebSocket (separate from legacy /ws/chat)
	r.GET("/ws/operator_chat", func(c *gin.Context) {
		handleOperatorChatWS(c, db)
	})

	// Client WebSocket
	r.GET("/ws/client_chat", func(c *gin.Context) {
		handleClientChatWS(c, db)
	})

	// REST APIs
	r.GET("/api/enterprise/chat/sessions", func(c *gin.Context) {
		handleEnterpriseChatSessions(c, db)
	})
	r.GET("/api/enterprise/chat/presence", func(c *gin.Context) {
		handleGetPresence(c, db)
	})
	r.POST("/api/enterprise/chat/presence", func(c *gin.Context) {
		handleSetPresence(c, db)
	})
	r.POST("/api/enterprise/chat/feedback", func(c *gin.Context) {
		handleChatFeedback(c, db)
	})
	r.GET("/api/enterprise/chat/ai_assist", func(c *gin.Context) {
		handleAIAssist(c, db, sup)
	})
	r.GET("/api/enterprise/chat/unread_counts", func(c *gin.Context) {
		handleUnreadCounts(c, db)
	})
	r.POST("/api/enterprise/chat/upload", handleChatAttachmentUpload)

	// History endpoint (required by Dashboard Live Chat)
	r.GET("/api/enterprise/chat/history/:client_id", func(c *gin.Context) {
		handleEnterpriseChatHistory(c, db)
	})

	// AI Issue Detection report endpoint
	r.GET("/api/enterprise/chat/issue_report/:client_id", func(c *gin.Context) {
		handleAIIssueReport(c, db, sup)
	})

	// Session status update (migrate from dashboard_chat)
	r.POST("/api/enterprise/chat/sessions/status/:client_id", func(c *gin.Context) {
		handleEnterpriseSessionStatus(c, db)
	})

	// Device context for chat sidebar
	r.GET("/api/enterprise/chat/device_context/:client_id", func(c *gin.Context) {
		handleEnterpriseDeviceContext(c, db)
	})
}



func triggerChatCompactionIfNeeded(db *gorm.DB, incidentID int) {
	if incidentID <= 0 || dashboardNatsConn == nil {
		return
	}

	go func() {
		// Find the last checkpoint ID
		var lastCheckpointID uint
		_ = db.Table("chat_messages").
			Select("id").
			Where("incident_id = ? AND sender = 'SYSTEM' AND message LIKE '[CHAT SUMMARY CHECKPOINT]%'", incidentID).
			Order("created_at DESC").
			Limit(1).
			Scan(&lastCheckpointID)

		// Count messages since last checkpoint
		var count int64
		if lastCheckpointID > 0 {
			db.Table("chat_messages").
				Where("incident_id = ? AND id > ? AND message NOT LIKE '[CHAT SUMMARY CHECKPOINT]%'", incidentID, lastCheckpointID).
				Count(&count)
		} else {
			db.Table("chat_messages").
				Where("incident_id = ? AND message NOT LIKE '[CHAT SUMMARY CHECKPOINT]%'", incidentID).
				Count(&count)
		}

		// If count >= 15, trigger compaction via NATS
		if count >= 15 {
			payload := map[string]interface{}{
				"incident_id": incidentID,
			}
			b, err := json.Marshal(payload)
			if err == nil {
				_ = dashboardNatsConn.Publish("chat.compact", b)
				fmt.Printf("[CHAT COMPACTION] Published compaction request for incident %d\n", incidentID)
			}
		}
	}()
}

