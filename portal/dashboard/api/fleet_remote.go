package api

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"os/exec"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
)

// TestRemoteTool tests network availability of remote utility.
func (h *Handler) TestRemoteTool(c *gin.Context) {
	client := &http.Client{Timeout: 2 * time.Second}
	resp, err := client.Get("http://host.docker.internal:44600/launcher/health")
	if err == nil && resp.StatusCode == 200 {
		c.JSON(http.StatusOK, gin.H{"found": true, "version": "v1.0 (Live)"})
	} else {
		c.JSON(http.StatusServiceUnavailable, gin.H{"found": false, "version": "Unavailable"})
	}
}

// SyncRemoteRoutes synchronizes routing tables to agent nodes.
func (h *Handler) SyncRemoteRoutes(c *gin.Context) {
	if h.rdb != nil {
		h.rdb.Publish(c.Request.Context(), "fleet_commands", `{"command":"SYNC_ROUTES"}`)
		c.JSON(http.StatusOK, gin.H{"status": "success", "message": "Routes synchronization command broadcasted"})
	} else {
		c.JSON(http.StatusInternalServerError, gin.H{"status": "error", "message": "Redis broker not available"})
	}
}

// RemoteLaunch triggers RustDesk, AnyDesk, VNC, RDP, or SSH remote sessions.
func (h *Handler) RemoteLaunch(c *gin.Context) {
	var rawReq struct {
		Tool     string `json:"tool"`
		Type     string `json:"type"`
		IP       string `json:"ip"`
		Target   string `json:"target"`
		PCName   string `json:"pc_name"`
		DeviceID string `json:"device_id"`
		Name     string `json:"name"`
		Host     string `json:"host"`
	}

	if err := c.ShouldBindJSON(&rawReq); err != nil && err.Error() != "EOF" {
		// Ignore bind errors if body is empty or non-JSON
	}

	// 1. Resolve Tool Name
	tool := strings.TrimSpace(c.Param("type"))
	if tool == "" {
		tool = strings.TrimSpace(c.Param("tool"))
	}
	if tool == "" {
		tool = strings.TrimSpace(rawReq.Tool)
	}
	if tool == "" {
		tool = strings.TrimSpace(rawReq.Type)
	}
	if tool == "" {
		tool = strings.TrimSpace(c.Query("type"))
	}
	if tool == "" {
		tool = strings.TrimSpace(c.Query("tool"))
	}
	if tool == "" {
		tool = "rdp"
	}
	toolLower := strings.ToLower(tool)

	// 2. Resolve target device identifiers
	pcName := strings.TrimSpace(rawReq.PCName)
	if pcName == "" {
		pcName = strings.TrimSpace(rawReq.DeviceID)
	}
	if pcName == "" {
		pcName = strings.TrimSpace(rawReq.Name)
	}
	if pcName == "" {
		pcName = strings.TrimSpace(c.Query("pc_name"))
	}
	if pcName == "" {
		pcName = strings.TrimSpace(c.Query("device_id"))
	}
	if pcName == "" {
		pcName = strings.TrimSpace(c.Query("device"))
	}

	targetIP := strings.TrimSpace(rawReq.IP)
	if targetIP == "" {
		targetIP = strings.TrimSpace(rawReq.Target)
	}
	if targetIP == "" {
		targetIP = strings.TrimSpace(rawReq.Host)
	}
	if targetIP == "" {
		targetIP = strings.TrimSpace(c.Query("ip"))
	}
	if targetIP == "" {
		targetIP = strings.TrimSpace(c.Query("target"))
	}
	if targetIP == "" {
		targetIP = strings.TrimSpace(c.Query("host"))
	}

	// 3. Database Device Lookup
	rustdeskID := ""
	anydeskID := ""
	vncPort := 5900
	password := ""

	if h.db != nil {
		type DeviceRecord struct {
			PCName       string `gorm:"column:pc_name"`
			IP           string `gorm:"column:ip"`
			RustdeskID   string `gorm:"column:rustdesk_id"`
			HardwareInfo string `gorm:"column:hardware_info"`
		}
		var dev DeviceRecord
		found := false

		if pcName != "" {
			if err := h.db.Table("fleet_devices").Where("pc_name = ?", pcName).First(&dev).Error; err == nil {
				found = true
			}
		}
		if !found && targetIP != "" {
			if err := h.db.Table("fleet_devices").Where("ip = ?", targetIP).First(&dev).Error; err == nil {
				found = true
			}
		}

		if found {
			if pcName == "" {
				pcName = dev.PCName
			}
			if targetIP == "" {
				targetIP = dev.IP
			}
			if dev.RustdeskID != "" {
				rustdeskID = dev.RustdeskID
			}

			if dev.HardwareInfo != "" {
				var hwInfo map[string]interface{}
				if err := json.Unmarshal([]byte(dev.HardwareInfo), &hwInfo); err == nil && hwInfo != nil {
					if targetIP == "" {
						if ipVal, ok := hwInfo["ip"].(string); ok {
							targetIP = ipVal
						}
					}
					if rustdeskID == "" {
						if rID, ok := hwInfo["rustdesk_id"].(string); ok {
							rustdeskID = rID
						}
					}
					if aID, ok := hwInfo["anydesk_id"].(string); ok {
						anydeskID = aID
					}
					if remotePassMap, ok := hwInfo["remote_passwords"].(map[string]interface{}); ok {
						if p, ok := remotePassMap[toolLower].(string); ok {
							password = p
						}
					}
				}
			}
		}
	}

	if pcName == "" && targetIP == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"status":  "error",
			"message": "Missing target device identifier (pc_name, device_id, or ip parameter required)",
		})
		return
	}

	if pcName == "" {
		pcName = targetIP
	}

	// 4. Construct URL Scheme, Commands, and Launcher Payload
	var launchURL string
	var exePath string
	launcherPayload := make(map[string]interface{})

	switch toolLower {
	case "rustdesk":
		targetID := rustdeskID
		if targetID == "" || targetID == "---" {
			targetID = targetIP
		}
		if targetID == "" || targetID == "---" {
			targetID = pcName
		}
		launchURL = fmt.Sprintf("rustdesk://%s", targetID)
		if password != "" {
			launchURL = fmt.Sprintf("rustdesk://%s?password=%s", targetID, url.QueryEscape(password))
		}
		exePath = "rustdesk"
		launcherPayload = map[string]interface{}{
			"tool":       "rustdesk",
			"id":         targetID,
			"ip":         targetIP,
			"password":   password,
			"exe_path":   exePath,
			"url_scheme": launchURL,
		}

	case "anydesk":
		targetID := anydeskID
		if targetID == "" {
			targetID = targetIP
		}
		if targetID == "" {
			targetID = pcName
		}
		launchURL = fmt.Sprintf("anydesk://%s", targetID)
		exePath = "anydesk"
		launcherPayload = map[string]interface{}{
			"tool":       "anydesk",
			"id":         targetID,
			"password":   password,
			"exe_path":   exePath,
			"url_scheme": launchURL,
		}

	case "vnc":
		if targetIP == "" {
			targetIP = "127.0.0.1"
		}
		launchURL = fmt.Sprintf("vnc://%s:%d", targetIP, vncPort)
		exePath = "vncviewer"
		launcherPayload = map[string]interface{}{
			"tool":       "vnc",
			"host":       targetIP,
			"port":       vncPort,
			"password":   password,
			"exe_path":   exePath,
			"url_scheme": launchURL,
		}

	case "ssh":
		if targetIP == "" {
			targetIP = "127.0.0.1"
		}
		launchURL = fmt.Sprintf("ssh://%s", targetIP)
		exePath = "ssh"
		launcherPayload = map[string]interface{}{
			"tool":       "ssh",
			"host":       targetIP,
			"exe_path":   exePath,
			"url_scheme": launchURL,
		}

	default: // rdp
		if targetIP == "" {
			targetIP = "127.0.0.1"
		}
		launchURL = fmt.Sprintf("rdp://full%%20address=s:%s", targetIP)
		exePath = `C:\Windows\System32\mstsc.exe`
		launcherPayload = map[string]interface{}{
			"tool":       "rdp",
			"host":       targetIP,
			"exe_path":   exePath,
			"url_scheme": launchURL,
		}
	}

	// 5. Multi-Channel Session Launch
	launcherStatus := "relay_required"
	executedLocally := false

	launcherURLs := []string{
		"http://127.0.0.1:44600/launch",
		"http://localhost:44600/launch",
		"http://host.docker.internal:44600/launch",
	}

	httpClient := &http.Client{Timeout: 2 * time.Second}
	payloadBytes, _ := json.Marshal(launcherPayload)

	for _, lURL := range launcherURLs {
		reqObj, err := http.NewRequest("POST", lURL, bytes.NewBuffer(payloadBytes))
		if err == nil {
			reqObj.Header.Set("Content-Type", "application/json")
			resp, err := httpClient.Do(reqObj)
			if err == nil {
				resp.Body.Close()
				if resp.StatusCode == http.StatusOK {
					launcherStatus = "online"
					executedLocally = true
					break
				}
			}
		}
	}

	// Channel B: Direct System Command Execution on host OS if launcher port not reachable
	if !executedLocally {
		switch toolLower {
		case "rdp":
			if _, err := exec.LookPath("mstsc.exe"); err == nil {
				if exec.Command("mstsc.exe", "/v:"+targetIP).Start() == nil {
					executedLocally = true
					launcherStatus = "launched_locally"
				}
			} else if _, err := exec.LookPath("xfreerdp"); err == nil {
				if exec.Command("xfreerdp", "/v:"+targetIP).Start() == nil {
					executedLocally = true
					launcherStatus = "launched_locally"
				}
			}
		case "vnc":
			if _, err := exec.LookPath("vncviewer"); err == nil {
				if exec.Command("vncviewer", targetIP).Start() == nil {
					executedLocally = true
					launcherStatus = "launched_locally"
				}
			}
		case "rustdesk":
			targetID := rustdeskID
			if targetID == "" {
				targetID = targetIP
			}
			if _, err := exec.LookPath("rustdesk"); err == nil {
				if exec.Command("rustdesk", "--connect", targetID).Start() == nil {
					executedLocally = true
					launcherStatus = "launched_locally"
				}
			}
		}

		if !executedLocally {
			if _, err := exec.LookPath("xdg-open"); err == nil {
				if exec.Command("xdg-open", launchURL).Start() == nil {
					executedLocally = true
					launcherStatus = "launched_locally"
				}
			}
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"status":           "success",
		"message":          fmt.Sprintf("%s remote session launched for %s (%s)", strings.ToUpper(toolLower), pcName, targetIP),
		"tool":             toolLower,
		"target":           targetIP,
		"pc_name":          pcName,
		"launch_url":       launchURL,
		"url_scheme":       launchURL,
		"launcher_status":  launcherStatus,
		"launcher_payload": launcherPayload,
		"executed_locally": executedLocally,
	})
}
