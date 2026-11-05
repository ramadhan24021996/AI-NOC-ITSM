package main

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"

	"go_incident_analysis/SERVER/go_core/database"
)

// handleGetChatSessions retrieves all active chat sessions sorted by recent activity.
func handleGetChatSessions(c *gin.Context, db *gorm.DB) {
	var sessions []database.ChatSession
	db.Order("updated_at desc").Find(&sessions)
	c.JSON(http.StatusOK, sessions)
}

// handleUpdateSessionStatus updates session state and broadcasts operator status.
func handleUpdateSessionStatus(c *gin.Context, db *gorm.DB) {
	clientID := c.Param("client_id")
	var req struct {
		Status string `json:"status"` // OPEN, WAITING_OPERATOR, ACTIVE, CLOSED
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	err := db.Model(&database.ChatSession{}).Where("client_id = ?", clientID).Update("status", req.Status).Error
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	publishDashboardChatEvent(DashboardChatEvent{
		Type:     "operator_status",
		ClientID: clientID,
		Sender:   "SYSTEM",
		Data: map[string]interface{}{
			"status": req.Status,
		},
	})

	c.JSON(http.StatusOK, gin.H{"status": "SUCCESS"})
}

// handleGetChatHistory retrieves full message history for a given client agent.
func handleGetChatHistory(c *gin.Context, db *gorm.DB) {
	clientID := c.Param("client_id")
	var messages []database.ChatMessage
	db.Where("client_id = ?", clientID).Order("id asc").Find(&messages)
	c.JSON(http.StatusOK, messages)
}
