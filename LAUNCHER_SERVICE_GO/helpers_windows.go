//go:build windows

package main

import (
	"bufio"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"golang.org/x/sys/windows/registry"
)

// Windows creation flags
const CREATE_NEW_CONSOLE = 0x00000010

// Candidate paths on Windows
var anydeskCandidates = []string{
	`C:\Program Files (x86)\AnyDesk\AnyDesk.exe`,
	`C:\Program Files\AnyDesk\AnyDesk.exe`,
}

var rustdeskCandidates = []string{
	`C:\Program Files\RustDesk\rustdesk.exe`,
	`C:\Program Files (x86)\RustDesk\rustdesk.exe`,
}

var vncCandidates = map[string][]string{
	"UltraVNC": {
		`C:\Program Files\UltraVNC\vncviewer.exe`,
		`C:\Program Files (x86)\UltraVNC\vncviewer.exe`,
	},
	"TigerVNC": {
		`C:\Program Files\TigerVNC\vncviewer.exe`,
		`C:\Program Files (x86)\TigerVNC\vncviewer.exe`,
	},
	"RealVNC": {
		`C:\Program Files\RealVNC\VNC Viewer\vncviewer.exe`,
		`C:\Program Files (x86)\RealVNC\VNC Viewer\vncviewer.exe`,
	},
}

// Registry lookup helper on Windows
func findInRegistry(path, keyName string) string {
	k, err := registry.OpenKey(registry.LOCAL_MACHINE, path, registry.QUERY_VALUE)
	if err != nil {
		k, err = registry.OpenKey(registry.CURRENT_USER, path, registry.QUERY_VALUE)
		if err != nil {
			return ""
		}
	}
	defer k.Close()

	val, _, err := k.GetStringValue(keyName)
	if err != nil {
		return ""
	}
	return val
}

// Process running check helper (Fase 3: Auto Detect Running Process)
func isProcessRunning(name string) bool {
	cmd := exec.Command("tasklist", "/FI", "IMAGENAME eq "+name, "/NH")
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
	out, err := cmd.Output()
	if err != nil {
		return false
	}
	return strings.Contains(strings.ToLower(string(out)), strings.ToLower(name))
}

// AnyDesk ID Reader (Fase 3: Auto Detect Remote ID)
func getAnydeskID() string {
	paths := []string{
		filepath.Join(os.Getenv("PROGRAMDATA"), "AnyDesk", "system.conf"),
		filepath.Join(os.Getenv("APPDATA"), "AnyDesk", "system.conf"),
	}
	for _, p := range paths {
		if fileExists(p) {
			file, err := os.Open(p)
			if err != nil {
				continue
			}
			scanner := bufio.NewScanner(file)
			for scanner.Scan() {
				line := scanner.Text()
				if strings.HasPrefix(line, "ad.anydesk.id=") {
					file.Close()
					return strings.TrimSpace(strings.TrimPrefix(line, "ad.anydesk.id="))
				}
			}
			if err := scanner.Err(); err != nil {
				// Log or handle scan error if needed
			}
			file.Close()
		}
	}
	return ""
}

// RustDesk ID Reader (Fase 3: Auto Detect Remote ID)
func getRustdeskID() string {
	paths := []string{
		filepath.Join(os.Getenv("APPDATA"), "RustDesk", "config", "RustDesk.toml"),
		filepath.Join(os.Getenv("APPDATA"), "RustDesk", "config", "RustDesk2.toml"),
		filepath.Join(os.Getenv("PROGRAMDATA"), "RustDesk", "config", "RustDesk.toml"),
		filepath.Join(os.Getenv("PROGRAMDATA"), "RustDesk", "config", "RustDesk2.toml"),
		`C:\Windows\ServiceProfiles\LocalService\AppData\Roaming\RustDesk\config\RustDesk.toml`,
		`C:\Windows\ServiceProfiles\LocalService\AppData\Roaming\RustDesk\config\RustDesk2.toml`,
	}
	for _, p := range paths {
		if fileExists(p) {
			bytes, err := os.ReadFile(p)
			if err != nil {
				continue
			}
			content := string(bytes)
			lines := strings.Split(content, "\n")
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

// Core auto-detection
func runDetection() DetectionResult {
	res := DetectionResult{
		VNC:       make(map[string]ToolStatus),
		Timestamp: time.Now(),
		CacheTTL:  CacheTTL,
	}

	// 1. Detect AnyDesk
	anydeskPath := ""
	for _, p := range anydeskCandidates {
		if fileExists(p) {
			anydeskPath = p
			break
		}
	}
	if anydeskPath == "" {
		// Registry fallback
		regPath := findInRegistry(`SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\AnyDesk`, "DisplayIcon")
		if fileExists(regPath) {
			anydeskPath = regPath
		}
	}
	if anydeskPath != "" {
		res.AnyDesk = ToolStatus{
			Installed:  true,
			Running:    isProcessRunning("AnyDesk.exe"),
			ID:         getAnydeskID(),
			ExePath:    anydeskPath,
			Version:    "Detected",
			DetectedAt: time.Now(),
		}
	} else {
		res.AnyDesk = ToolStatus{Installed: false}
	}

	// 2. Detect RustDesk
	rustdeskPath := ""
	for _, p := range rustdeskCandidates {
		if fileExists(p) {
			rustdeskPath = p
			break
		}
	}
	if rustdeskPath == "" {
		// Registry fallback
		regPath := findInRegistry(`SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\RustDesk`, "DisplayIcon")
		if fileExists(regPath) {
			rustdeskPath = regPath
		}
	}
	if rustdeskPath != "" {
		res.RustDesk = ToolStatus{
			Installed:  true,
			Running:    isProcessRunning("rustdesk.exe"),
			ID:         getRustdeskID(),
			ExePath:    rustdeskPath,
			Version:    "Detected",
			DetectedAt: time.Now(),
		}
	} else {
		res.RustDesk = ToolStatus{Installed: false}
	}

	// 3. Detect VNC Viewers
	for viewerName, paths := range vncCandidates {
		found := false
		for _, p := range paths {
			if fileExists(p) {
				res.VNC[viewerName] = ToolStatus{
					Installed:  true,
					Running:    isProcessRunning("vncviewer.exe"),
					ExePath:    p,
					Version:    "Detected",
					DetectedAt: time.Now(),
				}
				found = true
				break
			}
		}
		if !found {
			res.VNC[viewerName] = ToolStatus{Installed: false}
		}
	}

	return res
}

// Subprocess Launch Logic
func handleLaunch(payload LaunchPayload) error {
	var cmd *exec.Cmd

	switch strings.ToLower(payload.Tool) {
	case "rustdesk":
		exe := payload.ExePath
		if exe == "" {
			detectionMutex.RLock()
			d := lastDetectionResult
			detectionMutex.RUnlock()
			if d.RustDesk.Installed {
				exe = d.RustDesk.ExePath
			} else {
				return fmt.Errorf("RustDesk executable not found on host")
			}
		}
		args := []string{"--connect", payload.ID}
		if payload.Password != "" {
			args = append(args, "--password", payload.Password)
		}
		cmd = exec.Command(exe, args...)

	case "anydesk":
		exe := payload.ExePath
		if exe == "" {
			detectionMutex.RLock()
			d := lastDetectionResult
			detectionMutex.RUnlock()
			if d.AnyDesk.Installed {
				exe = d.AnyDesk.ExePath
			} else {
				return fmt.Errorf("AnyDesk executable not found on host")
			}
		}
		args := []string{payload.ID, "--with-password"}
		cmd = exec.Command(exe, args...)
		if payload.Password != "" {
			cmd.Env = append(os.Environ(), "ADY_PASSWORD="+payload.Password)
		}

	case "vnc":
		exe := payload.ExePath
		if exe == "" {
			detectionMutex.RLock()
			d := lastDetectionResult
			detectionMutex.RUnlock()
			for _, details := range d.VNC {
				if details.Installed {
					exe = details.ExePath
					break
				}
			}
			if exe == "" {
				return fmt.Errorf("VNC Viewer executable not found on host")
			}
		}
		connStr := payload.Host
		if payload.Port != 0 {
			connStr = fmt.Sprintf("%s:%d", payload.Host, payload.Port)
		}
		args := []string{connStr}
		if payload.Password != "" {
			args = append(args, "/password", payload.Password)
		}
		cmd = exec.Command(exe, args...)

	case "rdp":
		exe := payload.ExePath
		if exe == "" {
			exe = `C:\Windows\System32\mstsc.exe`
		}
		if payload.Host == "" {
			return fmt.Errorf("missing Host parameter for RDP")
		}
		args := []string{fmt.Sprintf("/v:%s", payload.Host)}
		cmd = exec.Command(exe, args...)

	case "explorer":
		path := payload.Path
		if path == "" {
			path = "."
		}
		absPath, err := filepath.Abs(path)
		if err != nil {
			absPath = path
		}
		cmd = exec.Command("explorer.exe", absPath)

	case "logs":
		path := payload.Path
		if path == "" {
			path = "debug.log"
		}
		absPath, err := filepath.Abs(path)
		if err != nil {
			absPath = path
		}
		cmd = exec.Command("notepad.exe", absPath)

	default:
		return fmt.Errorf("unsupported remote tool: %s", payload.Tool)
	}

	cmd.SysProcAttr = &syscall.SysProcAttr{
		CreationFlags: CREATE_NEW_CONSOLE,
	}

	// Start process asynchronously
	err := cmd.Start()
	if err != nil {
		return fmt.Errorf("failed to start process: %w", err)
	}

	return nil
}
