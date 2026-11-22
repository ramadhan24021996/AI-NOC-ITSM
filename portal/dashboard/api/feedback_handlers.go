package api

import (
	"bytes"
	"crypto/sha256"
	"encoding/csv"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"

	"go_incident_analysis/portal/dashboard/core"
	"go_incident_analysis/portal/dashboard/knowledge"
	"go_incident_analysis/portal/dashboard/middleware"
	"go_incident_analysis/portal/dashboard/websocket"
)

var (
	feedbackSchemaMu  sync.Mutex
	feedbackSchemaDBs = map[*gorm.DB]bool{}
)

// EnsureFeedbackSchema guarantees that all feedback tracking, HITL state, and OTel columns exist on live DBs.
func EnsureFeedbackSchema(db *gorm.DB) {
	if db == nil {
		return
	}
	feedbackSchemaMu.Lock()
	if feedbackSchemaDBs[db] {
		feedbackSchemaMu.Unlock()
		return
	}
	feedbackSchemaMu.Unlock()

	stmts := []string{
		`ALTER TABLE incident_feedback ADD COLUMN IF NOT EXISTS correlation_id TEXT`,
		`ALTER TABLE incident_feedback ADD COLUMN IF NOT EXISTS trace_id TEXT`,
		`ALTER TABLE incident_feedback ADD COLUMN IF NOT EXISTS knowledge_version INTEGER DEFAULT 1`,
		`ALTER TABLE incident_feedback ADD COLUMN IF NOT EXISTS policy_version INTEGER DEFAULT 1`,
		`ALTER TABLE incident_feedback ADD COLUMN IF NOT EXISTS status TEXT`,
		`ALTER TABLE incident_feedback ADD COLUMN IF NOT EXISTS rejection_reason TEXT`,
		`ALTER TABLE incident_feedback ADD COLUMN IF NOT EXISTS feedback_state TEXT DEFAULT 'PENDING'`,
		`ALTER TABLE incident_feedback ADD COLUMN IF NOT EXISTS review_result TEXT`,
		`ALTER TABLE incident_feedback ADD COLUMN IF NOT EXISTS ai_rca TEXT`,
		`ALTER TABLE incident_feedback ADD COLUMN IF NOT EXISTS human_rca TEXT`,
		`CREATE INDEX IF NOT EXISTS idx_feedback_status ON incident_feedback(status)`,
		`CREATE INDEX IF NOT EXISTS idx_feedback_trace ON incident_feedback(trace_id) WHERE trace_id IS NOT NULL`,
		`UPDATE incident_feedback SET status = CASE
			WHEN UPPER(COALESCE(review_result, '')) = 'CORRECT' OR UPPER(COALESCE(feedback_state, '')) IN ('PROCESSED', 'APPROVED') THEN 'APPROVED'
			WHEN UPPER(COALESCE(review_result, '')) IN ('INCORRECT', 'REJECTED') OR UPPER(COALESCE(feedback_state, '')) = 'REJECTED' THEN 'REJECTED'
			ELSE 'PENDING_APPROVAL'
		END WHERE status IS NULL OR status = ''`,
	}
	for _, stmt := range stmts {
		if err := db.Exec(stmt).Error; err != nil {
			fmt.Printf("[WARN] EnsureFeedbackSchema stmt failed (%s): %v\n", stmt, err)
		}
	}

	feedbackSchemaMu.Lock()
	feedbackSchemaDBs[db] = true
	feedbackSchemaMu.Unlock()
}

func (h *Handler) GetFeedback(c *gin.Context) {
	feedbacks := make([]map[string]interface{}, 0)
	if h.db != nil {
		EnsureFeedbackSchema(h.db)
		h.db.Table("incident_feedback").Order("created_at DESC").Limit(50).Find(&feedbacks)
	}
	c.JSON(http.StatusOK, feedbacks)
}

// GetFeedbackStats returns rating aggregated stats.
func (h *Handler) GetFeedbackStats(c *gin.Context) {
	var correctCount, incorrectCount, ragCount, pendingCount, approvedCount, rejectedCount int64

	if h.db != nil {
		EnsureFeedbackSchema(h.db)
		h.db.Table("incident_feedback").Where("(score >= 0.8 OR status = 'APPROVED') AND COALESCE(status, '') != 'REJECTED'").Count(&correctCount)
		h.db.Table("incident_feedback").Where("(score < 0.8 AND COALESCE(status, '') != 'APPROVED') OR status = 'REJECTED'").Count(&incorrectCount)
		h.db.Table("incident_feedback").Where("status = 'PENDING_APPROVAL'").Count(&pendingCount)
		h.db.Table("incident_feedback").Where("status = 'APPROVED'").Count(&approvedCount)
		h.db.Table("incident_feedback").Where("status = 'REJECTED'").Count(&rejectedCount)
		h.db.Table("knowledge_vectors").Count(&ragCount)
	}

	var queue []gin.H
	if h.db != nil {
		statusFilter := strings.TrimSpace(c.Query("status"))
		searchFilter := strings.TrimSpace(strings.ToLower(c.Query("q")))
		likePattern := "%" + searchFilter + "%"
		rows, err := h.db.Raw(`
			SELECT i.incident_id, 
			       COALESCE(NULLIF(i.device_name, ''), 'SYSTEM') AS device_name, 
			       COALESCE(NULLIF(i.flag, ''), 'UNKNOWN') AS flag, 
			       COALESCE(CASE WHEN i.confidence > 1 THEN i.confidence / 100.0 ELSE i.confidence END, 0.0) AS confidence,
			       COALESCE(i.evidence, '') AS evidence,
			       COALESCE((SELECT COALESCE(final_decision, first_hypothesis) FROM ai_reflection_logs WHERE incident_id = i.incident_id ORDER BY id DESC LIMIT 1), 'Autonomous Analysis') AS action,
			       COALESCE(f.status, 'PENDING_REVIEW') AS feedback_status,
			       COALESCE(f.correlation_id, '') AS correlation_id,
			       COALESCE(f.trace_id, '') AS trace_id
			FROM incidents i
			LEFT JOIN (
				SELECT DISTINCT ON (incident_id) incident_id, status, correlation_id, trace_id
				FROM incident_feedback
				ORDER BY incident_id, feedback_id DESC
			) f ON i.incident_id = f.incident_id
			WHERE (? = '' OR COALESCE(f.status, 'PENDING_REVIEW') = ?)
			  AND (? = '' OR LOWER(CAST(i.incident_id AS TEXT)) LIKE ? OR LOWER(COALESCE(i.device_name, '')) LIKE ? OR LOWER(COALESCE(i.flag, '')) LIKE ? OR LOWER(COALESCE(i.evidence, '')) LIKE ?)
			ORDER BY i.timestamp DESC
			LIMIT 50
		`, statusFilter, statusFilter, searchFilter, likePattern, likePattern, likePattern, likePattern).Rows()

		if err != nil {
			fmt.Printf("[WARN] GetFeedbackStats query error: %v\n", err)
		} else {
			defer rows.Close()
			for rows.Next() {
				var id int
				var device, flag, evidence, action, fbStatus, corrID, traceID string
				var conf float64
				if scanErr := rows.Scan(&id, &device, &flag, &conf, &evidence, &action, &fbStatus, &corrID, &traceID); scanErr != nil {
					fmt.Printf("[WARN] GetFeedbackStats scan error: %v\n", scanErr)
					continue
				}
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
	var accuracyRate float64 = 0.0
	if totalEvaluated > 0 {
		accuracyRate = float64(correctCount) / float64(totalEvaluated) * 100.0
	}

	var kbCount int64
	if knowledge.GlobalEngine != nil {
		kbCount = int64(len(knowledge.GlobalEngine.GetItems()))
	}

	c.JSON(http.StatusOK, gin.H{
		"correct_count":   correctCount,
		"incorrect_count": incorrectCount,
		"pending_count":   pendingCount,
		"approved_count":  approvedCount,
		"rejected_count":  rejectedCount,
		"accuracy_rate":   accuracyRate,
		"rag_count":       ragCount,
		"kb_count":        kbCount,
		"total_knowledge": ragCount + kbCount,
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
	if req.IncidentID <= 0 {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "error": "Valid incident_id is required"})
		return
	}

	role := c.GetString("role")
	if h.db != nil && !middleware.CheckPermission(h.db, role, "access_config") {
		c.JSON(http.StatusForbidden, gin.H{"status": "error", "error": "Insufficient permissions to submit training feedback"})
		return
	}

	if actor := c.GetString("username"); actor != "" && (req.Reviewer == "" || req.Reviewer == "NOC_OPERATOR" || req.Reviewer == "Dashboard Operator") {
		req.Reviewer = actor
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
	reviewResult := "Correct"
	feedbackState := "APPROVED"
	if req.Score < 0.8 {
		status = "PENDING_APPROVAL"
		reviewResult = "Pending"
		feedbackState = "PENDING"
	}

	if h.db != nil {
		EnsureFeedbackSchema(h.db)
		var incExists int64
		h.db.Table("incidents").Where("incident_id = ?", req.IncidentID).Count(&incExists)
		if incExists == 0 {
			c.JSON(http.StatusNotFound, gin.H{"status": "error", "error": fmt.Sprintf("Incident ID %d not found", req.IncidentID)})
			return
		}

		tx := h.db.Begin()
		if tx.Error != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"status": "error", "error": tx.Error.Error()})
			return
		}

		res := tx.Exec(`
			UPDATE incident_feedback
			SET ai_root_cause = ?, human_root_cause = ?, score = ?, reviewer = ?, status = ?, review_result = ?, feedback_state = ?, rejection_reason = ?, correlation_id = ?, trace_id = ?,
			    knowledge_version = COALESCE(knowledge_version, 0) + 1
			WHERE incident_id = ?
		`, req.AiRca, req.HumanRca, req.Score, req.Reviewer, status, reviewResult, feedbackState, req.RejectionReason, corrID, traceID, req.IncidentID)
		err := res.Error
		if err == nil && res.RowsAffected == 0 {
			err = tx.Exec(`
				INSERT INTO incident_feedback (incident_id, ai_root_cause, human_root_cause, score, reviewer, status, review_result, feedback_state, rejection_reason, correlation_id, trace_id, knowledge_version, policy_version, created_at)
				VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, NOW())
			`, req.IncidentID, req.AiRca, req.HumanRca, req.Score, req.Reviewer, status, reviewResult, feedbackState, req.RejectionReason, corrID, traceID).Error
		}

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

		if err := tx.Commit().Error; err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"status": "error", "error": err.Error()})
			return
		}
		_ = core.WriteAuditLog(h.db, "FEEDBACK_SUBMITTED", req.Reviewer, fmt.Sprintf("incident:%d", req.IncidentID), gin.H{
			"incident_id":    req.IncidentID,
			"score":          req.Score,
			"status":         status,
			"correlation_id": corrID,
			"trace_id":       traceID,
		})

		// ── Publish to NATS rag.learn ONLY if APPROVED ──
		if status == "APPROVED" && h.natsConn != nil {
			var incData struct {
				Flag     string `gorm:"column:flag"`
				Evidence string `gorm:"column:evidence"`
			}
			h.db.Raw(`SELECT flag, evidence FROM incidents WHERE incident_id = ? LIMIT 1`, req.IncidentID).Scan(&incData)

			learningPayload := map[string]interface{}{
				"incident_id":         fmt.Sprintf("%d", req.IncidentID),
				"title":               incData.Flag,
				"symptoms":            incData.Evidence,
				"root_cause":          req.HumanRca,
				"ai_root_cause":       req.AiRca,
				"human_root_cause":    req.HumanRca,
				"successful_action":   req.HumanRca,
				"resolution":          req.HumanRca,
				"confidence":          req.Score,
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

	websocket.BroadcastWSEvent("feedback_updated", map[string]interface{}{
		"incident_id": req.IncidentID,
		"status":      status,
		"score":       req.Score,
		"reviewer":    req.Reviewer,
		"source":      "training_feedback",
	})
	websocket.BroadcastWSEvent("system_log", map[string]interface{}{
		"type":    "INFO",
		"src":     "RLOF-FEEDBACK",
		"message": fmt.Sprintf("Feedback Incident #%d (%s) -> %s (score=%.2f)", req.IncidentID, req.Reviewer, status, req.Score),
	})

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
	if req.IncidentID <= 0 {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "error": "Valid incident_id is required"})
		return
	}

	role := c.GetString("role")
	if h.db != nil && !middleware.CheckPermission(h.db, role, "access_config") {
		c.JSON(http.StatusForbidden, gin.H{"status": "error", "error": "Insufficient permissions to approve feedback"})
		return
	}

	if actor := c.GetString("username"); actor != "" && (req.Reviewer == "" || req.Reviewer == "SUPERVISOR" || req.Reviewer == "NOC_SUPERVISOR" || req.Reviewer == "Dashboard Supervisor") {
		req.Reviewer = actor
	}
	if req.Reviewer == "" {
		req.Reviewer = "SUPERVISOR"
	}

	if h.db == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"status": "error", "error": "Database unavailable"})
		return
	}

	EnsureFeedbackSchema(h.db)
	res := h.db.Exec(`UPDATE incident_feedback SET status = 'APPROVED', feedback_state = 'APPROVED', review_result = 'Approved', reviewer = ? WHERE incident_id = ?`, req.Reviewer, req.IncidentID)
	if res.Error != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"status": "error", "error": res.Error.Error()})
		return
	}
	if res.RowsAffected == 0 {
		c.JSON(http.StatusNotFound, gin.H{"status": "error", "error": fmt.Sprintf("No feedback record found for Incident ID %d", req.IncidentID)})
		return
	}

	_ = core.WriteAuditLog(h.db, "FEEDBACK_APPROVED", req.Reviewer, fmt.Sprintf("incident:%d", req.IncidentID), gin.H{
		"incident_id": req.IncidentID,
		"reviewer":    req.Reviewer,
	})

	if h.natsConn != nil {
		var incData struct {
			Flag     string `gorm:"column:flag"`
			Evidence string `gorm:"column:evidence"`
		}
		h.db.Raw(`SELECT COALESCE(flag, '') AS flag, COALESCE(evidence, '') AS evidence FROM incidents WHERE incident_id = ? LIMIT 1`, req.IncidentID).Scan(&incData)

		var fbData struct {
			AiRootCause    string `gorm:"column:ai_root_cause"`
			HumanRootCause string `gorm:"column:human_root_cause"`
			CorrelationID  string `gorm:"column:correlation_id"`
			TraceID        string `gorm:"column:trace_id"`
		}
		h.db.Raw(`SELECT COALESCE(ai_root_cause, '') AS ai_root_cause, COALESCE(human_root_cause, '') AS human_root_cause, COALESCE(correlation_id, '') AS correlation_id, COALESCE(trace_id, '') AS trace_id FROM incident_feedback WHERE incident_id = ? ORDER BY feedback_id DESC LIMIT 1`, req.IncidentID).Scan(&fbData)

		humanRCA := fbData.HumanRootCause
		if humanRCA == "" {
			humanRCA = incData.Flag
		}

		learningPayload := map[string]interface{}{
			"incident_id":         fmt.Sprintf("%d", req.IncidentID),
			"title":               incData.Flag,
			"symptoms":            incData.Evidence,
			"root_cause":          humanRCA,
			"ai_root_cause":       fbData.AiRootCause,
			"human_root_cause":    humanRCA,
			"successful_action":   humanRCA,
			"resolution":          humanRCA,
			"confidence":          1.0,
			"verification_status": "SUCCESS",
			"human_confirmed":     true,
			"rollback_needed":     false,
			"reviewer":            req.Reviewer,
			"approved_by":         req.Reviewer,
			"approved_at":         time.Now().Format(time.RFC3339),
			"correlation_id":      fbData.CorrelationID,
			"trace_id":            fbData.TraceID,
		}
		if payloadBytes, jerr := json.Marshal(learningPayload); jerr == nil {
			_ = h.natsConn.Publish("rag.learn", payloadBytes)
		}
	}

	websocket.BroadcastWSEvent("feedback_updated", map[string]interface{}{
		"incident_id": req.IncidentID,
		"status":      "APPROVED",
		"reviewer":    req.Reviewer,
		"source":      "hitl_four_eyes_approval",
	})
	websocket.BroadcastWSEvent("system_log", map[string]interface{}{
		"type":    "OK",
		"src":     "HITL-GATE",
		"message": fmt.Sprintf("Four-Eyes Approval granted by %s for Incident #%d -> Published to RAG loop", req.Reviewer, req.IncidentID),
	})

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
	if req.IncidentID <= 0 {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "error": "Valid incident_id is required"})
		return
	}

	role := c.GetString("role")
	if h.db != nil && !middleware.CheckPermission(h.db, role, "access_config") {
		c.JSON(http.StatusForbidden, gin.H{"status": "error", "error": "Insufficient permissions to reject feedback"})
		return
	}

	if actor := c.GetString("username"); actor != "" && (req.Reviewer == "" || req.Reviewer == "SUPERVISOR") {
		req.Reviewer = actor
	}
	if req.Reviewer == "" {
		req.Reviewer = "SUPERVISOR"
	}

	if h.db == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"status": "error", "error": "Database unavailable"})
		return
	}

	EnsureFeedbackSchema(h.db)
	res := h.db.Exec(`UPDATE incident_feedback SET status = 'REJECTED', feedback_state = 'REJECTED', review_result = 'Rejected', rejection_reason = ?, reviewer = ? WHERE incident_id = ?`,
		req.RejectionReason, req.Reviewer, req.IncidentID)
	if res.Error != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"status": "error", "error": res.Error.Error()})
		return
	}
	if res.RowsAffected == 0 {
		c.JSON(http.StatusNotFound, gin.H{"status": "error", "error": fmt.Sprintf("No feedback record found for Incident ID %d", req.IncidentID)})
		return
	}

	_ = core.WriteAuditLog(h.db, "FEEDBACK_REJECTED", req.Reviewer, fmt.Sprintf("incident:%d", req.IncidentID), gin.H{
		"incident_id":      req.IncidentID,
		"rejection_reason": req.RejectionReason,
		"reviewer":         req.Reviewer,
	})

	websocket.BroadcastWSEvent("feedback_updated", map[string]interface{}{
		"incident_id": req.IncidentID,
		"status":      "REJECTED",
		"reviewer":    req.Reviewer,
		"source":      "hitl_four_eyes_rejection",
	})
	websocket.BroadcastWSEvent("system_log", map[string]interface{}{
		"type":    "WARN",
		"src":     "HITL-GATE",
		"message": fmt.Sprintf("Feedback Incident #%d rejected by %s: %s", req.IncidentID, req.Reviewer, req.RejectionReason),
	})

	c.JSON(http.StatusOK, gin.H{
		"status":  "success",
		"message": fmt.Sprintf("Feedback for Incident ID %d rejected successfully.", req.IncidentID),
	})
}

func sanitizeCSVCell(val interface{}) string {
	if val == nil {
		return ""
	}
	s := fmt.Sprintf("%v", val)
	if s == "<nil>" {
		return ""
	}
	trimmed := strings.TrimLeft(s, " \t\r\n")
	if trimmed != "" && strings.ContainsRune("=+-@", rune(trimmed[0])) {
		return "'" + s
	}
	return s
}

// ExportFeedbackHistory returns CSV or JSON audit export of feedback logs with SHA256 checksum.
func (h *Handler) ExportFeedbackHistory(c *gin.Context) {
	role := c.GetString("role")
	if h.db != nil && !middleware.CheckPermission(h.db, role, "access_config") {
		c.JSON(http.StatusForbidden, gin.H{"status": "error", "error": "Insufficient permissions to export feedback history"})
		return
	}

	format := c.DefaultQuery("format", "csv")
	feedbacks := make([]map[string]interface{}, 0)

	if h.db != nil {
		EnsureFeedbackSchema(h.db)
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
		idVal := f["feedback_id"]
		if idVal == nil {
			idVal = f["id"]
		}
		_ = writer.Write([]string{
			sanitizeCSVCell(idVal),
			sanitizeCSVCell(f["incident_id"]),
			sanitizeCSVCell(f["score"]),
			sanitizeCSVCell(f["status"]),
			sanitizeCSVCell(f["reviewer"]),
			sanitizeCSVCell(f["rejection_reason"]),
			sanitizeCSVCell(f["correlation_id"]),
			sanitizeCSVCell(f["trace_id"]),
			sanitizeCSVCell(f["created_at"]),
		})
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
