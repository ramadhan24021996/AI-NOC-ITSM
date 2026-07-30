package api

import (
	"net/http"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

// ── 1. PostgreSQL GORM Models for Enterprise Browser Monitoring ───────────────

type BrowserSession struct {
	SessionUUID       string     `gorm:"primaryKey;column:session_uuid;type:uuid;default:gen_random_uuid()" json:"session_uuid"`
	DeviceID          string     `gorm:"column:device_id;type:varchar(128);index" json:"device_id"`
	PCName            string     `gorm:"column:pc_name;type:varchar(128);index" json:"pc_name"`
	UserName          string     `gorm:"column:user_name;type:varchar(128)" json:"user_name"`
	BrowserName       string     `gorm:"column:browser_name;type:varchar(64);index" json:"browser_name"`
	BrowserExecutable string     `gorm:"column:browser_executable;type:varchar(255)" json:"browser_executable"`
	PID               int        `gorm:"column:pid" json:"pid"`
	UserProfile       string     `gorm:"column:user_profile;type:varchar(128)" json:"user_profile"`
	StartedAt         time.Time  `gorm:"column:started_at;index" json:"started_at"`
	ClosedAt          *time.Time `gorm:"column:closed_at" json:"closed_at,omitempty"`
	Status            string     `gorm:"column:status;type:varchar(32);default:'active'" json:"status"`
	TotalTabs         int        `gorm:"column:total_tabs;default:0" json:"total_tabs"`
	TotalWindows      int        `gorm:"column:total_windows;default:0" json:"total_windows"`
	CPUUsage          float64    `gorm:"column:cpu_usage;type:numeric(5,2)" json:"cpu_usage"`
	MemoryBytes       int64      `gorm:"column:memory_bytes" json:"memory_bytes"`
	CreatedAt         time.Time  `gorm:"column:created_at;autoCreateTime" json:"created_at"`
	UpdatedAt         time.Time  `gorm:"column:updated_at;autoUpdateTime" json:"updated_at"`
}

func (BrowserSession) TableName() string {
	return "browser_sessions"
}

type BrowserTab struct {
	TabUUID           string    `gorm:"primaryKey;column:tab_uuid;type:uuid;default:gen_random_uuid()" json:"tab_uuid"`
	DeviceID          string    `gorm:"column:device_id;type:varchar(128);index" json:"device_id"`
	PCName            string    `gorm:"column:pc_name;type:varchar(128);index" json:"pc_name"`
	SessionUUID       string    `gorm:"column:session_uuid;type:uuid;index" json:"session_uuid"`
	BrowserName       string    `gorm:"column:browser_name;type:varchar(64);index" json:"browser_name"`
	PID               int       `gorm:"column:pid" json:"pid"`
	WindowID          int       `gorm:"column:window_id" json:"window_id"`
	TabID             int       `gorm:"column:tab_id" json:"tab_id"`
	Title             string    `gorm:"column:title;type:text" json:"title"`
	URL               string    `gorm:"column:url;type:text" json:"url"`
	Domain            string    `gorm:"column:domain;type:varchar(255);index" json:"domain"`
	Protocol          string    `gorm:"column:protocol;type:varchar(16);default:'https'" json:"protocol"`
	Category          string    `gorm:"column:category;type:varchar(64);index;default:'Unknown'" json:"category"`
	IsActive          bool      `gorm:"column:is_active;default:false" json:"is_active"`
	IsFocused         bool      `gorm:"column:is_focused;default:false" json:"is_focused"`
	IsPinned          bool      `gorm:"column:is_pinned;default:false" json:"is_pinned"`
	IsMuted           bool      `gorm:"column:is_muted;default:false" json:"is_muted"`
	IsIncognito       bool      `gorm:"column:is_incognito;default:false" json:"is_incognito"`
	Status            string    `gorm:"column:status;type:varchar(32);default:'open'" json:"status"` // open, loading, suspended, crashed, discarded
	OpenedAt          time.Time `gorm:"column:opened_at;index" json:"opened_at"`
	LastActivityAt    time.Time `gorm:"column:last_activity_at;index" json:"last_activity_at"`
	DurationSeconds   int       `gorm:"column:duration_seconds;default:0" json:"duration_seconds"`
	IdleSeconds       int       `gorm:"column:idle_seconds;default:0" json:"idle_seconds"`
	CPUUsage          float64   `gorm:"column:cpu_usage;type:numeric(5,2)" json:"cpu_usage"`
	MemoryBytes       int64     `gorm:"column:memory_bytes" json:"memory_bytes"`
	BandwidthUpKbps   float64   `gorm:"column:bandwidth_up_kbps;type:numeric(10,2)" json:"bandwidth_up_kbps"`
	BandwidthDownKbps float64   `gorm:"column:bandwidth_down_kbps;type:numeric(10,2)" json:"bandwidth_down_kbps"`
	Favicon           string    `gorm:"column:favicon;type:text" json:"favicon"`
	Referrer          string    `gorm:"column:referrer;type:text" json:"referrer"`
	SSLVersion        string    `gorm:"column:ssl_version;type:varchar(32)" json:"ssl_version"`
	CertIssuer        string    `gorm:"column:cert_issuer;type:varchar(255)" json:"cert_issuer"`
	ResponseTimeMs    int       `gorm:"column:response_time_ms;default:0" json:"response_time_ms"`
	CreatedAt         time.Time `gorm:"column:created_at;autoCreateTime" json:"created_at"`
	UpdatedAt         time.Time `gorm:"column:updated_at;autoUpdateTime" json:"updated_at"`
}

func (BrowserTab) TableName() string {
	return "browser_tabs"
}

type BrowserHistory struct {
	HistoryID       int64     `gorm:"primaryKey;column:history_id;autoIncrement" json:"history_id"`
	DeviceID        string    `gorm:"column:device_id;type:varchar(128);index" json:"device_id"`
	PCName          string    `gorm:"column:pc_name;type:varchar(128);index" json:"pc_name"`
	UserName        string    `gorm:"column:user_name;type:varchar(128)" json:"user_name"`
	BrowserName     string    `gorm:"column:browser_name;type:varchar(64);index" json:"browser_name"`
	URL             string    `gorm:"column:url;type:text" json:"url"`
	Domain          string    `gorm:"column:domain;type:varchar(255);index" json:"domain"`
	Title           string    `gorm:"column:title;type:text" json:"title"`
	Category        string    `gorm:"column:category;type:varchar(64);index" json:"category"`
	VisitedAt       time.Time `gorm:"column:visited_at;index" json:"visited_at"`
	DurationSeconds int       `gorm:"column:duration_seconds;default:0" json:"duration_seconds"`
	Referrer        string    `gorm:"column:referrer;type:text" json:"referrer"`
}

func (BrowserHistory) TableName() string {
	return "browser_history"
}

type BrowserEvent struct {
	EventID     int64     `gorm:"primaryKey;column:event_id;autoIncrement" json:"event_id"`
	DeviceID    string    `gorm:"column:device_id;type:varchar(128);index" json:"device_id"`
	PCName      string    `gorm:"column:pc_name;type:varchar(128);index" json:"pc_name"`
	EventType   string    `gorm:"column:event_type;type:varchar(64);index" json:"event_type"` // tab_opened, tab_closed, tab_switched, url_changed, window_focus, window_blur, browser_started, browser_closed
	BrowserName string    `gorm:"column:browser_name;type:varchar(64)" json:"browser_name"`
	TabUUID     string    `gorm:"column:tab_uuid;type:uuid" json:"tab_uuid"`
	URL         string    `gorm:"column:url;type:text" json:"url"`
	Title       string    `gorm:"column:title;type:text" json:"title"`
	Timestamp   time.Time `gorm:"column:timestamp;index" json:"timestamp"`
}

func (BrowserEvent) TableName() string {
	return "browser_events"
}

type BrowserUsageStat struct {
	StatID               int64     `gorm:"primaryKey;column:stat_id;autoIncrement" json:"stat_id"`
	DeviceID             string    `gorm:"column:device_id;type:varchar(128);index" json:"device_id"`
	Date                 time.Time `gorm:"column:date;type:date;index" json:"date"`
	Domain               string    `gorm:"column:domain;type:varchar(255);index" json:"domain"`
	Category             string    `gorm:"column:category;type:varchar(64);index" json:"category"`
	TotalDurationSeconds int64     `gorm:"column:total_duration_seconds;default:0" json:"total_duration_seconds"`
	VisitCount           int       `gorm:"column:visit_count;default:0" json:"visit_count"`
	TotalBandwidthBytes  int64     `gorm:"column:total_bandwidth_bytes;default:0" json:"total_bandwidth_bytes"`
}

func (BrowserUsageStat) TableName() string {
	return "browser_usage_statistics"
}

type BrowserNavigation struct {
	NavID          int64     `gorm:"primaryKey;column:nav_id;autoIncrement" json:"nav_id"`
	TabUUID        string    `gorm:"column:tab_uuid;type:uuid;index" json:"tab_uuid"`
	FromURL        string    `gorm:"column:from_url;type:text" json:"from_url"`
	ToURL          string    `gorm:"column:to_url;type:text" json:"to_url"`
	TransitionType string    `gorm:"column:transition_type;type:varchar(64)" json:"transition_type"`
	Timestamp      time.Time `gorm:"column:timestamp;index" json:"timestamp"`
	SSLVersion     string    `gorm:"column:ssl_version;type:varchar(32)" json:"ssl_version"`
	CertIssuer     string    `gorm:"column:cert_issuer;type:varchar(255)" json:"cert_issuer"`
}

func (BrowserNavigation) TableName() string {
	return "browser_navigation"
}

// ── 2. Automatic URL Domain Classifier Engine ───────────────────────────────

func ClassifyURLDomain(domain string) string {
	d := strings.ToLower(strings.TrimSpace(domain))
	if d == "" {
		return "Unknown"
	}

	// Remove port if present
	if idx := strings.Index(d, ":"); idx != -1 {
		d = d[:idx]
	}

	// 1. Internal & Localhost
	if d == "localhost" || strings.HasPrefix(d, "127.") || strings.HasPrefix(d, "10.") ||
		strings.HasPrefix(d, "192.168.") || strings.HasSuffix(d, ".local") || strings.HasSuffix(d, ".internal") {
		return "Internal"
	}

	// 2. Monitoring & AIOps
	if strings.Contains(d, "grafana") || strings.Contains(d, "prometheus") || strings.Contains(d, "zabbix") ||
		strings.Contains(d, "kibana") || strings.Contains(d, "datadog") || strings.Contains(d, "newrelic") ||
		strings.Contains(d, "dynatrace") || strings.Contains(d, "splunk") {
		return "Monitoring"
	}

	// 3. AI & LLM Tools
	if strings.Contains(d, "openai.com") || strings.Contains(d, "chatgpt.com") || strings.Contains(d, "claude.ai") ||
		strings.Contains(d, "gemini.google.com") || strings.Contains(d, "huggingface.co") || strings.Contains(d, "anthropic.com") ||
		strings.Contains(d, "perplexity.ai") || strings.Contains(d, "midjourney.com") {
		return "AI"
	}

	// 4. Development, Git & Repositories
	if strings.Contains(d, "github.com") || strings.Contains(d, "gitlab.com") || strings.Contains(d, "bitbucket.org") ||
		strings.Contains(d, "stackoverflow.com") || strings.Contains(d, "npmjs.com") || strings.Contains(d, "pypi.org") ||
		strings.Contains(d, "docker.com") || strings.Contains(d, "pkg.go.dev") {
		return "Development"
	}

	// 5. Database Tools
	if strings.Contains(d, "pgadmin") || strings.Contains(d, "phpmyadmin") || strings.Contains(d, "dbeaver") ||
		strings.Contains(d, "mongodb.com") || strings.Contains(d, "supabase.com") {
		return "Database"
	}

	// 6. Cloud Services
	if strings.Contains(d, "aws.amazon.com") || strings.Contains(d, "azure.microsoft.com") ||
		strings.Contains(d, "console.cloud.google.com") || strings.Contains(d, "digitalocean.com") ||
		strings.Contains(d, "cloudflare.com") || strings.Contains(d, "heroku.com") {
		return "Cloud"
	}

	// 7. Security & Vault
	if strings.Contains(d, "passbolt") || strings.Contains(d, "vault") || strings.Contains(d, "1password.com") ||
		strings.Contains(d, "lastpass.com") || strings.Contains(d, "bitwarden.com") || strings.Contains(d, "crowdstrike.com") {
		return "Security"
	}

	// 8. Office, Collaboration & Docs
	if strings.Contains(d, "docs.google.com") || strings.Contains(d, "office.com") || strings.Contains(d, "sharepoint.com") ||
		strings.Contains(d, "notion.so") || strings.Contains(d, "confluence") || strings.Contains(d, "jira") ||
		strings.Contains(d, "trello.com") || strings.Contains(d, "slack.com") || strings.Contains(d, "teams.microsoft.com") {
		return "Office"
	}

	// 9. Email
	if strings.Contains(d, "mail.google.com") || strings.Contains(d, "outlook.live.com") || strings.Contains(d, "proton.me") ||
		strings.Contains(d, "webmail") {
		return "Email"
	}

	// 10. Business & Core Applications
	if strings.Contains(d, "sams.id") || strings.Contains(d, "salesforce.com") || strings.Contains(d, "sap.com") ||
		strings.Contains(d, "workday.com") || strings.Contains(d, "zoho.com") || strings.Contains(d, "hubspot.com") {
		return "Business"
	}

	// 11. Social Media
	if strings.Contains(d, "facebook.com") || strings.Contains(d, "instagram.com") || strings.Contains(d, "linkedin.com") ||
		strings.Contains(d, "twitter.com") || strings.Contains(d, "x.com") || strings.Contains(d, "tiktok.com") ||
		strings.Contains(d, "reddit.com") {
		return "Social Media"
	}

	// 12. Streaming & Media
	if strings.Contains(d, "youtube.com") || strings.Contains(d, "netflix.com") || strings.Contains(d, "spotify.com") ||
		strings.Contains(d, "twitch.tv") || strings.Contains(d, "vimeo.com") {
		return "Streaming"
	}

	// 13. Finance & Banking
	if strings.Contains(d, "bca.co.id") || strings.Contains(d, "mandiri.co.id") || strings.Contains(d, "paypal.com") ||
		strings.Contains(d, "stripe.com") || strings.Contains(d, "bank") {
		return "Finance"
	}

	return "Business"
}

// ── 3. Database Auto Migration Function ─────────────────────────────────────

func AutoMigrateBrowserTables(db *gorm.DB) error {
	if db == nil {
		return nil
	}
	return db.AutoMigrate(
		&BrowserSession{},
		&BrowserTab{},
		&BrowserHistory{},
		&BrowserEvent{},
		&BrowserUsageStat{},
		&BrowserNavigation{},
	)
}

// ── 4. Telemetry Submission Handler (POST /api/telemetry/browser_tabs) ─────

type TabTelemetryPayload struct {
	DeviceID   string                 `json:"device_id"`
	PCName     string                 `json:"pc_name"`
	UserName   string                 `json:"user_name"`
	Browsers   []BrowserTelemetryItem `json:"browsers"`
	ActiveTabs []TabTelemetryItem     `json:"active_tabs"`
	Timestamp  int64                  `json:"timestamp"`
}

type BrowserTelemetryItem struct {
	BrowserName string  `json:"browser_name"`
	Executable  string  `json:"executable"`
	PID         int     `json:"pid"`
	UserProfile string  `json:"user_profile"`
	TotalTabs   int     `json:"total_tabs"`
	CPUUsage    float64 `json:"cpu_usage"`
	MemoryBytes int64   `json:"memory_bytes"`
}

type TabTelemetryItem struct {
	BrowserName       string  `json:"browser_name"`
	PID               int     `json:"pid"`
	WindowID          int     `json:"window_id"`
	TabID             int     `json:"tab_id"`
	Title             string  `json:"title"`
	URL               string  `json:"url"`
	Domain            string  `json:"domain"`
	Protocol          string  `json:"protocol"`
	IsActive          bool    `json:"is_active"`
	IsFocused         bool    `json:"is_focused"`
	IsPinned          bool    `json:"is_pinned"`
	IsMuted           bool    `json:"is_muted"`
	IsIncognito       bool    `json:"is_incognito"`
	Status            string  `json:"status"`
	OpenedAt          int64   `json:"opened_at"`
	LastActivityAt    int64   `json:"last_activity_at"`
	DurationSeconds   int     `json:"duration_seconds"`
	IdleSeconds       int     `json:"idle_seconds"`
	CPUUsage          float64 `json:"cpu_usage"`
	MemoryBytes       int64   `json:"memory_bytes"`
	BandwidthUpKbps   float64 `json:"bandwidth_up_kbps"`
	BandwidthDownKbps float64 `json:"bandwidth_down_kbps"`
	Favicon           string  `json:"favicon"`
	Referrer          string  `json:"referrer"`
}

func (h *Handler) SubmitBrowserTelemetry(c *gin.Context) {
	var payload TabTelemetryPayload
	if err := c.ShouldBindJSON(&payload); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": "Invalid telemetry JSON: " + err.Error()})
		return
	}

	if payload.PCName == "" && payload.DeviceID != "" {
		payload.PCName = payload.DeviceID
	}
	if payload.DeviceID == "" && payload.PCName != "" {
		payload.DeviceID = payload.PCName
	}

	now := time.Now()

	if h.db != nil {
		// Auto Migrate tables if needed
		_ = AutoMigrateBrowserTables(h.db)

		// 1. Process Browser Sessions
		for _, b := range payload.Browsers {
			var sess BrowserSession
			err := h.db.Where("device_id = ? AND pid = ? AND status = 'active'", payload.DeviceID, b.PID).First(&sess).Error
			if err != nil {
				// Create new session
				sess = BrowserSession{
					DeviceID:          payload.DeviceID,
					PCName:            payload.PCName,
					UserName:          payload.UserName,
					BrowserName:       b.BrowserName,
					BrowserExecutable: b.Executable,
					PID:               b.PID,
					UserProfile:       b.UserProfile,
					StartedAt:         now,
					Status:            "active",
					TotalTabs:         b.TotalTabs,
					CPUUsage:          b.CPUUsage,
					MemoryBytes:       b.MemoryBytes,
				}
				h.db.Create(&sess)
			} else {
				// Update existing session metrics
				h.db.Model(&sess).Updates(map[string]interface{}{
					"total_tabs":   b.TotalTabs,
					"cpu_usage":    b.CPUUsage,
					"memory_bytes": b.MemoryBytes,
					"updated_at":   now,
				})
			}
		}

		// 2. Process Tabs
		for _, t := range payload.ActiveTabs {
			domain := strings.TrimSpace(t.Domain)
			if domain == "" && t.URL != "" {
				// Extract domain from URL
				parts := strings.Split(t.URL, "/")
				if len(parts) >= 3 {
					domain = parts[2]
				}
			}
			category := ClassifyURLDomain(domain)
			proto := strings.ToLower(t.Protocol)
			if proto == "" && strings.HasPrefix(t.URL, "https://") {
				proto = "https"
			} else if proto == "" && strings.HasPrefix(t.URL, "http://") {
				proto = "http"
			}

			openedTime := time.Unix(t.OpenedAt, 0)
			if t.OpenedAt == 0 {
				openedTime = now
			}
			lastActTime := time.Unix(t.LastActivityAt, 0)
			if t.LastActivityAt == 0 {
				lastActTime = now
			}

			var existingTab BrowserTab
			err := h.db.Where("device_id = ? AND browser_name = ? AND window_id = ? AND tab_id = ?",
				payload.DeviceID, t.BrowserName, t.WindowID, t.TabID).First(&existingTab).Error

			if err != nil {
				// Create new tab record
				newTab := BrowserTab{
					DeviceID:          payload.DeviceID,
					PCName:            payload.PCName,
					BrowserName:       t.BrowserName,
					PID:               t.PID,
					WindowID:          t.WindowID,
					TabID:             t.TabID,
					Title:             t.Title,
					URL:               t.URL,
					Domain:            domain,
					Protocol:          proto,
					Category:          category,
					IsActive:          t.IsActive,
					IsFocused:         t.IsFocused,
					IsPinned:          t.IsPinned,
					IsMuted:           t.IsMuted,
					IsIncognito:       t.IsIncognito,
					Status:            t.Status,
					OpenedAt:          openedTime,
					LastActivityAt:    lastActTime,
					DurationSeconds:   t.DurationSeconds,
					IdleSeconds:       t.IdleSeconds,
					CPUUsage:          t.CPUUsage,
					MemoryBytes:       t.MemoryBytes,
					BandwidthUpKbps:   t.BandwidthUpKbps,
					BandwidthDownKbps: t.BandwidthDownKbps,
					Favicon:           t.Favicon,
					Referrer:          t.Referrer,
				}
				h.db.Create(&newTab)

				// Record Tab Opened Event
				h.db.Create(&BrowserEvent{
					DeviceID:    payload.DeviceID,
					PCName:      payload.PCName,
					EventType:   "tab_opened",
					BrowserName: t.BrowserName,
					TabUUID:     newTab.TabUUID,
					URL:         t.URL,
					Title:       t.Title,
					Timestamp:   now,
				})
			} else {
				// Detect URL change
				if existingTab.URL != t.URL {
					h.db.Create(&BrowserEvent{
						DeviceID:    payload.DeviceID,
						PCName:      payload.PCName,
						EventType:   "url_changed",
						BrowserName: t.BrowserName,
						TabUUID:     existingTab.TabUUID,
						URL:         t.URL,
						Title:       t.Title,
						Timestamp:   now,
					})
					h.db.Create(&BrowserNavigation{
						TabUUID:        existingTab.TabUUID,
						FromURL:        existingTab.URL,
						ToURL:          t.URL,
						TransitionType: "link",
						Timestamp:      now,
					})
				}

				// Update Tab Record
				h.db.Model(&existingTab).Updates(map[string]interface{}{
					"title":               t.Title,
					"url":                 t.URL,
					"domain":              domain,
					"protocol":            proto,
					"category":            category,
					"is_active":           t.IsActive,
					"is_focused":          t.IsFocused,
					"is_pinned":           t.IsPinned,
					"is_muted":            t.IsMuted,
					"is_incognito":        t.IsIncognito,
					"status":              t.Status,
					"last_activity_at":    lastActTime,
					"duration_seconds":    t.DurationSeconds,
					"idle_seconds":        t.IdleSeconds,
					"cpu_usage":           t.CPUUsage,
					"memory_bytes":        t.MemoryBytes,
					"bandwidth_up_kbps":   t.BandwidthUpKbps,
					"bandwidth_down_kbps": t.BandwidthDownKbps,
					"updated_at":          now,
				})
			}
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"status":  "success",
		"message": "Browser telemetry ingested successfully",
		"count":   len(payload.ActiveTabs),
	})
}

// ── 5. Get Live Browser Tabs Endpoint (GET /api/browser_monitoring/live) ────

func (h *Handler) GetLiveBrowserTabs(c *gin.Context) {
	deviceName := strings.TrimSpace(c.Query("device"))
	search := strings.TrimSpace(c.Query("search"))
	category := strings.TrimSpace(c.Query("category"))
	browser := strings.TrimSpace(c.Query("browser"))

	var tabs []BrowserTab

	if h.db != nil {
		_ = AutoMigrateBrowserTables(h.db)
		q := h.db.Order("is_focused DESC, last_activity_at DESC")
		if deviceName != "" {
			q = q.Where("pc_name = ? OR device_id = ?", deviceName, deviceName)
		}
		if category != "" {
			q = q.Where("category = ?", category)
		}
		if browser != "" {
			q = q.Where("LOWER(browser_name) LIKE ?", "%"+strings.ToLower(browser)+"%")
		}
		if search != "" {
			s := "%" + strings.ToLower(search) + "%"
			q = q.Where("LOWER(title) LIKE ? OR LOWER(url) LIKE ? OR LOWER(domain) LIKE ?", s, s, s)
		}
		q.Limit(200).Find(&tabs)
	}

	c.JSON(http.StatusOK, gin.H{
		"status": "success",
		"count":  len(tabs),
		"data":   tabs,
	})
}

// ── 6. Get Browser Summary Endpoint (GET /api/browser_monitoring/summary) ──

func (h *Handler) GetBrowserSummary(c *gin.Context) {
	deviceName := strings.TrimSpace(c.Query("device"))

	summary := gin.H{
		"total_tabs":      0,
		"focused_tabs":    0,
		"background_tabs": 0,
		"incognito_tabs":  0,
		"browsers": gin.H{
			"chrome":  0,
			"firefox": 0,
			"edge":    0,
			"opera":   0,
			"brave":   0,
			"vivaldi": 0,
			"other":   0,
		},
	}

	if h.db != nil {
		_ = AutoMigrateBrowserTables(h.db)
		var tabs []BrowserTab
		q := h.db.Model(&BrowserTab{})
		if deviceName != "" {
			q = q.Where("pc_name = ? OR device_id = ?", deviceName, deviceName)
		}
		q.Find(&tabs)

		total := len(tabs)
		focused := 0
		background := 0
		incognito := 0
		bCounts := map[string]int{"chrome": 0, "firefox": 0, "edge": 0, "opera": 0, "brave": 0, "vivaldi": 0, "other": 0}

		for _, t := range tabs {
			if t.IsFocused {
				focused++
			} else {
				background++
			}
			if t.IsIncognito {
				incognito++
			}
			bn := strings.ToLower(t.BrowserName)
			if strings.Contains(bn, "chrome") {
				bCounts["chrome"]++
			} else if strings.Contains(bn, "firefox") {
				bCounts["firefox"]++
			} else if strings.Contains(bn, "edge") {
				bCounts["edge"]++
			} else if strings.Contains(bn, "opera") {
				bCounts["opera"]++
			} else if strings.Contains(bn, "brave") {
				bCounts["brave"]++
			} else if strings.Contains(bn, "vivaldi") {
				bCounts["vivaldi"]++
			} else {
				bCounts["other"]++
			}
		}

		summary["total_tabs"] = total
		summary["focused_tabs"] = focused
		summary["background_tabs"] = background
		summary["incognito_tabs"] = incognito
		summary["browsers"] = bCounts
	}

	c.JSON(http.StatusOK, gin.H{
		"status": "success",
		"data":   summary,
	})
}

// ── 7. Get Browser Timeline Endpoint (GET /api/browser_monitoring/timeline) ─

func (h *Handler) GetBrowserTimeline(c *gin.Context) {
	deviceName := strings.TrimSpace(c.Query("device"))
	var events []BrowserEvent

	if h.db != nil {
		_ = AutoMigrateBrowserTables(h.db)
		q := h.db.Order("timestamp DESC").Limit(50)
		if deviceName != "" {
			q = q.Where("pc_name = ? OR device_id = ?", deviceName, deviceName)
		}
		q.Find(&events)
	}

	c.JSON(http.StatusOK, gin.H{
		"status": "success",
		"count":  len(events),
		"data":   events,
	})
}

// ── 8. Get Browser Analytics Endpoint (GET /api/browser_monitoring/analytics) ─

func (h *Handler) GetBrowserAnalytics(c *gin.Context) {
	deviceName := strings.TrimSpace(c.Query("device"))

	type DomainGroup struct {
		Domain     string `json:"domain"`
		Category   string `json:"category"`
		TotalCount int    `json:"total_count"`
	}

	var topDomains []DomainGroup

	if h.db != nil {
		_ = AutoMigrateBrowserTables(h.db)
		q := h.db.Model(&BrowserTab{}).
			Select("domain, category, count(*) as total_count").
			Group("domain, category").
			Order("total_count DESC").
			Limit(10)
		if deviceName != "" {
			q = q.Where("pc_name = ? OR device_id = ?", deviceName, deviceName)
		}
		q.Scan(&topDomains)
	}

	c.JSON(http.StatusOK, gin.H{
		"status": "success",
		"data": gin.H{
			"top_domains": topDomains,
		},
	})
}

// ── 9. Get Tab Detail Endpoint (GET /api/browser_monitoring/tab_detail/:uuid) ─

func (h *Handler) GetBrowserTabDetail(c *gin.Context) {
	tabUUID := strings.TrimSpace(c.Param("uuid"))
	var tab BrowserTab
	var navs []BrowserNavigation

	if h.db != nil {
		_ = AutoMigrateBrowserTables(h.db)
		if err := h.db.Where("tab_uuid = ?", tabUUID).First(&tab).Error; err != nil {
			c.JSON(http.StatusNotFound, gin.H{"status": "error", "message": "Tab not found"})
			return
		}
		h.db.Where("tab_uuid = ?", tabUUID).Order("timestamp DESC").Limit(20).Find(&navs)
	}

	c.JSON(http.StatusOK, gin.H{
		"status":     "success",
		"tab":        tab,
		"navigation": navs,
	})
}
