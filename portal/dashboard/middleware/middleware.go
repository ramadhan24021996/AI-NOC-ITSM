package middleware

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/go-redis/redis/v8"
	"github.com/golang-jwt/jwt/v5"
	"golang.org/x/crypto/bcrypt"
	"gorm.io/gorm"
)

// getJWTSecret returns the JWT secret from environment or a fallback.
func getJWTSecret() []byte {
	if s := os.Getenv("JWT_SECRET"); s != "" {
		return []byte(s)
	}
	if s := os.Getenv("JWT_SECRET_KEY"); s != "" {
		return []byte(s)
	}
	fmt.Println("[SECURITY WARNING] JWT_SECRET env var not set. Using insecure default. Set JWT_SECRET in production!")
	return []byte("AIOPS_SUPER_SECRET_KEY_CHANGE_IN_PROD")
}

// verifyPassword checks bcrypt hash first, falls back to plain-text with a warning.
func verifyPassword(stored, provided string) bool {
	// Try bcrypt first
	if err := bcrypt.CompareHashAndPassword([]byte(stored), []byte(provided)); err == nil {
		return true
	}
	// Fallback: plain-text comparison (legacy — logs warning)
	if stored == provided {
		fmt.Println("[SECURITY WARNING] User authenticated with plain-text password. Migrate to bcrypt hash!")
		return true
	}
	return false
}

// CORSMiddleware handles CORS configuration.
// SEC-04: Restrict ALLOWED_ORIGIN from env; defaults to localhost for safety.
func CORSMiddleware() gin.HandlerFunc {
	allowedOrigin := os.Getenv("ALLOWED_ORIGIN")
	if allowedOrigin == "" {
		allowedOrigin = "http://localhost"
	}
	return func(c *gin.Context) {
		origin := c.Request.Header.Get("Origin")
		// Allow same-origin and configured origin
		if origin == allowedOrigin || origin == "" {
			c.Writer.Header().Set("Access-Control-Allow-Origin", allowedOrigin)
		}
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With, X-API-Key, X-CSRF-Token")
		c.Writer.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PUT, DELETE")
		c.Writer.Header().Set("Access-Control-Allow-Credentials", "true")
		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(http.StatusNoContent)
			return
		}
		c.Next()
	}
}

// AuthMiddleware validates basic credentials, JWT tokens, and API keys
func AuthMiddleware(db *gorm.DB, rdb ...*redis.Client) gin.HandlerFunc {
	var redisClient *redis.Client
	if len(rdb) > 0 {
		redisClient = rdb[0]
	}
	return func(c *gin.Context) {
		path := c.Request.URL.Path
		if strings.HasPrefix(path, "/ws/") || strings.HasPrefix(path, "/api/fleet/notify") || strings.HasPrefix(path, "/api/fleet/push_notification") || strings.HasPrefix(path, "/api/fleet/ota") || strings.Contains(path, "notify") {
			c.Next()
			return
		}
		// Allow public routes
		if path == "/" || path == "/portal" || path == "/health" || path == "/api/auth/login" || path == "/api/ai_command" ||
			path == "/telemetry" || path == "/activity" || path == "/issues" || path == "/browser-events" ||
			path == "/api/telemetry" || path == "/api/activity" || path == "/api/issues" || path == "/api/browser-events" ||
			strings.HasPrefix(path, "/static") || strings.HasPrefix(path, "/uploads") || strings.HasPrefix(path, "/downloads") || strings.HasPrefix(path, "/api/chat") || strings.HasPrefix(path, "/api/enterprise/chat") || strings.HasPrefix(path, "/api/fleet/update") || strings.HasPrefix(path, "/api/fleet/notify") || strings.HasPrefix(path, "/api/fleet/push_notification") || strings.HasPrefix(path, "/api/fleet/ota") || strings.HasPrefix(path, "/api/ai/knowledge") || strings.HasPrefix(path, "/api/causal_dag") || strings.HasPrefix(path, "/api/decision_graph") || strings.HasPrefix(path, "/api/incidents") || strings.Contains(path, "notify") {
			c.Next()
			return
		}

		// Check basic auth
		user, password, hasAuth := c.Request.BasicAuth()
		if hasAuth {
			valid := false
			role := "viewer"

			type DBUser struct {
				Username string `gorm:"column:username"`
				Password string `gorm:"column:password"`
				RoleName string `gorm:"column:role_name"`
			}
			var dbUser DBUser
			err := db.Table("rbac_users").Where("username = ?", user).First(&dbUser).Error
			if err == nil {
				// SEC-02: Use bcrypt with plain-text fallback
				if verifyPassword(dbUser.Password, password) {
					valid = true
					role = dbUser.RoleName
				}
			}

			if valid {
				c.Set("user", user)
				c.Set("role", role)
				c.Next()
				return
			}
		}

		// Check API Key
		apiKey := c.GetHeader("X-API-Key")
		if apiKey == "" {
			apiKey = c.Query("api_key")
		}
		if apiKey != "" {
			var dbUser struct {
				Username string `gorm:"column:username"`
				RoleName string `gorm:"column:role_name"`
			}
			if err := db.Table("rbac_users").Where("api_token = ?", apiKey).First(&dbUser).Error; err == nil {
				c.Set("user", dbUser.Username)
				c.Set("role", dbUser.RoleName)
				c.Next()
				return
			}
		}

		// Check Bearer Token (using proper JWT)
		authHeader := c.GetHeader("Authorization")
		if strings.HasPrefix(authHeader, "Bearer ") {
			tokenString := strings.TrimPrefix(authHeader, "Bearer ")
			tokenString = strings.TrimSpace(tokenString)

			if redisClient != nil && tokenString != "" {
				if isBlacklisted, err := redisClient.Exists(c.Request.Context(), "blacklist:token:"+tokenString).Result(); err == nil && isBlacklisted > 0 {
					c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized", "message": "Token has been revoked"})
					c.Abort()
					return
				}
			}

			// SEC-01: Use env-based JWT secret
			token, err := jwt.Parse(tokenString, func(token *jwt.Token) (interface{}, error) {
				if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
					return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
				}
				return getJWTSecret(), nil
			})

			if err == nil && token.Valid {
				if claims, ok := token.Claims.(jwt.MapClaims); ok {
					if jti, ok := claims["jti"].(string); ok && jti != "" && redisClient != nil {
						if isBlacklisted, err := redisClient.Exists(c.Request.Context(), "blacklist:jti:"+jti).Result(); err == nil && isBlacklisted > 0 {
							c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized", "message": "Token has been revoked"})
							c.Abort()
							return
						}
					}
					userID, _ := claims["user_id"].(string)
					role, _ := claims["role"].(string)

					var count int64
					if db != nil {
						var dbUser struct {
							RoleName string `gorm:"column:role_name"`
						}
						if err := db.Table("rbac_users").Where("username = ?", userID).Select("role_name").First(&dbUser).Error; err == nil && dbUser.RoleName != "" {
							role = dbUser.RoleName
						}
						db.Table("rbac_users").Where("username = ?", userID).Count(&count)
					}
					if count > 0 || userID == "admin" || userID == "superadmin" || userID == "system" {
						c.Set("user", userID)
						c.Set("role", role)
						c.Next()
						return
					}
				}
			}
		}

		// Enforce auth fallback
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized", "message": "Authorization required"})
		c.Abort()
	}
}

// CSRFMiddleware checks for X-CSRF-Token header on mutating requests
func CSRFMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		if c.Request.Method == "POST" || c.Request.Method == "PUT" || c.Request.Method == "DELETE" || c.Request.Method == "PATCH" {
			path := c.Request.URL.Path
			if path == "/api/auth/login" || path == "/api/telemetry" || path == "/api/activity" || path == "/api/issues" || path == "/api/browser-events" || strings.HasPrefix(path, "/api/ai_command") || strings.HasPrefix(path, "/api/timeline/") || strings.HasPrefix(path, "/api/fleet/notify") || strings.HasPrefix(path, "/api/fleet/push_notification") || strings.HasPrefix(path, "/api/fleet/ota") || strings.HasPrefix(path, "/api/ai/knowledge") || strings.HasPrefix(path, "/api/ai_file/") {
				c.Next()
				return
			}
			
			csrfToken := c.GetHeader("X-CSRF-Token")
			if csrfToken == "" {
				c.JSON(http.StatusForbidden, gin.H{"error": "Forbidden", "message": "Missing CSRF token"})
				c.Abort()
				return
			}
			
			authHeader := c.GetHeader("Authorization")
			tokenString := strings.TrimPrefix(authHeader, "Bearer ")
			if csrfToken != tokenString {
				c.JSON(http.StatusForbidden, gin.H{"error": "Forbidden", "message": "Invalid CSRF token"})
				c.Abort()
				return
			}
		}
		c.Next()
	}
}

// CheckPermission checks if a given role has permissions for a key
func CheckPermission(db *gorm.DB, role string, permissionKey string) bool {
	if role == "admin" || role == "superadmin" || role == "noc_engineering" {
		return true
	}

	var permissionsRaw []byte
	err := db.Table("rbac_policies").Where("role_name = ?", role).Select("permissions").Row().Scan(&permissionsRaw)
	if err != nil {
		return false
	}
	var perms map[string]interface{}
	if err := json.Unmarshal(permissionsRaw, &perms); err != nil {
		return false
	}
	if allVal, ok := perms["all"].(bool); ok && allVal {
		return true
	}
	if val, ok := perms[permissionKey].(bool); ok {
		return val
	}
	return false
}
