package main

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

// registerSprintORoutes wires all Sprint O Governance API endpoints.
// All endpoints are READ-ONLY per HITL policy.
func registerSprintORoutes(r *gin.Engine, db *gorm.DB) {
	gov := r.Group("/api/sprint_o")

	// ── O1: Engineer Benchmark ─────────────────────────────────────────────
	gov.GET("/benchmark", func(c *gin.Context) {
		type BenchmarkRow struct {
			Total       int64   `json:"total"`
			DiagCorrect int64   `json:"diag_correct"`
			RcaCorrect  int64   `json:"rca_correct"`
			SolCorrect  int64   `json:"sol_correct"`
			FpCount     int64   `json:"fp_count"`
			FnCount     int64   `json:"fn_count"`
		}
		var row BenchmarkRow
		db.Raw(`
			SELECT
				COUNT(*) as total,
				SUM(CASE WHEN ai_diagnosis_correct THEN 1 ELSE 0 END) as diag_correct,
				SUM(CASE WHEN ai_rca_correct THEN 1 ELSE 0 END) as rca_correct,
				SUM(CASE WHEN ai_solution_correct THEN 1 ELSE 0 END) as sol_correct,
				SUM(CASE WHEN false_positive THEN 1 ELSE 0 END) as fp_count,
				SUM(CASE WHEN false_negative THEN 1 ELSE 0 END) as fn_count
			FROM ai_engineer_benchmark
		`).Scan(&row)

		result := gin.H{
			"total_comparisons":        row.Total,
			"diagnosis_accuracy":        safeDivPct(row.DiagCorrect, row.Total),
			"rca_accuracy":              safeDivPct(row.RcaCorrect, row.Total),
			"recommendation_accuracy":   safeDivPct(row.SolCorrect, row.Total),
			"false_positive_rate":       safeDivPct(row.FpCount, row.Total),
			"false_negative_rate":       safeDivPct(row.FnCount, row.Total),
		}
		c.JSON(http.StatusOK, result)
	})

	gov.GET("/benchmark/history", func(c *gin.Context) {
		type Row struct {
			CreatedAt   time.Time `json:"created_at"`
			IncidentID  string    `json:"incident_id"`
			AiDiagnosis string    `json:"ai_diagnosis"`
			HumanDiagnosis string `json:"human_diagnosis"`
			AiRca       string    `json:"ai_rca"`
			HumanRca    string    `json:"human_rca"`
			DiagCorrect bool      `json:"ai_diagnosis_correct"`
			RcaCorrect  bool      `json:"ai_rca_correct"`
		}
		var rows []Row
		db.Raw("SELECT created_at, incident_id, ai_diagnosis, human_diagnosis, ai_rca, human_rca, ai_diagnosis_correct, ai_rca_correct FROM ai_engineer_benchmark ORDER BY created_at DESC LIMIT 50").Scan(&rows)
		c.JSON(http.StatusOK, rows)
	})

	// ── O2: Drift Detection ────────────────────────────────────────────────
	gov.GET("/drift", func(c *gin.Context) {
		type Row struct {
			MetricType          string    `json:"metric_type"`
			TargetName          string    `json:"target_name"`
			BaselineSuccessRate float64   `json:"baseline_success_rate"`
			CurrentSuccessRate  float64   `json:"current_success_rate"`
			DriftPercentage     float64   `json:"drift_percentage"`
			DetectedAt          time.Time `json:"detected_at"`
		}
		var rows []Row
		db.Raw("SELECT metric_type, target_name, baseline_success_rate, current_success_rate, drift_percentage, detected_at FROM ai_drift_metrics ORDER BY detected_at DESC LIMIT 50").Scan(&rows)
		c.JSON(http.StatusOK, rows)
	})

	// ── O3: Recommendation Benchmark ───────────────────────────────────────
	gov.GET("/recommendation_benchmark", func(c *gin.Context) {
		type Row struct {
			Recommendation string  `json:"recommendation"`
			TotalSelected  int64   `json:"total_selected"`
			TotalSuccess   int64   `json:"total_success"`
			TotalFailure   int64   `json:"total_failure"`
			SuccessRate    float64 `json:"success_rate"`
			AvgMttr        float64 `json:"avg_mttr"`
			AvgDowntime    float64 `json:"avg_downtime"`
		}
		var rows []Row
		db.Raw(`
			SELECT
				recommendation,
				COUNT(*) filter (WHERE was_selected) as total_selected,
				COUNT(*) filter (WHERE was_successful) as total_success,
				COUNT(*) filter (WHERE NOT was_successful) as total_failure,
				COALESCE(AVG(CASE WHEN was_selected THEN CASE WHEN was_successful THEN 1.0 ELSE 0.0 END END) * 100, 0) as success_rate,
				COALESCE(AVG(mttr_minutes), 0) as avg_mttr,
				COALESCE(AVG(downtime_minutes), 0) as avg_downtime
			FROM ai_recommendation_benchmark
			GROUP BY recommendation
			ORDER BY success_rate DESC
			LIMIT 30
		`).Scan(&rows)
		c.JSON(http.StatusOK, rows)
	})

	// ── O4: Gold Dataset ────────────────────────────────────────────────────
	gov.GET("/gold_dataset", func(c *gin.Context) {
		type Row struct {
			ID         uint      `json:"id"`
			FinalRca   string    `json:"final_rca"`
			Outcome    string    `json:"outcome"`
			CreatedAt  time.Time `json:"created_at"`
		}
		var rows []Row
		var total int64
		db.Table("ai_gold_dataset").Count(&total)
		db.Raw("SELECT id, final_rca, outcome, created_at FROM ai_gold_dataset ORDER BY created_at DESC LIMIT 20").Scan(&rows)
		c.JSON(http.StatusOK, gin.H{"total": total, "datasets": rows})
	})

	// ── O5: AI Governance Audit ─────────────────────────────────────────────
	gov.GET("/governance_audit", func(c *gin.Context) {
		type Row struct {
			ID             uint      `json:"id"`
			AssetType      string    `json:"asset_type"`
			AssetName      string    `json:"asset_name"`
			VersionTag     string    `json:"version_tag"`
			Author         string    `json:"author"`
			ApprovalStatus string    `json:"approval_status"`
			CreatedAt      time.Time `json:"created_at"`
		}
		var rows []Row
		db.Raw("SELECT id, asset_type, asset_name, version_tag, author, approval_status, created_at FROM ai_governance_audit ORDER BY created_at DESC LIMIT 50").Scan(&rows)
		c.JSON(http.StatusOK, rows)
	})

	// ── O6: Prompt Evaluation ───────────────────────────────────────────────
	gov.GET("/prompt_evaluation", func(c *gin.Context) {
		type Row struct {
			PromptVersion    string    `json:"prompt_version"`
			DiagAccuracy     float64   `json:"diag_accuracy"`
			RcaAccuracy      float64   `json:"rca_accuracy"`
			HallucinationRate float64  `json:"hallucination_rate"`
			EngineerAgreement float64  `json:"engineer_agreement"`
			LatencySec       float64   `json:"latency_sec"`
			Status           string    `json:"status"`
			EvaluatedAt      time.Time `json:"evaluated_at"`
		}
		var rows []Row
		db.Raw("SELECT prompt_version, diag_accuracy, rca_accuracy, hallucination_rate, engineer_agreement, latency_sec, status, evaluated_at FROM ai_prompt_evaluation ORDER BY evaluated_at DESC LIMIT 20").Scan(&rows)
		c.JSON(http.StatusOK, rows)
	})

	// ── O7: Evidence Quality ────────────────────────────────────────────────
	gov.GET("/evidence_quality", func(c *gin.Context) {
		type Row struct {
			IncidentID   string    `json:"incident_id"`
			MetricsScore float64   `json:"metrics_score"`
			LogsScore    float64   `json:"logs_score"`
			TopologyScore float64  `json:"topology_score"`
			OverallScore float64   `json:"overall_score"`
			EvaluatedAt  time.Time `json:"evaluated_at"`
		}
		var rows []Row
		var avgScore float64
		db.Raw("SELECT AVG(overall_score) FROM ai_evidence_quality").Scan(&avgScore)
		db.Raw("SELECT incident_id, metrics_score, logs_score, topology_score, overall_score, evaluated_at FROM ai_evidence_quality ORDER BY evaluated_at DESC LIMIT 30").Scan(&rows)
		c.JSON(http.StatusOK, gin.H{"avg_overall_score": avgScore, "records": rows})
	})

	// ── O8: RCA Validation ──────────────────────────────────────────────────
	gov.GET("/rca_validation", func(c *gin.Context) {
		type Row struct {
			IncidentID      string    `json:"incident_id"`
			AiPred          string    `json:"ai_pred"`
			HumanRca        string    `json:"human_rca"`
			LayerDifference int       `json:"layer_difference"`
			RootCauseMatch  bool      `json:"root_cause_match"`
			Reason          string    `json:"reason"`
			ValidatedAt     time.Time `json:"validated_at"`
		}
		var rows []Row
		var matchRate float64
		db.Raw("SELECT COALESCE(AVG(CASE WHEN root_cause_match THEN 100.0 ELSE 0.0 END), 0) FROM ai_rca_validation").Scan(&matchRate)
		db.Raw("SELECT incident_id, ai_pred, human_rca, layer_difference, root_cause_match, reason, validated_at FROM ai_rca_validation ORDER BY validated_at DESC LIMIT 30").Scan(&rows)
		c.JSON(http.StatusOK, gin.H{"match_rate": matchRate, "validations": rows})
	})

	// ── O9: Knowledge Coverage ──────────────────────────────────────────────
	gov.GET("/knowledge_coverage", func(c *gin.Context) {
		type Row struct {
			Domain             string    `json:"domain"`
			CoveragePercentage float64   `json:"coverage_percentage"`
			LastUpdated        time.Time `json:"last_updated"`
		}
		var rows []Row
		db.Raw("SELECT domain, coverage_percentage, last_updated FROM ai_knowledge_coverage ORDER BY coverage_percentage ASC").Scan(&rows)
		
		// Identify gaps (below 85%)
		gaps := []string{}
		for _, r := range rows {
			if r.CoveragePercentage < 85.0 {
				gaps = append(gaps, r.Domain)
			}
		}
		c.JSON(http.StatusOK, gin.H{"domains": rows, "knowledge_gaps": gaps})
	})

	// ── O10: AI Capability Score ────────────────────────────────────────────
	gov.GET("/capability_score", func(c *gin.Context) {
		type Row struct {
			MonitoringScore  float64   `json:"monitoring_score"`
			ReasoningScore   float64   `json:"reasoning_score"`
			KnowledgeScore   float64   `json:"knowledge_score"`
			ConversationScore float64  `json:"conversation_score"`
			PredictionScore  float64   `json:"prediction_score"`
			TrustScore       float64   `json:"trust_score"`
			EvidenceScore    float64   `json:"evidence_score"`
			GovernanceScore  float64   `json:"governance_score"`
			OverallScore     float64   `json:"overall_score"`
			RecordedAt       time.Time `json:"recorded_at"`
		}
		var row Row
		db.Raw("SELECT * FROM ai_capability_score ORDER BY recorded_at DESC LIMIT 1").Scan(&row)
		c.JSON(http.StatusOK, row)
	})

	// ── O11: Continuous Improvement ─────────────────────────────────────────
	gov.GET("/continuous_improvement", func(c *gin.Context) {
		type Row struct {
			KnowledgeGaps      int       `json:"knowledge_gaps"`
			PlaybookFailures   int       `json:"playbook_failures"`
			HallucinationRate  float64   `json:"hallucination_rate"`
			SuggestionPayload  string    `json:"suggestion_payload"`
			ReportDate         time.Time `json:"report_date"`
		}
		var rows []Row
		db.Raw("SELECT knowledge_gaps, playbook_failures, hallucination_rate, suggestion_payload::text, report_date FROM ai_continuous_improvement ORDER BY report_date DESC LIMIT 10").Scan(&rows)
		c.JSON(http.StatusOK, rows)
	})

	// ── Aggregate: AI Health Overview ───────────────────────────────────────
	gov.GET("/ai_health", func(c *gin.Context) {
		var avgConf, rcaAcc, recAcc float64
		var totalInc int64
		db.Raw("SELECT COALESCE(AVG(CASE WHEN confidence <= 1.0 THEN confidence * 100 ELSE confidence END), 0) FROM incidents").Scan(&avgConf)
		if avgConf > 100.0 {
			avgConf = 100.0
		}
		db.Raw("SELECT COALESCE(AVG(CASE WHEN ai_rca_correct THEN 100.0 ELSE 0.0 END), 0) FROM ai_engineer_benchmark").Scan(&rcaAcc)
		db.Raw("SELECT COALESCE(AVG(CASE WHEN ai_solution_correct THEN 100.0 ELSE 0.0 END), 0) FROM ai_engineer_benchmark").Scan(&recAcc)
		db.Table("incidents").Count(&totalInc)
		var halRate float64
		db.Raw("SELECT COALESCE(AVG(hallucination_rate), 0) FROM ai_prompt_evaluation").Scan(&halRate)
		var capScore float64
		db.Raw("SELECT COALESCE(overall_score, 0) FROM ai_capability_score ORDER BY recorded_at DESC LIMIT 1").Scan(&capScore)

		c.JSON(http.StatusOK, gin.H{
			"overall_health":          capScore,
			"reasoning_accuracy":      rcaAcc,
			"recommendation_accuracy": recAcc,
			"average_confidence":      avgConf,
			"hallucination_rate":      halRate,
			"total_incidents":         totalInc,
			"last_updated":            time.Now().Format(time.RFC3339),
		})
	})
}

func safeDivPct(numerator, denominator int64) float64 {
	if denominator == 0 {
		return 0.0
	}
	return float64(numerator) / float64(denominator) * 100.0
}
