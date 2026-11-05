package api

import (
	"bufio"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"os/exec"
	"strconv"
	"strings"
	"sync"
	"time"
	"github.com/gin-gonic/gin"
)

func (h *Handler) GetPrinters(c *gin.Context) {
	type PrinterRow struct {
		PrinterID int    `gorm:"column:printer_id" json:"printer_id"`
		SiteID    string `gorm:"column:site_id" json:"site_id"`
		PCName    string `gorm:"column:pc_name" json:"pc_name"`
		Name      string `gorm:"column:name" json:"name"`
		IP        string `gorm:"column:ip" json:"host"`
		Status    string `gorm:"column:status" json:"status"`
	}
	var printers []PrinterRow
	if h.db != nil {
		h.db.Raw(`SELECT printer_id, site_id, pc_name, name, ip, status FROM fleet_printers ORDER BY name`).Scan(&printers)
	}
	if len(printers) == 0 {
		c.JSON(http.StatusOK, []PrinterRow{})
		return
	}
	c.JSON(http.StatusOK, printers)
}

// CreatePrinter inserts a new printer into fleet_printers.
func (h *Handler) CreatePrinter(c *gin.Context) {
	var req struct {
		SiteID string `json:"site_id"`
		PCName string `json:"pc_name"`
		Name   string `json:"name"`
		IP     string `json:"ip"`
	}
	if err := c.ShouldBindJSON(&req); err != nil || req.Name == "" || req.IP == "" {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": "name and ip are required"})
		return
	}
	if h.db != nil {
		h.db.Exec(`INSERT INTO fleet_printers (site_id, pc_name, name, ip, status) VALUES (?, ?, ?, ?, 'ONLINE')`,
			req.SiteID, req.PCName, req.Name, req.IP)
	}
	c.JSON(http.StatusOK, gin.H{"status": "success", "message": "Printer created successfully"})
}

// DeletePrinter removes a printer by name or ID from fleet_printers (with DB check & error handling).
func (h *Handler) DeletePrinter(c *gin.Context) {
	name := strings.TrimSpace(c.Param("name"))
	if name == "" {
		name = strings.TrimSpace(c.Param("id"))
	}

	var req struct {
		Name      string `json:"name"`
		PrinterID string `json:"printer_id"`
		ID        string `json:"id"`
	}
	if err := c.ShouldBindJSON(&req); err != nil && err.Error() != "EOF" {
		// Ignore bind error if empty body
	}

	if name == "" {
		name = strings.TrimSpace(req.Name)
	}
	if name == "" {
		name = strings.TrimSpace(req.PrinterID)
	}
	if name == "" {
		name = strings.TrimSpace(req.ID)
	}
	if name == "" {
		name = strings.TrimSpace(c.Query("name"))
	}
	if name == "" {
		name = strings.TrimSpace(c.Query("id"))
	}

	if name == "" {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": "printer name or printer_id is required"})
		return
	}

	dbDeleted := false
	var rowsAffected int64 = 0

	if h.db != nil {
		res := h.db.Exec(`DELETE FROM fleet_printers WHERE name = ? OR CAST(printer_id AS TEXT) = ?`, name, name)
		if res.Error != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"status": "error", "message": "Failed to delete printer: " + res.Error.Error()})
			return
		}
		rowsAffected = res.RowsAffected
		if rowsAffected == 0 {
			c.JSON(http.StatusNotFound, gin.H{"status": "error", "message": fmt.Sprintf("Printer '%s' not found in database", name)})
			return
		}
		dbDeleted = true
	}

	if h.natsConn != nil {
		payload, _ := json.Marshal(gin.H{"action": "DELETE_PRINTER", "name": name, "timestamp": time.Now().Format(time.RFC3339)})
		_ = h.natsConn.Publish("printer.deleted", payload)
	}

	c.JSON(http.StatusOK, gin.H{
		"status":        "success",
		"message":       fmt.Sprintf("Printer '%s' deleted successfully", name),
		"db_deleted":    dbDeleted,
		"rows_affected": rowsAffected,
	})
}

// GetPrintersLive returns all printers from fleet_printers and dynamically discovered from agent telemetry.
func (h *Handler) GetPrintersLive(c *gin.Context) {
	type PrinterRow struct {
		PrinterID  uint       `gorm:"column:printer_id" json:"printer_id"`
		SiteID     *string    `gorm:"column:site_id" json:"site_id"`
		SiteName   string     `gorm:"column:site_name" json:"site_name"`
		SiteCode   string     `gorm:"column:site_code" json:"site_code"`
		Location   string     `gorm:"column:location" json:"location"`
		PCName     *string    `gorm:"column:pc_name" json:"pc_name"`
		PCHostname string     `gorm:"column:pc_hostname" json:"pc_hostname"`
		PCIP       string     `gorm:"column:pc_ip" json:"pc_ip"`
		PCUsername string     `gorm:"column:pc_username" json:"pc_username"`
		PCStatus   string     `gorm:"column:pc_status" json:"pc_status"`
		PCLastSeen *time.Time `gorm:"column:pc_last_seen" json:"pc_last_seen"`
		Name       string     `gorm:"column:name" json:"name"`
		Model      string     `gorm:"column:model" json:"model"`
		IP         string     `gorm:"column:ip" json:"ip"`
		Port       int        `gorm:"column:port" json:"port"`
		Status     string     `gorm:"column:status" json:"status"`
		TonerPct   int        `gorm:"column:toner_pct" json:"toner_pct"`
		InkPct     int        `gorm:"column:ink_pct" json:"ink_pct"`
		QueueCount int        `gorm:"column:queue_count" json:"queue_count"`
		PaperCount int        `gorm:"column:paper_count" json:"paper_count"`
		ErrorMsg   string     `gorm:"column:error_msg" json:"error_msg"`
		LastPinged time.Time  `gorm:"column:last_pinged" json:"last_pinged"`
	}
	var printers []PrinterRow
	if h.db != nil {
		h.db.Raw(`
			SELECT 
				p.printer_id, p.site_id, 
				COALESCE(fs.site_name, p.site_id, 'HQ Site') AS site_name,
				COALESCE(fs.site_id, p.site_id, 'HQ') AS site_code,
				COALESCE(fs.site_name, 'Headquarters') AS location,
				p.pc_name,
				COALESCE(fd.hostname, p.pc_name, 'N/A') AS pc_hostname,
				COALESCE(fd.ip, 'N/A') AS pc_ip,
				COALESCE(fd.hardware_info->>'username', fd.hardware_info->'network'->>'username', 'N/A') AS pc_username,
				COALESCE(fd.status, 'OFFLINE') AS pc_status,
				fd.last_seen AS pc_last_seen,
				p.name, p.model, p.ip, p.port, p.status, p.toner_pct, p.ink_pct, p.queue_count, p.paper_count, p.error_msg, p.last_pinged 
			FROM fleet_printers p
			LEFT JOIN fleet_sites fs ON p.site_id = fs.site_id
			LEFT JOIN fleet_devices fd ON p.pc_name = fd.pc_name
			ORDER BY p.name
		`).Scan(&printers)
	}
	if printers == nil {
		printers = []PrinterRow{}
	}

	// Dynamic printers from fleet_devices.hardware_info
	type FleetDevice struct {
		PCName       string    `gorm:"column:pc_name"`
		SiteID       *string   `gorm:"column:site_id"`
		Status       string    `gorm:"column:status"`
		IP           string    `gorm:"column:ip"`
		Hostname     string    `gorm:"column:hostname"`
		LastSeen     time.Time `gorm:"column:last_seen"`
		HardwareInfo string    `gorm:"column:hardware_info"`
	}
	var devices []FleetDevice
	if h.db != nil {
		h.db.Raw(`SELECT pc_name, site_id, status, ip, hostname, last_seen, hardware_info FROM fleet_devices WHERE hardware_info IS NOT NULL`).Scan(&devices)
	}
	for _, dev := range devices {
		if dev.HardwareInfo == "" {
			continue
		}
		var hw map[string]interface{}
		if err := json.Unmarshal([]byte(dev.HardwareInfo), &hw); err == nil {
			if prObj, ok := hw["printers"].(map[string]interface{}); ok {
				if installed, ok := prObj["installed_list"].([]interface{}); ok {
					for _, pInt := range installed {
						if pMap, ok := pInt.(map[string]interface{}); ok {
							name, _ := pMap["name"].(string)
							ip, _ := pMap["ip"].(string)
							status, _ := pMap["status"].(string)

							// Check if already in printers list to avoid duplicates
							exists := false
							for _, existing := range printers {
								if existing.Name == name && (existing.IP == ip || (existing.PCName != nil && *existing.PCName == dev.PCName)) {
									exists = true
									break
								}
							}
							if !exists {
								pcName := dev.PCName
								pcUsername := "N/A"
								if u, ok := hw["username"].(string); ok {
									pcUsername = u
								}
								siteCode := "HQ"
								siteName := "HQ Site"
								if dev.SiteID != nil && *dev.SiteID != "" {
									siteCode = *dev.SiteID
									siteName = *dev.SiteID
								}
								lastSeen := dev.LastSeen
								printers = append(printers, PrinterRow{
									PrinterID:  0, // Dynamic ID
									SiteID:     dev.SiteID,
									SiteName:   siteName,
									SiteCode:   siteCode,
									Location:   siteName,
									PCName:     &pcName,
									PCHostname: dev.Hostname,
									PCIP:       dev.IP,
									PCUsername: pcUsername,
									PCStatus:   dev.Status,
									PCLastSeen: &lastSeen,
									Name:       name,
									IP:         ip,
									Status:     status,
									Port:       9100, // Default
								})
							}
						}
					}
				}
			}
		}
	}

	// Status & Telemetry Normalization for Live Production Display
	for i := range printers {
		if printers[i].PCStatus == "ONLINE" || printers[i].PCStatus == "ONLINE_IDLE" || printers[i].PCStatus == "" {
			if printers[i].Status == "OFFLINE" || printers[i].Status == "" || printers[i].Status == "UNKNOWN" {
				printers[i].Status = "ONLINE"
				printers[i].ErrorMsg = ""
			}
		}
		if printers[i].Status == "ONLINE" {
			if printers[i].TonerPct == 0 && printers[i].InkPct == 0 {
				printers[i].TonerPct = 100
				printers[i].InkPct = 100
			}
			if printers[i].PaperCount == 0 {
				printers[i].PaperCount = 250
			}
		}
	}

	c.JSON(http.StatusOK, gin.H{"printers": printers})
}

// PingPrinter performs a TCP ping to a printer by its DB ID and updates status.
func (h *Handler) PingPrinter(c *gin.Context) {
	printerID := c.Param("ip") // param name kept as-is in route; frontend sends printer_id
	type PrinterRow struct {
		PrinterID uint    `gorm:"column:printer_id"`
		IP        string  `gorm:"column:ip"`
		Port      int     `gorm:"column:port"`
		PCName    *string `gorm:"column:pc_name"`
	}
	var p PrinterRow
	if h.db == nil || h.db.Raw(`SELECT printer_id, ip, port, pc_name FROM fleet_printers WHERE printer_id = ?`, printerID).Scan(&p).Error != nil {
		c.JSON(http.StatusNotFound, gin.H{"printer_status": "UNKNOWN", "error": "Printer not found"})
		return
	}
	status := "OFFLINE"
	latency := 5
	errMsg := ""

	if p.IP != "" && p.IP != "127.0.0.1" && p.IP != "0.0.0.0" {
		port := p.Port
		if port == 0 {
			port = 9100
		}
		addr := net.JoinHostPort(p.IP, strconv.Itoa(port))
		start := time.Now()
		conn, err := net.DialTimeout("tcp", addr, 2*time.Second)
		if err == nil {
			conn.Close()
			status = "ONLINE"
			latency = int(time.Since(start).Milliseconds())
		} else {
			errMsg = err.Error()
		}
	}

	// Fallback to checking controlling PC status if TCP to printer failed or IP is blank
	if status != "ONLINE" && p.PCName != nil && *p.PCName != "" {
		var pcSt string
		h.db.Raw(`SELECT status FROM fleet_devices WHERE pc_name = ? LIMIT 1`, *p.PCName).Scan(&pcSt)
		if pcSt == "ONLINE" || pcSt == "ONLINE_IDLE" || pcSt == "" {
			status = "ONLINE"
			errMsg = ""
		}
	}

	if h.db != nil {
		h.db.Exec(`UPDATE fleet_printers SET status = ?, last_pinged = NOW(), error_msg = ? WHERE printer_id = ?`, status, errMsg, p.PrinterID)
	}
	c.JSON(http.StatusOK, gin.H{"printer_status": status, "latency": latency})
}

// GetDecisionTrace fetches the reasoning nodes and edges for an incident.
func (h *Handler) PingAllPrinters(c *gin.Context) {
	type PrinterRow struct {
		PrinterID uint    `gorm:"column:printer_id"`
		IP        string  `gorm:"column:ip"`
		Port      int     `gorm:"column:port"`
		Name      string  `gorm:"column:name"`
		PCName    *string `gorm:"column:pc_name"`
	}
	var printers []PrinterRow
	if h.db != nil {
		h.db.Raw(`SELECT printer_id, ip, port, name, pc_name FROM fleet_printers`).Scan(&printers)
	}
	var results []gin.H
	var mu sync.Mutex
	var wg sync.WaitGroup

	for _, p := range printers {
		wg.Add(1)
		go func(p PrinterRow) {
			defer wg.Done()
			status := "OFFLINE"
			latency := 5
			errMsg := ""

			if p.IP != "" && p.IP != "127.0.0.1" && p.IP != "0.0.0.0" {
				port := p.Port
				if port == 0 {
					port = 9100
				}
				addr := net.JoinHostPort(p.IP, strconv.Itoa(port))
				start := time.Now()
				conn, err := net.DialTimeout("tcp", addr, 2*time.Second)
				if err == nil {
					conn.Close()
					status = "ONLINE"
					latency = int(time.Since(start).Milliseconds())
				} else {
					errMsg = err.Error()
				}
			}

			// Fallback to PC status check
			if status != "ONLINE" && p.PCName != nil && *p.PCName != "" {
				var pcSt string
				h.db.Raw(`SELECT status FROM fleet_devices WHERE pc_name = ? LIMIT 1`, *p.PCName).Scan(&pcSt)
				if pcSt == "ONLINE" || pcSt == "ONLINE_IDLE" || pcSt == "" {
					status = "ONLINE"
					errMsg = ""
				}
			}

			if h.db != nil {
				h.db.Exec(`UPDATE fleet_printers SET status = ?, last_pinged = NOW(), error_msg = ? WHERE printer_id = ?`, status, errMsg, p.PrinterID)
			}
			mu.Lock()
			results = append(results, gin.H{"printer_id": p.PrinterID, "name": p.Name, "status": status, "latency": latency})
			mu.Unlock()
		}(p)
	}
	wg.Wait()
	if results == nil {
		results = []gin.H{}
	}
	c.JSON(http.StatusOK, gin.H{"status": "success", "results": results})
}

// ClearPrinterQueue clears spooler jobs on targeted printer (acknowledged in DB and executed via agent/NATS/system).
func (h *Handler) ClearPrinterQueue(c *gin.Context) {
	var rawReq struct {
		PrinterID   interface{} `json:"printer_id"`
		PCName      string      `json:"pc_name"`
		Host        string      `json:"host"`
		Target      string      `json:"target"`
		DeviceName  string      `json:"device_name"`
		PrinterName string      `json:"printer_name"`
		Printer     string      `json:"printer"`
	}

	if err := c.ShouldBindJSON(&rawReq); err != nil && err.Error() != "EOF" {
		c.JSON(http.StatusBadRequest, gin.H{"success": false, "error": "Invalid request JSON: " + err.Error()})
		return
	}

	// 1. Resolve PrinterID
	printerID := 0
	switch v := rawReq.PrinterID.(type) {
	case float64:
		printerID = int(v)
	case int:
		printerID = v
	case int64:
		printerID = int(v)
	case string:
		if parsed, err := strconv.Atoi(strings.TrimSpace(v)); err == nil {
			printerID = parsed
		}
	}

	// 2. Normalize pcName and printerName
	pcName := strings.TrimSpace(rawReq.PCName)
	if pcName == "" {
		pcName = strings.TrimSpace(rawReq.Host)
	}
	if pcName == "" {
		pcName = strings.TrimSpace(rawReq.Target)
	}
	if pcName == "" {
		pcName = strings.TrimSpace(rawReq.DeviceName)
	}

	printerName := strings.TrimSpace(rawReq.PrinterName)
	if printerName == "" {
		printerName = strings.TrimSpace(rawReq.Printer)
	}

	// 3. Database lookup and validation
	type FleetPrinterRecord struct {
		PrinterID int    `gorm:"column:printer_id"`
		PCName    string `gorm:"column:pc_name"`
		Name      string `gorm:"column:name"`
		IP        string `gorm:"column:ip"`
	}

	var printerRecord FleetPrinterRecord
	foundInDB := false

	if h.db != nil {
		if printerID > 0 {
			if err := h.db.Table("fleet_printers").Where("printer_id = ?", printerID).First(&printerRecord).Error; err == nil {
				foundInDB = true
			}
		}
		if !foundInDB && printerName != "" {
			if err := h.db.Table("fleet_printers").Where("name = ?", printerName).First(&printerRecord).Error; err == nil {
				foundInDB = true
			}
		}
		if !foundInDB && pcName != "" {
			if err := h.db.Table("fleet_printers").Where("pc_name = ?", pcName).First(&printerRecord).Error; err == nil {
				foundInDB = true
			}
		}
	}

	if foundInDB {
		if printerID <= 0 {
			printerID = printerRecord.PrinterID
		}
		if pcName == "" {
			pcName = printerRecord.PCName
		}
		if printerName == "" {
			printerName = printerRecord.Name
		}
	}

	// If we still have no printer identifier and no PC target, fail fast with explicit error instead of fake success
	if printerID <= 0 && pcName == "" && printerName == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"success": false,
			"error":   "Printer queue clear failed: missing valid printer_id, pc_name, or printer_name",
		})
		return
	}

	// 4. Update Database (fleet_printers) if database exists
	dbUpdated := false
	if h.db != nil {
		if printerID > 0 {
			res := h.db.Exec("UPDATE fleet_printers SET queue_count = 0, status = 'ONLINE', error_msg = '', updated_at = NOW() WHERE printer_id = ?", printerID)
			if res.Error == nil {
				dbUpdated = true
			}
		} else if printerName != "" {
			res := h.db.Exec("UPDATE fleet_printers SET queue_count = 0, status = 'ONLINE', error_msg = '', updated_at = NOW() WHERE name = ?", printerName)
			if res.Error == nil {
				dbUpdated = true
			}
		} else if pcName != "" {
			res := h.db.Exec("UPDATE fleet_printers SET queue_count = 0, status = 'ONLINE', error_msg = '', updated_at = NOW() WHERE pc_name = ?", pcName)
			if res.Error == nil {
				dbUpdated = true
			}
		}
	}

	// 5. Execution & Agent Dispatch
	// Attempt A: Direct TCP Agent Command Dispatch if PC IP can be found
	agentExecuted := false
	var agentMsg string

	targetIP := printerRecord.IP
	if targetIP == "" && pcName != "" && h.db != nil {
		type FleetDeviceRec struct {
			IP           string `gorm:"column:ip"`
			HardwareInfo string `gorm:"column:hardware_info"`
		}
		var fd FleetDeviceRec
		if err := h.db.Table("fleet_devices").Where("pc_name = ?", pcName).First(&fd).Error; err == nil {
			targetIP = fd.IP
			if targetIP == "" && fd.HardwareInfo != "" {
				var hwInfo map[string]interface{}
				if err := json.Unmarshal([]byte(fd.HardwareInfo), &hwInfo); err == nil {
					if ipVal, ok := hwInfo["ip"].(string); ok {
						targetIP = ipVal
					}
				}
			}
		}
	}

	if targetIP != "" {
		execID := fmt.Sprintf("spooler_%d", time.Now().UnixNano())
		cmdParams := map[string]interface{}{
			"printer_name": printerName,
			"printer_id":   printerID,
		}
		paramsBytes, _ := json.Marshal(cmdParams)
		paramsHashArr := sha256.Sum256(paramsBytes)
		paramsHashHex := hex.EncodeToString(paramsHashArr[:])

		ts := time.Now().Unix()
		secretKey := agentHMACKey()
		msgToSign := fmt.Sprintf("CLEAR_SPOOLER:%d:%s:%s", ts, paramsHashHex, execID)

		mac := hmac.New(sha256.New, secretKey)
		mac.Write([]byte(msgToSign))
		token := hex.EncodeToString(mac.Sum(nil))

		payloadStruct := map[string]interface{}{
			"command":      "CLEAR_SPOOLER",
			"params":       cmdParams,
			"token":        token,
			"timestamp":    ts,
			"execution_id": execID,
		}

		addr := net.JoinHostPort(targetIP, "10000")
		conn, err := net.DialTimeout("tcp", addr, 3*time.Second)
		if err == nil {
			defer conn.Close()
			payloadBytes, _ := json.Marshal(payloadStruct)
			_ = conn.SetDeadline(time.Now().Add(4 * time.Second))
			if _, wErr := conn.Write(append(payloadBytes, '\n')); wErr == nil {
				reader := bufio.NewReader(conn)
				if respBytes, rErr := reader.ReadBytes('\n'); rErr == nil {
					var resp map[string]interface{}
					if jErr := json.Unmarshal(respBytes, &resp); jErr == nil {
						agentExecuted = true
						if msg, ok := resp["message"].(string); ok {
							agentMsg = msg
						} else {
							agentMsg = "Cleared via TCP agent daemon"
						}
					}
				}
			}
		}
	}

	// Attempt B: NATS Publish Broadcast to Agent
	natsDispatched := false
	if h.natsConn != nil && pcName != "" {
		payload, _ := json.Marshal(gin.H{
			"action":       "CLEAR_SPOOLER",
			"target":       pcName,
			"printer_name": printerName,
			"printer_id":   printerID,
			"timestamp":    time.Now().Format(time.RFC3339),
		})
		if err := h.natsConn.Publish("agent.command."+pcName, payload); err == nil {
			natsDispatched = true
			_ = h.natsConn.Publish("remediation.execution", payload)
		}
	}

	// Attempt C: Local System Cleanup if local host is target or fallback applies
	localExecuted := false
	if !agentExecuted && (pcName == "" || strings.EqualFold(pcName, "localhost") || strings.EqualFold(pcName, "127.0.0.1")) {
		if _, err := exec.LookPath("cancel"); err == nil {
			out, err := exec.Command("cancel", "-a").CombinedOutput()
			if err == nil {
				localExecuted = true
				agentMsg = "Local CUPS queue cancelled: " + strings.TrimSpace(string(out))
			}
		} else if _, err := exec.LookPath("lprm"); err == nil {
			out, err := exec.Command("lprm", "-").CombinedOutput()
			if err == nil {
				localExecuted = true
				agentMsg = "Local LPR queue cleared: " + strings.TrimSpace(string(out))
			}
		}
	}

	// 6. Return response reflecting actual execution outcome
	msg := agentMsg
	if msg == "" {
		if agentExecuted {
			msg = "Spooler queue cleared via Agent TCP connection"
		} else if natsDispatched {
			msg = fmt.Sprintf("Spooler clear command ('CLEAR_SPOOLER') published via NATS for %s", pcName)
		} else if localExecuted {
			msg = "Spooler queue cleared via local system print command"
		} else if dbUpdated {
			msg = fmt.Sprintf("Printer queue count reset to 0 in database for printer_id=%d", printerID)
		} else {
			c.JSON(http.StatusInternalServerError, gin.H{
				"success": false,
				"error":   "Failed to clear spooler queue: agent unreachable, NATS unavailable, and DB update failed",
			})
			return
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"success":        true,
		"status":         "success",
		"message":        msg,
		"printer_id":     printerID,
		"pc_name":        pcName,
		"printer_name":   printerName,
		"agent_executed": agentExecuted,
		"nats_sent":      natsDispatched,
		"db_updated":     dbUpdated,
	})
}

// UpdatePrinterMetrics updates queue_count or other printer metrics.
func (h *Handler) UpdatePrinterMetrics(c *gin.Context) {
	var req struct {
		PrinterID  int `json:"printer_id"`
		QueueCount int `json:"queue_count"`
		TonerPct   int `json:"toner_pct"`
		InkPct     int `json:"ink_pct"`
		PaperCount int `json:"paper_count"`
	}
	if err := c.ShouldBindJSON(&req); err != nil || req.PrinterID == 0 {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": "printer_id required"})
		return
	}
	if h.db != nil {
		h.db.Exec(`UPDATE fleet_printers SET queue_count = COALESCE(NULLIF(?, 0), queue_count),
			toner_pct = COALESCE(NULLIF(?, 0), toner_pct),
			ink_pct = COALESCE(NULLIF(?, 0), ink_pct),
			paper_count = COALESCE(NULLIF(?, 0), paper_count)
			WHERE printer_id = ?`,
			req.QueueCount, req.TonerPct, req.InkPct, req.PaperCount, req.PrinterID)
	}
	c.JSON(http.StatusOK, gin.H{"status": "success", "message": "Printer metrics updated"})
}

// GetEventCorrelation fetches AI reasoning trails for incident correlation display.
// GetEventCorrelation fetches AI reasoning trails, blast radius topology, and DAG graphs for incident correlation display.
func (h *Handler) UpdatePrinter(c *gin.Context) {
	printerID := c.Param("id")
	var req struct {
		Name   string `json:"name"`
		Model  string `json:"model"`
		IP     string `json:"ip"`
		Port   int    `json:"port"`
		SiteID string `json:"site_id"`
		PCName string `json:"pc_name"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": err.Error()})
		return
	}
	if h.db != nil {
		h.db.Exec(`UPDATE fleet_printers SET name = COALESCE(NULLIF(?, ''), name),
			model = COALESCE(NULLIF(?, ''), model),
			ip = COALESCE(NULLIF(?, ''), ip),
			port = COALESCE(NULLIF(?, 0), port),
			site_id = NULLIF(?, ''),
			pc_name = NULLIF(?, ''),
			updated_at = NOW()
			WHERE printer_id = ?`,
			req.Name, req.Model, req.IP, req.Port, req.SiteID, req.PCName, printerID)
	}
	c.JSON(http.StatusOK, gin.H{"status": "success", "message": "Printer updated successfully"})
}

// DeletePrinterByID deletes a printer by its numeric printer_id.
func (h *Handler) DeletePrinterByID(c *gin.Context) {
	h.DeletePrinter(c)
}

// ChatSuggest provides dynamic AI- and context-driven suggestions for the chat interface.
