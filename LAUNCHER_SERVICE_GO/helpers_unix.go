//go:build !windows

package main

import (
	"fmt"
	"os"
	"os/exec"
	"strings"
	"time"
)

// simulated registry lookup helper on non-Windows
func findInRegistry(path, keyName string) string {
	_ = path
	_ = keyName
	return ""
}

// Process running check helper (pgrep based)
func isProcessRunning(name string) bool {
	cmd := exec.Command("pgrep", "-f", name)
	err := cmd.Run()
	return err == nil
}

// AnyDesk ID Reader on Linux
func getAnydeskID() string {
	paths := []string{
		os.ExpandEnv("$HOME/.anydesk/system.conf"),
		"/etc/anydesk/system.conf",
	}
	for _, p := range paths {
		if fileExists(p) {
			bytes, err := os.ReadFile(p)
			if err != nil {
				continue
			}
			lines := strings.Split(string(bytes), "\n")
			for _, line := range lines {
				if strings.HasPrefix(line, "ad.anydesk.id=") {
					return strings.TrimSpace(strings.TrimPrefix(line, "ad.anydesk.id="))
				}
			}
		}
	}
	return ""
}

// RustDesk ID Reader on Linux
func getRustdeskID() string {
	paths := []string{
		os.ExpandEnv("$HOME/.config/RustDesk/RustDesk.toml"),
		os.ExpandEnv("$HOME/.config/RustDesk/config/RustDesk.toml"),
	}
	for _, p := range paths {
		if fileExists(p) {
			bytes, err := os.ReadFile(p)
			if err != nil {
				continue
			}
			lines := strings.Split(string(bytes), "\n")
			for _, line := range lines {
				line = strings.TrimSpace(line)
				if strings.HasPrefix(line, "id") {
					parts := strings.SplitN(line, "=", 2)
					if len(parts) == 2 {
						idVal := strings.TrimSpace(parts[1])
						idVal = strings.Trim(idVal, `"'`)
						if idVal != "" {
							return idVal
						}
					}
				}
			}
		}
	}
	return ""
}

// Core auto-detection on non-Windows
func runDetection() DetectionResult {
	res := DetectionResult{
		VNC:       make(map[string]ToolStatus),
		Timestamp: time.Now(),
		CacheTTL:  CacheTTL,
	}

	// AnyDesk
	anydeskPath := "/usr/bin/anydesk"
	res.AnyDesk = ToolStatus{
		Installed:  fileExists(anydeskPath),
		Running:    isProcessRunning("anydesk"),
		ID:         getAnydeskID(),
		ExePath:    anydeskPath,
		Version:    "v6.3.0",
		DetectedAt: time.Now(),
	}

	// RustDesk
	rustdeskPath := "/usr/bin/rustdesk"
	res.RustDesk = ToolStatus{
		Installed:  fileExists(rustdeskPath),
		Running:    isProcessRunning("rustdesk"),
		ID:         getRustdeskID(),
		ExePath:    rustdeskPath,
		Version:    "v1.2.3",
		DetectedAt: time.Now(),
	}

	// VNC Viewers
	res.VNC["TigerVNC"] = ToolStatus{
		Installed:  fileExists("/usr/bin/vncviewer"),
		Running:    isProcessRunning("vncviewer"),
		ExePath:    "/usr/bin/vncviewer",
		Version:    "v1.13.1",
		DetectedAt: time.Now(),
	}
	res.VNC["UltraVNC"] = ToolStatus{Installed: false}
	res.VNC["RealVNC"] = ToolStatus{Installed: false}

	return res
}

// Subprocess Launch Logic on non-Windows
func handleLaunch(payload LaunchPayload) error {
	var cmd *exec.Cmd

	switch strings.ToLower(payload.Tool) {
	case "rustdesk":
		exe := "/usr/bin/rustdesk"
		if !fileExists(exe) {
			return fmt.Errorf("rustdesk not installed")
		}
		args := []string{"--connect", payload.ID}
		cmd = exec.Command(exe, args...)

	case "anydesk":
		exe := "/usr/bin/anydesk"
		if !fileExists(exe) {
			return fmt.Errorf("anydesk not installed")
		}
		args := []string{payload.ID}
		cmd = exec.Command(exe, args...)

	case "vnc":
		exe := "/usr/bin/vncviewer"
		if !fileExists(exe) {
			return fmt.Errorf("vncviewer not installed")
		}
		connStr := payload.Host
		if payload.Port != 0 {
			connStr = fmt.Sprintf("%s:%d", payload.Host, payload.Port)
		}
		cmd = exec.Command(exe, connStr)

	case "rdp":
		exe := "/usr/bin/remmina"
		if fileExists(exe) {
			cmd = exec.Command(exe, "-c", fmt.Sprintf("rdp://%s", payload.Host))
		} else if fileExists("/usr/bin/xfreerdp") {
			cmd = exec.Command("/usr/bin/xfreerdp", "/v:"+payload.Host)
		} else {
			return fmt.Errorf("rdp client not installed")
		}

	case "explorer":
		// xdg-open stands in for Windows explorer on Linux
		cmd = exec.Command("xdg-open", ".")

	case "logs":
		path := payload.Path
		if path == "" {
			path = "debug.log"
		}
		cmd = exec.Command("xdg-open", path)

	default:
		return fmt.Errorf("unsupported remote tool on Linux: %s", payload.Tool)
	}

	if cmd != nil {
		err := cmd.Start()
		if err != nil {
			return fmt.Errorf("failed to start process: %w", err)
		}
	}

	return nil
}
