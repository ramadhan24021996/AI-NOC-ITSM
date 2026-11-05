package api

import (
	"encoding/json"
	"fmt"
	"net/http"
	"time"
	"github.com/gin-gonic/gin"
)

func (h *Handler) GetRBACPolicies(c *gin.Context) {
	if h.db != nil {
		h.db.Exec(`CREATE TABLE IF NOT EXISTS rbac_policies (
			id SERIAL PRIMARY KEY,
			role_name VARCHAR(50) UNIQUE,
			permissions TEXT,
			updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)`)
	}

	type PolicyRow struct {
		RoleName    string                 `json:"role_name" gorm:"column:role_name"`
		Permissions map[string]interface{} `json:"permissions"`
		PermText    string                 `json:"-" gorm:"column:permissions"`
	}

	var rows []PolicyRow
	if h.db != nil {
		h.db.Raw(`SELECT role_name, permissions FROM rbac_policies ORDER BY id`).Scan(&rows)
	}

	if len(rows) == 0 {
		// Seed default RBAC matrix
		defaults := []struct {
			Role string
			Perm map[string]bool
		}{
			{"superadmin", map[string]bool{"all": true, "access_config": true, "remote_access": true, "access_governance": true, "restart_containers": true}},
			{"admin", map[string]bool{"all": true, "access_config": true, "remote_access": true, "access_governance": true, "restart_containers": true}},
			{"operator", map[string]bool{"all": false, "access_config": false, "remote_access": true, "access_governance": false, "restart_containers": true}},
			{"auditor", map[string]bool{"all": false, "access_config": false, "remote_access": false, "access_governance": true, "restart_containers": false}},
			{"viewer", map[string]bool{"all": false, "access_config": false, "remote_access": false, "access_governance": false, "restart_containers": false}},
		}
		for _, d := range defaults {
			permBytes, _ := json.Marshal(d.Perm)
			if h.db != nil {
				h.db.Exec(`INSERT INTO rbac_policies (role_name, permissions, updated_at) VALUES (?, ?, NOW()) ON CONFLICT (role_name) DO NOTHING`, d.Role, string(permBytes))
			}
			rows = append(rows, PolicyRow{RoleName: d.Role, Permissions: map[string]interface{}{
				"all": d.Perm["all"], "access_config": d.Perm["access_config"], "remote_access": d.Perm["remote_access"],
				"access_governance": d.Perm["access_governance"], "restart_containers": d.Perm["restart_containers"],
			}})
		}
	} else {
		for i := range rows {
			if rows[i].PermText != "" {
				var p map[string]interface{}
				_ = json.Unmarshal([]byte(rows[i].PermText), &p)
				rows[i].Permissions = p
			}
		}
	}

	c.JSON(http.StatusOK, rows)
}

// SaveRBACPolicies saves updated permissions matrix.
func (h *Handler) SaveRBACPolicies(c *gin.Context) {
	var req []struct {
		RoleName    string                 `json:"role_name"`
		Permissions map[string]interface{} `json:"permissions"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": err.Error()})
		return
	}

	if h.db != nil {
		for _, item := range req {
			permBytes, _ := json.Marshal(item.Permissions)
			h.db.Exec(`INSERT INTO rbac_policies (role_name, permissions, updated_at) VALUES (?, ?, NOW())
				ON CONFLICT (role_name) DO UPDATE SET permissions = EXCLUDED.permissions, updated_at = NOW()`,
				item.RoleName, string(permBytes))
		}
		h.db.Exec(`INSERT INTO security_audit_logs (event_type, target, details, severity, created_at)
			VALUES ('RBAC_POLICIES_UPDATED', 'superadmin', 'Updated RBAC policy matrix for roles', 'INFO', NOW())`)
	}

	c.JSON(http.StatusOK, gin.H{"status": "success", "message": "Kebijakan RBAC berhasil disimpan."})
}

// GetRBACUsers returns user list for Superadmin.
func (h *Handler) GetRBACUsers(c *gin.Context) {
	type UserRow struct {
		UserID            uint      `json:"user_id" gorm:"column:user_id"`
		Username          string    `json:"username" gorm:"column:username"`
		RoleName          string    `json:"role_name" gorm:"column:role_name"`
		DisplayName       string    `json:"display_name" gorm:"column:display_name"`
		Avatar            string    `json:"avatar" gorm:"column:avatar"`
		DashboardSettings string    `json:"dashboard_settings" gorm:"column:dashboard_settings"`
		CreatedAt         time.Time `json:"created_at" gorm:"column:created_at"`
	}
	var users []UserRow
	if h.db != nil {
		h.db.Exec(`CREATE TABLE IF NOT EXISTS users (
			user_id SERIAL PRIMARY KEY,
			username VARCHAR(50) UNIQUE NOT NULL,
			password_hash VARCHAR(255),
			role_name VARCHAR(50) DEFAULT 'viewer',
			display_name VARCHAR(100),
			avatar VARCHAR(255),
			dashboard_settings TEXT,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)`)
		h.db.Raw(`SELECT user_id, username, COALESCE(role_name, 'admin') as role_name, COALESCE(display_name, username) as display_name, COALESCE(avatar, '') as avatar, COALESCE(dashboard_settings, '{}') as dashboard_settings, created_at FROM users ORDER BY user_id`).Scan(&users)
	}

	if len(users) == 0 {
		users = []UserRow{
			{UserID: 1, Username: "superadmin", RoleName: "superadmin", DisplayName: "Super Administrator", DashboardSettings: `{"theme":"dark","visible_panels":["all"],"landing_panel":"overview"}`, CreatedAt: time.Now()},
			{UserID: 2, Username: "admin", RoleName: "admin", DisplayName: "System Administrator", DashboardSettings: `{"theme":"dark","visible_panels":["all"],"landing_panel":"incident"}`, CreatedAt: time.Now()},
			{UserID: 3, Username: "noc_operator", RoleName: "operator", DisplayName: "NOC Operator Level 2", DashboardSettings: `{"theme":"dark","visible_panels":["incident","pchealth","monitoring"],"landing_panel":"incident"}`, CreatedAt: time.Now()},
		}
	}

	c.JSON(http.StatusOK, users)
}

// SaveRBACUser creates or edits user details.
func (h *Handler) SaveRBACUser(c *gin.Context) {
	var req struct {
		Username          string `json:"username"`
		Password          string `json:"password"`
		RoleName          string `json:"role_name"`
		DisplayName       string `json:"display_name"`
		Avatar            string `json:"avatar"`
		DashboardSettings string `json:"dashboard_settings"`
		IsEdit            bool   `json:"is_edit"`
	}
	if err := c.ShouldBindJSON(&req); err != nil || req.Username == "" {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": "username required"})
		return
	}

	if h.db != nil {
		if req.IsEdit {
			h.db.Exec(`UPDATE users SET role_name = ?, display_name = ?, avatar = ?, dashboard_settings = ? WHERE username = ?`,
				req.RoleName, req.DisplayName, req.Avatar, req.DashboardSettings, req.Username)
		} else {
			h.db.Exec(`INSERT INTO users (username, password_hash, role_name, display_name, avatar, dashboard_settings, created_at)
				VALUES (?, ?, ?, ?, ?, ?, NOW()) ON CONFLICT (username) DO UPDATE SET role_name = EXCLUDED.role_name, display_name = EXCLUDED.display_name, dashboard_settings = EXCLUDED.dashboard_settings`,
				req.Username, req.Password, req.RoleName, req.DisplayName, req.Avatar, req.DashboardSettings)
		}
		h.db.Exec(`INSERT INTO security_audit_logs (event_type, target, details, severity, created_at)
			VALUES ('USER_SAVED', ?, ?, 'INFO', NOW())`, req.Username, fmt.Sprintf("Saved user %s with role %s", req.Username, req.RoleName))
	}

	c.JSON(http.StatusOK, gin.H{"status": "success", "success": true, "message": fmt.Sprintf("Pengguna %s berhasil disimpan.", req.Username)})
}

// DeleteRBACUser removes user account.
func (h *Handler) DeleteRBACUser(c *gin.Context) {
	username := c.Param("username")
	if username == "superadmin" || username == "admin" {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "success": false, "message": "Superadmin / Admin utama tidak dapat dihapus."})
		return
	}

	if h.db != nil {
		h.db.Exec(`DELETE FROM users WHERE username = ?`, username)
		h.db.Exec(`INSERT INTO security_audit_logs (event_type, target, details, severity, created_at)
			VALUES ('USER_DELETED', ?, 'Deleted user account', 'WARN', NOW())`, username)
	}

	c.JSON(http.StatusOK, gin.H{"status": "success", "success": true, "message": fmt.Sprintf("Pengguna %s berhasil dihapus.", username)})
}

// GetRoleTemplates returns layout templates per role.
func (h *Handler) GetRoleTemplates(c *gin.Context) {
	role := c.DefaultQuery("role", "admin")
	type TemplateRow struct {
		RoleName string `json:"role_name" gorm:"column:role_name"`
		Layout   string `json:"layout" gorm:"column:layout"`
	}

	if h.db != nil {
		h.db.Exec(`CREATE TABLE IF NOT EXISTS rbac_role_templates (
			id SERIAL PRIMARY KEY,
			role_name VARCHAR(50) UNIQUE,
			layout TEXT,
			updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)`)
	}

	var row TemplateRow
	if h.db != nil {
		h.db.Raw(`SELECT role_name, layout FROM rbac_role_templates WHERE role_name = ? LIMIT 1`, role).Scan(&row)
	}

	if row.Layout == "" {
		row = TemplateRow{
			RoleName: role,
			Layout:   `{"widgets":["kpi-total","kpi-online","kpi-offline","widget-topology","widget-incident-feed","widget-pchealth"]}`,
		}
	}

	c.JSON(http.StatusOK, gin.H{"status": "success", "role_name": role, "layout": row.Layout})
}

// SaveRoleTemplate saves role dashboard template.
func (h *Handler) SaveRoleTemplate(c *gin.Context) {
	var req struct {
		RoleName string `json:"role_name"`
		Layout   string `json:"layout"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": err.Error()})
		return
	}

	if h.db != nil {
		h.db.Exec(`INSERT INTO rbac_role_templates (role_name, layout, updated_at) VALUES (?, ?, NOW())
			ON CONFLICT (role_name) DO UPDATE SET layout = EXCLUDED.layout, updated_at = NOW()`,
			req.RoleName, req.Layout)
	}

	c.JSON(http.StatusOK, gin.H{"status": "success", "message": fmt.Sprintf("Template dashboard untuk role %s berhasil disimpan.", req.RoleName)})
}

// GetRBACOverrides returns custom user layout overrides.
func (h *Handler) GetRBACOverrides(c *gin.Context) {
	type OverrideRow struct {
		Username  string    `json:"username" gorm:"column:username"`
		RoleName  string    `json:"role_name" gorm:"column:role_name"`
		UpdatedAt time.Time `json:"updated_at" gorm:"column:created_at"`
	}
	var overrides []OverrideRow
	if h.db != nil {
		h.db.Raw(`SELECT username, COALESCE(role_name, 'admin') as role_name, created_at FROM users WHERE dashboard_settings IS NOT NULL AND dashboard_settings != '{}'`).Scan(&overrides)
	}

	c.JSON(http.StatusOK, overrides)
}

// DeleteRBACOverride resets user custom layout.
func (h *Handler) DeleteRBACOverride(c *gin.Context) {
	username := c.Param("username")
	if h.db != nil {
		h.db.Exec(`UPDATE users SET dashboard_settings = '{}' WHERE username = ?`, username)
	}

	c.JSON(http.StatusOK, gin.H{"status": "success", "message": fmt.Sprintf("Override layout pengguna %s berhasil direset.", username)})
}

// GetSessionPolicies returns session timeouts and security constraints per role.
func (h *Handler) GetSessionPolicies(c *gin.Context) {
	type SessionRow struct {
		RoleName       string `json:"role_name" gorm:"column:role_name"`
		TimeoutMinutes int    `json:"timeout_minutes" gorm:"column:timeout_minutes"`
		MaxConcurrent  int    `json:"max_concurrent" gorm:"column:max_concurrent"`
		IPRestriction  string `json:"ip_restriction" gorm:"column:ip_restriction"`
	}

	if h.db != nil {
		h.db.Exec(`CREATE TABLE IF NOT EXISTS rbac_session_policies (
			id SERIAL PRIMARY KEY,
			role_name VARCHAR(50) UNIQUE,
			timeout_minutes INT DEFAULT 60,
			max_concurrent INT DEFAULT 5,
			ip_restriction VARCHAR(100) DEFAULT '0.0.0.0/0',
			updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)`)
	}

	var rows []SessionRow
	if h.db != nil {
		h.db.Raw(`SELECT role_name, COALESCE(timeout_minutes, 60) as timeout_minutes, COALESCE(max_concurrent, 5) as max_concurrent, COALESCE(ip_restriction, '0.0.0.0/0') as ip_restriction FROM rbac_session_policies ORDER BY id`).Scan(&rows)
	}

	if len(rows) == 0 {
		rows = []SessionRow{
			{RoleName: "superadmin", TimeoutMinutes: 0, MaxConcurrent: 10, IPRestriction: "0.0.0.0/0"},
			{RoleName: "admin", TimeoutMinutes: 480, MaxConcurrent: 5, IPRestriction: "10.0.0.0/8"},
			{RoleName: "operator", TimeoutMinutes: 120, MaxConcurrent: 3, IPRestriction: "10.20.0.0/16"},
			{RoleName: "auditor", TimeoutMinutes: 60, MaxConcurrent: 2, IPRestriction: "0.0.0.0/0"},
			{RoleName: "viewer", TimeoutMinutes: 30, MaxConcurrent: 1, IPRestriction: "0.0.0.0/0"},
		}
	}

	c.JSON(http.StatusOK, rows)
}

// SaveSessionPolicy updates session timeout and IP restriction per role.
func (h *Handler) SaveSessionPolicy(c *gin.Context) {
	var req struct {
		RoleName       string `json:"role_name"`
		TimeoutMinutes int    `json:"timeout_minutes"`
		MaxConcurrent  int    `json:"max_concurrent"`
		IPRestriction  string `json:"ip_restriction"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": err.Error()})
		return
	}

	if h.db != nil {
		h.db.Exec(`INSERT INTO rbac_session_policies (role_name, timeout_minutes, max_concurrent, ip_restriction, updated_at)
			VALUES (?, ?, ?, ?, NOW())
			ON CONFLICT (role_name) DO UPDATE SET timeout_minutes = EXCLUDED.timeout_minutes, max_concurrent = EXCLUDED.max_concurrent, ip_restriction = EXCLUDED.ip_restriction, updated_at = NOW()`,
			req.RoleName, req.TimeoutMinutes, req.MaxConcurrent, req.IPRestriction)
	}

	c.JSON(http.StatusOK, gin.H{"status": "success", "message": fmt.Sprintf("Kebijakan sesi untuk role %s berhasil disimpan.", req.RoleName)})
}

// GetRBACAuditLogs returns security audit logs for Superadmin.
func (h *Handler) GetRBACAuditLogs(c *gin.Context) {
	type AuditRow struct {
		LogID     uint      `json:"log_id" gorm:"column:log_id"`
		EventType string    `json:"event_type" gorm:"column:event_type"`
		Target    string    `json:"target" gorm:"column:target"`
		Details   string    `json:"details" gorm:"column:details"`
		Severity  string    `json:"severity" gorm:"column:severity"`
		CreatedAt time.Time `json:"created_at" gorm:"column:created_at"`
	}
	var logs []AuditRow
	if h.db != nil {
		h.db.Exec(`CREATE TABLE IF NOT EXISTS security_audit_logs (
			log_id SERIAL PRIMARY KEY,
			event_type VARCHAR(100),
			target VARCHAR(100),
			details TEXT,
			severity VARCHAR(20),
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)`)
		h.db.Raw(`SELECT log_id, event_type, target, details, severity, created_at FROM security_audit_logs ORDER BY log_id DESC LIMIT 50`).Scan(&logs)
	}

	if len(logs) == 0 {
		logs = []AuditRow{
			{LogID: 1, EventType: "SYSTEM_STARTUP", Target: "superadmin", Details: "RBAC Subsystem initialized with Superadmin full access", Severity: "INFO", CreatedAt: time.Now()},
		}
	}

	c.JSON(http.StatusOK, logs)
}

// GetFleetSites returns all registered sites from fleet_sites table.
