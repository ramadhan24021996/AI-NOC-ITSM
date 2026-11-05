package main

import (
	"crypto/subtle"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/gin-gonic/gin"

	"go_incident_analysis/SERVER/go_core/hardening"
)

// Config holds defaults
const (
	Port           = 44600
	CacheFilename  = "detection_cache.json"
	CacheTTL       = 3600 // 1 hour in seconds
)

// Struct definitions for API payloads
type LaunchPayload struct {
	Tool      string `json:"tool" binding:"required"`
	ID        string `json:"id"`
	Password  string `json:"password"`
	ExePath   string `json:"exe_path"`
	Host      string `json:"host"`
	Port      int    `json:"port"`
	Viewer    string `json:"viewer"`
	Path      string `json:"path"`
	SessionID string `json:"session_id"`
}

type ToolStatus struct {
	Installed  bool      `json:"installed"`
	Running    bool      `json:"running"`
	ID         string    `json:"id,omitempty"`
	ExePath    string    `json:"exe_path,omitempty"`
	Version    string    `json:"version,omitempty"`
	DetectedAt time.Time `json:"detected_at,omitempty"`
}

type DetectionResult struct {
	AnyDesk   ToolStatus            `json:"anydesk"`
	RustDesk  ToolStatus            `json:"rustdesk"`
	VNC       map[string]ToolStatus `json:"vnc"`
	Timestamp time.Time             `json:"timestamp"`
	CacheTTL  int                   `json:"cache_ttl"`
}

var (
	lastDetectionResult DetectionResult
	detectionMutex      sync.RWMutex
)

func main() {
	// Set Gin mode
	gin.SetMode(gin.ReleaseMode)

	r := gin.Default()

	// [WS-1 / T-09] CORS restricted to local origin only (never *)
	r.Use(func(c *gin.Context) {
		origin := c.GetHeader("Origin")
		if origin == "http://127.0.0.1:44600" || origin == "http://localhost:44600" || origin == "http://127.0.0.1:8080" || origin == "http://localhost:8080" {
			c.Writer.Header().Set("Access-Control-Allow-Origin", origin)
		}
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Launcher-Token, X-Session-ID")
		c.Writer.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(http.StatusNoContent)
			return
		}
		c.Next()
	})

	// [WS-1 / T-09] Authentication middleware: require session token for mutating/exec endpoints
	authMiddleware := func(c *gin.Context) {
		path := c.Request.URL.Path
		if path == "/health" || path == "/version" {
			c.Next()
			return
		}
		expectedToken := os.Getenv("LAUNCHER_SESSION_TOKEN")
		if expectedToken != "" {
			provided := c.GetHeader("X-Launcher-Token")
			if provided == "" {
				authHdr := c.GetHeader("Authorization")
				if strings.HasPrefix(authHdr, "Bearer ") {
					provided = strings.TrimPrefix(authHdr, "Bearer ")
				}
			}
			if provided == "" || subtle.ConstantTimeCompare([]byte(provided), []byte(expectedToken)) != 1 {
				c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized", "message": "Valid launcher session token required"})
				c.Abort()
				return
			}
		}
		c.Next()
	}
	r.Use(authMiddleware)

	// Setup directories and cache path
	dataDir := filepath.Join(".", "data")
	_ = os.MkdirAll(dataDir, 0755)
	cacheFile := filepath.Join(dataDir, CacheFilename)

	// Initialize background watcher
	startWatcher(cacheFile)

	// ===== GET /health =====
	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status":    "healthy",
			"service":   "OSI Launcher Service",
			"timestamp": time.Now().Format(time.RFC3339),
			"port":      Port,
		})
	})

	// ===== GET /status =====
	r.GET("/status", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status":  "online",
			"running": true,
			"service": "OSI Launcher Service",
		})
	})

	// ===== GET /version =====
	r.GET("/version", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status":  "success",
			"version": "1.0.0-Go",
		})
	})

	// ===== DETECT ENDPOINT =====
	r.POST("/detect", func(c *gin.Context) {
		detectionMutex.RLock()
		res := lastDetectionResult
		detectionMutex.RUnlock()

		// Fallback to on-demand scan if cache is empty
		if res.Timestamp.IsZero() {
			res = runDetection()
			detectionMutex.Lock()
			lastDetectionResult = res
			detectionMutex.Unlock()
			_ = saveCache(cacheFile, res)
		}

		c.JSON(http.StatusOK, res)
	})

	// ===== CLEAR CACHE =====
	r.POST("/detect/clear-cache", func(c *gin.Context) {
		_ = os.Remove(cacheFile)
		c.JSON(http.StatusOK, gin.H{"status": "cache cleared"})
	})

	// ===== HEARTBEAT =====
	r.POST("/heartbeat", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "alive"})
	})

	// ===== LAUNCH ENDPOINT =====
	r.POST("/launch", func(c *gin.Context) {
		var payload LaunchPayload
		if err := c.ShouldBindJSON(&payload); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Missing or invalid payload parameters"})
			return
		}

		err := handleLaunch(payload)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"status":    "launching",
			"tool":      payload.Tool,
			"id":        payload.ID,
			"timestamp": time.Now().Format(time.RFC3339),
		})
	})

	// [WS-1 / T-09] Bind to 127.0.0.1 by default instead of 0.0.0.0
	bindHost := os.Getenv("LAUNCHER_BIND_HOST")
	if bindHost == "" {
		bindHost = "127.0.0.1"
	}
	fmt.Printf("[LAUNCHER] OSI AI Launcher Service running locally on http://%s:%d\n", bindHost, Port)
	_ = r.Run(fmt.Sprintf("%s:%d", bindHost, Port))
}

// File existence helper (platform independent)
func fileExists(path string) bool {
	if path == "" {
		return false
	}
	info, err := os.Stat(path)
	if err != nil {
		return false
	}
	return !info.IsDir()
}

// Background Registry and Process Watcher
func startWatcher(cacheFile string) {
	// Try loading cached result first
	if cached, err := loadCache(cacheFile); err == nil && cached != nil {
		detectionMutex.Lock()
		lastDetectionResult = *cached
		detectionMutex.Unlock()
	}

	// Ticker for Registry/Process check every 5 seconds
	hardening.GoSafe(func() {
		ticker := time.NewTicker(5 * time.Second)
		for range ticker.C {
			res := runDetection()
			detectionMutex.Lock()
			lastDetectionResult = res
			detectionMutex.Unlock()
			_ = saveCache(cacheFile, res)
		}
	}, func(cat, msg string) {
		fmt.Printf("[%s] Watcher warning: %s\n", cat, msg)
	})
}

// Cache storage
func saveCache(path string, data DetectionResult) error {
	bytes, err := json.MarshalIndent(data, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, bytes, 0644)
}

func loadCache(path string) (*DetectionResult, error) {
	info, err := os.Stat(path)
	if err != nil {
		return nil, err
	}

	// Verify TTL
	age := time.Since(info.ModTime())
	if age.Seconds() > CacheTTL {
		return nil, nil
	}

	bytes, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}

	var res DetectionResult
	if err := json.Unmarshal(bytes, &res); err != nil {
		return nil, err
	}
	return &res, nil
}
