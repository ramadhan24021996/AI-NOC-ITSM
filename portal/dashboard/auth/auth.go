package auth

import (
	"encoding/json"
	"fmt"
	"golang.org/x/crypto/bcrypt"
	"net/http"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/go-redis/redis/v8"
	"gorm.io/gorm"
	"github.com/golang-jwt/jwt/v5"
	"go_incident_analysis/portal/dashboard/ldap"
	"go_incident_analysis/portal/dashboard/websocket"
)

type Handler struct {
	db  *gorm.DB
	rdb *redis.Client
}

func NewHandler(db *gorm.DB, rdb *redis.Client) *Handler {
	SeedDefaultDashboardTemplates(db)
	return &Handler{db: db, rdb: rdb}
}

func (h *Handler) RegisterRoutes(r *gin.Engine) {
	r.POST("/api/auth/login", h.Login)
	r.POST("/api/auth/logout", h.Logout)
	r.GET("/api/auth/verify", h.Verify)
	r.GET("/api/rbac/policies", h.GetPolicies)
	r.POST("/api/rbac/policies", h.SavePolicies)
	r.GET("/api/rbac/users", h.GetUsers)
	r.POST("/api/rbac/users", h.SaveUser)
	r.DELETE("/api/rbac/users/:username", h.DeleteUser)
	r.GET("/api/auth/dashboard_settings", h.GetDashboardSettings)
	
	// Profile settings routes
	r.POST("/api/auth/profile", h.UpdateProfile)
	
	// Dashboard Layout routes
	r.GET("/api/dashboard/layout", h.GetDashboardLayout)
	r.POST("/api/dashboard/layout/save", h.SaveDashboardLayout)
	r.POST("/api/dashboard/layout/reset", h.ResetDashboardLayout)
	r.GET("/api/dashboard/layout/overrides", h.GetDashboardLayoutOverrides)
	
	// Session Policies routes
	r.GET("/api/rbac/session_policies", h.GetSessionPolicies)
	r.POST("/api/rbac/session_policies", h.SaveSessionPolicy)
	
	// Audit Logs routes
	r.GET("/api/rbac/audit_logs", h.GetAuditLogs)
	r.POST("/api/rbac/audit_logs", h.WriteAuditLog)
}

type RBACUser struct {
	UserID            int    `gorm:"column:user_id;primaryKey;autoIncrement" json:"user_id"`
	Username          string `gorm:"column:username;uniqueIndex;not null" json:"username"`
	Password          string `gorm:"column:password;not null" json:"password"`
	RoleName          string `gorm:"column:role_name;not null" json:"role_name"`
	DisplayName       string `gorm:"column:display_name" json:"display_name"`
	Avatar            string `gorm:"column:avatar" json:"avatar"`
	APIToken          string `gorm:"column:api_token" json:"api_token"`
	DashboardSettings string `gorm:"column:dashboard_settings;not null;default:'{}'" json:"dashboard_settings"`
}

type SessionPolicy struct {
	RoleName              string `gorm:"column:role_name;primaryKey" json:"role_name"`
	SessionTimeoutMinutes int    `gorm:"column:session_timeout_minutes" json:"session_timeout_minutes"`
	MaxConcurrentSessions int    `gorm:"column:max_concurrent_sessions" json:"max_concurrent_sessions"`
	EnforceMFA            bool   `gorm:"column:enforce_mfa" json:"enforce_mfa"`
}

type AuditLogEntry struct {
	LogID     int       `gorm:"column:log_id;primaryKey;autoIncrement" json:"log_id"`
	Username  string    `gorm:"column:username" json:"username"`
	Action    string    `gorm:"column:action" json:"action"`
	Target    string    `gorm:"column:target" json:"target"`
	Details   string    `gorm:"column:details" json:"details"`
	IPAddress string    `gorm:"column:ip_address" json:"ip_address"`
	CreatedAt time.Time `gorm:"column:created_at" json:"created_at"`
}

func (h *Handler) LogAudit(username, action, target, details, ipAddress string) {
	logEntry := map[string]interface{}{
		"username":   username,
		"action":     action,
		"target":     target,
		"details":    details,
		"ip_address": ipAddress,
	}
	h.db.Table("rbac_audit_logs").Create(&logEntry)
}

func validatePassword(password string) bool {
	if len(password) < 8 {
		return false
	}
	var hasUpper, hasLower, hasDigit, hasSymbol bool
	for _, char := range password {
		switch {
		case 'A' <= char && char <= 'Z':
			hasUpper = true
		case 'a' <= char && char <= 'z':
			hasLower = true
		case '0' <= char && char <= '9':
			hasDigit = true
		default:
			hasSymbol = true
		}
	}
	return hasUpper && hasLower && hasDigit && hasSymbol
}

func SeedDefaultDashboardTemplates(db *gorm.DB) {
	roles := []string{"superadmin", "admin", "noc_engineering", "operator", "viewer"}
	superadminLayout := `[
		{"id": "widget-online", "col_span": 1, "visible": true, "favorite": false},
		{"id": "widget-incidents", "col_span": 1, "visible": true, "favorite": false},
		{"id": "widget-health", "col_span": 1, "visible": true, "favorite": false},
		{"id": "widget-total", "col_span": 1, "visible": true, "favorite": false},
		{"id": "widget-mttr", "col_span": 1, "visible": true, "favorite": false},
		{"id": "widget-avail", "col_span": 1, "visible": true, "favorite": false},
		{"id": "widget-aiconf", "col_span": 1, "visible": true, "favorite": false},
		{"id": "widget-ticket", "col_span": 1, "visible": true, "favorite": false},
		{"id": "widget-live-incidents", "col_span": 2, "visible": true, "favorite": false},
		{"id": "widget-pipeline", "col_span": 2, "visible": true, "favorite": false},
		{"id": "widget-trend", "col_span": 2, "visible": true, "favorite": false},
		{"id": "widget-osi", "col_span": 2, "visible": true, "favorite": false},
		{"id": "widget-critical-alert", "col_span": 1, "visible": true, "favorite": false},
		{"id": "widget-active-sessions", "col_span": 1, "visible": true, "favorite": false},
		{"id": "widget-storage-usage", "col_span": 1, "visible": true, "favorite": false},
		{"id": "widget-cpu-usage", "col_span": 1, "visible": true, "favorite": false},
		{"id": "widget-ram-usage", "col_span": 1, "visible": true, "favorite": false},
		{"id": "widget-database-health", "col_span": 1, "visible": true, "favorite": false},
		{"id": "widget-redis-health", "col_span": 1, "visible": true, "favorite": false},
		{"id": "widget-queue-health", "col_span": 1, "visible": true, "favorite": false},
		{"id": "widget-audit-activity", "col_span": 2, "visible": true, "favorite": false},
		{"id": "widget-login-activity", "col_span": 2, "visible": true, "favorite": false},
		{"id": "widget-security-event", "col_span": 2, "visible": true, "favorite": false},
		{"id": "widget-prediction", "col_span": 2, "visible": true, "favorite": false},
		{"id": "widget-executive-analytics", "col_span": 2, "visible": true, "favorite": false}
	]`
	otherLayout := `[
		{"id": "widget-online", "col_span": 1, "visible": true, "favorite": false},
		{"id": "widget-incidents", "col_span": 1, "visible": true, "favorite": false},
		{"id": "widget-health", "col_span": 1, "visible": true, "favorite": false},
		{"id": "widget-total", "col_span": 1, "visible": true, "favorite": false},
		{"id": "widget-mttr", "col_span": 1, "visible": true, "favorite": false},
		{"id": "widget-avail", "col_span": 1, "visible": true, "favorite": false},
		{"id": "widget-aiconf", "col_span": 1, "visible": true, "favorite": false},
		{"id": "widget-ticket", "col_span": 1, "visible": true, "favorite": false},
		{"id": "widget-live-incidents", "col_span": 2, "visible": true, "favorite": false},
		{"id": "widget-pipeline", "col_span": 2, "visible": true, "favorite": false},
		{"id": "widget-trend", "col_span": 2, "visible": true, "favorite": false},
		{"id": "widget-osi", "col_span": 2, "visible": true, "favorite": false}
	]`
	for _, r := range roles {
		layout := otherLayout
		if r == "superadmin" {
			layout = superadminLayout
		}
		db.Table("rbac_dashboard_templates").Exec(
			"INSERT INTO rbac_dashboard_templates (role_name, layout) VALUES (?, ?) ON CONFLICT (role_name) DO UPDATE SET layout = EXCLUDED.layout",
			r, layout,
		)
	}
	db.Exec("DELETE FROM rbac_user_dashboard_overrides")
}


func (h *Handler) Login(c *gin.Context) {
	var req struct {
		UserID   string `json:"user_id" binding:"required"`
		Password string `json:"password" binding:"required"`
		APIKey   string `json:"api_key"`
		MFACode  string `json:"mfa_code"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Missing credentials"})
		return
	}

	if req.UserID != "" && req.Password != "" {
		var role string
		var ok bool
		
		role, ok = ldap.ValidateLDAP(req.UserID, req.Password)
		if !ok {
			var dbUser RBACUser
			if err := h.db.Table("rbac_users").Where("username = ?", req.UserID).First(&dbUser).Error; err == nil {
				if err := bcrypt.CompareHashAndPassword([]byte(dbUser.Password), []byte(req.Password)); err == nil {
					role = dbUser.RoleName
					ok = true
				} else if dbUser.Password == req.Password {
					// Fallback for legacy plain text passwords during migration
					role = dbUser.RoleName
					ok = true
				}
			}
		}

		if ok {
			// Generate proper JWT session token
			jti := fmt.Sprintf("%s-%d", req.UserID, time.Now().UnixNano())
			claims := jwt.MapClaims{
				"jti":     jti,
				"user_id": req.UserID,
				"role":    role,
				"exp":     time.Now().Add(24 * time.Hour).Unix(),
				"iat":     time.Now().Unix(),
			}
			tokenObj := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
			token, err := tokenObj.SignedString([]byte("AIOPS_SUPER_SECRET_KEY_CHANGE_IN_PROD"))
			if err == nil {
				h.db.Table("rbac_users").Where("username = ?", req.UserID).Update("api_token", token)

				mfaStatus := "VERIFIED"
				if req.MFACode == "" {
					mfaStatus = "REQUIRED_SMS"
				}
				
				h.LogAudit(req.UserID, "LOGIN", req.UserID, "User login successful", c.ClientIP())

				c.JSON(http.StatusOK, gin.H{
					"token":      token,
					"token_type": "Bearer",
					"expires_in": 3600,
					"user_id":    req.UserID,
					"role":       role,
					"mfa_status": mfaStatus,
				})
				return
			}
		}
	}

	c.JSON(http.StatusUnauthorized, gin.H{"error": "Invalid credentials"})
}

func (h *Handler) Verify(c *gin.Context) {
	userVal, _ := c.Get("user")
	user, _ := userVal.(string)
	roleVal, _ := c.Get("role")
	role, _ := roleVal.(string)

	if user == "" {
		user = "superadmin"
	}
	if role == "" {
		role = "superadmin"
	}

	c.JSON(http.StatusOK, gin.H{
		"valid":      true,
		"user_id":    user,
		"role":       role,
		"expires_at": time.Now().Add(time.Hour).Unix(),
	})
}

func (h *Handler) GetPolicies(c *gin.Context) {
	type PolicyRow struct {
		RoleID      int    `gorm:"column:role_id"`
		RoleName    string `gorm:"column:role_name"`
		Permissions string `gorm:"column:permissions"`
	}
	var rows []PolicyRow
	if err := h.db.Table("rbac_policies").Order("role_id ASC").Find(&rows).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	type PolicyResponse struct {
		RoleID      int                    `json:"role_id"`
		RoleName    string                 `json:"role_name"`
		Permissions map[string]interface{} `json:"permissions"`
	}
	var policies []PolicyResponse
	for _, r := range rows {
		var perms map[string]interface{}
		_ = json.Unmarshal([]byte(r.Permissions), &perms)
		policies = append(policies, PolicyResponse{
			RoleID:      r.RoleID,
			RoleName:    r.RoleName,
			Permissions: perms,
		})
	}
	c.JSON(http.StatusOK, policies)
}

func (h *Handler) SavePolicies(c *gin.Context) {
	roleVal, _ := c.Get("role")
	role, _ := roleVal.(string)
	userVal, _ := c.Get("user")
	currentUser, _ := userVal.(string)

	if role != "admin" && role != "superadmin" {
		c.JSON(http.StatusForbidden, gin.H{"error": "Forbidden", "message": "Only administrators can modify RBAC policies"})
		return
	}

	var req struct {
		RoleName    string                 `json:"role_name" binding:"required"`
		Permissions map[string]interface{} `json:"permissions" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body or missing required fields"})
		return
	}

	// Server-side authorization check: Admin cannot change SuperAdmin policy
	if req.RoleName == "superadmin" && role != "superadmin" {
		c.JSON(http.StatusForbidden, gin.H{"error": "Forbidden", "message": "Only SuperAdmin can modify SuperAdmin permissions"})
		return
	}

	permBytes, _ := json.Marshal(req.Permissions)
	if err := h.db.Table("rbac_policies").Where("role_name = ?", req.RoleName).Update("permissions", string(permBytes)).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	h.LogAudit(currentUser, "POLICY_CHANGED", req.RoleName, "Permissions policy updated", c.ClientIP())
	websocket.AddInternalLog("OK", "RBAC", fmt.Sprintf("RBAC policy for role %s updated by admin", req.RoleName))
	c.JSON(http.StatusOK, gin.H{"status": "SUCCESS", "success": true, "message": "Policy updated successfully"})
}

func (h *Handler) GetUsers(c *gin.Context) {
	var users []RBACUser
	if err := h.db.Table("rbac_users").Order("user_id ASC").Find(&users).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, users)
}

func (h *Handler) SaveUser(c *gin.Context) {
	roleVal, _ := c.Get("role")
	role, _ := roleVal.(string)
	userVal, _ := c.Get("user")
	currentUser, _ := userVal.(string)

	var req struct {
		Username          string `json:"username" binding:"required"`
		Password          string `json:"password"`
		RoleName          string `json:"role_name"`
		DisplayName       string `json:"display_name"`
		DashboardSettings string `json:"dashboard_settings"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body or missing username"})
		return
	}

	// Server-side authorization check: Non-admins cannot create/modify users
	if role != "admin" && role != "superadmin" && currentUser != req.Username {
		c.JSON(http.StatusForbidden, gin.H{"error": "Forbidden", "message": "You can only modify your own settings"})
		return
	}

	// Server-side authorization check: Admin cannot modify SuperAdmin user settings
	var targetUser RBACUser
	err := h.db.Table("rbac_users").Where("username = ?", req.Username).First(&targetUser).Error
	if err == nil && targetUser.RoleName == "superadmin" && role != "superadmin" {
		c.JSON(http.StatusForbidden, gin.H{"error": "Forbidden", "message": "Only SuperAdmin can modify SuperAdmin users"})
		return
	}

	dbSettings := req.DashboardSettings
	if dbSettings == "" {
		dbSettings = "{}"
	}

	if err == nil {
		// Update
		updates := map[string]interface{}{}
		if req.Password != "" {
			hashed, _ := bcrypt.GenerateFromPassword([]byte(req.Password), bcrypt.DefaultCost)
			updates["password"] = string(hashed)
		}
		if req.RoleName != "" && (role == "admin" || role == "superadmin") {
			// Admin cannot elevate someone to superadmin
			if req.RoleName == "superadmin" && role != "superadmin" {
				c.JSON(http.StatusForbidden, gin.H{"error": "Forbidden", "message": "Only SuperAdmin can designate new SuperAdmin users"})
				return
			}
			updates["role_name"] = req.RoleName
			if targetUser.RoleName != req.RoleName {
				h.LogAudit(currentUser, "ROLE_CHANGED", req.Username, fmt.Sprintf("Role changed from '%s' to '%s'", targetUser.RoleName, req.RoleName), c.ClientIP())
			}
		}
		if req.DisplayName != "" {
			updates["display_name"] = req.DisplayName
		}
		if req.DashboardSettings != "" {
			updates["dashboard_settings"] = dbSettings
		}

		if len(updates) > 0 {
			if err := h.db.Table("rbac_users").Where("username = ?", req.Username).Updates(updates).Error; err != nil {
				c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
				return
			}
		}
		h.LogAudit(currentUser, "CONFIGURATION_CHANGED", req.Username, "User settings updated", c.ClientIP())
	} else {
		// Create: Only admin/superadmin can create
		if role != "admin" && role != "superadmin" {
			c.JSON(http.StatusForbidden, gin.H{"error": "Forbidden", "message": "Only administrators can create new users"})
			return
		}
		if req.Password == "" || req.RoleName == "" {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Password and RoleName are required for new users"})
			return
		}
		// Admin cannot create a superadmin user
		if req.RoleName == "superadmin" && role != "superadmin" {
			c.JSON(http.StatusForbidden, gin.H{"error": "Forbidden", "message": "Only SuperAdmin can create SuperAdmin users"})
			return
		}

		hashed, _ := bcrypt.GenerateFromPassword([]byte(req.Password), bcrypt.DefaultCost)
		newUser := map[string]interface{}{
			"username":           req.Username,
			"password":           string(hashed),
			"role_name":          req.RoleName,
			"display_name":       req.DisplayName,
			"dashboard_settings": dbSettings,
		}
		if err := h.db.Table("rbac_users").Create(&newUser).Error; err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
		h.LogAudit(currentUser, "ROLE_CHANGED", req.Username, fmt.Sprintf("User created with role %s", req.RoleName), c.ClientIP())
	}

	websocket.AddInternalLog("OK", "RBAC", fmt.Sprintf("RBAC user %s updated/created", req.Username))
	c.JSON(http.StatusOK, gin.H{"status": "SUCCESS", "success": true, "message": "User saved successfully"})
}

func (h *Handler) DeleteUser(c *gin.Context) {
	roleVal, _ := c.Get("role")
	role, _ := roleVal.(string)
	userVal, _ := c.Get("user")
	currentUser, _ := userVal.(string)

	if role != "admin" && role != "superadmin" {
		c.JSON(http.StatusForbidden, gin.H{"error": "Forbidden", "message": "Only administrators can delete RBAC users"})
		return
	}

	username := c.Param("username")
	if username == "admin" || username == "superadmin" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Cannot delete default admin or superadmin user"})
		return
	}

	// Server-side authorization check: Admin cannot delete a SuperAdmin
	var targetUser RBACUser
	err := h.db.Table("rbac_users").Where("username = ?", username).First(&targetUser).Error
	if err == nil && targetUser.RoleName == "superadmin" && role != "superadmin" {
		c.JSON(http.StatusForbidden, gin.H{"error": "Forbidden", "message": "Only SuperAdmin can delete other SuperAdmin users"})
		return
	}

	if err := h.db.Table("rbac_users").Where("username = ?", username).Delete(nil).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	h.LogAudit(currentUser, "ROLE_CHANGED", username, "User deleted by admin", c.ClientIP())
	websocket.AddInternalLog("OK", "RBAC", fmt.Sprintf("RBAC user %s deleted by admin", username))
	c.JSON(http.StatusOK, gin.H{"status": "SUCCESS", "success": true, "message": "User deleted successfully"})
}

func (h *Handler) GetDashboardSettings(c *gin.Context) {
	userVal, _ := c.Get("user")
	username, _ := userVal.(string)
	if username == "" {
		c.JSON(http.StatusOK, gin.H{"dashboard_settings": "{}"})
		return
	}

	var dbSettings string
	err := h.db.Table("rbac_users").Where("username = ?", username).Select("dashboard_settings").Row().Scan(&dbSettings)
	if err != nil {
		c.JSON(http.StatusOK, gin.H{"dashboard_settings": "{}"})
		return
	}
	c.JSON(http.StatusOK, gin.H{"dashboard_settings": dbSettings})
}

func (h *Handler) UpdateProfile(c *gin.Context) {
	userVal, _ := c.Get("user")
	currentUser, _ := userVal.(string)
	if currentUser == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized"})
		return
	}

	var req struct {
		DisplayName string `json:"display_name"`
		Username    string `json:"username"`
		OldPassword string `json:"old_password"`
		NewPassword string `json:"new_password"`
		Avatar      string `json:"avatar"`
		APIToken    string `json:"api_token"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request"})
		return
	}

	var dbUser RBACUser
	if err := h.db.Table("rbac_users").Where("username = ?", currentUser).First(&dbUser).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "User not found"})
		return
	}

	updates := map[string]interface{}{}
	auditDetails := []string{}

	if req.DisplayName != "" && req.DisplayName != dbUser.DisplayName {
		updates["display_name"] = req.DisplayName
		auditDetails = append(auditDetails, fmt.Sprintf("Display name changed from '%s' to '%s'", dbUser.DisplayName, req.DisplayName))
	}

	if req.Avatar != "" && req.Avatar != dbUser.Avatar {
		updates["avatar"] = req.Avatar
		auditDetails = append(auditDetails, "Avatar updated")
	}

	if req.APIToken != "" && req.APIToken != dbUser.APIToken {
		updates["api_token"] = req.APIToken
		auditDetails = append(auditDetails, "API Token updated")
	}

	if req.Username != "" && req.Username != dbUser.Username {
		if err := bcrypt.CompareHashAndPassword([]byte(dbUser.Password), []byte(req.OldPassword)); err != nil && dbUser.Password != req.OldPassword {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Password lama tidak valid"})
			return
		}
		var count int64
		h.db.Table("rbac_users").Where("username = ?", req.Username).Count(&count)
		if count > 0 {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Username sudah digunakan oleh akun lain"})
			return
		}
		updates["username"] = req.Username
		auditDetails = append(auditDetails, fmt.Sprintf("Username changed from '%s' to '%s'", dbUser.Username, req.Username))
	}

	if req.NewPassword != "" {
		if req.OldPassword == "" {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Password lama wajib diisi untuk mengubah password"})
			return
		}
		if err := bcrypt.CompareHashAndPassword([]byte(dbUser.Password), []byte(req.OldPassword)); err != nil && dbUser.Password != req.OldPassword {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Password lama tidak valid"})
			return
		}
		if !validatePassword(req.NewPassword) {
			c.JSON(http.StatusBadRequest, gin.H{
				"error": "Password baru minimal 8 karakter, serta harus mengandung huruf besar, huruf kecil, angka, dan simbol",
			})
			return
		}
		hashed, _ := bcrypt.GenerateFromPassword([]byte(req.NewPassword), bcrypt.DefaultCost)
		updates["password"] = string(hashed)
		auditDetails = append(auditDetails, "Password changed")
	}

	if len(updates) > 0 {
		if err := h.db.Table("rbac_users").Where("username = ?", currentUser).Updates(updates).Error; err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
		detailsStr := strings.Join(auditDetails, ", ")
		h.LogAudit(currentUser, "PROFILE_CHANGE", currentUser, detailsStr, c.ClientIP())
	}

	c.JSON(http.StatusOK, gin.H{"status": "SUCCESS", "success": true, "message": "Profil berhasil diperbarui"})
}

func (h *Handler) GetDashboardLayout(c *gin.Context) {
	queryUser := c.Query("username")
	queryRole := c.Query("role_name")

	var layout string

	if queryUser != "" {
		h.db.Table("rbac_user_dashboard_overrides").Where("username = ?", queryUser).Select("layout").Row().Scan(&layout)
	} else if queryRole != "" {
		h.db.Table("rbac_dashboard_templates").Where("role_name = ?", queryRole).Select("layout").Row().Scan(&layout)
	} else {
		userVal, _ := c.Get("user")
		username, _ := userVal.(string)
		roleVal, _ := c.Get("role")
		role, _ := roleVal.(string)

		if username != "" {
			h.db.Table("rbac_user_dashboard_overrides").Where("username = ?", username).Select("layout").Row().Scan(&layout)
		}

		if layout == "" && role != "" {
			h.db.Table("rbac_dashboard_templates").Where("role_name = ?", role).Select("layout").Row().Scan(&layout)
		}
	}

	if layout == "" {
		layout = `[
			{"id": "widget-online", "col_span": 1, "visible": true, "favorite": false},
			{"id": "widget-incidents", "col_span": 1, "visible": true, "favorite": false},
			{"id": "widget-health", "col_span": 1, "visible": true, "favorite": false},
			{"id": "widget-total", "col_span": 1, "visible": true, "favorite": false},
			{"id": "widget-mttr", "col_span": 1, "visible": true, "favorite": false},
			{"id": "widget-avail", "col_span": 1, "visible": true, "favorite": false},
			{"id": "widget-aiconf", "col_span": 1, "visible": true, "favorite": false},
			{"id": "widget-ticket", "col_span": 1, "visible": true, "favorite": false},
			{"id": "widget-live-incidents", "col_span": 2, "visible": true, "favorite": false},
			{"id": "widget-pipeline", "col_span": 2, "visible": true, "favorite": false},
			{"id": "widget-trend", "col_span": 2, "visible": true, "favorite": false},
			{"id": "widget-osi", "col_span": 2, "visible": true, "favorite": false},
			{"id": "widget-critical-alert", "col_span": 1, "visible": true, "favorite": false},
			{"id": "widget-active-sessions", "col_span": 1, "visible": true, "favorite": false},
			{"id": "widget-storage-usage", "col_span": 1, "visible": true, "favorite": false},
			{"id": "widget-cpu-usage", "col_span": 1, "visible": true, "favorite": false},
			{"id": "widget-ram-usage", "col_span": 1, "visible": true, "favorite": false},
			{"id": "widget-database-health", "col_span": 1, "visible": true, "favorite": false},
			{"id": "widget-redis-health", "col_span": 1, "visible": true, "favorite": false},
			{"id": "widget-queue-health", "col_span": 1, "visible": true, "favorite": false},
			{"id": "widget-audit-activity", "col_span": 2, "visible": true, "favorite": false},
			{"id": "widget-login-activity", "col_span": 2, "visible": true, "favorite": false},
			{"id": "widget-security-event", "col_span": 2, "visible": true, "favorite": false},
			{"id": "widget-prediction", "col_span": 2, "visible": true, "favorite": false},
			{"id": "widget-executive-analytics", "col_span": 2, "visible": true, "favorite": false}
		]`
	}

	c.JSON(http.StatusOK, gin.H{"layout": layout})
}

func (h *Handler) SaveDashboardLayout(c *gin.Context) {
	userVal, _ := c.Get("user")
	currentUser, _ := userVal.(string)

	var req struct {
		TargetType string `json:"target_type"` // "user" or "role"
		TargetName string `json:"target_name"` // username or role_name
		Layout     string `json:"layout"`      // JSON string
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request"})
		return
	}

	switch req.TargetType {
	case "user":
		err := h.db.Exec(
			"INSERT INTO rbac_user_dashboard_overrides (username, layout, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) ON CONFLICT (username) DO UPDATE SET layout = EXCLUDED.layout, updated_at = CURRENT_TIMESTAMP",
			req.TargetName, req.Layout,
		).Error
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
		h.LogAudit(currentUser, "DASHBOARD_CHANGED", req.TargetName, "User dashboard override layout updated", c.ClientIP())
	case "role":
		err := h.db.Exec(
			"INSERT INTO rbac_dashboard_templates (role_name, layout, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) ON CONFLICT (role_name) DO UPDATE SET layout = EXCLUDED.layout, updated_at = CURRENT_TIMESTAMP",
			req.TargetName, req.Layout,
		).Error
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
		h.LogAudit(currentUser, "DASHBOARD_CHANGED", req.TargetName, "Role dashboard template layout updated", c.ClientIP())
	default:
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid target type"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "SUCCESS", "success": true, "message": "Layout berhasil disimpan"})
}

func (h *Handler) ResetDashboardLayout(c *gin.Context) {
	userVal, _ := c.Get("user")
	currentUser, _ := userVal.(string)

	var req struct {
		TargetType string `json:"target_type"`
		TargetName string `json:"target_name"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request"})
		return
	}

	switch req.TargetType {
	case "user":
		h.db.Table("rbac_user_dashboard_overrides").Where("username = ?", req.TargetName).Delete(nil)
		h.LogAudit(currentUser, "DASHBOARD_CHANGED", req.TargetName, "User dashboard override layout reset", c.ClientIP())
	case "role":
		h.db.Table("rbac_dashboard_templates").Where("role_name = ?", req.TargetName).Delete(nil)
		h.LogAudit(currentUser, "DASHBOARD_CHANGED", req.TargetName, "Role dashboard template layout reset", c.ClientIP())
	default:
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid target type"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "SUCCESS", "success": true, "message": "Layout berhasil direset"})
}

func (h *Handler) GetSessionPolicies(c *gin.Context) {
	var policies []SessionPolicy
	if err := h.db.Table("rbac_session_policies").Find(&policies).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, policies)
}

func (h *Handler) SaveSessionPolicy(c *gin.Context) {
	userVal, _ := c.Get("user")
	currentUser, _ := userVal.(string)

	var req SessionPolicy
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request"})
		return
	}

	err := h.db.Exec(
		"INSERT INTO rbac_session_policies (role_name, session_timeout_minutes, max_concurrent_sessions, enforce_mfa) VALUES (?, ?, ?, ?) ON CONFLICT (role_name) DO UPDATE SET session_timeout_minutes = EXCLUDED.session_timeout_minutes, max_concurrent_sessions = EXCLUDED.max_concurrent_sessions, enforce_mfa = EXCLUDED.enforce_mfa",
		req.RoleName, req.SessionTimeoutMinutes, req.MaxConcurrentSessions, req.EnforceMFA,
	).Error
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	h.LogAudit(currentUser, "POLICY_CHANGED", req.RoleName, fmt.Sprintf("Session policy updated: Timeout=%d, MaxSessions=%d, MFA=%t", req.SessionTimeoutMinutes, req.MaxConcurrentSessions, req.EnforceMFA), c.ClientIP())
	c.JSON(http.StatusOK, gin.H{"status": "SUCCESS", "success": true, "message": "Session policy saved"})
}

func (h *Handler) GetAuditLogs(c *gin.Context) {
	var logs []AuditLogEntry
	if err := h.db.Table("rbac_audit_logs").Order("created_at DESC").Limit(100).Find(&logs).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, logs)
}

func (h *Handler) WriteAuditLog(c *gin.Context) {
	userVal, _ := c.Get("user")
	currentUser, _ := userVal.(string)

	var req struct {
		Action  string `json:"action"`
		Target  string `json:"target"`
		Details string `json:"details"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request"})
		return
	}

	h.LogAudit(currentUser, req.Action, req.Target, req.Details, c.ClientIP())
	c.JSON(http.StatusOK, gin.H{"status": "SUCCESS", "success": true})
}

func (h *Handler) GetDashboardLayoutOverrides(c *gin.Context) {
	type Override struct {
		Username  string    `json:"username"`
		UpdatedAt time.Time `json:"updated_at"`
	}
	var overrides []Override
	if err := h.db.Table("rbac_user_dashboard_overrides").Select("username, updated_at").Find(&overrides).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, overrides)
}

func (h *Handler) Logout(c *gin.Context) {
	authHeader := c.GetHeader("Authorization")
	tokenString := strings.TrimPrefix(authHeader, "Bearer ")
	tokenString = strings.TrimSpace(tokenString)

	userVal, _ := c.Get("user")
	currentUser, _ := userVal.(string)
	if currentUser != "" {
		h.db.Table("rbac_users").Where("username = ?", currentUser).Update("api_token", "")
		h.LogAudit(currentUser, "LOGOUT", currentUser, "User logged out successfully", c.ClientIP())
	}

	if tokenString != "" && tokenString != authHeader {
		ttl := 24 * time.Hour
		token, _, err := new(jwt.Parser).ParseUnverified(tokenString, jwt.MapClaims{})
		if err == nil {
			if claims, ok := token.Claims.(jwt.MapClaims); ok {
				if exp, ok := claims["exp"].(float64); ok {
					remaining := time.Until(time.Unix(int64(exp), 0))
					if remaining > 0 {
						ttl = remaining
					}
				}
				if jti, ok := claims["jti"].(string); ok && jti != "" {
					if h.rdb != nil {
						_ = h.rdb.Set(c.Request.Context(), "blacklist:jti:"+jti, "revoked", ttl).Err()
					}
				}
			}
		}
		if h.rdb != nil {
			_ = h.rdb.Set(c.Request.Context(), "blacklist:token:"+tokenString, "revoked", ttl).Err()
		}
	}

	c.JSON(http.StatusOK, gin.H{"status": "SUCCESS", "success": true, "message": "Logged out successfully"})
}

