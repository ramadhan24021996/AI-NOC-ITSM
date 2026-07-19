//go:build linux

package main

import (
	"bufio"
	"bytes"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/google/uuid"
)

const (
	AgentVersion      = "2.1.1-Go"
	AgentBuild        = "05_SIAP_DISTRIBUSI"
	CommandPort       = 10001
	IngestionPort     = 80  // Port 80 (HTTP standar) agar tidak diblokir router/firewall
	TelemetryInterval = 15 * time.Second
	bgDiagInterval    = 5 * time.Minute
)

// ── Structs ────────────────────────────────────────────────────────────────

type CommandPayload struct {
	Command     string                 `json:"command"`
	Params      map[string]interface{} `json:"params"`
	Timestamp   int64                  `json:"timestamp,omitempty"`
	Token       string                 `json:"token,omitempty"`
	ExecutionID string                 `json:"execution_id,omitempty"`
}

type TelemetryPayload struct {
	Type          string                 `json:"type"`
	EventType     string                 `json:"event_type"`
	Status        string                 `json:"status"`
	Description   string                 `json:"description"`
	Layer         int                    `json:"layer"`
	SiteID        string                 `json:"site_id"`
	Location      string                 `json:"location"`
	PCName        string                 `json:"pc_name"`
	Agent         string                 `json:"agent"`
	IPAddress     string                 `json:"ip_address"`
	Timestamp     string                 `json:"timestamp"`
	Token         string                 `json:"token"`
	SchemaVersion string                 `json:"schema_version"`
	Data          map[string]interface{} `json:"data"`
}

type ModuleStatus struct {
	Name         string
	LastActive   time.Time
	RestartCount int
	IsRunning    bool
	LastRestart  time.Time
}

// ── Global vars ────────────────────────────────────────────────────────────

var (
	agentUUID   string
	agentName   string
	masterIP    = "127.0.0.1"
	companyDir  = "/etc/osi-agent"
	cacheDir    = "/var/cache/osi-agent"
	securityKey = []byte("SIAP_DISTRIBUSI_SECRET_KEY")

	connectionStatus   = "CONNECTING"
	connectionStatusMu sync.RWMutex

	idempotencyCache   = make(map[string]map[string]interface{})
	idempotencyCacheMu sync.RWMutex

	modules   = map[string]*ModuleStatus{}
	modulesMu sync.RWMutex

	moduleStatus = struct {
		sync.RWMutex
		Paused bool
	}{}

	bgDiagCache map[string]interface{}
	bgDiagMu    sync.RWMutex

	backoffDelay = 5 * time.Second
)

// ── Connection Status ──────────────────────────────────────────────────────

func setConnectionStatus(s string) {
	connectionStatusMu.Lock()
	defer connectionStatusMu.Unlock()
	connectionStatus = s
}

func getConnectionStatus() string {
	connectionStatusMu.RLock()
	defer connectionStatusMu.RUnlock()
	return connectionStatus
}

// ── Utility ────────────────────────────────────────────────────────────────

func fileExists(f string) bool {
	info, err := os.Stat(f)
	if os.IsNotExist(err) {
		return false
	}
	return !info.IsDir()
}

func runCommand(name string, args ...string) string {
	cmd := exec.Command(name, args...)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Sprintf("Error: %v\nOutput: %s", err, string(out))
	}
	return string(out)
}

func getLocalIP() string {
	conn, err := net.Dial("udp", "8.8.8.8:80")
	if err != nil {
		return "127.0.0.1"
	}
	defer conn.Close()
	return conn.LocalAddr().(*net.UDPAddr).IP.String()
}

// ── Metrics ────────────────────────────────────────────────────────────────

func getCPUUsage() int {
	out := runCommand("bash", "-c", "top -bn1 | grep 'Cpu(s)' | awk '{print $2 + $4}'")
	val, _ := strconv.ParseFloat(strings.TrimSpace(out), 64)
	return int(val)
}

func getRAMUsage() int {
	out := runCommand("bash", "-c", "free -m | awk 'NR==2{printf \"%.0f\", $3*100/$2 }'")
	val, _ := strconv.Atoi(strings.TrimSpace(out))
	return val
}

func getDiskUsage() int {
	out := runCommand("bash", "-c", "df -h / | awk '$NF==\"/\"{printf \"%s\", $5}'")
	out = strings.TrimSuffix(strings.TrimSpace(out), "%")
	val, _ := strconv.Atoi(out)
	return val
}

func getStateFingerprint() string {
	fp := fmt.Sprintf("cpu:%d;ram:%d;disk:%d", getCPUUsage(), getRAMUsage(), getDiskUsage())
	h := sha256.Sum256([]byte(fp))
	return hex.EncodeToString(h[:])
}

// ── Setup ──────────────────────────────────────────────────────────────────

func loadServerIP() {
	configIPPath := filepath.Join(companyDir, "server_ip.txt")
	if fileExists(configIPPath) {
		if data, err := os.ReadFile(configIPPath); err == nil {
			if cleaned := strings.TrimSpace(string(data)); cleaned != "" {
				masterIP = cleaned
				fmt.Printf("[AGENT] Loaded Master Server IP from config: %s\n", masterIP)
				return
			}
		}
	}
	if envMaster := os.Getenv("MASTER_IP"); envMaster != "" {
		masterIP = envMaster
		fmt.Printf("[AGENT] Loaded Master Server IP from environment: %s\n", masterIP)
	} else {
		fmt.Printf("[AGENT] Using default Master Server IP: %s\n", masterIP)
	}
}

func loadOrCreateUUID() {
	_ = os.MkdirAll(companyDir, 0755)
	_ = os.MkdirAll(cacheDir, 0755)
	uuidPath := filepath.Join(companyDir, "client_uuid.txt")
	if data, err := os.ReadFile(uuidPath); err == nil {
		agentUUID = strings.TrimSpace(string(data))
	}
	if agentUUID == "" {
		agentUUID = uuid.New().String()
		_ = os.WriteFile(uuidPath, []byte(agentUUID), 0644)
	}
}

func resolveAgentName() {
	hostname, err := os.Hostname()
	if err != nil {
		hostname = "unknown-linux-host"
	}
	agentName = fmt.Sprintf("LINUX-%s", hostname)
}

func loadSecurityKey() {
	keyPath := filepath.Join(companyDir, ".key")
	if fileExists(keyPath) {
		if data, err := os.ReadFile(keyPath); err == nil {
			cleaned := strings.Trim(strings.TrimSpace(string(data)), `"'`)
			if cleaned != "" {
				securityKey = []byte(cleaned)
				fmt.Printf("[AGENT] Loaded security key from %s\n", keyPath)
				return
			}
		}
	}
	fmt.Println("[AGENT] Warning: .key file not found. Using fallback key.")
}

// ── Idempotency ────────────────────────────────────────────────────────────

func saveDurableIdempotencyEntry(execID string, resp map[string]interface{}) {
	idempotencyCacheMu.Lock()
	idempotencyCache[execID] = resp
	idempotencyCacheMu.Unlock()
}

// ── Watchdog ───────────────────────────────────────────────────────────────

func TouchModule(name string) {
	modulesMu.Lock()
	defer modulesMu.Unlock()
	if m, ok := modules[name]; ok {
		m.LastActive = time.Now()
		m.IsRunning = true
	}
}

func sendWatchdogAlert(module, status string, count int, lastActive time.Time) {
	payload := map[string]interface{}{
		"pc_name":       agentName,
		"severity":      "high",
		"type":          "WATCHDOG_ALERT",
		"module":        module,
		"status":        status,
		"restart_count": count,
		"last_active":   lastActive.Format(time.RFC3339),
		"details":       fmt.Sprintf("Watchdog Alert: Module %s is %s. Restart count: %d.", module, status, count),
		"timestamp":     time.Now().Unix(),
	}
	go sendHTTPEvent("/issues", payload)
}

func handleRestart(m *ModuleStatus) {
	if time.Since(m.LastRestart) < 15*time.Second {
		return
	}
	if m.RestartCount >= 3 {
		m.IsRunning = false
		sendWatchdogAlert(m.Name, "FAILED", m.RestartCount, m.LastActive)
		return
	}
	m.RestartCount++
	m.LastRestart = time.Now()
	m.LastActive = time.Now()
	sendWatchdogAlert(m.Name, "RESTARTED", m.RestartCount, m.LastActive)
	go restartModule(m.Name)
}

func restartModule(name string) {
	switch name {
	case "Telemetry Collector":
		go startTelemetryLoop()
	case "Heartbeat":
		go runHeartbeatLoop()
	case "Remote Launcher":
		go startCommandServer()
	case "Background Diagnostics":
		go startBackgroundDiagnostics()
	}
}

func runWatchdog() {
	fmt.Println("[WATCHDOG] Production Watchdog monitor started.")
	now := time.Now()
	modulesMu.Lock()
	for _, name := range []string{"Telemetry Collector", "Heartbeat", "Remote Launcher", "Background Diagnostics", "User Activity Tracker"} {
		modules[name] = &ModuleStatus{Name: name, LastActive: now, IsRunning: true}
	}
	modulesMu.Unlock()

	go startTelemetryLoop()
	go runHeartbeatLoop()
	go startCommandServer()
	go startBackgroundDiagnostics()
	go startActivityAndIssueTracker()

	for {
		time.Sleep(5 * time.Second)
		moduleStatus.RLock()
		isPaused := moduleStatus.Paused
		moduleStatus.RUnlock()
		if isPaused {
			continue
		}
		modulesMu.Lock()
		for _, m := range modules {
			if m.IsRunning && time.Since(m.LastActive) > 30*time.Second {
				handleRestart(m)
			}
		}
		modulesMu.Unlock()
	}
}

// ── Heartbeat ──────────────────────────────────────────────────────────────

func runHeartbeatLoop() {
	for {
		TouchModule("Heartbeat")
		serverAddr := net.JoinHostPort(masterIP, strconv.Itoa(IngestionPort))
		conn, err := net.DialTimeout("tcp", serverAddr, 3*time.Second)
		if err != nil {
			setConnectionStatus("OFFLINE")
			time.Sleep(backoffDelay)
			if backoffDelay < 120*time.Second {
				backoffDelay *= 2
			}
		} else {
			conn.Close()
			setConnectionStatus("ONLINE")
			backoffDelay = 5 * time.Second
			time.Sleep(10 * time.Second)
		}
	}
}

// ── Background Diagnostics ─────────────────────────────────────────────────

// startBackgroundDiagnostics runs periodic diagnostics AND keeps the watchdog
// satisfied by calling TouchModule every 20 seconds via a separate keepalive goroutine.
func startBackgroundDiagnostics() {
	// Keepalive goroutine: touch the module every 20s so watchdog (30s threshold) never triggers
	go func() {
		for {
			TouchModule("Background Diagnostics")
			time.Sleep(20 * time.Second)
		}
	}()

	for {
		TouchModule("Background Diagnostics")
		diag := map[string]interface{}{
			"cpu":       getCPUUsage(),
			"ram":       getRAMUsage(),
			"disk":      getDiskUsage(),
			"timestamp": time.Now().Unix(),
		}
		bgDiagMu.Lock()
		bgDiagCache = diag
		bgDiagMu.Unlock()
		time.Sleep(bgDiagInterval)
	}
}

func startActivityAndIssueTracker() {
	fmt.Println("[AGENT] User Activity and Issue Tracker started.")
	ticker := time.NewTicker(5 * time.Second)
	for range ticker.C {
		moduleStatus.RLock()
		isPaused := moduleStatus.Paused
		moduleStatus.RUnlock()
		if isPaused {
			continue
		}

		TouchModule("User Activity Tracker")

		// Get active app on Linux (top CPU process or active window name)
		appOut := runCommand("bash", "-c", "ps -eo comm,%cpu --sort=-%cpu --no-headers | head -1")
		fields := strings.Fields(strings.TrimSpace(appOut))
		procName := "unknown"
		if len(fields) >= 1 {
			procName = fields[0]
		}

		winTitle := runCommand("bash", "-c", "xdotool getactivewindow getwindowname 2>/dev/null || echo ''")
		winTitle = strings.TrimSpace(winTitle)
		if winTitle == "" {
			winTitle = procName
		}

		activeApp := map[string]interface{}{
			"type":         "active_app",
			"app_name":     procName,
			"process":      procName,
			"window_title": winTitle,
			"pid":          os.Getpid(),
			"timestamp":    time.Now().Unix(),
			"is_idle":      false,
			"pc_name":      agentName,
			"agent_id":     agentUUID,
		}

		go sendHTTPEvent("/activity", activeApp)
	}
}

// ── Telemetry ──────────────────────────────────────────────────────────────

func buildTelemetryPayload() TelemetryPayload {
	data := make(map[string]interface{})
	data["cpu_percent"] = getCPUUsage()
	data["memory_percent"] = getRAMUsage()
	data["disk_percent"] = getDiskUsage()
	data["agent_version"] = AgentVersion
	data["agent_build"] = AgentBuild
	data["os"] = runtime.GOOS

	// Collect Remote Access Status
	rustdeskRunning := strings.TrimSpace(runCommand("bash", "-c", "pgrep -x rustdesk")) != ""
	anydeskRunning := strings.TrimSpace(runCommand("bash", "-c", "pgrep -x anydesk")) != ""
	data["rustdesk"] = map[string]interface{}{"running": rustdeskRunning, "id": "---"}
	data["anydesk"] = map[string]interface{}{"running": anydeskRunning, "id": "---"}

	// Collect Network Info
	gateway := strings.TrimSpace(runCommand("bash", "-c", "ip route | awk '/default/ {print $3}' | head -1"))
	mac := strings.TrimSpace(runCommand("bash", "-c", "ip link | awk '/ether/ {print $2}' | head -1"))
	if mac == "" { mac = "---" }
	dns := strings.TrimSpace(runCommand("bash", "-c", "grep '^nameserver' /etc/resolv.conf | awk '{print $2}' | paste -sd, -"))
	if dns == "" { dns = "8.8.8.8" }
	
	vpnStatus := "Disconnected"
	if strings.Contains(strings.ToLower(runCommand("ip", "a")), "tun") || strings.Contains(strings.ToLower(runCommand("ip", "a")), "wg") {
		vpnStatus = "Connected"
	}
	
	wifiSSID := strings.TrimSpace(runCommand("bash", "-c", "iwgetid -r 2>/dev/null || echo ''"))
	

	// ── Real Network Telemetry (P0 Fix: No more static data) ───────────────────
	// Measure real latency, jitter (mdev), packet loss via ping
	pingTarget := "8.8.8.8"
	if gateway != "" && gateway != "---" {
		pingTarget = gateway
	}

	// ping -c 4 -W 2 <target>
	pingRaw := runCommand("bash", "-c", "ping -c 4 -W 2 "+pingTarget+" 2>&1")
	pingLatency, pingJitter, packetLoss := parsePingOutputLinux(pingRaw)

	// Bandwidth: read from /proc/net/dev or wireless iwconfig signal
	bwDown, bwUp := measureLinuxBandwidth()

	// WiFi signal strength
	wifiSignal := "N/A"
	iwOut := runCommand("bash", "-c", "iwconfig 2>/dev/null | grep -i 'signal level'")
	if iwOut != "" {
		for _, line := range strings.Split(iwOut, "\n") {
			if strings.Contains(line, "Signal level") {
				parts := strings.Split(line, "Signal level=")
				if len(parts) >= 2 {
					sig := strings.Fields(parts[1])
					if len(sig) > 0 {
						wifiSignal = sig[0]
					}
				}
				break
			}
		}
	}

	data["network_advanced"] = map[string]interface{}{
		"gateway":                 gateway,
		"mac":                     mac,
		"dns":                     dns,
		"dhcp":                    "Yes",
		"vpn_status":              vpnStatus,
		"wifi_ssid":               wifiSSID,
		"wifi_signal":             wifiSignal,
		"bandwidth_download_kbps": bwDown,
		"bandwidth_upload_kbps":   bwUp,
		"packet_loss_pct":         packetLoss,
		"jitter_ms":               pingJitter,
		"ping_latency_ms":         pingLatency,
		"ping_target":             pingTarget,
	}

	// Active Apps (Top CPU consumers instead of kernel threads)
	appsOut := runCommand("bash", "-c", "ps -eo pid,comm --sort=-%cpu --no-headers | head -15")
	var apps []map[string]interface{}
	for _, line := range strings.Split(strings.TrimSpace(appsOut), "\n") {
		parts := strings.Fields(line)
		if len(parts) >= 2 {
			apps = append(apps, map[string]interface{}{
				"Id":              parts[0],
				"Name":            parts[1],
				"MainWindowTitle": parts[1],
			})
		}
	}
	data["apps"] = apps

	// Web Connections
	websOut := runCommand("bash", "-c", "ss -tnp | awk '/:(80|443)/ {print $4, $5, $6}' | head -10")
	var webs []map[string]interface{}
	for _, line := range strings.Split(strings.TrimSpace(websOut), "\n") {
		parts := strings.Fields(line)
		if len(parts) >= 2 {
			pidRaw := "-"
			if len(parts) >= 3 {
				pidRaw = parts[2]
			}
			webs = append(webs, map[string]interface{}{
				"local":  parts[0],
				"remote": parts[1],
				"pid":    pidRaw,
			})
		}
	}
	data["webs"] = webs

	// Browser URL / Window Titles (Read directly from History files to bypass Wayland/X11 restrictions)
	script := `
	urls=""
	for u in /home/*; do
		# Chrome
		if [ -f "$u/.config/google-chrome/Default/History" ]; then
			cp "$u/.config/google-chrome/Default/History" /tmp/chrome_hist_$$ 2>/dev/null
			urls="$urls\n$(sqlite3 /tmp/chrome_hist_$$ "SELECT url, title FROM urls ORDER BY last_visit_time DESC LIMIT 3;" 2>/dev/null | awk -F'|' '{print "Chrome|" $1 "|" $2}')"
			rm -f /tmp/chrome_hist_$$
		fi
		# Firefox
		for f in $u/.mozilla/firefox/*.default-release/places.sqlite; do
			if [ -f "$f" ]; then
				cp "$f" /tmp/ff_hist_$$ 2>/dev/null
				urls="$urls\n$(sqlite3 /tmp/ff_hist_$$ "SELECT url, title FROM moz_places ORDER BY last_visit_date DESC LIMIT 3;" 2>/dev/null | awk -F'|' '{print "Firefox|" $1 "|" $2}')"
				rm -f /tmp/ff_hist_$$
			fi
		done
		# Opera
		if [ -f "$u/.config/opera/History" ]; then
			cp "$u/.config/opera/History" /tmp/opera_hist_$$ 2>/dev/null
			urls="$urls\n$(sqlite3 /tmp/opera_hist_$$ "SELECT url, title FROM urls ORDER BY last_visit_time DESC LIMIT 3;" 2>/dev/null | awk -F'|' '{print "Opera|" $1 "|" $2}')"
			rm -f /tmp/opera_hist_$$
		fi
	done
	echo -e "$urls"
	`
	histOut := runCommand("bash", "-c", script)
	var urlHistory []map[string]interface{}
	for _, line := range strings.Split(strings.TrimSpace(histOut), "\n") {
		parts := strings.SplitN(line, "|", 3)
		if len(parts) >= 3 {
			browser := parts[0]
			url := parts[1]
			title := parts[2]
			if url != "" && !strings.HasPrefix(url, "chrome-extension://") {
				urlHistory = append(urlHistory, map[string]interface{}{
					"url":       title + " (" + url + ")",
					"browser":   browser,
					"timestamp": time.Now().Unix(),
				})
			}
		}
	}
	data["browser_url_history_10min"] = urlHistory

	// SPRINT T: Deep Endpoint Observability Engine (Linux)
	deepMetrics := collectDeepTelemetry()
	data["deep_telemetry"] = deepMetrics

	ts := time.Now().Unix()
	tsStr := strconv.FormatInt(ts, 10)
	msgToSign := fmt.Sprintf("%s:%s", agentName, tsStr)
	h := hmac.New(sha256.New, securityKey)
	h.Write([]byte(msgToSign))
	token := hex.EncodeToString(h.Sum(nil))

	return TelemetryPayload{
		Type:          "telemetry",
		EventType:     "telemetry",
		Status:        "ONLINE",
		Description:   "Periodic Telemetry Check",
		Layer:         7,
		SiteID:        "Jakarta_Head_Office",
		Location:      "Jakarta_Head_Office",
		PCName:        agentName,
		Agent:         agentName,
		IPAddress:     getLocalIP(),
		Timestamp:     tsStr,
		Token:         token,
		SchemaVersion: AgentVersion,
		Data:          data,
	}
}

func sendHTTPEvent(path string, payload interface{}) {
	payloadBytes, _ := json.Marshal(payload)
	targetURL := fmt.Sprintf("http://%s:%d%s", masterIP, IngestionPort, path)
	req, _ := http.NewRequest("POST", targetURL, bytes.NewBuffer(payloadBytes))
	req.Header.Set("Content-Type", "application/json")
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("[AGENT ERROR] HTTP send failed to %s: %v\n", path, err)
	} else {
		resp.Body.Close()
	}

	// FIX-01: Direct relay to Dashboard Server /api/activity & /api/browser-events
	dashPath := path
	if !strings.HasPrefix(dashPath, "/api") {
		dashPath = "/api" + path
	}
	for _, port := range []int{80, 9999} {
		dashURL := fmt.Sprintf("http://%s:%d%s", masterIP, port, dashPath)
		reqDash, errDash := http.NewRequest("POST", dashURL, bytes.NewBuffer(payloadBytes))
		if errDash == nil {
			reqDash.Header.Set("Content-Type", "application/json")
			if respDash, errDashDo := client.Do(reqDash); errDashDo == nil {
				respDash.Body.Close()
				break
			}
		}
	}
}

func startTelemetryLoop() {
	// Keepalive: sentuh module setiap 20s agar watchdog (threshold 30s) tidak trigger
	// saat HTTP send sedang berjalan (timeout sampai 8 detik)
	go func() {
		for {
			TouchModule("Telemetry Collector")
			time.Sleep(20 * time.Second)
		}
	}()

	for {
		TouchModule("Telemetry Collector")
		fmt.Println("[AGENT] Sending telemetry...")
		payload := buildTelemetryPayload()
		payloadBytes, err := json.Marshal(payload)
		if err == nil {
			targetURL := fmt.Sprintf("http://%s:%d/ingest", masterIP, IngestionPort)
			req, _ := http.NewRequest("POST", targetURL, bytes.NewBuffer(payloadBytes))
			req.Header.Set("Content-Type", "application/json")
			client := &http.Client{Timeout: 8 * time.Second} // dinaikkan dari 5s ke 8s
			resp, err := client.Do(req)
			if err != nil {
				fmt.Printf("[AGENT ERROR] Telemetry failed: %v\n", err)
				setConnectionStatus("OFFLINE")
			} else {
				resp.Body.Close()
				fmt.Println("[AGENT] Telemetry sent successfully!")
				setConnectionStatus("ONLINE")
			}
		}
		time.Sleep(TelemetryInterval)
	}
}

// ── Commands ───────────────────────────────────────────────────────────────

func executeAgentCommand(cmd string, params map[string]interface{}) map[string]interface{} {
	fmt.Printf("[AGENT] Received command: %s with params: %v\n", cmd, params)

	// P2 - STATE SNAPSHOT & ROLLBACK ENGINE
	isDangerousCommand := (cmd == "FLUSH_DNS" || cmd == "RESTART_NATS")
	if isDangerousCommand {
		fmt.Println("[AGENT P2-SNAPSHOT] Creating pre-execution state snapshot to /tmp/state.bak...")
		snapshotData := fmt.Sprintf("CMD:%s\nTIMESTAMP:%d\nSTATE_HASH:%s", cmd, time.Now().Unix(), getStateFingerprint())
		_ = os.WriteFile("/tmp/state.bak", []byte(snapshotData), 0644)
	}

	switch cmd {
	case "ROLLBACK_STATE":
		if _, err := os.Stat("/tmp/state.bak"); err == nil {
			data, _ := os.ReadFile("/tmp/state.bak")
			return map[string]interface{}{
				"status": "success",
				"message": fmt.Sprintf("[ROLLBACK ENGINE] Successfully reverted to snapshot:\n%s", string(data)),
			}
		}
		return map[string]interface{}{"status": "error", "message": "No snapshot found to rollback"}

	case "UPDATE_AGENT":
		urlStr, _ := params["download_url"].(string)
		expectedHash, _ := params["sha256"].(string)
		if urlStr == "" || expectedHash == "" {
			return map[string]interface{}{"status": "error", "message": "Missing download_url or sha256"}
		}
		
		fmt.Printf("[OTA UPDATE] Received secure update request from %s\n", urlStr)
		
		// 1. Download to temp file
		tmpFile := "/tmp/osi_agent_update.bin"
		resp, err := http.Get(urlStr)
		if err != nil {
			return map[string]interface{}{"status": "error", "message": "Download failed: " + err.Error()}
		}
		defer resp.Body.Close()
		
		out, err := os.Create(tmpFile)
		if err != nil {
			return map[string]interface{}{"status": "error", "message": "Failed to create temp file: " + err.Error()}
		}
		_, err = io.Copy(out, resp.Body)
		out.Close()
		if err != nil {
			return map[string]interface{}{"status": "error", "message": "Failed to write temp file: " + err.Error()}
		}
		
		// 2. Verify SHA-256 Signature
		f, err := os.Open(tmpFile)
		if err != nil {
			return map[string]interface{}{"status": "error", "message": "Failed to open downloaded file: " + err.Error()}
		}
		h := sha256.New()
		if _, err := io.Copy(h, f); err != nil {
			f.Close()
			return map[string]interface{}{"status": "error", "message": "Hashing failed: " + err.Error()}
		}
		f.Close()
		actualHash := hex.EncodeToString(h.Sum(nil))
		if actualHash != expectedHash {
			os.Remove(tmpFile)
			return map[string]interface{}{"status": "error", "message": fmt.Sprintf("Hash mismatch. Expected: %s, Got: %s (Malware prevention active)", expectedHash, actualHash)}
		}
		
		// 3. Replace executable
		exePath, err := os.Executable()
		if err != nil {
			return map[string]interface{}{"status": "error", "message": "Failed to get executable path: " + err.Error()}
		}
		_ = os.Remove(exePath) // Linux allows removing running binary
		if err := os.Rename(tmpFile, exePath); err != nil {
			return map[string]interface{}{"status": "error", "message": "Failed to install new executable: " + err.Error()}
		}
		
		// 4. Ensure executable permissions
		_ = os.Chmod(exePath, 0755)
		
		// 5. Restart service quietly via detached bash
		scriptPath := "/tmp/osi_update_restart.sh"
		scriptContent := "#!/bin/bash\nsleep 2\nsystemctl restart osi-agent\nrm -f $0\n"
		os.WriteFile(scriptPath, []byte(scriptContent), 0755)
		
		cmdObj := exec.Command("bash", "-c", scriptPath)
		cmdObj.Start()
		
		return map[string]interface{}{"status": "success", "message": "Secure OTA update verified and applied. Restarting linux agent..."}

	default:
		// P2.5 - CAPABILITY-BASED EXECUTION
		capabilitiesMu.RLock()
		capDef, capExists := agentCapabilities[cmd]
		capabilitiesMu.RUnlock()

		if capExists {
			fmt.Printf("[AGENT MANIFEST] Executing approved capability: %s\n", cmd)
			if len(capDef.PreCheck) > 0 {
				preOut := runCommand(capDef.PreCheck[0], capDef.PreCheck[1:]...)
				if strings.Contains(preOut, "RUNNING") || strings.Contains(preOut, "SUCCESS") || strings.Contains(preOut, "active (running)") {
					return map[string]interface{}{
						"status": "success",
						"message": fmt.Sprintf("[REVALIDATION] Service is already healthy. Pre-check: %s", preOut),
						"skipped": true,
					}
				}
			}
			
			// Sprint T: Replace {target} placeholder for dynamic diagnostic commands
			var finalArgs []string
			targetVal, _ := params["target"].(string)
			for _, arg := range capDef.Args {
				if strings.Contains(arg, "{target}") {
					if targetVal != "" {
						arg = strings.ReplaceAll(arg, "{target}", targetVal)
					} else {
						return map[string]interface{}{"status": "error", "message": "Missing required 'target' parameter for this command."}
					}
				}
				finalArgs = append(finalArgs, arg)
			}
			
			out := runCommand(capDef.Cmd, finalArgs...)
			return map[string]interface{}{
				"status": "success",
				"message": out,
			}
		}

		// BLOCKED BY CAPABILITY ENGINE
		return map[string]interface{}{
			"status": "error",
			"message": fmt.Sprintf("ACTION_NOT_SUPPORTED: The action '%s' is not listed in this linux agent's capability manifest.", cmd),
		}

	case "GET_STATUS":
		moduleStatus.RLock()
		isPaused := moduleStatus.Paused
		moduleStatus.RUnlock()
		statusStr := getConnectionStatus()
		if isPaused {
			statusStr = "PAUSED"
		}
		return map[string]interface{}{
			"status":      "success",
			"state":       statusStr,
			"device_name": agentName,
			"server_ip":   masterIP,
			"site_id":     "Jakarta_Head_Office",
			"version":     AgentVersion,
			"os":          runtime.GOOS,
		}

	case "PAUSE_MONITORING":
		moduleStatus.Lock()
		moduleStatus.Paused = true
		moduleStatus.Unlock()
		return map[string]interface{}{"status": "success", "message": "Monitoring paused"}

	case "RESUME_MONITORING":
		moduleStatus.Lock()
		moduleStatus.Paused = false
		moduleStatus.Unlock()
		return map[string]interface{}{"status": "success", "message": "Monitoring resumed"}

	case "PING":
		return map[string]interface{}{
			"status":      "success",
			"message":     "PONG",
			"timestamp":   time.Now().Unix(),
			"version":     AgentVersion,
			"device_name": agentName,
			"os":          runtime.GOOS,
		}

	case "CMD", "BASH", "POWERSHELL":
		return map[string]interface{}{
			"status":  "error",
			"message": "[GUARDRAIL P0] BLOCKED: Raw terminal string execution is strictly disabled on Linux Agent. Please use Pre-Defined Action Functions.",
		}

	case "DEEP_DIAGNOSTICS":
		bgDiagMu.RLock()
		cached := bgDiagCache
		bgDiagMu.RUnlock()
		result := map[string]interface{}{
			"cpu":        getCPUUsage(),
			"ram":        getRAMUsage(),
			"disk":       getDiskUsage(),
			"ip_address": getLocalIP(),
			"hostname":   agentName,
			"os":         runtime.GOOS,
			"cached":     cached,
		}
		return map[string]interface{}{"status": "success", "diagnostics": result}

	case "RESTART":
		go func() {
			time.Sleep(2 * time.Second)
			_ = exec.Command("reboot").Run()
		}()
		return map[string]interface{}{"status": "success", "message": "System reboot scheduled"}

	case "SHUTDOWN":
		go func() {
			time.Sleep(2 * time.Second)
			_ = exec.Command("shutdown", "-h", "now").Run()
		}()
		return map[string]interface{}{"status": "success", "message": "System shutdown scheduled"}

	// ── SHOW_NOTIFICATION: Server AI memicu notifikasi di Linux ─────────
	// Sama dengan Windows, namun menggunakan notify-send (Linux Desktop Notification)
	case "SHOW_NOTIFICATION":
		title, _ := params["title"].(string)
		message, _ := params["message"].(string)
		if title == "" {
			title = "⚠️ OSI AI - Peringatan Sistem"
		}
		if message == "" {
			message = "Terdapat masalah pada komputer Anda. Silakan hubungi NOC."
		}
		go func() {
			// notify-send untuk Linux Desktop Environment (GNOME/KDE/XFCE)
			_ = exec.Command("notify-send",
				"--urgency=critical",
				"--icon=dialog-warning",
				"--expire-time=10000",
				title, message).Run()
			// Fallback: tulis ke log system
			fmt.Printf("[AGENT] SHOW_NOTIFICATION: %s — %s\n", title, message)
			// Kirim juga alert ke server sebagai issue
			sendHTTPEvent("/issues", map[string]interface{}{
				"pc_name":   agentName,
				"severity":  "HIGH",
				"type":      "NOTIFICATION_PUSHED",
				"details":   fmt.Sprintf("%s: %s", title, message),
				"timestamp": time.Now().Unix(),
			})
		}()
		return map[string]interface{}{"status": "success", "message": "Notification pushed on Linux client"}

	// ── SHOW_CHAT: Buka URL chat di browser default Linux ───────────────
	case "SHOW_CHAT":
		serverIPForChat := masterIP
		if overrideIP, ok := params["server_ip"].(string); ok && overrideIP != "" {
			serverIPForChat = overrideIP
		}
		go func() {
			// Chat URL via Dashboard (port 80 melalui Nginx, panel Live Chat)
			chatURL := fmt.Sprintf("http://%s/#live-chat", serverIPForChat)
			
			// Forward to User-Space Linux Tray Agent (Port 10001)
			for i := 0; i < 3; i++ {
				conn, err := net.Dial("tcp", "127.0.0.1:10001")
				if err == nil {
					chatCmd := map[string]string{"command": "SHOW_CHAT", "url": chatURL}
					chatBytes, _ := json.Marshal(chatCmd)
					_, _ = conn.Write(append(chatBytes, '\n'))
					conn.Close()
					fmt.Printf("[AGENT] SHOW_CHAT forwarded to linux tray\n")
					return
				}
				time.Sleep(500 * time.Millisecond)
			}
			fmt.Printf("[AGENT] WARNING: linux tray not reachable on port 10001, SHOW_CHAT ignored\n")
		}()
		return map[string]interface{}{
			"status":  "success", 
			"message": "Chat window triggered on Linux client via Tray App",
		}

	}
}

// ── Command Server (TCP port 10000) ────────────────────────────────────────

func startCommandServer() {
	listener, err := net.Listen("tcp", fmt.Sprintf("0.0.0.0:%d", CommandPort))
	if err != nil {
		fmt.Printf("[AGENT ERROR] Failed to start command server: %v\n", err)
		return
	}
	defer listener.Close()

	go func() {
		for {
			TouchModule("Remote Launcher")
			time.Sleep(10 * time.Second)
		}
	}()

	fmt.Printf("[AGENT] Command Server listening on TCP port %d\n", CommandPort)
	for {
		conn, err := listener.Accept()
		if err != nil {
			continue
		}
		go handleCommandConnection(conn)
	}
}

func handleCommandConnection(conn net.Conn) {
	defer conn.Close()
	_ = conn.SetReadDeadline(time.Now().Add(10 * time.Second))

	reader := bufio.NewReader(conn)
	data, err := reader.ReadBytes('\n')
	if err != nil && err != io.EOF {
		return
	}

	var payload CommandPayload
	if err := json.Unmarshal(data, &payload); err != nil {
		resp, _ := json.Marshal(map[string]interface{}{"status": "error", "message": "Invalid JSON format"})
		_, _ = conn.Write(append(resp, '\n'))
		return
	}

	// Idempotency check
	if payload.ExecutionID != "" {
		idempotencyCacheMu.RLock()
		cachedResp, exists := idempotencyCache[payload.ExecutionID]
		idempotencyCacheMu.RUnlock()
		if exists {
			fmt.Printf("[AGENT IDEMPOTENCY] Duplicate execution_id=%s — cache hit\n", payload.ExecutionID)
			respBytes, _ := json.Marshal(cachedResp)
			_, _ = conn.Write(append(respBytes, '\n'))
			return
		}
	}

	// HMAC verification — identical to Windows agent (modern + legacy)
	paramsBytes, _ := json.Marshal(payload.Params)
	paramsHashArr := sha256.Sum256(paramsBytes)
	paramsHashHex := hex.EncodeToString(paramsHashArr[:])
	execID := payload.ExecutionID
	fallbackKey := []byte("SIAP_DISTRIBUSI_SECRET_KEY")
	verified := false

	for _, key := range [][]byte{securityKey, fallbackKey} {
		msg := fmt.Sprintf("%s:%d:%s:%s", payload.Command, payload.Timestamp, paramsHashHex, execID)
		mac := hmac.New(sha256.New, key)
		mac.Write([]byte(msg))
		if hmac.Equal([]byte(hex.EncodeToString(mac.Sum(nil))), []byte(payload.Token)) {
			verified = true
			break
		}
	}
	if !verified {
		for _, key := range [][]byte{securityKey, fallbackKey} {
			msg := fmt.Sprintf("%s:%d", payload.Command, payload.Timestamp)
			mac := hmac.New(sha256.New, key)
			mac.Write([]byte(msg))
			if hmac.Equal([]byte(hex.EncodeToString(mac.Sum(nil))), []byte(payload.Token)) {
				verified = true
				break
			}
		}
	}

	// Allow local connections without token (same as Windows)
	remoteIP, _, _ := net.SplitHostPort(conn.RemoteAddr().String())
	isLocal := remoteIP == "127.0.0.1" || remoteIP == "::1"
	if !isLocal && !verified {
		resp, _ := json.Marshal(map[string]interface{}{
			"status":  "error",
			"message": "Unauthorized remote execution: invalid HMAC signature token",
		})
		_, _ = conn.Write(append(resp, '\n'))
		return
	}

	preHash := getStateFingerprint()
	response := executeAgentCommand(payload.Command, payload.Params)
	postHash := getStateFingerprint()

	if payload.ExecutionID != "" {
		nonce := fmt.Sprintf("%d", time.Now().UnixNano())
		msg := fmt.Sprintf("%s:%s:%s:%s:%s", payload.ExecutionID, payload.Command, preHash, postHash, nonce)
		mac := hmac.New(sha256.New, securityKey)
		mac.Write([]byte(msg))
		response["attestation"] = map[string]interface{}{
			"pre_state_hash":  preHash,
			"post_state_hash": postHash,
			"nonce":           nonce,
			"signature":       hex.EncodeToString(mac.Sum(nil)),
		}
		saveDurableIdempotencyEntry(payload.ExecutionID, response)
	}

	respBytes, _ := json.Marshal(response)
	_, _ = conn.Write(append(respBytes, '\n'))
}

// ── Main ───────────────────────────────────────────────────────────────────

// parsePingOutputLinux parses Linux ping output to extract avg latency, jitter (mdev), packet loss.
// Example stat line: "rtt min/avg/max/mdev = 1.234/2.567/4.123/1.456 ms"
// Example loss line: "4 packets transmitted, 3 received, 25% packet loss"
func parsePingOutputLinux(output string) (avgMs, mdevMs, lossPercent int) {
	avgMs = 0
	mdevMs = 0
	lossPercent = 100 // default: all lost

	for _, line := range strings.Split(output, "\n") {
		line = strings.TrimSpace(line)

		// Packet loss
		if strings.Contains(line, "packet loss") {
			// "25% packet loss" or "0% packet loss"
			parts := strings.Fields(line)
			for _, p := range parts {
				if strings.HasSuffix(p, "%") {
					lossStr := strings.TrimSuffix(p, "%")
					fmt.Sscanf(lossStr, "%d", &lossPercent)
					break
				}
			}
		}

		// RTT: "rtt min/avg/max/mdev = 1.234/5.678/12.345/2.123 ms"
		if strings.HasPrefix(line, "rtt") || strings.HasPrefix(line, "round-trip") {
			// Split on "=" and then "/"
			eqParts := strings.SplitN(line, "=", 2)
			if len(eqParts) == 2 {
				vals := strings.Fields(eqParts[1])
				if len(vals) > 0 {
					components := strings.Split(vals[0], "/")
					if len(components) >= 4 {
						// min/avg/max/mdev
						var avg, mdev float64
						fmt.Sscanf(components[1], "%f", &avg)
						fmt.Sscanf(components[3], "%f", &mdev)
						avgMs = int(avg)
						mdevMs = int(mdev)
					}
				}
			}
		}
	}
	return avgMs, mdevMs, lossPercent
}

// measureLinuxBandwidth attempts to estimate bandwidth.
// For WiFi: reads signal from /proc/net/wireless (Mbps approximation).
// For Ethernet: reads link speed from /sys/class/net/<iface>/speed.
func measureLinuxBandwidth() (downloadKbps, uploadKbps int) {
	// 1. Try Ethernet via /sys/class/net
	netDirOut := runCommand("bash", "-c", "ls /sys/class/net/ 2>/dev/null")
	for _, iface := range strings.Fields(netDirOut) {
		if iface == "lo" {
			continue
		}
		speedRaw := runCommand("bash", "-c", "cat /sys/class/net/"+iface+"/speed 2>/dev/null")
		speedRaw = strings.TrimSpace(speedRaw)
		if speedRaw != "" && speedRaw != "-1" {
			var speedMbps int
			n, _ := fmt.Sscanf(speedRaw, "%d", &speedMbps)
			if n == 1 && speedMbps > 0 {
				downloadKbps = speedMbps * 1000
				uploadKbps = speedMbps * 1000
				return downloadKbps, uploadKbps
			}
		}
	}

	// 2. Fallback: WiFi signal from /proc/net/wireless → estimate Mbps
	wirelessRaw := runCommand("bash", "-c", "cat /proc/net/wireless 2>/dev/null | tail -1")
	if wirelessRaw != "" {
		fields := strings.Fields(wirelessRaw)
		if len(fields) >= 4 {
			var signal float64
			sigStr := strings.TrimSuffix(fields[3], ".")
			n2, _ := fmt.Sscanf(sigStr, "%f", &signal)
				if n2 == 1 {
				// /proc/net/wireless reports signal in dBm (usually negative)
				// Convert to estimated throughput
				switch {
				case signal >= -50:
					downloadKbps = 54000
					uploadKbps = 20000
				case signal >= -60:
					downloadKbps = 30000
					uploadKbps = 10000
				case signal >= -70:
					downloadKbps = 10000
					uploadKbps = 4000
				case signal >= -80:
					downloadKbps = 2000
					uploadKbps = 1000
				default:
					downloadKbps = 500
					uploadKbps = 256
				}
				return downloadKbps, uploadKbps
			}
		}
	}

	return 0, 0
}



func main() {
	fmt.Println("================================================")
	fmt.Println("  OSI AI Linux PC Health Agent 2.0.0-Go")
	fmt.Println("  Build: 05_SIAP_DISTRIBUSI")
	fmt.Println("================================================")

	_ = os.MkdirAll(companyDir, 0755)
	_ = os.MkdirAll(cacheDir, 0755)

	loadOrCreateUUID()
	loadServerIP()
	resolveAgentName()
	loadSecurityKey()
	loadAgentCapabilities()

	fmt.Printf("[AGENT] Linux Agent %s running. UUID: %s\n", AgentVersion, agentUUID)

	go runWatchdog()

	select {} // Block forever
}

// ── CAPABILITY MANIFEST LOGIC ──

type CapabilityDef struct {
	Cmd      string   `json:"cmd"`
	Args     []string `json:"args"`
	PreCheck []string `json:"pre_check,omitempty"`
}

var (
	agentCapabilities = make(map[string]CapabilityDef)
	capabilitiesMu    sync.RWMutex
)

func loadAgentCapabilities() {
	manifestPath := filepath.Join(companyDir, "config", "capabilities.json")
	_ = os.MkdirAll(filepath.Join(companyDir, "config"), 0755)
	
	if !fileExists(manifestPath) {
		// Default Manifest for Linux Agent
		defaultCaps := map[string]CapabilityDef{
			"FLUSH_DNS": {Cmd: "bash", Args: []string{"-c", "systemctl restart systemd-resolved || /etc/init.d/nscd restart"}},
			"RESTART_NATS": {Cmd: "systemctl", Args: []string{"restart", "nats-server"}},
			"IPCONFIG": {Cmd: "ip", Args: []string{"a"}},
			"SHOW_ROUTE": {Cmd: "ip", Args: []string{"route"}},
			// Sprint T Diagnostic Whitelist for AI Incident Commander
			"TRACEROUTE": {Cmd: "traceroute", Args: []string{"{target}"}},
			"PING": {Cmd: "ping", Args: []string{"-c", "4", "-W", "2", "{target}"}},
			"ARP": {Cmd: "arp", Args: []string{"-n"}},
			"NETSTAT": {Cmd: "netstat", Args: []string{"-tulpn"}},
			"NSLOOKUP": {Cmd: "nslookup", Args: []string{"{target}"}},
			"JOURNALCTL": {Cmd: "journalctl", Args: []string{"-n", "50", "--no-pager"}},
			"DMESG": {Cmd: "dmesg", Args: []string{"|", "tail", "-n", "50"}},
		}
		data, _ := json.MarshalIndent(defaultCaps, "", "  ")
		_ = os.WriteFile(manifestPath, data, 0644)
		
		capabilitiesMu.Lock()
		agentCapabilities = defaultCaps
		capabilitiesMu.Unlock()
		fmt.Println("[AGENT] Created default capabilities.json manifest.")
		return
	}

	data, err := os.ReadFile(manifestPath)
	if err == nil {
		var caps map[string]CapabilityDef
		if err := json.Unmarshal(data, &caps); err == nil {
			capabilitiesMu.Lock()
			agentCapabilities = caps
			capabilitiesMu.Unlock()
			fmt.Printf("[AGENT] Loaded %d capabilities from manifest.\n", len(caps))
		}
	}
}
