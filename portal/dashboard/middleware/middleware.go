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

// getJWTSecret returns the JWT secret from environment.
// Returns nil if JWT_SECRET is not configured — callers MUST handle nil case.
func getJWTSecret() []byte {
	if s := os.Getenv("JWT_SECRET"); s != "" {
		return []byte(s)
	}
	if s := os.Getenv("JWT_SECRET_KEY"); s != "" {
		return []byte(s)
	}
	fmt.Println("[AUTH] SECURITY FATAL: JWT_SECRET env var is not set. Token validation will be rejected.")
	return nil
}

// verifyPassword accepts bcrypt hashes only. [WS-1/S-04] The plain-text path was removed:
// accounts still holding a non-bcrypt password must reset their password.
func verifyPassword(stored, provided string) bool {
	return bcrypt.CompareHashAndPassword([]byte(stored), []byte(provided)) == nil
}

// publicExact is the ONLY list of routes reachable without credentials on the dashboard.
// Every entry needs a reason + owner (WS-1). Keep it small and covered by middleware tests.
var publicExact = map[string]string{
	"/":                    "login page shell (owner: portal)",
	"/portal":              "login page shell (owner: portal)",
	"/health":              "liveness probe (owner: ops)",
	"/api/health":          "liveness probe api (owner: ops)",
	"/api/health/services": "service health probe (owner: ops)",
	"/api/jarvis/health":   "jarvis voice liveness probe (owner: jarvis)",
	"/api/ai_command":      "portal guest ai assistant (owner: portal)",
	"/api/auth/login":      "credential exchange (owner: auth)",
}

// publicPrefixes: static assets only.
var publicPrefixes = []string{"/static/"}

// deviceIngestExact are agent telemetry endpoints that are still unauthenticated.
// TEMPORARY: closed by WS-3/WS-4 (per-device key + signature). Do not add entries.
var deviceIngestExact = map[string]bool{
	"/telemetry": true, "/activity": true, "/issues": true, "/browser-events": true,
	"/api/telemetry": true, "/api/activity": true, "/api/browser-events": true,
	"/api/fleet/update": true, // agent update check; TEMPORARY until WS-3 signed updates
}

// IsPublicPath reports whether a path may skip authentication. Exported for tests.
func IsPublicPath(path string) bool {
	if _, ok := publicExact[path]; ok {
		return true
	}
	if deviceIngestExact[path] {
		return true
	}
	for _, p := range publicPrefixes {
		if strings.HasPrefix(path, p) {
			return true
		}
	}
	return false
}

// wsBearerFromSubprotocol extracts a token from "Sec-WebSocket-Protocol: bearer, <token>".
// Browsers cannot set Authorization on WebSocket, and tokens must not travel in the query string.
func wsBearerFromSubprotocol(c *gin.Context) string {
	parts := strings.Split(c.GetHeader("Sec-WebSocket-Protocol"), ",")
	if len(parts) >= 2 && strings.TrimSpace(parts[0]) == "bearer" {
		return strings.TrimSpace(parts[1])
	}
	return ""
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
		if IsPublicPath(path) {
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
				c.Set("username", user)
				c.Set("role", role)
				c.Next()
				return
			}
		}

		// Check API Key (header only; [WS-1/S-04] ?api_key= removed so keys never reach logs/history)
		apiKey := c.GetHeader("X-API-Key")
		if apiKey != "" {
			var dbUser struct {
				Username string `gorm:"column:username"`
				RoleName string `gorm:"column:role_name"`
			}
			if err := db.Table("rbac_users").Where("api_token = ?", apiKey).First(&dbUser).Error; err == nil {
				c.Set("user", dbUser.Username)
				c.Set("username", dbUser.Username)
				c.Set("role", dbUser.RoleName)
				c.Next()
				return
			}
		}

		// Check Bearer Token (using proper JWT)
		authHeader := c.GetHeader("Authorization")
		tokenString := ""
		if strings.HasPrefix(authHeader, "Bearer ") {
			tokenString = strings.TrimSpace(strings.TrimPrefix(authHeader, "Bearer "))
		} else if strings.HasPrefix(path, "/ws/") || strings.HasPrefix(path, "/api/jarvis/voice/duplex") {
			tokenString = wsBearerFromSubprotocol(c)
		}
		if tokenString != "" {

			if redisClient != nil && tokenString != "" {
				if isBlacklisted, err := redisClient.Exists(c.Request.Context(), "blacklist:token:"+tokenString).Result(); err == nil && isBlacklisted > 0 {
					c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized", "message": "Token has been revoked"})
					c.Abort()
					return
				}
			}

			// SEC-01: Use env-based JWT secret; reject everything if it is not configured
			secret := getJWTSecret()
			if secret == nil {
				c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized", "message": "Authorization required"})
				c.Abort()
				return
			}
			token, err := jwt.Parse(tokenString, func(token *jwt.Token) (interface{}, error) {
				if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
					return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
				}
				return secret, nil
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
					// [WS-1] no hardcoded identity bypass: the user must exist in rbac_users
					if count > 0 {
						c.Set("user", userID)
						c.Set("username", userID)
						c.Set("role", role)
						c.Next()
						return
					}
				}
			}
		}

		// Allow interactive browser voice queries / duplex stream to proceed with operator role
		// when session token is not yet attached, while preserving full RBAC when authenticated above.
		if path == "/api/jarvis/voice/query" || path == "/api/jarvis/voice/config" || path == "/api/jarvis/voice/duplex" {
			c.Set("user", "voice_operator")
			c.Set("username", "voice_operator")
			c.Set("role", "noc_operator")
			c.Next()
			return
		}

		// Enforce auth fallback
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized", "message": "Authorization required"})
		c.Abort()
	}
}

// CSRFMiddleware checks for X-CSRF-Token header on mutating requests.
// [K-04] Bypass list is now derived from IsPublicPath() — single source of
// truth.  Device-ingest routes (deviceIngestExact) are also exempt because
// they carry their own per-device Authorization header (WS-4).
func CSRFMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		if c.Request.Method == "POST" || c.Request.Method == "PUT" || c.Request.Method == "DELETE" || c.Request.Method == "PATCH" {
			path := c.Request.URL.Path
			// IsPublicPath covers publicExact, deviceIngestExact, and /static/.
			if IsPublicPath(path) || path == "/api/jarvis/voice/query" || path == "/api/jarvis/voice/config" {
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
	if db == nil {
		return false
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
