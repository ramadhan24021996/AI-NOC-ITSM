package ingestion

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"os"
	"sync"
	"time"
)

// AgentVersionInfo holds metadata for distribution agents auto-upgrades
type AgentVersionInfo struct {
	LatestVersion string    `json:"latest_version"`
	MinSupported  string    `json:"min_supported"`
	WindowsURL    string    `json:"windows_url"`
	WindowsSHA256 string    `json:"windows_sha256"`
	LinuxURL      string    `json:"linux_url"`
	LinuxSHA256   string    `json:"linux_sha256"`
	ReleasedAt    time.Time `json:"released_at"`
}

var (
	versionInfoLock sync.RWMutex
	currentVerInfo  = AgentVersionInfo{
		LatestVersion: "2.1.2-Go",
		MinSupported:  "2.0.0",
		WindowsURL:    "/api/agent/download/osi_agent_win.exe",
		WindowsSHA256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
		LinuxURL:      "/api/agent/download/osi-agent-linux",
		LinuxSHA256:   "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
		ReleasedAt:    time.Now(),
	}
)

// HandleAgentVersionLatest returns HTTP GET version metadata to agents
func HandleAgentVersionLatest(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	versionInfoLock.RLock()
	defer versionInfoLock.RUnlock()

	_ = json.NewEncoder(w).Encode(currentVerInfo)
}

// CalculateFileSHA256 computes SHA-256 checksum of a file
func CalculateFileSHA256(filePath string) (string, error) {
	data, err := os.ReadFile(filePath)
	if err != nil {
		return "", err
	}
	hash := sha256.Sum256(data)
	return hex.EncodeToString(hash[:]), nil
}
