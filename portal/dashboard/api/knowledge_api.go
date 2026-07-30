package api

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"go_incident_analysis/portal/dashboard/knowledge"
)

// SearchKnowledgeBase handles POST /api/ai/knowledge/search
func (h *Handler) SearchKnowledgeBase(c *gin.Context) {
	var req struct {
		Query string `json:"query"`
	}
	if err := c.ShouldBindJSON(&req); err != nil || req.Query == "" {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": "query parameter required"})
		return
	}

	match := knowledge.GlobalEngine.Match(req.Query)
	if match == nil {
		c.JSON(http.StatusOK, gin.H{
			"status":  "not_found",
			"message": "Tidak ada panduan spesifik yang cocok di Knowledge Base.",
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"status": "matched",
		"data":   match,
	})
}

// ListKnowledgeBase handles GET /api/ai/knowledge/list
func (h *Handler) ListKnowledgeBase(c *gin.Context) {
	items := knowledge.GlobalEngine.GetItems()
	c.JSON(http.StatusOK, gin.H{
		"status": "success",
		"count":  len(items),
		"data":   items,
	})
}

// ImportKnowledgeBase handles POST /api/ai/knowledge/import
func (h *Handler) ImportKnowledgeBase(c *gin.Context) {
	var req struct {
		Items []knowledge.KnowledgeItem `json:"items"`
	}
	if err := c.ShouldBindJSON(&req); err != nil || len(req.Items) == 0 {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": "items array required"})
		return
	}

	count, err := knowledge.GlobalEngine.ImportItems(req.Items)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"status": "error", "message": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"status":  "success",
		"message": "Berhasil mengimpor basis pengetahuan RAG baru",
		"imported_count": count,
	})
}
