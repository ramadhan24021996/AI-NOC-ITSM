package main

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

func RegisterMultiAgentRoutes(r *gin.Engine, dbConn *gorm.DB) {
	// API GET /api/agents
	r.GET("/api/agents", func(c *gin.Context) {
		var agents []map[string]interface{}
		if err := dbConn.Table("agent_registry").Find(&agents).Error; err != nil {
			c.JSON(http.StatusOK, []map[string]interface{}{})
			return
		}
		c.JSON(http.StatusOK, agents)
	})

	// API GET /api/agents/status
	r.GET("/api/agents/status", func(c *gin.Context) {
		var statuses []map[string]interface{}
		if err := dbConn.Table("agent_health").Order("checked_at DESC").Limit(50).Find(&statuses).Error; err != nil {
			c.JSON(http.StatusOK, []map[string]interface{}{})
			return
		}
		c.JSON(http.StatusOK, statuses)
	})

	// API GET /api/agents/trust
	r.GET("/api/agents/trust", func(c *gin.Context) {
		var trusts []map[string]interface{}
		if err := dbConn.Table("agent_registry").Select("agent_id, trust_score, confidence").Order("trust_score DESC").Find(&trusts).Error; err != nil {
			c.JSON(http.StatusOK, []map[string]interface{}{})
			return
		}
		c.JSON(http.StatusOK, trusts)
	})

	// API GET /api/agents/performance
	r.GET("/api/agents/performance", func(c *gin.Context) {
		var perf []map[string]interface{}
		if err := dbConn.Table("agent_performance").Order("recorded_at DESC").Limit(50).Find(&perf).Error; err != nil {
			c.JSON(http.StatusOK, []map[string]interface{}{})
			return
		}
		c.JSON(http.StatusOK, perf)
	})

	// API GET /api/consensus
	r.GET("/api/consensus", func(c *gin.Context) {
		var consensuses []map[string]interface{}
		if err := dbConn.Table("consensus_history").Order("created_at DESC").Limit(50).Find(&consensuses).Error; err != nil {
			c.JSON(http.StatusOK, []map[string]interface{}{})
			return
		}
		c.JSON(http.StatusOK, consensuses)
	})
}
