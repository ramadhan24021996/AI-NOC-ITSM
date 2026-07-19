package config

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"

	"go_incident_analysis/SERVER/go_core/security"
)

// WebTarget represents layer 7 targets to monitor
type WebTarget struct {
	URL     string `json:"url"`
	Name    string `json:"name"`
	Keyword string `json:"keyword"`
}

// Config stores all system configurations
type Config struct {
	OrchestratorHost      string            `json:"orchestrator_host"`
	OrchestratorPort      int               `json:"orchestrator_port"`
	DashboardPort         int               `json:"dashboard_port"`
	NatsHost              string            `json:"nats_host"`
	NatsPort              int               `json:"nats_port"`
	DBHost                string            `json:"db_host"`
	DBPort                int               `json:"db_port"`
	DBName                string            `json:"db_name"`
	DBUser                string            `json:"db_user"`
	DBPass                string            `json:"db_pass"`
	RedisHost             string            `json:"redis_host"`
	RedisPort             int               `json:"redis_port"`
	RedisPass             string            `json:"redis_pass"`
	NatsToken             string            `json:"nats_token"`
	TelegramBotToken      string            `json:"telegram_bot_token"`
	TelegramChatID        string            `json:"telegram_chat_id"`
	ZammadToken           string            `json:"zammad_token"`
	ZammadURL             string            `json:"zammad_url"`
	GatewayToSiteMap      map[string]string `json:"gateway_to_site_map"`
	PingTargets           []string          `json:"ping_targets"`
	PrinterList           []string          `json:"printer_list"`
	WebTargets            []WebTarget       `json:"web_targets"`
	LatencyThreshold      int               `json:"latency_threshold"`
	PacketLossThreshold   int               `json:"packet_loss_threshold"`
	PrinterQueueThreshold int               `json:"printer_queue_threshold"`
	CheckInterval         int               `json:"check_interval"`
	RecoveryMode          string            `json:"recovery_mode"`
	NetdataMasterURL      string            `json:"netdata_master_url"`
	NetdataBearerToken    string            `json:"netdata_bearer_token"`
}

var globalConfig *Config

// GetConfig returns the initialized global configuration
func GetConfig() (*Config, error) {
	if globalConfig != nil {
		return globalConfig, nil
	}

	// 1. Load .env file if available
	_ = LoadEnv()

	// 2. Initialize security manager for decryption
	sm, err := security.GetSecurityManager()
	if err != nil {
		return nil, fmt.Errorf("failed to initialize security manager for config: %w", err)
	}

	// 3. Populate configuration with fallback defaults matching config.py
	cfg := &Config{
		OrchestratorHost:      getEnv("ORCHESTRATOR_HOST", "127.0.0.1"),
		OrchestratorPort:      getEnvInt("ORCHESTRATOR_PORT", 18800),
		DashboardPort:         getEnvInt("DASHBOARD_PORT", 9999),
		NatsHost:              getEnv("NATS_HOST", "127.0.0.1"),
		NatsPort:              getEnvInt("NATS_PORT", 4222),
		DBHost:                getEnv("DB_HOST", "localhost"),
		DBPort:                getEnvInt("DB_PORT", 5432),
		DBName:                getEnv("DB_NAME", "osi_system"),
		RedisHost:             getEnv("REDIS_HOST", "127.0.0.1"),
		RedisPort:             getEnvInt("REDIS_PORT", 6379),
		RedisPass:             getEnv("OSI_SECURITY_KEY", ""),
		NatsToken:             getEnv("OSI_SECURITY_KEY", ""),
		ZammadURL:             getEnv("ZAMMAD_URL", "https://your-zammad.com/api/v1/"),
		LatencyThreshold:      getEnvInt("LATENCY_THRESHOLD", 200),
		PacketLossThreshold:   getEnvInt("PACKET_LOSS_THRESHOLD", 20),
		PrinterQueueThreshold: getEnvInt("PRINTER_QUEUE_THRESHOLD", 10),
		CheckInterval:         getEnvInt("CHECK_INTERVAL", 300),
		RecoveryMode:          getEnv("RECOVERY_MODE", "Semi-Auto"),
		NetdataMasterURL:      getEnv("NETDATA_MASTER_URL", "http://127.0.0.1:19999"),
	}

	// Gateway to site mapping defaults
	cfg.GatewayToSiteMap = map[string]string{
		"192.168.1.1":  "Jateng 3",
		"192.168.4.1":  "PKL",
		"192.168.10.1": "PML",
		"192.168.20.1": "IDM",
		"127.0.0.1":    "Lab_Local",
		"10.20.0.1":    "Kantor Cabang",
	}

	// Ping targets default
	cfg.PingTargets = []string{"8.8.8.8", "1.1.1.1", "google.com"}

	// Printer list defaults
	cfg.PrinterList = []string{"192.168.1.101", "192.168.1.102"}

	// Web targets default
	cfg.WebTargets = []WebTarget{
		{URL: "https://google.com", Name: "Google Search", Keyword: "Google"},
		{URL: "https://youtube.com", Name: "YouTube Video", Keyword: "YouTube"},
		{URL: "https://cloudflare.com", Name: "Cloudflare CDN", Keyword: "Cloudflare"},
		{URL: "https://github.com", Name: "GitHub", Keyword: "GitHub"},
		{URL: "http://localhost:9999/", Name: "OSI Dashboard (Local)", Keyword: "OSI"},
		{URL: "https://localhost:8800/", Name: "Orchestrator API", Keyword: ""},
	}

	// Decrypt DB User
	encUser := getEnv("DB_USER", "postgres")
	if strings.HasPrefix(encUser, "gAAAAA") {
		if decUser, err := sm.Decrypt(encUser); err == nil {
			cfg.DBUser = decUser
		} else {
			cfg.DBUser = "postgres"
		}
	} else {
		cfg.DBUser = encUser
	}

	// Decrypt DB Pass
	encPass := getEnv("DB_PASSWORD", "")
	if encPass == "" {
		encPass = getEnv("DB_PASS", "SecurePassword_123!")
	}
	if strings.HasPrefix(encPass, "gAAAAA") {
		if decPass, err := sm.Decrypt(encPass); err == nil {
			cfg.DBPass = decPass
		} else {
			cfg.DBPass = encPass
		}
	} else {
		cfg.DBPass = encPass
	}

	// Decrypt Telegram Bot Token
	encBotToken := getEnv("TELEGRAM_BOT_TOKEN", "gAAAAABqLWmK_SrP_nJci0Yn5TeoBxWhmfWuoR1NTWKj23UXQbxNBFI3_euIFhr_Cu4SD_Fh1I2_nE1tY2EhQG5zxdcZSCwgOiB9Uk5jVbEYHzBGCIYXHOgXxzixp9Rh7Gb6PdiDqy9R")
	decBotToken, err := sm.Decrypt(encBotToken)
	if err == nil {
		cfg.TelegramBotToken = decBotToken
	} else {
		cfg.TelegramBotToken = encBotToken // fallback if not encrypted
	}

	// Decrypt Telegram Chat ID
	encChatID := getEnv("TELEGRAM_CHAT_ID", "gAAAAABqLWmKxLT7z9bq3qT8BUQXFtYmjyYDO70LTv033uYA4GNxhmRzMpzMN300O4AlnUHSyh91XI6wNbx4uyq0kU3BLRnukw==")
	decChatID, err := sm.Decrypt(encChatID)
	if err == nil {
		cfg.TelegramChatID = decChatID
	} else {
		cfg.TelegramChatID = encChatID
	}

	// Decrypt Zammad Token
	encZammadToken := getEnv("ZAMMAD_TOKEN", "gAAAAABqK9zVIHEIaAY7ctq0Aw6h0X5rHJ5xTRV_uvcNdTjUWMxNBmkm2ctMma_z1NDE8W5K6Rmg4V2pVuvuO5IkPXB8DwfU3bp9CFcOVx5ArOqJOn6UYDg=")
	decZammadToken, err := sm.Decrypt(encZammadToken)
	if err == nil {
		cfg.ZammadToken = decZammadToken
	} else {
		cfg.ZammadToken = encZammadToken
	}

	// Decrypt Netdata Bearer Token
	encNetdataToken := getEnv("NETDATA_BEARER_TOKEN", "gAAAAABqEOkn-WqZrqGWLR0Ag51ISSqwVcBIZAInhDGiKyzTA48ZTcOTtBeXaa3Gr47l6PQvewue5t1FzXdpmvESvocE9e5Fs9PF6TbtE4JSdyRZuWZk14k=")
	decNetdataToken, err := sm.Decrypt(encNetdataToken)
	if err == nil {
		cfg.NetdataBearerToken = decNetdataToken
	} else {
		cfg.NetdataBearerToken = encNetdataToken
	}

	// Override with JSON file if config.json is present in project root
	_, filename, _, _ := runtime.Caller(0)
	projectRoot := filepath.Dir(filepath.Dir(filepath.Dir(filename)))
	jsonPath := filepath.Join(projectRoot, "config.json")
	if fileExists(jsonPath) {
		jsonBytes, err := os.ReadFile(jsonPath)
		if err == nil {
			var fileCfg Config
			if err := json.Unmarshal(jsonBytes, &fileCfg); err == nil {
				// Merge loaded config
				if fileCfg.OrchestratorHost != "" {
					cfg.OrchestratorHost = fileCfg.OrchestratorHost
				}
				if fileCfg.OrchestratorPort != 0 {
					cfg.OrchestratorPort = fileCfg.OrchestratorPort
				}
				if fileCfg.DashboardPort != 0 {
					cfg.DashboardPort = fileCfg.DashboardPort
				}
				if fileCfg.DBHost != "" {
					cfg.DBHost = fileCfg.DBHost
				}
				if fileCfg.DBName != "" {
					cfg.DBName = fileCfg.DBName
				}
				// Decrypt db credentials from file if they are encrypted
				if fileCfg.DBUser != "" {
					if dec, err := sm.Decrypt(fileCfg.DBUser); err == nil {
						cfg.DBUser = dec
					} else {
						cfg.DBUser = fileCfg.DBUser
					}
				}
				if fileCfg.DBPass != "" {
					if dec, err := sm.Decrypt(fileCfg.DBPass); err == nil {
						cfg.DBPass = dec
					} else {
						cfg.DBPass = fileCfg.DBPass
					}
				}
				// Copy maps and arrays if specified
				if fileCfg.GatewayToSiteMap != nil {
					cfg.GatewayToSiteMap = fileCfg.GatewayToSiteMap
				}
				if fileCfg.PingTargets != nil {
					cfg.PingTargets = fileCfg.PingTargets
				}
				if fileCfg.WebTargets != nil {
					cfg.WebTargets = fileCfg.WebTargets
				}
			}
		}
	}

	globalConfig = cfg
	return cfg, nil
}

// LoadEnv reads a .env file and sets environment variables
func LoadEnv() error {
	_, filename, _, _ := runtime.Caller(0)
	projectRoot := filepath.Dir(filepath.Dir(filepath.Dir(filename)))
	envPath := filepath.Join(projectRoot, ".env")

	file, err := os.Open(envPath)
	if err != nil {
		return err
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := scanner.Text()
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		if len(parts) != 2 {
			continue
		}
		key := strings.TrimSpace(parts[0])
		val := strings.TrimSpace(parts[1])
		// Remove quotes
		val = strings.Trim(val, `"'`)
		if os.Getenv(key) == "" {
			_ = os.Setenv(key, val)
		}
	}
	return scanner.Err()
}

func getEnv(key, fallback string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	return fallback
}

func getEnvInt(key string, fallback int) int {
	if val := os.Getenv(key); val != "" {
		if i, err := strconv.Atoi(val); err == nil {
			return i
		}
	}
	return fallback
}

func fileExists(path string) bool {
	info, err := os.Stat(path)
	if err != nil {
		return false
	}
	return !info.IsDir()
}
