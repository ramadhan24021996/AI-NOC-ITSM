package main

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

func RegisterPredictiveRoutes(r *gin.Engine, dbConn *gorm.DB) {
	// 9. API endpoint prediction for asset
	r.GET("/api/prediction/:asset_id", func(c *gin.Context) {
		assetID := c.Param("asset_id")
		var predictions []map[string]interface{}
		// Get latest prediction
		res := dbConn.Table("prediction_history").Where("asset_id = ?", assetID).Order("predicted_at DESC").Limit(5).Find(&predictions)
		if res.Error != nil || len(predictions) == 0 {
			c.JSON(http.StatusOK, gin.H{"prediction": false, "message": "No predictive data available"})
			return
		}
		c.JSON(http.StatusOK, predictions[0])
	})

	// 10. Prediction REST API (All active predictions/warnings)
	r.GET("/api/predictions/active", func(c *gin.Context) {
		var activeWarnings []map[string]interface{}
		dbConn.Table("prediction_history").
			Where("eta_minutes > 0 AND eta_minutes <= 60").
			Order("eta_minutes ASC").
			Limit(20).
			Find(&activeWarnings)
		c.JSON(http.StatusOK, activeWarnings)
	})

	// 11. Prediction Metrics
	r.GET("/api/predictions/metrics", func(c *gin.Context) {
		var total, falsePositive, falseNegative int64
		dbConn.Table("prediction_history").Count(&total)
		dbConn.Table("prediction_history").Where("false_positive = ?", true).Count(&falsePositive)
		dbConn.Table("prediction_history").Where("false_negative = ?", true).Count(&falseNegative)

		accuracy := 100.0
		var precision, recall, f1Score float64
		if total > 0 {
			accuracy = float64(total-falsePositive-falseNegative) / float64(total) * 100.0
			tp := float64(total - falsePositive - falseNegative)
			if tp+float64(falsePositive) > 0 {
				precision = tp / (tp + float64(falsePositive))
			}
			if tp+float64(falseNegative) > 0 {
				recall = tp / (tp + float64(falseNegative))
			}
			if precision+recall > 0 {
				f1Score = 2 * (precision * recall) / (precision + recall)
			}
		}

		c.JSON(http.StatusOK, gin.H{
			"total_predictions": total,
			"false_positives":   falsePositive,
			"false_negatives":   falseNegative,
			"accuracy_score":    accuracy,
			"f1_score":          f1Score,
			"precision":         precision,
			"recall":            recall,
		})
	})
}
