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
		WindowsURL:    "/api/fleet/ota/download?platform=windows",
		WindowsSHA256: "",
		LinuxURL:      "/api/fleet/ota/download?platform=linux",
		LinuxSHA256:   "",
		ReleasedAt:    time.Now(),
	}
)

// resolveAgentBinarySHA256 searches candidate binary paths and returns the first valid SHA-256 checksum.
func resolveAgentBinarySHA256(candidates []string) string {
	for _, p := range candidates {
		if sum, err := CalculateFileSHA256(p); err == nil && len(sum) == 64 {
			return sum
		}
	}
	return ""
}

// HandleAgentVersionLatest returns HTTP GET version metadata to agents with real binary SHA-256 checksums.
func HandleAgentVersionLatest(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	winCandidates := []string{
		"CLIENT_DISTRIBUSI_GO/05_SIAP_DISTRIBUSI/agent.exe",
		"/app/workspace/CLIENT_DISTRIBUSI_GO/05_SIAP_DISTRIBUSI/agent.exe",
		"portal/ota_binaries/agent.exe",
	}
	linuxCandidates := []string{
		"CLIENT_DISTRIBUSI_GO/05_SIAP_DISTRIBUSI/osi_linux_agent",
		"CLIENT_DISTRIBUSI_GO/linux_agent/osi-agent",
		"CLIENT_DISTRIBUSI_GO/linux_agent/linux_agent",
		"/app/workspace/CLIENT_DISTRIBUSI_GO/05_SIAP_DISTRIBUSI/osi_linux_agent",
		"portal/ota_binaries/osi_linux_agent",
	}

	versionInfoLock.Lock()
	if winSum := resolveAgentBinarySHA256(winCandidates); winSum != "" {
		currentVerInfo.WindowsSHA256 = winSum
	}
	if linSum := resolveAgentBinarySHA256(linuxCandidates); linSum != "" {
		currentVerInfo.LinuxSHA256 = linSum
	}
	infoCopy := currentVerInfo
	versionInfoLock.Unlock()

	_ = json.NewEncoder(w).Encode(infoCopy)
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
