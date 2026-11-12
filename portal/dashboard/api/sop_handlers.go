package api

import (
	"encoding/json"
	"fmt"
	"github.com/gin-gonic/gin"
	"go_incident_analysis/SERVER/go_core/database"
	"net"
	"net/http"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
)

func (h *Handler) GetSOPs(c *gin.Context) {
	var sops []database.GovernanceSOP
	if h.db == nil {
		c.JSON(http.StatusOK, gin.H{"sops": []database.GovernanceSOP{}, "count": 0})
		return
	}
	if err := h.db.Find(&sops).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// Dynamic AI SOP Generator: Query unhandled active anomalies from incidents table
	// If an active incident has no covering SOP in governance_sops, auto-insert a DRAFT SOP into PostgreSQL!
	type IncidentRow struct {
		Flag       string    `gorm:"column:flag"`
		DeviceName string    `gorm:"column:device_name"`
		Agent      string    `gorm:"column:agent"`
		Evidence   string    `gorm:"column:evidence"`
		Timestamp  time.Time `gorm:"column:timestamp"`
	}
	var activeIncidents []IncidentRow
	h.db.Raw(`
		SELECT flag, COALESCE(NULLIF(device_name, ''), 'SYSTEM') AS device_name, COALESCE(NULLIF(agent, ''), 'agent') AS agent, COALESCE(NULLIF(evidence, ''), NULLIF(description, ''), 'Anomali terdeteksi') AS evidence, timestamp
		FROM incidents
		WHERE status != 'RESOLVED'
		ORDER BY timestamp DESC LIMIT 20
	`).Scan(&activeIncidents)

	seenTriggers := make(map[string]bool)
	for _, s := range sops {
		if s.Trigger != "" {
			seenTriggers[s.Trigger] = true
		}
	}

	for _, inc := range activeIncidents {
		trig := inc.Flag
		if trig == "" {
			trig = "SYSTEM_ALERT"
		}
		if seenTriggers[trig] {
			continue
		}
		seenTriggers[trig] = true

		devName := inc.DeviceName
		if devName == "" {
			devName = inc.Agent
		}
		sopName := fmt.Sprintf("Auto-%s jika %s anomali", trig, devName)
		sopDesc := inc.Evidence
		if sopDesc == "" {
			sopDesc = fmt.Sprintf("Prosedur mitigasi AI untuk %s pada %s.", trig, devName)
		}

		newDraft := database.GovernanceSOP{
			Name:        sopName,
			Title:       sopName,
			Description: sopDesc,
			Desc:        sopDesc,
			Symptoms:    trig,
			Trigger:     trig,
			Remediation: trig,
			Status:      "DRAFT",
			Confidence:  0.85,
			Meta:        fmt.Sprintf("DRAFT · AI-Generated · Trigger: %s", strings.ToLower(trig)),
			CreatedAt:   inc.Timestamp,
		}
		if errIns := h.db.Create(&newDraft).Error; errIns == nil {
			sops = append(sops, newDraft)
		}
	}

	active := make([]database.GovernanceSOP, 0)
	drafts := make([]database.GovernanceSOP, 0)
	pendingReview := make([]database.GovernanceSOP, 0)

	for _, s := range sops {
		switch s.Status {
		case "ACTIVE":
			active = append(active, s)
		case "PENDING_REVIEW":
			pendingReview = append(pendingReview, s)
			drafts = append(drafts, s)
		case "DRAFT":
			drafts = append(drafts, s)
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"success":        true,
		"active":         active,
		"drafts":         drafts,
		"pending_review": pendingReview,
	})
}

// CreateSOP creates a new SOP in PostgreSQL and logs audit event.
func (h *Handler) CreateSOP(c *gin.Context) {
	var req struct {
		Name    string `json:"name"`
		Trigger string `json:"trigger"`
		Desc    string `json:"desc"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"success": false, "error": err.Error()})
		return
	}

	if strings.TrimSpace(req.Name) == "" || strings.TrimSpace(req.Trigger) == "" {
		c.JSON(http.StatusBadRequest, gin.H{"success": false, "error": "Nama SOP dan Trigger Event wajib diisi"})
		return
	}

	newSOP := database.GovernanceSOP{
		Name:        req.Name,
		Title:       req.Name,
		Description: req.Desc,
		Desc:        req.Desc,
		Symptoms:    req.Trigger,
		Trigger:     req.Trigger,
		Remediation: req.Trigger,
		Status:      "DRAFT",
		Confidence:  0.90,
		Meta:        fmt.Sprintf("DRAFT · Manual · Trigger: %s", req.Trigger),
		CreatedAt:   time.Now(),
	}

	if err := h.db.Create(&newSOP).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"success": false, "error": err.Error()})
		return
	}

	_ = h.db.Exec(`INSERT INTO ai_audit_trail (event_id, action_executed, llm_response, created_at) VALUES ('SOP_CREATED', ?, ?, NOW())`, req.Name, fmt.Sprintf("New SOP draft created: %s (Trigger: %s)", req.Name, req.Trigger))

	c.JSON(http.StatusOK, gin.H{"success": true, "message": "SOP created successfully", "sop": newSOP})
}

// PromoteSOP promotes a SOP to ACTIVE and logs audit event.
func (h *Handler) PromoteSOP(c *gin.Context) {
	var req struct {
		Name    string `json:"name"`
		Trigger string `json:"trigger"`
		Desc    string `json:"desc"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"success": false, "error": err.Error()})
		return
	}

	var sop database.GovernanceSOP
	if err := h.db.Where("name = ?", req.Name).First(&sop).Error; err != nil {
		// Auto-create and promote if it doesn't exist yet in DB
		trig := req.Trigger
		if trig == "" {
			trig = "HIGH_ALERT"
		}
		newSOP := database.GovernanceSOP{
			Name:        req.Name,
			Title:       req.Name,
			Description: req.Desc,
			Desc:        req.Desc,
			Symptoms:    trig,
			Trigger:     trig,
			Remediation: trig,
			Status:      "ACTIVE",
			Confidence:  1.0,
			Meta:        fmt.Sprintf("ACTIVE · Remediation: %s", trig),
			CreatedAt:   time.Now(),
		}
		h.db.Create(&newSOP)
	} else {
		sop.Status = "ACTIVE"
		sop.Meta = fmt.Sprintf("ACTIVE · Remediation: %s", sop.Trigger)
		h.db.Save(&sop)
	}

	_ = h.db.Exec(`INSERT INTO ai_audit_trail (event_id, action_executed, llm_response, created_at) VALUES ('SOP_PROMOTED', ?, ?, NOW())`, req.Name, fmt.Sprintf("SOP promoted to ACTIVE: %s", req.Name))

	c.JSON(http.StatusOK, gin.H{"success": true, "message": "SOP promoted successfully"})
}

// DeleteSOP deletes a SOP and records audit event.
func (h *Handler) DeleteSOP(c *gin.Context) {
	var req struct {
		Name string `json:"name"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"success": false, "error": err.Error()})
		return
	}

	h.db.Where("name = ?", req.Name).Delete(&database.GovernanceSOP{})
	_ = h.db.Exec(`INSERT INTO ai_audit_trail (event_id, action_executed, llm_response, created_at) VALUES ('SOP_DELETED', ?, ?, NOW())`, req.Name, fmt.Sprintf("SOP deleted: %s", req.Name))

	c.JSON(http.StatusOK, gin.H{"success": true, "message": "SOP deleted successfully"})
}

// ExecuteSOP triggers execution of an active SOP and dispatches NATS event.
func (h *Handler) ExecuteSOP(c *gin.Context) {
	var req struct {
		Name   string `json:"name"`
		Target string `json:"target"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"success": false, "error": err.Error()})
		return
	}

	var sop database.GovernanceSOP
	if err := h.db.Where("name ILIKE ? OR title ILIKE ?", req.Name, req.Name).First(&sop).Error; err != nil {
		sop = database.GovernanceSOP{
			Name:        req.Name,
			Title:       req.Name,
			Remediation: "AUTOMATED_MITIGATION",
			Status:      "ACTIVE",
		}
	}

	if h.natsConn != nil {
		payload, _ := json.Marshal(gin.H{
			"event_type":  "SOP_EXECUTION",
			"sop_id":      sop.SopID,
			"sop_name":    sop.Name,
			"target":      req.Target,
			"remediation": sop.Remediation,
			"timestamp":   time.Now().Format(time.RFC3339),
		})
		_ = h.natsConn.Publish("sop.execution.trigger", payload)
	}

	_ = h.db.Exec(`INSERT INTO ai_audit_trail (event_id, action_executed, llm_response, created_at) VALUES ('SOP_EXECUTED', ?, ?, NOW())`, req.Name, fmt.Sprintf("SOP executed: %s on target %s", sop.Name, req.Target))

	c.JSON(http.StatusOK, gin.H{"success": true, "message": fmt.Sprintf("SOP '%s' executed successfully", sop.Name)})
}

var (
	lastCPUTotal uint64
	lastCPUIdle  uint64
	cpuMutex     sync.Mutex
)

func readHostStats() (cpuPct, ramPct, diskPct float64) {
	// 1. RAM from /proc/meminfo
	if memBytes, err := os.ReadFile("/proc/meminfo"); err == nil {
		lines := strings.Split(string(memBytes), "\n")
		var total, avail float64
		for _, line := range lines {
			fields := strings.Fields(line)
			if len(fields) >= 2 {
				switch fields[0] {
				case "MemTotal:":
					total, _ = strconv.ParseFloat(fields[1], 64)
				case "MemAvailable:":
					avail, _ = strconv.ParseFloat(fields[1], 64)
				}
			}
		}
		if total > 0 {
			ramPct = ((total - avail) / total) * 100.0
		}
	}

	// 2. Disk from syscall.Statfs("/")
	var stat syscall.Statfs_t
	if err := syscall.Statfs("/", &stat); err == nil && stat.Blocks > 0 {
		free := stat.Bfree
		total := stat.Blocks
		diskPct = (float64(total-free) / float64(total)) * 100.0
	}

	// 3. CPU from /proc/stat
	if statBytes, err := os.ReadFile("/proc/stat"); err == nil {
		lines := strings.Split(string(statBytes), "\n")
		if len(lines) > 0 && strings.HasPrefix(lines[0], "cpu ") {
			fields := strings.Fields(lines[0])
			if len(fields) >= 5 {
				user, _ := strconv.ParseUint(fields[1], 10, 64)
				nice, _ := strconv.ParseUint(fields[2], 10, 64)
				sys, _ := strconv.ParseUint(fields[3], 10, 64)
				idle, _ := strconv.ParseUint(fields[4], 10, 64)
				var iowait, irq, softirq, steal uint64
				if len(fields) >= 6 {
					iowait, _ = strconv.ParseUint(fields[5], 10, 64)
				}
				if len(fields) >= 7 {
					irq, _ = strconv.ParseUint(fields[6], 10, 64)
				}
				if len(fields) >= 8 {
					softirq, _ = strconv.ParseUint(fields[7], 10, 64)
				}
				if len(fields) >= 9 {
					steal, _ = strconv.ParseUint(fields[8], 10, 64)
				}

				total := user + nice + sys + idle + iowait + irq + softirq + steal
				idleTotal := idle + iowait

				cpuMutex.Lock()
				if lastCPUTotal > 0 && total > lastCPUTotal {
					totalDiff := float64(total - lastCPUTotal)
					idleDiff := float64(idleTotal - lastCPUIdle)
					cpuPct = ((totalDiff - idleDiff) / totalDiff) * 100.0
				}
				lastCPUTotal = total
				lastCPUIdle = idleTotal
				cpuMutex.Unlock()
			}
		}
	}
	return cpuPct, ramPct, diskPct
}

func pingIPTarget(targetIP string) (online bool, latencyMs int, pktLoss float64) {
	if targetIP == "" || targetIP == "-" {
		return false, -1, 100.0
	}
	// Try ICMP ping command with 1 count and 1s timeout
	cmd := exec.Command("ping", "-c", "1", "-W", "1", targetIP)
	outBytes, err := cmd.CombinedOutput()
	out := string(outBytes)

	if err == nil || strings.Contains(out, "bytes from") || strings.Contains(out, "ttl=") {
		online = true
		pktLoss = 0.0
		if idx := strings.Index(out, "time="); idx != -1 {
			sub := out[idx+5:]
			if endIdx := strings.Index(sub, " "); endIdx != -1 {
				valStr := strings.TrimSuffix(sub[:endIdx], "ms")
				if f, errParse := strconv.ParseFloat(valStr, 64); errParse == nil {
					latencyMs = int(f)
				}
			}
		}
		if latencyMs <= 0 {
			latencyMs = 2
		}
		return true, latencyMs, 0.0
	}

	// TCP fallback check (Parallel goroutine scan across candidate ports)
	ports := []string{"10000", "80", "443", "22", "9100", "8080", "19999", "9999"}
	type tcpResult struct {
		online    bool
		latencyMs int
	}
	resChan := make(chan tcpResult, len(ports))
	var tcpWg sync.WaitGroup

	for _, p := range ports {
		tcpWg.Add(1)
		go func(port string) {
			defer tcpWg.Done()
			start := time.Now()
			conn, errDial := net.DialTimeout("tcp", net.JoinHostPort(targetIP, port), 400*time.Millisecond)
			if errDial == nil {
				conn.Close()
				lat := int(time.Since(start).Milliseconds())
				if lat <= 0 {
					lat = 3
				}
				select {
				case resChan <- tcpResult{online: true, latencyMs: lat}:
				default:
				}
			}
		}(p)
	}

	// Close channel when all goroutines finish
	go func() {
		tcpWg.Wait()
		close(resChan)
	}()

	// Wait for first successful connection or completion
	if firstRes, ok := <-resChan; ok && firstRes.online {
		return true, firstRes.latencyMs, 0.0
	}

	return false, -1, 100.0
}

// GetHostMetrics reads real host metrics from the server host & latest telemetry in DB.
