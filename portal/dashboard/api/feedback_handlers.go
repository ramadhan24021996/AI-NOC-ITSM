package api

import (
	"bytes"
	"crypto/sha256"
	"encoding/csv"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"time"
	"github.com/gin-gonic/gin"
)

func (h *Handler) GetFeedback(c *gin.Context) {
	var feedbacks []map[string]interface{}
	if h.db != nil {
		h.db.Table("incident_feedback").Order("created_at DESC").Limit(50).Find(&feedbacks)
	}
	c.JSON(http.StatusOK, feedbacks)
}

// GetFeedbackStats returns rating aggregated stats.
func (h *Handler) GetFeedbackStats(c *gin.Context) {
	var correctCount, incorrectCount, ragCount, pendingCount, approvedCount, rejectedCount int64

	if h.db != nil {
		h.db.Table("incident_feedback").Where("score >= 0.8 OR status = 'APPROVED'").Count(&correctCount)
		h.db.Table("incident_feedback").Where("score < 0.8 AND status != 'APPROVED'").Count(&incorrectCount)
		h.db.Table("incident_feedback").Where("status = 'PENDING_APPROVAL'").Count(&pendingCount)
		h.db.Table("incident_feedback").Where("status = 'APPROVED'").Count(&approvedCount)
		h.db.Table("incident_feedback").Where("status = 'REJECTED'").Count(&rejectedCount)
		h.db.Table("knowledge_vectors").Count(&ragCount)
	}

	var queue []gin.H
	if h.db != nil {
		rows, err := h.db.Raw(`
			SELECT i.incident_id, 
			       COALESCE(NULLIF(i.device_name, ''), 'SYSTEM') AS device_name, 
			       COALESCE(NULLIF(i.flag, ''), 'UNKNOWN') AS flag, 
			       CASE WHEN i.confidence > 1 THEN i.confidence / 100.0 ELSE i.confidence END AS confidence,
			       i.evidence AS evidence,
			       COALESCE((SELECT COALESCE(final_decision, first_hypothesis) FROM ai_reflection_logs WHERE incident_id = i.incident_id ORDER BY id DESC LIMIT 1), 'Autonomous Analysis') AS action,
			       COALESCE(f.status, 'PENDING_REVIEW') AS feedback_status,
			       COALESCE(f.correlation_id, '') AS correlation_id,
			       COALESCE(f.trace_id, '') AS trace_id
			FROM incidents i
			LEFT JOIN incident_feedback f ON i.incident_id = f.incident_id
			WHERE f.incident_id IS NULL OR f.status = 'PENDING_APPROVAL'
			ORDER BY i.timestamp DESC
			LIMIT 25
		`).Rows()

		if err == nil {
			defer rows.Close()
			for rows.Next() {
				var id int
				var device, flag, evidence, action, fbStatus, corrID, traceID string
				var conf float64
				rows.Scan(&id, &device, &flag, &conf, &evidence, &action, &fbStatus, &corrID, &traceID)
				if corrID == "" {
					corrID = fmt.Sprintf("corr_fb_%d", id)
				}
				if traceID == "" {
					traceID = fmt.Sprintf("trace_fb_%d", id)
				}
				queue = append(queue, gin.H{
					"incident_id":    id,
					"device_name":    device,
					"flag":           flag,
					"confidence":     conf,
					"evidence":       evidence,
					"action":         action,
					"status":         fbStatus,
					"correlation_id": corrID,
					"trace_id":       traceID,
				})
			}
		}
	}

	if queue == nil {
		queue = []gin.H{}
	}

	totalEvaluated := correctCount + incorrectCount
	var accuracyRate float64 = 100.0
	if totalEvaluated > 0 {
		accuracyRate = float64(correctCount) / float64(totalEvaluated) * 100.0
	}

	c.JSON(http.StatusOK, gin.H{
		"correct_count":   correctCount,
		"incorrect_count": incorrectCount,
		"pending_count":   pendingCount,
		"approved_count":  approvedCount,
		"rejected_count":  rejectedCount,
		"accuracy_rate":   accuracyRate,
		"rag_count":       ragCount,
		"queue":           queue,
	})
}

// GetSystemAudits returns compliance check logs.
func (h *Handler) SubmitFeedback(c *gin.Context) {
	var req struct {
		IncidentID      int     `json:"incident_id"`
		AiRca           string  `json:"ai_rca"`
		HumanRca        string  `json:"human_rca"`
		Score           float64 `json:"score"`
		Reviewer        string  `json:"reviewer"`
		RejectionReason string  `json:"rejection_reason"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "error": err.Error()})
		return
	}

	if req.Reviewer == "" {
		req.Reviewer = "NOC_OPERATOR"
	}
	if req.HumanRca == "" && req.RejectionReason != "" {
		req.HumanRca = req.RejectionReason
	}
	if req.HumanRca == "" {
		req.HumanRca = "Manual Verification"
	}

	corrID := fmt.Sprintf("corr_fb_%d_%d", req.IncidentID, time.Now().UnixNano())
	traceID := fmt.Sprintf("trace_fb_%d_%d", req.IncidentID, time.Now().Unix())

	// Determine status: If score >= 0.8 status is APPROVED, if score < 0.8 status is PENDING_APPROVAL for Four-Eyes review
	status := "APPROVED"
	if req.Score < 0.8 {
		status = "PENDING_APPROVAL"
	}

	if h.db != nil {
		tx := h.db.Begin()
		if tx.Error != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"status": "error", "error": tx.Error.Error()})
			return
		}

		err := tx.Exec(`
			INSERT INTO incident_feedback (incident_id, ai_root_cause, human_root_cause, score, reviewer, status, rejection_reason, correlation_id, trace_id, knowledge_version, policy_version, created_at)
			VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, NOW())
		`, req.IncidentID, req.AiRca, req.HumanRca, req.Score, req.Reviewer, status, req.RejectionReason, corrID, traceID).Error

		if err != nil {
			tx.Rollback()
			c.JSON(http.StatusInternalServerError, gin.H{"status": "error", "error": err.Error()})
			return
		}

		// Per-incident FP/FN tracking
		isCorrect := req.Score >= 0.8
		isFalsePositive := false
		isFalseNegative := false
		if !isCorrect {
			if req.AiRca == "UNKNOWN" || req.AiRca == "" || req.AiRca == "N/A" {
				isFalseNegative = true
			} else {
				isFalsePositive = true
			}
		}

		// Ensure benchmark table exists
		tx.Exec(`CREATE TABLE IF NOT EXISTS ai_engineer_benchmark (
			id SERIAL PRIMARY KEY, incident_id VARCHAR(50),
			ai_diagnosis TEXT, human_diagnosis TEXT, ai_rca TEXT, human_rca TEXT,
			ai_solution TEXT, human_solution TEXT, final_resolution TEXT,
			ai_diagnosis_correct BOOLEAN, ai_rca_correct BOOLEAN, ai_solution_correct BOOLEAN,
			false_positive BOOLEAN, false_negative BOOLEAN,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)`)

		err = tx.Exec(`
			INSERT INTO ai_engineer_benchmark (
				incident_id, ai_diagnosis, human_diagnosis, ai_rca, human_rca,
				ai_diagnosis_correct, ai_rca_correct, ai_solution_correct,
				false_positive, false_negative, created_at
			) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NOW())
		`, fmt.Sprintf("%d", req.IncidentID), req.AiRca, req.HumanRca, req.AiRca, req.HumanRca,
			isCorrect, isCorrect, isCorrect, isFalsePositive, isFalseNegative).Error

		if err != nil {
			tx.Rollback()
			c.JSON(http.StatusInternalServerError, gin.H{"status": "error", "error": "Failed to update benchmark: " + err.Error()})
			return
		}

		tx.Commit()

		// ── Publish to NATS rag.learn ONLY if APPROVED ──
		if status == "APPROVED" && h.natsConn != nil {
			var incData struct {
				Flag     string `gorm:"column:flag"`
				Evidence string `gorm:"column:evidence"`
			}
			h.db.Raw(`SELECT flag, evidence FROM incidents WHERE incident_id = ? LIMIT 1`, req.IncidentID).Scan(&incData)

			learningPayload := map[string]interface{}{
				"incident_id":          fmt.Sprintf("%d", req.IncidentID),
				"title":                incData.Flag,
				"symptoms":             incData.Evidence,
				"root_cause":           req.HumanRca,
				"ai_root_cause":        req.AiRca,
				"human_root_cause":     req.HumanRca,
				"successful_action":    req.HumanRca,
				"resolution":           req.HumanRca,
				"confidence":           req.Score,
				"verification_status": "SUCCESS",
				"human_confirmed":     true,
				"rollback_needed":     false,
				"reviewer":            req.Reviewer,
				"correlation_id":      corrID,
				"trace_id":            traceID,
				"rejection_reason":    req.RejectionReason,
			}
			if payloadBytes, jerr := json.Marshal(learningPayload); jerr == nil {
				_ = h.natsConn.Publish("rag.learn", payloadBytes)
			}
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"success":        true,
		"status":         status,
		"correlation_id": corrID,
		"trace_id":       traceID,
		"message":        fmt.Sprintf("Feedback submitted with status %s", status),
	})
}

// ApproveFeedback approves a pending feedback and publishes it to NATS JetStream RAG loop.
func (h *Handler) ApproveFeedback(c *gin.Context) {
	var req struct {
		IncidentID int    `json:"incident_id"`
		Reviewer   string `json:"reviewer"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "error": err.Error()})
		return
	}

	if req.Reviewer == "" {
		req.Reviewer = "SUPERVISOR"
	}

	if h.db != nil {
		h.db.Exec(`UPDATE incident_feedback SET status = 'APPROVED', reviewer = ? WHERE incident_id = ?`, req.Reviewer, req.IncidentID)

		if h.natsConn != nil {
			var incData struct {
				Flag     string `gorm:"column:flag"`
				Evidence string `gorm:"column:evidence"`
			}
			h.db.Raw(`SELECT flag, evidence FROM incidents WHERE incident_id = ? LIMIT 1`, req.IncidentID).Scan(&incData)

			learningPayload := map[string]interface{}{
				"incident_id":          fmt.Sprintf("%d", req.IncidentID),
				"title":                incData.Flag,
				"symptoms":             incData.Evidence,
				"verification_status": "APPROVED_HUMAN",
				"human_confirmed":     true,
				"reviewer":            req.Reviewer,
				"approved_at":          time.Now().Format(time.RFC3339),
			}
			if payloadBytes, jerr := json.Marshal(learningPayload); jerr == nil {
				_ = h.natsConn.Publish("rag.learn", payloadBytes)
			}
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"status":  "success",
		"message": fmt.Sprintf("Feedback for Incident ID %d approved successfully.", req.IncidentID),
	})
}

// RejectFeedback rejects a feedback item.
func (h *Handler) RejectFeedback(c *gin.Context) {
	var req struct {
		IncidentID      int    `json:"incident_id"`
		RejectionReason string `json:"rejection_reason"`
		Reviewer        string `json:"reviewer"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "error": err.Error()})
		return
	}

	if h.db != nil {
		h.db.Exec(`UPDATE incident_feedback SET status = 'REJECTED', rejection_reason = ?, reviewer = ? WHERE incident_id = ?`,
			req.RejectionReason, req.Reviewer, req.IncidentID)
	}

	c.JSON(http.StatusOK, gin.H{
		"status":  "success",
		"message": fmt.Sprintf("Feedback for Incident ID %d rejected successfully.", req.IncidentID),
	})
}

// ExportFeedbackHistory returns CSV or JSON audit export of feedback logs with SHA256 checksum.
func (h *Handler) ExportFeedbackHistory(c *gin.Context) {
	format := c.DefaultQuery("format", "csv")
	var feedbacks []map[string]interface{}

	if h.db != nil {
		h.db.Table("incident_feedback").Order("created_at DESC").Limit(500).Find(&feedbacks)
	}

	if format == "json" {
		data, err := json.MarshalIndent(feedbacks, "", "  ")
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
		hash := sha256.Sum256(data)
		checksum := hex.EncodeToString(hash[:])
		c.Header("X-Audit-Checksum-SHA256", checksum)
		c.Header("Content-Disposition", fmt.Sprintf("attachment; filename=training_feedback_%d.json", time.Now().Unix()))
		c.Data(http.StatusOK, "application/json", data)
		return
	}

	// CSV Export
	var buf bytes.Buffer
	writer := csv.NewWriter(&buf)
	_ = writer.Write([]string{"ID", "IncidentID", "Score", "Status", "Reviewer", "RejectionReason", "CorrelationID", "TraceID", "CreatedAt"})

	for _, f := range feedbacks {
		id := fmt.Sprintf("%v", f["id"])
		incID := fmt.Sprintf("%v", f["incident_id"])
		score := fmt.Sprintf("%v", f["score"])
		status := fmt.Sprintf("%v", f["status"])
		reviewer := fmt.Sprintf("%v", f["reviewer"])
		reason := fmt.Sprintf("%v", f["rejection_reason"])
		corrID := fmt.Sprintf("%v", f["correlation_id"])
		traceID := fmt.Sprintf("%v", f["trace_id"])
		createdAt := fmt.Sprintf("%v", f["created_at"])
		_ = writer.Write([]string{id, incID, score, status, reviewer, reason, corrID, traceID, createdAt})
	}
	writer.Flush()

	csvBytes := buf.Bytes()
	hash := sha256.Sum256(csvBytes)
	checksum := hex.EncodeToString(hash[:])
	c.Header("X-Audit-Checksum-SHA256", checksum)
	c.Header("Content-Disposition", fmt.Sprintf("attachment; filename=training_feedback_%d.csv", time.Now().Unix()))
	c.Data(http.StatusOK, "text/csv", csvBytes)
}

// UpdatePrinter updates a printer's name, model, IP, port, site_id, pc_name.
