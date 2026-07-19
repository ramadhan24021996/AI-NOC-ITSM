package ingestion

import (
	"encoding/json"
	"fmt"
	"time"

	"go_incident_analysis/SERVER/go_core/database"
)

// ChatService provides modular methods for managing chat sessions and messages.
type ChatService struct{}

var DefaultChatService = &ChatService{}

// GetOrCreateChatSession retrieves an existing chat session or creates one if it doesn't exist.
func (s *ChatService) GetOrCreateChatSession(clientID string, pcName string) (database.ChatSession, error) {
	var session database.ChatSession
	err := database.DB.Where("client_id = ?", clientID).First(&session).Error
	if err != nil {
		session = database.ChatSession{
			ClientID:  clientID,
			PCName:    pcName,
			Status:    "OPEN",
			CreatedAt: time.Now(),
			UpdatedAt: time.Now(),
		}
		if err := database.DB.Create(&session).Error; err != nil {
			return session, err
		}
	}
	return session, nil
}

// SaveChatMessage saves a message to the database.
func (s *ChatService) SaveChatMessage(clientID string, sender string, message string, attachmentPath string, readStatus string) (database.ChatMessage, error) {
	msg := database.ChatMessage{
		ClientID:       clientID,
		Sender:         sender,
		Message:        message,
		AttachmentPath: attachmentPath,
		ReadStatus:     readStatus,
		CreatedAt:      time.Now(),
	}
	err := database.DB.Create(&msg).Error
	return msg, err
}

// PublishChatEvent sends a chat event to Redis channels for operator/client sync.
func (s *ChatService) PublishChatEvent(event ChatEvent) {
	if redisClient == nil {
		return
	}
	payloadBytes, err := json.Marshal(event)
	if err != nil {
		return
	}
	// Publish to both channels to sync dashboard and client agent
	_ = redisClient.Publish(ctx, "chat_channel", string(payloadBytes)).Err()

	// Translate to operator dashboard format
	dashboardEvent := DashboardChatEvent{
		Type:       "RECEIVE_MESSAGE",
		ClientID:   event.ClientID,
		SenderType: event.Sender,
		Data:       event.Data,
	}
	dashBytes, _ := json.Marshal(dashboardEvent)
	_ = redisClient.Publish(ctx, "enterprise_chat", string(dashBytes)).Err()
}

// SendWSCommand sends a command directly to a connected client tray application WebSocket.
func (s *ChatService) SendWSCommand(clientID string, cmdType string, data interface{}) error {
	wsChatClientsMu.RLock()
	clientConn, exists := wsChatClients[clientID]
	wsChatClientsMu.RUnlock()

	if !exists {
		return fmt.Errorf("client %s not connected via WebSocket", clientID)
	}

	event := ChatEvent{
		Type:     cmdType,
		ClientID: clientID,
		Sender:   "SYSTEM",
		Data:     data,
	}

	clientConn.mu.Lock()
	defer clientConn.mu.Unlock()
	return clientConn.conn.WriteJSON(event)
}
