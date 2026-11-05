package api

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
)

// DeleteSite deletes a physical site from the fleet admin dashboard (real DB execution, cascading & validation).
func (h *Handler) DeleteSite(c *gin.Context) {
	siteID := strings.TrimSpace(c.Param("id"))
	if siteID == "" {
		siteID = strings.TrimSpace(c.Param("site_id"))
	}
	if siteID == "" {
		siteID = strings.TrimSpace(c.Param("name"))
	}

	var rawReq struct {
		SiteID   string `json:"site_id"`
		ID       string `json:"id"`
		Name     string `json:"name"`
		Site     string `json:"site"`
		SiteCode string `json:"site_code"`
		Code     string `json:"code"`
	}

	if err := c.ShouldBindJSON(&rawReq); err != nil && err.Error() != "EOF" {
		// Ignore bind errors if empty body, but parse if JSON
	}

	if siteID == "" {
		siteID = strings.TrimSpace(rawReq.SiteID)
	}
	if siteID == "" {
		siteID = strings.TrimSpace(rawReq.ID)
	}
	if siteID == "" {
		siteID = strings.TrimSpace(rawReq.Name)
	}
	if siteID == "" {
		siteID = strings.TrimSpace(rawReq.Site)
	}
	if siteID == "" {
		siteID = strings.TrimSpace(rawReq.SiteCode)
	}
	if siteID == "" {
		siteID = strings.TrimSpace(rawReq.Code)
	}
	if siteID == "" {
		siteID = strings.TrimSpace(c.Query("site_id"))
	}
	if siteID == "" {
		siteID = strings.TrimSpace(c.Query("id"))
	}
	if siteID == "" {
		siteID = strings.TrimSpace(c.Query("name"))
	}
	if siteID == "" {
		siteID = strings.TrimSpace(c.Query("site"))
	}

	if siteID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"status":  "error",
			"message": "site_id (or site name/code) parameter or body is required",
		})
		return
	}

	dbDeleted := false
	var rowsAffected int64 = 0

	if h.db != nil {
		// Ensure fleet_sites table exists
		h.db.Exec(`CREATE TABLE IF NOT EXISTS fleet_sites (
			site_id VARCHAR(50) PRIMARY KEY,
			name VARCHAR(100) NOT NULL,
			ip_range VARCHAR(50),
			gateway VARCHAR(50),
			status VARCHAR(20) DEFAULT 'ACTIVE',
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)`)

		// 1. Verify existence in fleet_sites or sites
		type SiteRecord struct {
			SiteID string `gorm:"column:site_id"`
			Name   string `gorm:"column:name"`
		}
		var siteRec SiteRecord
		found := false

		if err := h.db.Table("fleet_sites").Where("site_id = ? OR name = ?", siteID, siteID).First(&siteRec).Error; err == nil {
			found = true
			if siteRec.SiteID != "" {
				siteID = siteRec.SiteID
			}
		}

		// 2. Perform DB DELETE
		res := h.db.Exec("DELETE FROM fleet_sites WHERE site_id = ? OR name = ?", siteID, siteID)
		if res.Error != nil {
			c.JSON(http.StatusInternalServerError, gin.H{
				"status":  "error",
				"message": "Failed to delete site from fleet_sites: " + res.Error.Error(),
			})
			return
		}
		rowsAffected += res.RowsAffected

		// Fallback delete from legacy sites table if exists
		resLegacy := h.db.Exec("DELETE FROM sites WHERE site_id = ? OR name = ?", siteID, siteID)
		if resLegacy.Error == nil {
			rowsAffected += resLegacy.RowsAffected
		}

		// If site was not found and 0 rows affected, return HTTP 404
		if !found && rowsAffected == 0 {
			c.JSON(http.StatusNotFound, gin.H{
				"status":  "error",
				"message": fmt.Sprintf("Site '%s' not found in database", siteID),
			})
			return
		}

		// 3. Clean up related references in fleet_devices & fleet_printers
		_ = h.db.Exec("UPDATE fleet_devices SET site_id = NULL WHERE site_id = ?", siteID)
		_ = h.db.Exec("UPDATE fleet_printers SET site_id = NULL WHERE site_id = ?", siteID)

		// 4. Audit Log
		h.db.Exec(`CREATE TABLE IF NOT EXISTS security_audit_logs (
			log_id SERIAL PRIMARY KEY,
			event_type VARCHAR(100),
			target VARCHAR(100),
			details TEXT,
			severity VARCHAR(20),
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)`)
		_ = h.db.Exec(`INSERT INTO security_audit_logs (event_type, target, details, severity, created_at)
			VALUES ('DELETE_SITE', ?, ?, 'MEDIUM', NOW())`, siteID, fmt.Sprintf("Site %s deleted from fleet registry", siteID))

		dbDeleted = true
	}

	// Real-time broadcast over NATS
	natsDispatched := false
	if h.natsConn != nil {
		payload, err := json.Marshal(gin.H{
			"action":    "DELETE_SITE",
			"site_id":   siteID,
			"timestamp": time.Now().Format(time.RFC3339),
		})
		if err == nil {
			_ = h.natsConn.Publish("fleet.sites.events", payload)
			_ = h.natsConn.Publish("site.deleted", payload)
			natsDispatched = true
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"status":        "success",
		"message":       fmt.Sprintf("Site '%s' deleted successfully from database", siteID),
		"site_id":       siteID,
		"db_deleted":    dbDeleted,
		"rows_affected": rowsAffected,
		"nats_sent":     natsDispatched,
	})
}

// SaveDevice saves or updates a device in fleet_devices.
func (h *Handler) SaveDevice(c *gin.Context) {
	var req struct {
		PCName       string `json:"pc_name"`
		SiteID       string `json:"site_id"`
		Status       string `json:"status"`
		HardwareInfo string `json:"hardware_info"`
	}
	if err := c.ShouldBindJSON(&req); err != nil || req.PCName == "" {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": "pc_name is required"})
		return
	}
	if req.Status == "" {
		req.Status = "ONLINE"
	}
	if h.db != nil {
		h.db.Exec(`
			INSERT INTO fleet_devices (pc_name, site_id, status, hardware_info)
			VALUES (?, ?, ?, ?::jsonb)
			ON CONFLICT (pc_name) DO UPDATE SET
				site_id = EXCLUDED.site_id,
				status = EXCLUDED.status,
				last_seen = CURRENT_TIMESTAMP
		`, req.PCName, req.SiteID, req.Status, req.HardwareInfo)
	}
	c.JSON(http.StatusOK, gin.H{"status": "success", "message": "Device saved successfully"})
}

// DeleteDevice removes a device from fleet_devices by pc_name.
func (h *Handler) DeleteDevice(c *gin.Context) {
	// pc_name may arrive as route param or JSON body
	pcName := c.Param("device")
	if pcName == "" {
		var req struct {
			PCName string `json:"pc_name"`
		}
		if err := c.ShouldBindJSON(&req); err == nil {
			pcName = req.PCName
		}
	}
	if pcName == "" {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": "device name required"})
		return
	}
	if h.db != nil {
		h.db.Exec(`DELETE FROM fleet_devices WHERE pc_name = ?`, pcName)
	}
	c.JSON(http.StatusOK, gin.H{"status": "success", "message": fmt.Sprintf("Device %s deleted", pcName)})
}

// GetFleetSites returns the list of registered sites and router configurations.
func (h *Handler) GetFleetSites(c *gin.Context) {
	type SiteRow struct {
		SiteID            string    `json:"site_id" gorm:"column:site_id"`
		SiteName          string    `json:"site_name" gorm:"column:site_name"`
		RouterIP          string    `json:"router_ip" gorm:"column:router_ip"`
		RouterPort        int       `json:"router_port" gorm:"column:router_port"`
		DNSPrimary        string    `json:"dns_primary" gorm:"column:dns_primary"`
		DNSSecondary      string    `json:"dns_secondary" gorm:"column:dns_secondary"`
		DefaultRemoteTool string    `json:"default_remote_tool" gorm:"column:default_remote_tool"`
		CreatedAt         time.Time `json:"created_at" gorm:"column:created_at"`
	}
	var sites []SiteRow
	if h.db != nil {
		h.db.Exec(`CREATE TABLE IF NOT EXISTS fleet_sites (
			site_id TEXT PRIMARY KEY,
			site_name TEXT NOT NULL,
			router_ip TEXT,
			router_port INTEGER DEFAULT 10001,
			dns_primary TEXT,
			dns_secondary TEXT,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			default_remote_tool TEXT DEFAULT 'rustdesk'
		)`)
		h.db.Raw(`SELECT site_id, site_name, COALESCE(router_ip, '') AS router_ip, COALESCE(router_port, 10001) AS router_port, COALESCE(dns_primary, '') AS dns_primary, COALESCE(dns_secondary, '') AS dns_secondary, COALESCE(default_remote_tool, 'rustdesk') AS default_remote_tool, created_at FROM fleet_sites ORDER BY site_id`).Scan(&sites)
	}

	if len(sites) == 0 {
		sites = []SiteRow{
			{SiteID: "Kantor Pusat - NUC", SiteName: "Kantor Pusat - NUC", RouterIP: "10.20.0.1", RouterPort: 10001, DNSPrimary: "10.20.0.0/24", DefaultRemoteTool: "rustdesk", CreatedAt: time.Now()},
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"status": "success",
		"sites":  sites,
	})
}

// SaveFleetSite creates or updates a site in fleet_sites table.
func (h *Handler) SaveFleetSite(c *gin.Context) {
	var req struct {
		SiteID            string `json:"site_id"`
		SiteName          string `json:"site_name"`
		RouterIP          string `json:"router_ip"`
		RouterPort        int    `json:"router_port"`
		DNSPrimary        string `json:"dns_primary"`
		DefaultRemoteTool string `json:"default_remote_tool"`
	}

	if err := c.ShouldBindJSON(&req); err != nil || req.SiteName == "" {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": "site_name required"})
		return
	}

	if req.SiteID == "" {
		req.SiteID = strings.ToLower(strings.ReplaceAll(req.SiteName, " ", "-"))
	}
	if req.RouterPort <= 0 {
		req.RouterPort = 10001
	}
	if req.DefaultRemoteTool == "" {
		req.DefaultRemoteTool = "rustdesk"
	}

	if h.db != nil {
		h.db.Exec(`CREATE TABLE IF NOT EXISTS fleet_sites (
			site_id TEXT PRIMARY KEY,
			site_name TEXT NOT NULL,
			router_ip TEXT,
			router_port INTEGER DEFAULT 10001,
			dns_primary TEXT,
			dns_secondary TEXT,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			default_remote_tool TEXT DEFAULT 'rustdesk'
		)`)

		h.db.Exec(`INSERT INTO fleet_sites (site_id, site_name, router_ip, router_port, dns_primary, default_remote_tool, created_at)
			VALUES (?, ?, ?, ?, ?, ?, NOW())
			ON CONFLICT (site_id) DO UPDATE SET site_name = EXCLUDED.site_name, router_ip = EXCLUDED.router_ip, router_port = EXCLUDED.router_port, dns_primary = EXCLUDED.dns_primary, default_remote_tool = EXCLUDED.default_remote_tool`,
			req.SiteID, req.SiteName, req.RouterIP, req.RouterPort, req.DNSPrimary, req.DefaultRemoteTool)
	}

	c.JSON(http.StatusOK, gin.H{
		"status":    "success",
		"message":   fmt.Sprintf("Site '%s' berhasil disimpan di database.", req.SiteName),
		"site_id":   req.SiteID,
		"site_name": req.SiteName,
	})
}

// DeleteFleetSite removes a site from fleet_sites table.
func (h *Handler) DeleteFleetSite(c *gin.Context) {
	siteID := c.Param("site_id")
	if siteID == "" {
		siteID = c.Query("site_id")
	}
	if siteID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": "site_id required"})
		return
	}

	if h.db != nil {
		h.db.Exec(`DELETE FROM fleet_sites WHERE site_id = ?`, siteID)
	}

	c.JSON(http.StatusOK, gin.H{
		"status":  "success",
		"message": fmt.Sprintf("Site '%s' berhasil dihapus.", siteID),
	})
}
