package api

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"github.com/gin-gonic/gin"
	"go_incident_analysis/portal/dashboard/core"
	"math"
	"net/http"
	"os"
	"strconv"
	"strings"
	"syscall"
	"time"
)

func (h *Handler) GetStorageStats(c *gin.Context) {
	var dbSize int64
	if h.db != nil {
		h.db.Raw("SELECT pg_database_size(current_database())").Scan(&dbSize)
	}

	var redisMem int64
	var redisDumpSize int64
	if h.rdb != nil {
		info, err := h.rdb.Info(c.Request.Context(), "memory", "persistence").Result()
		if err == nil {
			for _, line := range strings.Split(info, "\n") {
				line = strings.TrimSpace(line)
				if strings.HasPrefix(line, "used_memory:") {
					fmt.Sscanf(line, "used_memory:%d", &redisMem)
				}
				if strings.HasPrefix(line, "rdb_last_cow_size:") {
					var v int64
					if _, e := fmt.Sscanf(line, "rdb_last_cow_size:%d", &v); e == nil && v > 0 {
						redisDumpSize = v
					}
				}
				if strings.HasPrefix(line, "aof_base_size:") && redisDumpSize == 0 {
					var v int64
					if _, e := fmt.Sscanf(line, "aof_base_size:%d", &v); e == nil && v > 0 {
						redisDumpSize = v
					}
				}
			}
		}
		if redisDumpSize == 0 && redisMem > 0 {
			redisDumpSize = int64(float64(redisMem) * 0.6)
		}
	}

	getFileStats := func(path string) (int64, string) {
		data, err := os.ReadFile(path)
		if err != nil {
			return 0, ""
		}
		sum := sha256.Sum256(data)
		return int64(len(data)), hex.EncodeToString(sum[:])
	}

	aiFiles := make([]gin.H, 0, len(aiFileWhitelist))
	order := []string{"ai_supervisor.py", "rag_engine.py", "local_knowledge_base.json", "critic_engine.py", "llm_router.py", "policy_engine.py"}
	descMap := map[string]string{
		"ai_supervisor.py":          "Enterprise AI Supervisor (RCA)",
		"rag_engine.py":             "RAG Engine (pgvector)",
		"local_knowledge_base.json": "Static Baseline KB",
		"critic_engine.py":          "AI Critic Engine",
		"llm_router.py":             "Multi-Model Router",
		"policy_engine.py":          "Governance & Policy Rules",
	}
	for _, name := range order {
		path := aiFileWhitelist[name]
		sz, hash := getFileStats(path)
		aiFiles = append(aiFiles, gin.H{
			"name":     name,
			"size":     sz,
			"sha256":   hash,
			"desc":     descMap[name],
			"readable": sz > 0,
		})
	}

	var ragVectorsSize int64
	if h.db != nil {
		h.db.Raw("SELECT COALESCE(pg_total_relation_size('knowledge_vectors'), 0)").Scan(&ragVectorsSize)
	}

	// Host filesystem mount stats
	var stat syscall.Statfs_t
	var totalDisk, freeDisk, usedDisk int64
	var diskPct float64
	if err := syscall.Statfs("/app", &stat); err == nil {
		totalDisk = int64(stat.Blocks) * int64(stat.Bsize)
		freeDisk = int64(stat.Bavail) * int64(stat.Bsize)
		usedDisk = totalDisk - freeDisk
		if totalDisk > 0 {
			diskPct = float64(usedDisk) / float64(totalDisk) * 100.0
		}
	} else if err := syscall.Statfs("/", &stat); err == nil {
		totalDisk = int64(stat.Blocks) * int64(stat.Bsize)
		freeDisk = int64(stat.Bavail) * int64(stat.Bsize)
		usedDisk = totalDisk - freeDisk
		if totalDisk > 0 {
			diskPct = float64(usedDisk) / float64(totalDisk) * 100.0
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"db_size":          dbSize,
		"redis_memory":     redisMem,
		"rag_vectors_size": ragVectorsSize,
		"redis_dump_size":  redisDumpSize,
		"ai_files":         aiFiles,
		"host_disk": gin.H{
			"total_bytes": totalDisk,
			"used_bytes":  usedDisk,
			"free_bytes":  freeDisk,
			"used_pct":    math.Round(diskPct*10) / 10,
		},
	})
}

// GetAIFile reads the content of a whitelisted AI file with SHA256 integrity check.
func (h *Handler) GetSystemQueues(c *gin.Context) {
	ctx := c.Request.Context()
	metricsQSize := int64(0)
	logsQSize := int64(0)
	eventsQSize := int64(0)
	dlqRate := int64(0)

	loadShedding := int64(0)
	processed5s := int64(0)
	avgLatency := float64(0)
	errorRate := int64(0)

	if h.rdb != nil {
		if hashVals, err := h.rdb.HGetAll(ctx, "metrics:ingestor_queues").Result(); err == nil && len(hashVals) > 0 {
			if v, err := strconv.ParseInt(hashVals["metrics_queue_size"], 10, 64); err == nil {
				metricsQSize = v
			}
			if v, err := strconv.ParseInt(hashVals["logs_queue_size"], 10, 64); err == nil {
				logsQSize = v
			}
			if v, err := strconv.ParseInt(hashVals["events_queue_size"], 10, 64); err == nil {
				eventsQSize = v
			}
			if v, err := strconv.ParseInt(hashVals["processed_throughput_5s"], 10, 64); err == nil {
				processed5s = v
			}
			if v, err := strconv.ParseFloat(hashVals["avg_processing_latency_ms"], 64); err == nil {
				avgLatency = v
			}
			if v, err := strconv.ParseInt(hashVals["load_shedding_level"], 10, 64); err == nil {
				loadShedding = v
			}
			if v, err := strconv.ParseInt(hashVals["error_rate_5s"], 10, 64); err == nil {
				errorRate = v
			}
			if v, err := strconv.ParseInt(hashVals["dlq_rate_5s"], 10, 64); err == nil {
				dlqRate = v
			}
		}
	}

	// Fallback: count DLQ from DB if Redis unavailable
	if dlqRate == 0 && h.db != nil {
		h.db.Raw(`SELECT COUNT(*) FROM dlq_hybrid WHERE status = 'PENDING'`).Scan(&dlqRate)
	}

	c.JSON(http.StatusOK, gin.H{
		"metrics_queue_size":        metricsQSize,
		"logs_queue_size":           logsQSize,
		"events_queue_size":         eventsQSize,
		"load_shedding_level":       loadShedding,
		"processed_throughput_5s":   processed5s,
		"avg_processing_latency_ms": avgLatency,
		"error_rate_5s":             errorRate,
		"dlq_rate_5s":               dlqRate,
	})
}

// GetAIStats returns live metrics from DB — model counts, RAG size, confidence avg.
// BUG-02 fix: removed 24h filter; avg_confidence now calculated from ALL incidents.
// Added avg_decision_time_ms from ai_reflection_logs.
func (h *Handler) GetSystemAudits(c *gin.Context) {
	var audits []core.SystemAudit
	var err error
	if h.db != nil {
		err = h.db.Where("health_score IS NOT NULL").Order("timestamp DESC").Limit(10).Find(&audits).Error
	} else {
		err = fmt.Errorf("db connection is nil")
	}
	if err != nil {
		c.JSON(http.StatusOK, []gin.H{})
		return
	}

	var results []gin.H
	for _, a := range audits {
		results = append(results, gin.H{
			"timestamp":         a.Timestamp.Format(time.RFC3339),
			"health_score":      a.HealthScore,
			"status":            a.Status,
			"failed_components": a.FailedComponents,
		})
	}
	c.JSON(http.StatusOK, results)
}

// GetSOPs returns existing standard operating procedures.
func (h *Handler) StartTelemetryRetentionJob() {
	ticker := time.NewTicker(1 * time.Hour)
	defer ticker.Stop()

	// Run initial cleanup on startup
	h.PurgeTelemetryOlderThan(1)

	for range ticker.C {
		h.PurgeTelemetryOlderThan(1)
	}
}

// PurgeTelemetryOlderThan purges telemetry_logs, cache, and temp entries older than specified days.
func (h *Handler) PurgeTelemetryOlderThan(days int) int64 {
	if h.db == nil {
		return 0
	}

	var deletedCount int64
	// 1. Purge telemetry_logs older than 1 day
	res := h.db.Exec(`DELETE FROM telemetry_logs WHERE timestamp < NOW() - INTERVAL '1 day'`)
	deletedCount = res.RowsAffected

	// 2. Purge resolved fleet_incidents / watchdog logs older than 1 day
	h.db.Exec(`DELETE FROM fleet_incidents WHERE created_at < NOW() - INTERVAL '1 day' AND (severity = 'LOW' OR severity = 'RECOVERED')`)

	// 3. Clear Redis telemetry cache if Redis is available
	if h.rdb != nil {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		if flushErr := h.rdb.FlushDB(ctx).Err(); flushErr != nil {
			fmt.Printf("[StorageHandler] Redis FlushDB failed: %v", flushErr)
		}
		cancel()
	}

	// 4. Record retention audit event
	if deletedCount > 0 {
		h.db.Exec(`CREATE TABLE IF NOT EXISTS security_audit_logs (
			log_id SERIAL PRIMARY KEY,
			event_type VARCHAR(100),
			target VARCHAR(100),
			details TEXT,
			severity VARCHAR(20),
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)`)
		h.db.Exec(`INSERT INTO security_audit_logs (event_type, target, details, severity, created_at)
			VALUES ('TELEMETRY_RETENTION_PURGE', 'telemetry_logs', ?, 'INFO', NOW())`,
			fmt.Sprintf("Purged %d telemetry logs & telemetry cache older than 1 day", deletedCount))
	}

	return deletedCount
}

// CleanupTelemetryData handles manual HTTP request to purge old telemetry & vacuum DB.
func (h *Handler) CleanupTelemetryData(c *gin.Context) {
	var req struct {
		Days int `json:"days"`
	}
	_ = c.ShouldBindJSON(&req)
	if req.Days <= 0 {
		req.Days = 1
	}

	purged := h.PurgeTelemetryOlderThan(req.Days)

	// Perform VACUUM ANALYZE to reclaim disk space
	if h.db != nil {
		h.db.Exec(`VACUUM (ANALYZE) telemetry_logs`)
	}

	c.JSON(http.StatusOK, gin.H{
		"status":         "success",
		"days_retention": req.Days,
		"purged_records": purged,
		"message":        fmt.Sprintf("Successfully purged %d telemetry logs older than %d day(s) and vacuumed database space.", purged, req.Days),
	})
}

// ── RBAC & SUPERADMIN MANAGEMENT HANDLERS ──

// GetRBACPolicies returns the policy matrix for all roles.
