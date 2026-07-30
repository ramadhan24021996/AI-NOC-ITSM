package database

import (
	"fmt"
	"os"
	"strings"
	"time"

	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"

	"go_incident_analysis/SERVER/go_core/security"
)

// DB holds the global GORM database connection
var DB *gorm.DB

type FleetSite struct {
	SiteID            string    `gorm:"type:text;primaryKey;column:site_id" json:"site_id"`
	SiteName          string    `gorm:"type:text;not null;column:site_name" json:"site_name"`
	RouterIP          string    `gorm:"type:text;column:router_ip" json:"router_ip"`
	RouterPort        int       `gorm:"column:router_port;default:10001" json:"router_port"`
	DNSPrimary        string    `gorm:"type:text;column:dns_primary" json:"dns_primary"`
	DNSSecondary      string    `gorm:"type:text;column:dns_secondary" json:"dns_secondary"`
	DefaultRemoteTool string         `gorm:"type:text;column:default_remote_tool;default:'rustdesk'" json:"default_remote_tool"`
	CreatedAt         time.Time      `gorm:"column:created_at;autoCreateTime" json:"created_at"`
	DeletedAt         gorm.DeletedAt `gorm:"index" json:"deleted_at,omitempty"`
}

func (FleetSite) TableName() string {
	return "fleet_sites"
}

type FleetPrinter struct {
	PrinterID  uint      `gorm:"primaryKey;column:printer_id;autoIncrement" json:"printer_id"`
	SiteID     *string   `gorm:"column:site_id" json:"site_id"`
	PCName     *string   `gorm:"column:pc_name" json:"pc_name"`
	Name       string    `gorm:"column:name;not null" json:"name"`
	Model      string    `gorm:"column:model;default:''" json:"model"`
	IP         string    `gorm:"column:ip;not null" json:"ip"`
	Port       int       `gorm:"column:port;default:9100" json:"port"`
	Status     string    `gorm:"column:status;default:'UNKNOWN'" json:"status"`
	TonerPct   int       `gorm:"column:toner_pct;default:0" json:"toner_pct"`
	InkPct     int       `gorm:"column:ink_pct;default:0" json:"ink_pct"`
	QueueCount int       `gorm:"column:queue_count;default:0" json:"queue_count"`
	PaperCount int       `gorm:"column:paper_count;default:0" json:"paper_count"`
	ErrorMsg   string    `gorm:"column:error_msg;default:''" json:"error_msg"`
	LastPinged time.Time `gorm:"column:last_pinged" json:"last_pinged"`
	UpdatedAt  time.Time `gorm:"column:updated_at;autoUpdateTime" json:"updated_at"`
}

func (FleetPrinter) TableName() string {
	return "fleet_printers"
}

type FleetDevice struct {
	PCName           string    `gorm:"type:text;primaryKey;column:pc_name" json:"pc_name"`
	SiteID           *string   `gorm:"type:text;column:site_id" json:"site_id"`
	Status           string    `gorm:"type:text;default:'PENDING';column:status" json:"status"`
	IsApproved       bool      `gorm:"column:is_approved;default:false" json:"is_approved"`
	HardwareInfo     string    `gorm:"type:jsonb;column:hardware_info" json:"hardware_info"` // stored as raw JSON string
	LastSeen         time.Time `gorm:"column:last_seen;autoCreateTime" json:"last_seen"`
	ConfigVersion    int       `gorm:"column:config_version;default:0" json:"config_version"`
	RustdeskID       string    `gorm:"type:text;column:rustdesk_id" json:"rustdesk_id"`
	RustdeskVersion  string    `gorm:"type:text;column:rustdesk_version" json:"rustdesk_version"`
	RustdeskRunning  bool      `gorm:"column:rustdesk_running;default:false" json:"rustdesk_running"`
	IP               string    `gorm:"column:ip" json:"ip"`
	Hostname         string    `gorm:"column:hostname" json:"hostname"`
	Online           bool      `gorm:"column:online;default:false" json:"online"`
	TelemetryVersion string    `gorm:"column:telemetry_version" json:"telemetry_version"`
	AgentCollectedAt time.Time      `gorm:"column:agent_collected_at" json:"agent_collected_at"`
	OSVersion        string         `gorm:"column:os_version" json:"os_version"`
	DeletedAt        gorm.DeletedAt `gorm:"index" json:"deleted_at,omitempty"`
}

func (FleetDevice) TableName() string {
	return "fleet_devices"
}

type RemoteSession struct {
	SessionID  uint       `gorm:"primaryKey;column:session_id;autoIncrement" json:"session_id"`
	IncidentID *int       `gorm:"column:incident_id" json:"incident_id"`
	DeviceID   string     `gorm:"type:text;not null;column:device_id" json:"device_id"`
	Operator   string     `gorm:"type:text;not null;column:operator" json:"operator"`
	StartTime  time.Time  `gorm:"column:start_time;autoCreateTime" json:"start_time"`
	EndTime    *time.Time `gorm:"column:end_time" json:"end_time"`
	Duration   *int       `gorm:"column:duration" json:"duration"`
	Status     string     `gorm:"type:text;default:'ACTIVE';column:status" json:"status"`
	Reason     string     `gorm:"type:text;column:reason" json:"reason"`
	CreatedAt  time.Time  `gorm:"column:created_at;autoCreateTime" json:"created_at"`
}

func (RemoteSession) TableName() string {
	return "remote_sessions"
}

// Device represents infrastructure devices (routers, switches)
type Device struct {
	DeviceID uint   `gorm:"primaryKey;column:device_id;autoIncrement" json:"device_id"`
	Name     string `gorm:"type:text;unique;not null;column:name" json:"name"`
	IP       string `gorm:"type:text;column:ip" json:"ip"`
	Layer    int    `gorm:"column:layer" json:"layer"`
	Location string         `gorm:"type:text;column:location" json:"location"`
	Status   string         `gorm:"type:text;default:'ONLINE';column:status" json:"status"`
	Metadata string         `gorm:"type:jsonb;column:metadata" json:"metadata"` // stored as raw JSON string
	DeletedAt gorm.DeletedAt `gorm:"index" json:"deleted_at,omitempty"`
}

func (Device) TableName() string {
	return "devices"
}

type ChatSession struct {
	ID        uint      `gorm:"primaryKey;column:id;autoIncrement" json:"id"`
	ClientID  string    `gorm:"type:text;uniqueIndex;column:client_id" json:"client_id"`
	PCName    string    `gorm:"type:text;column:pc_name" json:"pc_name"`
	Status    string    `gorm:"type:text;default:'OPEN';column:status" json:"status"` // OPEN, WAITING_OPERATOR, ACTIVE, CLOSED
	Metadata  string    `gorm:"type:jsonb;column:metadata" json:"metadata"`
	CreatedAt time.Time `gorm:"column:created_at;autoCreateTime" json:"created_at"`
	UpdatedAt time.Time `gorm:"column:updated_at;autoUpdateTime" json:"updated_at"`
}

func (ChatSession) TableName() string {
	return "chat_sessions"
}

type ChatMessage struct {
	ID             uint      `gorm:"primaryKey;column:id;autoIncrement" json:"id"`
	ClientID       string    `gorm:"type:text;index;column:client_id" json:"client_id"`
	Sender         string    `gorm:"type:text;column:sender" json:"sender"` // CLIENT, OPERATOR, SYSTEM, AI_HYPOTHESIS
	Message        string    `gorm:"type:text;column:message" json:"message"`
	AttachmentPath string    `gorm:"type:text;column:attachment_path" json:"attachment_path"`        // Comma-separated paths
	ReadStatus     string    `gorm:"type:text;default:'SENT';column:read_status" json:"read_status"` // SENT, DELIVERED, READ
	IncidentID     int       `gorm:"column:incident_id" json:"incident_id"`
	ThreadType     string    `gorm:"column:thread_type;default:'SUPPORT'" json:"thread_type"`
	IsSystemMsg    bool      `gorm:"column:is_system_msg;default:false" json:"is_system_msg"`
	CreatedAt      time.Time `gorm:"column:created_at;primaryKey;autoCreateTime" json:"created_at"`
}

func (ChatMessage) TableName() string {
	return "chat_messages"
}

type TelegramChatMapping struct {
	ID                uint      `gorm:"primaryKey;column:id;autoIncrement"`
	TelegramMessageID int64     `gorm:"uniqueIndex;column:telegram_message_id"`
	ClientID          string    `gorm:"type:text;index;column:client_id"`
	ChatMessageID     uint      `gorm:"column:chat_message_id"`
	CreatedAt         time.Time `gorm:"column:created_at;autoCreateTime"`
}

type GovernanceSOP struct {
	SopID       uint      `gorm:"primaryKey;column:sop_id;autoIncrement" json:"sop_id"`
	Name        string    `gorm:"column:name;unique;not null" json:"name"`
	Title       string    `gorm:"column:title" json:"title"`
	Description string    `gorm:"column:description" json:"description"`
	Desc        string    `gorm:"column:desc" json:"desc"`
	Symptoms    string    `gorm:"column:symptoms" json:"symptoms"`
	Trigger     string    `gorm:"column:trigger" json:"trigger"`
	Remediation string    `gorm:"column:remediation" json:"remediation"`
	Status      string    `gorm:"column:status;default:'DRAFT'" json:"status"`
	Confidence  float64   `gorm:"column:confidence;default:1.0" json:"confidence"`
	Meta        string    `gorm:"column:meta" json:"meta"`
	CreatedAt   time.Time `gorm:"column:created_at;autoCreateTime" json:"created_at"`
}

func (GovernanceSOP) TableName() string {
	return "governance_sops"
}

// ValidatedKnowledgeBase stores human-validated, operationally proven remediation steps (RLOF)
type ValidatedKnowledgeBase struct {
	KbID               uint       `gorm:"primaryKey;column:kb_id;autoIncrement" json:"kb_id"`
	IssueType          string     `gorm:"type:text;column:issue_type" json:"issue_type"`
	Symptoms           string     `gorm:"type:jsonb;column:symptoms" json:"symptoms"`
	RootCause          string     `gorm:"type:text;column:root_cause" json:"root_cause"`
	Evidence           string     `gorm:"type:jsonb;column:evidence" json:"evidence"`
	RemediationSteps   string     `gorm:"type:jsonb;column:remediation_steps" json:"remediation_steps"`
	Verification       string     `gorm:"type:jsonb;column:verification" json:"verification"`
	Rollback           string     `gorm:"type:jsonb;column:rollback" json:"rollback"`
	AutomationScript   string     `gorm:"type:text;column:automation_script" json:"automation_script"`
	Environment        string     `gorm:"type:text;column:environment" json:"environment"`
	OSVersion          string     `gorm:"type:text;column:os_version" json:"os_version"`
	ApplicationVersion string     `gorm:"type:text;column:application_version" json:"application_version"`
	DeviceType         string     `gorm:"type:text;column:device_type" json:"device_type"`
	Site               string     `gorm:"type:text;column:site" json:"site"`
	SuccessCount       int        `gorm:"column:success_count;default:0" json:"success_count"`
	FailCount          int        `gorm:"column:fail_count;default:0" json:"fail_count"`
	SuccessRate        float64    `gorm:"column:success_rate;default:0.0" json:"success_rate"`
	Confidence         float64    `gorm:"column:confidence;default:1.0" json:"confidence"`
	LastValidatedBy    string     `gorm:"type:varchar(100);column:last_validated_by" json:"last_validated_by"`
	LastVerified       *time.Time `gorm:"column:last_verified" json:"last_verified"`
	LastUsed           *time.Time `gorm:"column:last_used" json:"last_used"`
	EmbeddingVector    string     `gorm:"type:text;column:embedding_vector" json:"embedding_vector"` // PostgreSQL vector extension or stored as raw text/json
	CreatedAt          time.Time  `gorm:"column:created_at;autoCreateTime" json:"created_at"`
	UpdatedAt          time.Time  `gorm:"column:updated_at;autoUpdateTime" json:"updated_at"`
}

func (ValidatedKnowledgeBase) TableName() string {
	return "validated_knowledge_base"
}

// SOPMetadata stores execution history and last success timestamp for Learning Gate decay calculations
type SOPMetadata struct {
	SopID                string    `gorm:"primaryKey;column:sop_id" json:"sop_id"`
	SopName              string    `gorm:"column:sop_name;index" json:"sop_name"`
	InitialWeight        float64   `gorm:"column:initial_weight;default:1.0" json:"initial_weight"`
	TotalSuccess         int       `gorm:"column:total_success;default:0" json:"total_success"`
	TotalFailure         int       `gorm:"column:total_failure;default:0" json:"total_failure"`
	LastSuccessTimestamp time.Time `gorm:"column:last_success_timestamp;autoCreateTime" json:"last_success_timestamp"`
	CreatedAt            time.Time `gorm:"column:created_at;autoCreateTime" json:"created_at"`
	UpdatedAt            time.Time `gorm:"column:updated_at;autoUpdateTime" json:"updated_at"`
}

func (SOPMetadata) TableName() string {
	return "sop_metadata"
}


// InitDatabase initializes GORM database connectivity
func InitDatabase() (*gorm.DB, error) {
	if DB != nil {
		return DB, nil
	}

	// Load connection parameters from env or fallback
	host := getEnv("DB_HOST", "localhost")
	port := getEnv("DB_PORT", "5432")
	dbname := getEnv("DB_NAME", "osi_system")

	// Get security manager to decrypt username and password
	sm, err := security.GetSecurityManager()
	if err != nil {
		return nil, fmt.Errorf("failed to init security manager: %w", err)
	}

	// Decrypt or load DB_USER
	dbUser := getEnv("DB_USER", "postgres")
	if strings.HasPrefix(dbUser, "gAAAAA") {
		if decUser, err := sm.Decrypt(dbUser); err == nil {
			dbUser = decUser
		} else {
			dbUser = "postgres"
		}
	}

	dbPass := getEnv("DB_PASSWORD", "")
	if dbPass == "" {
		dbPass = getEnv("DB_PASS", "SecurePassword_123!")
	}
	if strings.HasPrefix(dbPass, "gAAAAA") {
		if decPass, err := sm.Decrypt(dbPass); err == nil {
			dbPass = decPass
		}
	}

	dsn := fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=disable TimeZone=UTC",
		host, port, dbUser, dbPass, dbname)

	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{
		Logger: logger.Default.LogMode(logger.Info),
	})
	if err != nil {
		return nil, fmt.Errorf("failed to open postgres connection: %w", err)
	}

	// BAB 19 / Gap 2: Support DB Read Replica routing if DB_READ_HOST is configured
	readHost := getEnv("DB_READ_HOST", "")
	if readHost != "" && readHost != host {
		readPort := getEnv("DB_READ_PORT", port)
		readDSN := fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=disable TimeZone=UTC",
			readHost, readPort, dbUser, dbPass, dbname)
		_ = readDSN // Read replica DSN ready for DBResolver plugin
	}

	// 1. Database Auto-Migration & Custom Schema Setup (Fase 2)
	// ONLY run if MIGRATE_DB is set to true to prevent startup deadlocks in production
	if getEnv("MIGRATE_DB", "false") == "true" {
		err = db.AutoMigrate(&FleetSite{}, &FleetDevice{}, &RemoteSession{}, &Device{}, &FleetPrinter{}, &ChatSession{}, &ChatMessage{}, &TelegramChatMapping{}, &GovernanceSOP{}, &ValidatedKnowledgeBase{})
		if err != nil {
			return nil, fmt.Errorf("database auto-migration failed: %w", err)
		}

		err = InitializeSchema(db)
		if err != nil {
			return nil, fmt.Errorf("database custom schema initialization failed: %w", err)
		}
	}

	// 2. Index Optimizer (Fase 2)
	// Optimize telemetry_logs indexes (table is partitioned, but indexes on target columns are key)
	db.Exec("CREATE INDEX IF NOT EXISTS idx_telemetry_device_timestamp ON telemetry_logs (device_name, timestamp DESC)")
	db.Exec("CREATE INDEX IF NOT EXISTS idx_telemetry_type_timestamp ON telemetry_logs (metric_type, timestamp DESC)")
	// Optimize devices lookup by name
	db.Exec("CREATE INDEX IF NOT EXISTS idx_devices_name ON devices (name)")

	// Create sop_metadata table for Learning Gate decay tracking
	db.Exec(`CREATE TABLE IF NOT EXISTS sop_metadata (
		sop_id VARCHAR(255) PRIMARY KEY,
		sop_name VARCHAR(255),
		initial_weight DOUBLE PRECISION DEFAULT 1.0,
		total_success INT DEFAULT 0,
		total_failure INT DEFAULT 0,
		last_success_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
		created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
		updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
	)`)

	// Configure pool parameters
	sqlDB, err := db.DB()
	if err != nil {
		return nil, fmt.Errorf("failed to get sql.DB: %w", err)
	}

	sqlDB.SetMaxIdleConns(5)
	sqlDB.SetMaxOpenConns(50)
	sqlDB.SetConnMaxLifetime(time.Hour)

	DB = db
	return DB, nil
}

// CheckDatabaseHealth verifies database connectivity and liveness (Fase 2)
func CheckDatabaseHealth() error {
	if DB == nil {
		return fmt.Errorf("database connection is not initialized")
	}
	sqlDB, err := DB.DB()
	if err != nil {
		return fmt.Errorf("failed to get underlying sql.DB: %w", err)
	}
	return sqlDB.Ping()
}

func getEnv(key, fallback string) string {
	if value, exists := os.LookupEnv(key); exists {
		return value
	}
	return fallback
}
