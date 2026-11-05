package api

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	"github.com/gin-gonic/gin"
)

// GetUpdateManifest serves the update manifest for fleet agents.
func (h *Handler) GetUpdateManifest(c *gin.Context) {
	manifestPath := "./portal/ota_binaries/manifest.json"
	if fileBytes, err := os.ReadFile(manifestPath); err == nil {
		var manifest map[string]interface{}
		if json.Unmarshal(fileBytes, &manifest) == nil {
			c.JSON(http.StatusOK, manifest)
			return
		}
	}

	host := c.Request.Host
	downloadURL := fmt.Sprintf("http://%s/api/fleet/ota/download?platform=windows", host)

	manifest := gin.H{
		"version":      "v1.1.0",
		"download_url": downloadURL,
		"status":       "fallback_manifest",
	}

	c.JSON(http.StatusOK, manifest)
}

// DownloadOTABinary streams agent update binary with application/octet-stream.
func (h *Handler) DownloadOTABinary(c *gin.Context) {
	platform := c.DefaultQuery("platform", "linux")
	var filename string
	var relPath string

	if strings.Contains(strings.ToLower(platform), "win") {
		relPath = "CLIENT_DISTRIBUSI_GO/05_SIAP_DISTRIBUSI/agent.exe"
		filename = "agent.exe"
	} else {
		relPath = "CLIENT_DISTRIBUSI_GO/05_SIAP_DISTRIBUSI/osi_linux_agent"
		filename = "osi_linux_agent"
	}

	candidates := []string{
		filepath.Join(h.baseDir, "CLIENT_DISTRIBUSI_GO/linux_agent", "osi-agent"),
		filepath.Join(h.baseDir, "CLIENT_DISTRIBUSI_GO/linux_agent", "linux_agent"),
		filepath.Join(h.baseDir, "CLIENT_DISTRIBUSI_GO/05_SIAP_DISTRIBUSI", filename),
		filepath.Join(h.baseDir, "CLIENT_DISTRIBUSI_GO/05_SIAP_DISTRIBUSI", "osi_linux_agent"),
		filepath.Join(h.baseDir, "CLIENT_DISTRIBUSI_GO/05_SIAP_DISTRIBUSI", "linux_agent"),
		filepath.Join(h.baseDir, "portal/ota_binaries", filename),
		filepath.Join("/app/workspace/CLIENT_DISTRIBUSI_GO/05_SIAP_DISTRIBUSI", filename),
		filepath.Join(".", relPath),
		filepath.Join("portal/ota_binaries", filename),
		filepath.Join("../portal/ota_binaries", filename),
		filepath.Join("/app", relPath),
	}

	targetPath := ""
	for _, p := range candidates {
		if _, err := os.Stat(p); err == nil {
			targetPath = p
			break
		}
	}

	if targetPath == "" {
		c.JSON(http.StatusNotFound, gin.H{"status": "error", "message": "OTA binary not found. Please compile agents first."})
		return
	}

	c.Header("Content-Disposition", "attachment; filename="+filename)
	c.Header("Content-Type", "application/octet-stream")
	c.File(targetPath)
}

// TriggerOTAUpdate handles OTA update requests for a specified client device.
func (h *Handler) TriggerOTAUpdate(c *gin.Context) {
	var req struct {
		DeviceName string `json:"device_name"`
		PCName     string `json:"pc_name"`
		Device     string `json:"device"`
		Name       string `json:"name"`
		ClientID   string `json:"client_id"`
		Target     string `json:"target"`
	}
	if err := c.ShouldBindJSON(&req); err != nil && req.DeviceName == "" && req.PCName == "" && req.Device == "" && req.Name == "" && req.ClientID == "" && req.Target == "" {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": "device_name or pc_name required"})
		return
	}

	deviceName := req.DeviceName
	if deviceName == "" {
		deviceName = req.PCName
	}
	if deviceName == "" {
		deviceName = req.Device
	}
	if deviceName == "" {
		deviceName = req.Name
	}
	if deviceName == "" {
		deviceName = req.ClientID
	}
	if deviceName == "" {
		deviceName = req.Target
	}
	if deviceName == "" {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": "device_name required"})
		return
	}

	isLinux := strings.Contains(strings.ToUpper(deviceName), "LINUX") || strings.Contains(strings.ToLower(deviceName), "ubu")

	platform := "linux"
	filename := "osi_linux_agent"
	relPath := "CLIENT_DISTRIBUSI_GO/05_SIAP_DISTRIBUSI/osi_linux_agent"
	if !isLinux {
		platform = "windows"
		filename = "agent.exe"
		relPath = "CLIENT_DISTRIBUSI_GO/05_SIAP_DISTRIBUSI/agent.exe"
	}

	candidates := []string{
		filepath.Join(h.baseDir, "CLIENT_DISTRIBUSI_GO/05_SIAP_DISTRIBUSI", filename),
		filepath.Join(h.baseDir, "CLIENT_DISTRIBUSI_GO/05_SIAP_DISTRIBUSI", "linux_agent"),
		filepath.Join(h.baseDir, "portal/ota_binaries", filename),
		filepath.Join("/app/workspace/CLIENT_DISTRIBUSI_GO/05_SIAP_DISTRIBUSI", filename),
		filepath.Join(".", relPath),
		filepath.Join("portal/ota_binaries", filename),
		filepath.Join("../portal/ota_binaries", filename),
		filepath.Join("/app", relPath),
	}

	var fileBytes []byte
	var err error
	var foundPath string
	for _, p := range candidates {
		if data, readErr := os.ReadFile(p); readErr == nil && len(data) > 0 {
			fileBytes = data
			foundPath = p
			err = nil
			break
		} else {
			err = readErr
		}
	}

	if len(fileBytes) == 0 {
		c.JSON(http.StatusInternalServerError, gin.H{"status": "error", "message": fmt.Sprintf("Failed to read agent binary '%s': %v (searched %v)", filename, err, candidates)})
		return
	}
	_ = foundPath
	hash := sha256.Sum256(fileBytes)
	hashHex := hex.EncodeToString(hash[:])

	// Host for download URL
	host := os.Getenv("SERVER_IP")
	if host == "" {
		host = os.Getenv("MASTER_IP")
	}
	if host == "" {
		host = "10.20.0.154"
	}
	scheme := "http"
	if c.Request.TLS != nil {
		scheme = "https"
	}
	downloadURL := fmt.Sprintf("%s://%s/api/fleet/ota/download?platform=%s", scheme, host, platform)

	// Fetch device IP from database (supports both devices and fleet_devices schema + hardware_info JSONB fallback)
	var deviceIP string
	if h.db != nil {
		h.db.Raw(`SELECT COALESCE(ip, '') FROM devices WHERE LOWER(name) = LOWER(?) OR LOWER(ip) = LOWER(?) LIMIT 1`, deviceName, deviceName).Scan(&deviceIP)
		if deviceIP == "" {
			h.db.Raw(`SELECT COALESCE(NULLIF(ip, ''), hardware_info->>'ip', hardware_info->'network'->>'ip', '') FROM fleet_devices WHERE LOWER(pc_name) = LOWER(?) OR LOWER(COALESCE(hostname, '')) = LOWER(?) OR LOWER(COALESCE(ip, '')) = LOWER(?) LIMIT 1`, deviceName, deviceName, deviceName).Scan(&deviceIP)
		}
	}

	// Prepare payload for agent socket
	payload := map[string]interface{}{
		"download_url": downloadURL,
		"sha256":       hashHex,
		"version":      "v2.1.1-Go",
	}

	// Send command to agent if online
	var statusMsg string
	var otaStatus string
	if deviceIP != "" && deviceIP != "N/A" {
		socketErr := sendSocketCommand(deviceIP, "UPDATE_AGENT", payload)
		if socketErr == nil {
			otaStatus = "SUCCESS"
			statusMsg = fmt.Sprintf("OTA Update v2.1.1-Go (SHA256: %s...) berhasil dikirim langsung ke %s (%s:10000). Agen sedang melakukan update.", hashHex[:8], deviceName, deviceIP)
		} else {
			otaStatus = "QUEUED"
			statusMsg = fmt.Sprintf("Payload OTA v2.1.1-Go telah disiapkan untuk %s (%s). Menunggu sinyal socket agen: %v.", deviceName, deviceIP, socketErr)
		}
	} else {
		otaStatus = "QUEUED"
		statusMsg = fmt.Sprintf("Payload OTA v2.1.1-Go disiapkan untuk %s. Menunggu perangkat online.", deviceName)
	}

	c.JSON(http.StatusOK, gin.H{
		"status":       "success",
		"ota_status":   otaStatus,
		"device":       deviceName,
		"platform":     platform,
		"download_url": downloadURL,
		"sha256":       hashHex,
		"version":      "v2.1.1-Go",
		"message":      statusMsg,
	})
}
