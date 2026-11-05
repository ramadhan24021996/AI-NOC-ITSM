package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/go-redis/redis/v8"
	"github.com/nats-io/nats.go"

	"go_incident_analysis/SERVER/go_core/ai"
	"go_incident_analysis/SERVER/go_core/config"
	"go_incident_analysis/SERVER/go_core/database"
	"go_incident_analysis/SERVER/go_core/security"

	// Sub-packages dashboard
	"go_incident_analysis/portal/dashboard/api"
	"go_incident_analysis/portal/dashboard/auth"
	"go_incident_analysis/portal/dashboard/core"
	"go_incident_analysis/portal/dashboard/incident"
	"go_incident_analysis/portal/dashboard/metrics"
	"go_incident_analysis/portal/dashboard/middleware"
	"go_incident_analysis/portal/dashboard/topology"
	wsPkg "go_incident_analysis/portal/dashboard/websocket"

	// pkg/ — Modular packages (Pragmatic Modularization Phase 3)
	portalAuth "go_incident_analysis/portal/pkg/auth"
)

// runPortal adalah fungsi inisialisasi utama portal.
// Dipanggil dari main.go yang merupakan entry point bersih.
// Mengembalikan error agar main() dapat menangani fatal error.
func runPortal() error {
	// Alias portalAuth untuk ValidateLDAP — delegasi ke pkg/auth
	_ = portalAuth.ValidateLDAP // ensure pkg/auth is used
	cfg, err := config.GetConfig()
	if err != nil {
		fmt.Printf("[ERROR] Failed to load config: %v\n", err)
		os.Exit(1)
	}
	fmt.Println("[BOOT 1] Config loaded successfully")

	dbConn, err := database.InitDatabase()
	if err != nil {
		fmt.Printf("[ERROR] Database initialization failed: %v\n", err)
		os.Exit(1)
	}
	fmt.Println("[BOOT 2] Database initialized successfully")

	// Clean up stale or mock FLAT_LINE rows from incidents table so database has zero lingering hallucinations
	dbConn.Exec(`UPDATE incidents SET status = 'RESOLVED' WHERE flag = 'FLAT_LINE' OR (status IS NULL AND flag LIKE '%FLAT_LINE%')`)
	dbConn.Exec(`DELETE FROM incidents WHERE flag = 'FLAT_LINE'`)

	// Seed operational baseline data across all 26 modules if empty
	if seedErr := core.SeedProductionBaselineData(dbConn); seedErr != nil {
		fmt.Printf("[WARN] Baseline data seeding encountered non-fatal error: %v\n", seedErr)
	}

	// Seed default SOPs if empty
	var sopCount int64
	dbConn.Model(&database.GovernanceSOP{}).Count(&sopCount)
	fmt.Println("[BOOT 3] Governance SOP count checked:", sopCount)
	if sopCount == 0 {
		defaultSOPs := []database.GovernanceSOP{
			{
				Name:        "SOP Restart Spooler",
				Title:       "SOP Restart Spooler",
				Description: "Standard procedure to restart print spooler service on failure.",
				Desc:        "Standard procedure to restart print spooler service on failure.",
				Symptoms:    "spooler stopped",
				Trigger:     "spooler stopped",
				Remediation: "RESTART_SPOOLER",
				Status:      "ACTIVE",
				Confidence:  0.95,
				Meta:        "ACTIVE · Remediation: RESTART_SPOOLER",
			},
			{
				Name:        "SOP Clear Print Spooler",
				Title:       "SOP Clear Print Spooler",
				Description: "Delete corrupted spooler files and restart the service.",
				Desc:        "Delete corrupted spooler files and restart the service.",
				Symptoms:    "print queue stuck / spooler error",
				Trigger:     "print queue stuck / spooler error",
				Remediation: "CLEAR_SPOOLER",
				Status:      "ACTIVE",
				Confidence:  0.88,
				Meta:        "ACTIVE · Remediation: CLEAR_SPOOLER",
			},
		}
		for _, sop := range defaultSOPs {
			dbConn.Create(&sop)
		}
		fmt.Println("[INFO] Seeded default governance SOPs.")
	}

	// Initialize Redis client for Dashboard Chat Pub/Sub
	redisHost := os.Getenv("REDIS_HOST")
	if redisHost == "" {
		redisHost = "redis"
	}
	redisPort := os.Getenv("REDIS_PORT")
	if redisPort == "" {
		redisPort = "6379"
	}
	dashboardRedisClient = redis.NewClient(&redis.Options{
		Addr:     redisHost + ":" + redisPort,
		Password: cfg.RedisPass,
	})
	if pingErr := dashboardRedisClient.Ping(dashboardCtx).Err(); pingErr != nil {
		fmt.Printf("[WARN] Dashboard server cannot reach Redis: %v. Fallback in-memory active.\n", pingErr)
	} else {
		fmt.Println("[BOOT 4] Redis connected for Dashboard Chat Pub/Sub")
	}

	// Initialize NATS connection for real-time telemetry streaming
	token := os.Getenv("NATS_TOKEN")
	if token == "" {
		token = os.Getenv("OSI_SECURITY_KEY")
	}
	if token == "" {
		token = cfg.NatsToken
	}
	if token == "" {
		token = "UWaVSW9Jz-Yl9wumi7SdHV0o9HSVZCWDlHclqWLUBkE="
	}

	natsHost := os.Getenv("NATS_HOST")
	if natsHost == "" {
		natsHost = "nats"
	}
	natsPort := os.Getenv("NATS_PORT")
	if natsPort == "" {
		natsPort = "4222"
	}
	endpoints := []string{
		fmt.Sprintf("nats://%s@%s:%s", token, natsHost, natsPort),
		fmt.Sprintf("nats://%s@127.0.0.1:%s", token, natsPort),
		fmt.Sprintf("nats://%s@localhost:%s", token, natsPort),
		fmt.Sprintf("nats://%s:%s", natsHost, natsPort),
		"nats://127.0.0.1:4222",
		"nats://localhost:4222",
	}

	for _, ep := range endpoints {
		if conn, err := nats.Connect(ep, nats.Timeout(2*time.Second), nats.MaxReconnects(-1), nats.ReconnectWait(2*time.Second)); err == nil {
			dashboardNatsConn = conn
			fmt.Printf("[BOOT 5] NATS connected successfully to %s\n", ep)
			break
		}
	}

	// Start Background Workers & Subscribers
	StartDashboardChatRedisSubscriber()
	StartTelemetryRedisSubscriber()
	startSystemAuditor(context.Background(), dbConn)
	startEndToEndHealthCheck(context.Background(), dbConn)
	startRLOFDecayWorker(context.Background(), dbConn)
	startAgentHeartbeatWorker(context.Background(), dbConn)

	// Resolve directories — auto-detect Docker container vs local dev environment
	baseDir, err := os.Getwd()
	if err != nil {
		baseDir = "."
	}

	// Docker container: volumes are mounted as /app/static, /app/templates (no 'portal/' prefix)
	// Local dev: paths are relative to repo root as portal/static, portal/templates
	var staticDir, templatesDir, otaBinariesDir, audioDir, settingsFile string
	if _, err := os.Stat(filepath.Join(baseDir, "static")); err == nil {
		// Running in Docker container — flat mount layout
		staticDir = filepath.Join(baseDir, "static")
		templatesDir = filepath.Join(baseDir, "templates")
		otaBinariesDir = filepath.Join(baseDir, "ota_binaries")
		audioDir = filepath.Join(baseDir, "audio")
		settingsFile = filepath.Join(baseDir, "remote_settings.json")
	} else {
		// Local dev — standard repo layout
		staticDir = filepath.Join(baseDir, "portal/static")
		templatesDir = filepath.Join(baseDir, "portal/templates")
		otaBinariesDir = filepath.Join(baseDir, "portal/ota_binaries")
		audioDir = filepath.Join(baseDir, "portal/audio")
		settingsFile = filepath.Join(baseDir, "portal/settings.json")
	}


	// Gin Engine configuration
	gin.SetMode(gin.ReleaseMode)
	r := gin.New()
	r.Use(gin.Recovery())

	// Logging & Security Middleware
	r.Use(security.SecurityHeadersMiddleware())
	r.Use(security.WAFMiddleware())
	r.Use(security.NewIPRateLimiter().Limit())
	r.Use(middleware.CORSMiddleware())
	r.Use(middleware.AuthMiddleware(dbConn, dashboardRedisClient))
	r.Use(middleware.CSRFMiddleware())

	// Force no-cache headers for all static HTML/JS/CSS assets to prevent browser disk caching
	r.Use(func(c *gin.Context) {
		c.Header("Cache-Control", "no-cache, no-store, must-revalidate")
		c.Header("Pragma", "no-cache")
		c.Header("Expires", "0")
		c.Next()
	})

	// Static & Template Assets
	r.Static("/static", staticDir)
	r.Static("/ota_binaries", otaBinariesDir)
	r.Static("/audio", audioDir)

	uploadDir := filepath.Join(baseDir, "portal/uploads")
	downloadsDir := filepath.Join(filepath.Dir(baseDir), "CLIENT_DISTRIBUSI_GO")
	if runtime.GOOS != "windows" {
		uploadDir = "/app/uploads"
		downloadsDir = "/app/workspace/CLIENT_DISTRIBUSI_GO"
	}
	r.Static("/uploads", uploadDir)
	r.StaticFS("/downloads", gin.Dir(downloadsDir, false) /* [T-03] no directory listing */)

	serveIndex := func(c *gin.Context) {
		c.Header("Cache-Control", "no-cache, no-store, must-revalidate")
		c.Header("Pragma", "no-cache")
		c.Header("Expires", "0")
		c.File(filepath.Join(templatesDir, "index.html"))
	}

	r.GET("/", serveIndex)
	r.HEAD("/", serveIndex)
	r.GET("/portal", func(c *gin.Context) {
		c.Header("Cache-Control", "no-cache, no-store, must-revalidate")
		c.File(filepath.Join(templatesDir, "portal.html"))
	})

	// Server-side authorization check for role-based landing pages
	r.GET("/dashboard/executive", func(c *gin.Context) {
		roleVal, _ := c.Get("role")
		role, _ := roleVal.(string)
		if role != "superadmin" {
			c.JSON(http.StatusForbidden, gin.H{"error": "Forbidden", "message": "Akses ke dashboard eksekutif ditolak"})
			c.Abort()
			return
		}
		serveIndex(c)
	})
	r.GET("/dashboard/admin", func(c *gin.Context) {
		roleVal, _ := c.Get("role")
		role, _ := roleVal.(string)
		if role != "admin" && role != "superadmin" {
			c.JSON(http.StatusForbidden, gin.H{"error": "Forbidden", "message": "Akses ke dashboard admin ditolak"})
			c.Abort()
			return
		}
		serveIndex(c)
	})
	r.GET("/dashboard/monitoring", func(c *gin.Context) {
		roleVal, _ := c.Get("role")
		role, _ := roleVal.(string)
		if role != "noc_engineering" && role != "admin" && role != "superadmin" {
			c.JSON(http.StatusForbidden, gin.H{"error": "Forbidden", "message": "Akses ke dashboard monitoring ditolak"})
			c.Abort()
			return
		}
		serveIndex(c)
	})
	r.GET("/dashboard/operator", func(c *gin.Context) {
		roleVal, _ := c.Get("role")
		role, _ := roleVal.(string)
		if role != "operator" && role != "admin" && role != "superadmin" {
			c.JSON(http.StatusForbidden, gin.H{"error": "Forbidden", "message": "Akses ke dashboard operator ditolak"})
			c.Abort()
			return
		}
		serveIndex(c)
	})
	r.GET("/dashboard/viewer", func(c *gin.Context) {
		roleVal, _ := c.Get("role")
		role, _ := roleVal.(string)
		if role != "viewer" && role != "operator" && role != "noc_engineering" && role != "admin" && role != "superadmin" {
			c.JSON(http.StatusForbidden, gin.H{"error": "Forbidden", "message": "Akses ke dashboard viewer ditolak"})
			c.Abort()
			return
		}
		serveIndex(c)
	})

	// Instantiate handlers from modular sub-packages
	apiHandler := api.NewHandler(dbConn, dashboardRedisClient, dashboardNatsConn, baseDir, settingsFile)
	// ⚡ Inject JARVIS Proactive Alert Voice callback — bridges main package func into api sub-package
	apiHandler.ProactiveAlertFn = TriggerJarvisProactiveAnnounce
	authHandler := auth.NewHandler(dbConn, dashboardRedisClient)
	incidentHandler := incident.NewHandler(dbConn, dashboardRedisClient, dashboardNatsConn, baseDir)
	topologyHandler := topology.NewHandler(dbConn)
	metricsHandler := metrics.NewHandler(dbConn, dashboardRedisClient)
	websocketHandler := wsPkg.NewHandler(dbConn)


	// Register sub-package routes
	apiHandler.RegisterRoutes(r)
	authHandler.RegisterRoutes(r)
	incidentHandler.RegisterRoutes(r)
	topologyHandler.RegisterRoutes(r)
	metricsHandler.RegisterRoutes(r)
	websocketHandler.RegisterRoutes(r)

	// Legacy WS Chat
	r.GET("/ws/chat", func(c *gin.Context) {
		handleDashboardWebSocket(c, dbConn)
	})
	r.GET("/api/dashboard_chat/sessions", func(c *gin.Context) {
		handleGetChatSessions(c, dbConn)
	})
	r.POST("/api/dashboard_chat/sessions/status/:client_id", func(c *gin.Context) {
		handleUpdateSessionStatus(c, dbConn)
	})
	r.GET("/api/dashboard_chat/history/:client_id", func(c *gin.Context) {
		handleGetChatHistory(c, dbConn)
	})

	// Enterprise Chat Engine
	supervisor := ai.NewAISupervisor(dbConn)
	RegisterChatEngineRoutes(r, dbConn, dashboardRedisClient, supervisor)

	// Module 11: Enterprise Asset Graph APIs
	RegisterAssetRoutes(r, dbConn)
	
	// Sprint B: Predictive Intelligence APIs
	RegisterPredictiveRoutes(r, dbConn)

	// Multi-Agent Consensus (Sprint N)
	RegisterMultiAgentRoutes(r, dbConn)

	// Cognitive Memory & Knowledge Graph (Sprint M)
	RegisterCognitiveMemoryRoutes(r, dbConn)

	// Sprint O: AI Governance Dashboard APIs (READ-ONLY)
	registerSprintORoutes(r, dbConn)

	// FIX-1B: JARVIS Voice API Proxy Routes (bridges browser → Python JarvisVoiceAPIServer)
	RegisterJarvisAPIRoutes(r)

	// Start server
	port := "9999"
	if envPort := os.Getenv("PORT"); envPort != "" {
		port = envPort
	}
	fmt.Printf("[DASHBOARD] Starting NOC HTTP Server on 0.0.0.0:%s...\n", port)
	if err = r.Run("0.0.0.0:" + port); err != nil {
		return fmt.Errorf("[ERROR] Server failed: %w", err)
	}
	return nil
}
