package main

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

func RegisterAssetRoutes(r *gin.Engine, dbConn *gorm.DB) {
	// MODULE 11: GET /api/assets
	r.GET("/api/assets", func(c *gin.Context) {
		var assets []map[string]interface{}
		dbConn.Table("assets").Find(&assets)
		c.JSON(http.StatusOK, assets)
	})

	// GET /api/assets/{id}
	r.GET("/api/assets/:id", func(c *gin.Context) {
		id := c.Param("id")
		var asset map[string]interface{}
		res := dbConn.Table("assets").Where("asset_id = ?", id).First(&asset)
		if res.Error != nil {
			c.JSON(http.StatusNotFound, gin.H{"error": "Asset not found"})
			return
		}
		c.JSON(http.StatusOK, asset)
	})

	// GET /api/assets/topology
	r.GET("/api/assets/topology", func(c *gin.Context) {
		var assets []map[string]interface{}
		dbConn.Table("assets").Find(&assets)
		
		var links []map[string]interface{}
		dbConn.Table("asset_dependencies").Find(&links)
		
		c.JSON(http.StatusOK, gin.H{
			"nodes": assets,
			"links": links,
		})
	})

	// GET /api/assets/health
	r.GET("/api/assets/health", func(c *gin.Context) {
		var assets []map[string]interface{}
		dbConn.Table("assets").Select("asset_id, hostname, health_score, status").Find(&assets)
		c.JSON(http.StatusOK, assets)
	})

	// GET /api/assets/dependency
	r.GET("/api/assets/dependency", func(c *gin.Context) {
		var links []map[string]interface{}
		dbConn.Table("asset_dependencies").Find(&links)
		c.JSON(http.StatusOK, links)
	})

	// GET /api/assets/business-impact
	r.GET("/api/assets/business-impact", func(c *gin.Context) {
		var impacts []map[string]interface{}
		dbConn.Table("asset_business_impacts").Find(&impacts)
		c.JSON(http.StatusOK, impacts)
	})

	// GET /api/assets/site
	r.GET("/api/assets/site", func(c *gin.Context) {
		var sites []map[string]interface{}
		dbConn.Table("sites").Find(&sites)
		c.JSON(http.StatusOK, sites)
	})
}
