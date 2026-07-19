package core

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"net"
	"os"
	"strings"
	"sync"
	"time"

	"gorm.io/gorm"
)

type RemoteSettings struct {
	General   map[string]interface{} `json:"general"`
	AnyDesk   map[string]interface{} `json:"anydesk"`
	RustDesk  map[string]interface{} `json:"rustdesk"`
	VNC       map[string]interface{} `json:"vnc"`
	Passwords map[string]string      `json:"passwords"`
}

var (
	globalSettings      RemoteSettings
	globalSettingsMutex sync.RWMutex
	lastSettingsModTime time.Time
	settingsFilePath    string
)

func InitConfigWatcher(path string) {
	settingsFilePath = path
	ReloadSettings()

	go func() {
		for {
			time.Sleep(3 * time.Second)
			info, err := os.Stat(settingsFilePath)
			if err != nil {
				continue
			}
			modTime := info.ModTime()
			globalSettingsMutex.RLock()
			lastTime := lastSettingsModTime
			globalSettingsMutex.RUnlock()

			if lastTime.IsZero() {
				globalSettingsMutex.Lock()
				lastSettingsModTime = modTime
				globalSettingsMutex.Unlock()
				continue
			}

			if modTime.After(lastTime) {
				fmt.Printf("[CONFIG] remote_settings.json modified at %s. Hot reloading configuration...\n", modTime.Format(time.RFC3339))
				ReloadSettings()
			}
		}
	}()
}

func ReloadSettings() {
	globalSettingsMutex.Lock()
	defer globalSettingsMutex.Unlock()

	settings, err := LoadSettings(settingsFilePath)
	if err == nil {
		globalSettings = settings
		info, errStat := os.Stat(settingsFilePath)
		if errStat == nil {
			lastSettingsModTime = info.ModTime()
		}
	} else {
		fmt.Printf("[CONFIG ERROR] Failed to reload settings: %v\n", err)
	}
}

func GetGlobalSettings() RemoteSettings {
	globalSettingsMutex.RLock()
	defer globalSettingsMutex.RUnlock()
	return globalSettings
}

func LoadSettings(settingsPath string) (RemoteSettings, error) {
	var settings RemoteSettings
	data, err := os.ReadFile(settingsPath)
	if err != nil {
		return RemoteSettings{}, err
	}

	err = json.Unmarshal(data, &settings)
	return settings, err
}

func SaveSettings(settingsPath string, settings RemoteSettings) error {
	data, err := json.MarshalIndent(settings, "", "    ")
	if err != nil {
		return err
	}
	return os.WriteFile(settingsPath, data, 0644)
}

func FileExists(path string) bool {
	info, err := os.Stat(path)
	if err != nil {
		return false
	}
	return !info.IsDir()
}

// Helper to get launcher host IP dynamically from inside container
func GetLauncherURL(path string) string {
	if envIP := os.Getenv("LAUNCHER_HOST_IP"); envIP != "" {
		return fmt.Sprintf("http://%s:44600%s", envIP, path)
	}

	if data, err := os.ReadFile("/etc/resolv.conf"); err == nil {
		lines := strings.Split(string(data), "\n")
		for _, line := range lines {
			line = strings.TrimSpace(line)
			if strings.Contains(line, "host(") {
				idx := strings.Index(line, "host(")
				if idx != -1 {
					ipPart := line[idx+5:]
					endIdx := strings.Index(ipPart, ")")
					if endIdx != -1 {
						ip := ipPart[:endIdx]
						if net.ParseIP(ip) != nil {
							return fmt.Sprintf("http://%s:44600%s", ip, path)
						}
					}
				}
			}
		}

		for _, line := range lines {
			line = strings.TrimSpace(line)
			if strings.HasPrefix(line, "nameserver") {
				parts := strings.Fields(line)
				if len(parts) >= 2 {
					ip := parts[1]
					if ip != "127.0.0.11" && net.ParseIP(ip) != nil {
						return fmt.Sprintf("http://%s:44600%s", ip, path)
					}
				}
			}
		}
	}

	return fmt.Sprintf("http://host.docker.internal:44600%s", path)
}

func WriteAuditLog(db *gorm.DB, actionType, actor, target string, payload interface{}) error {
	payloadBytes, _ := json.Marshal(payload)
	payloadStr := string(payloadBytes)

	var lastRow struct {
		HashSignature string `gorm:"column:hash_signature"`
	}
	prevHash := "0"
	if err := db.Raw("SELECT hash_signature FROM immutable_audit_log ORDER BY log_id DESC LIMIT 1").Scan(&lastRow).Error; err == nil && lastRow.HashSignature != "" {
		prevHash = lastRow.HashSignature
	}

	dataToHash := fmt.Sprintf("%s|%s|%s|%s|%s", prevHash, actionType, actor, target, payloadStr)
	hash := sha256.Sum256([]byte(dataToHash))
	hashSig := fmt.Sprintf("%x", hash)

	return db.Exec(`
		INSERT INTO immutable_audit_log (action_type, actor, target, payload, prev_hash, hash_signature, timestamp)
		VALUES (?, ?, ?, ?, ?, ?, NOW())
	`, actionType, actor, target, payloadStr, prevHash, hashSig).Error
}

func CleanSiteID(siteID string) string {
	if siteID == "" {
		return "global"
	}
	s := strings.ToLower(siteID)
	s = strings.ReplaceAll(s, " ", "_")
	s = strings.ReplaceAll(s, ".", "_")
	return s
}
