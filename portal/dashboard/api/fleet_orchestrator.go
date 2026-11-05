package api

import (
	"bufio"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
)

// ValidateCommandSafety provides a dual-layer security guardrail: AST-like canonicalization & Playbook Whitelist check.
func ValidateCommandSafety(command string, params map[string]interface{}) (bool, string) {
	cmdUpper := strings.ToUpper(strings.TrimSpace(command))

	// 1. Whitelist of Pre-approved Safe Production Actions
	safeActions := map[string]bool{
		"CLEAR_SPOOLER":                   true,
		"RESTART_SPOOLER":                 true,
		"TEST_PRINT":                      true,
		"UPDATE_AGENT":                    true,
		"DEEP_DIAGNOSTICS":                true,
		"EXECUTE_PLAYBOOK_L3_ROUTE_FLUSH": true,
		"SERVICE_RESTART":                 true,
		"COLLECT_METRICS":                 true,
	}

	if safeActions[cmdUpper] {
		// Inspect parameters for command injection / obfuscation
		for k, v := range params {
			valStr := fmt.Sprintf("%v", v)
			if isObfuscatedOrDestructive(valStr) {
				return false, fmt.Sprintf("Obfuscated or destructive pattern detected in parameter '%s'", k)
			}
		}
		return true, ""
	}

	// 2. De-obfuscation & AST Tokenization for raw shell commands
	rawCmd := command
	if params != nil {
		if c, ok := params["cmd"].(string); ok && c != "" {
			rawCmd = c
		} else if script, ok := params["script"].(string); ok && script != "" {
			rawCmd = script
		}
	}

	if isObfuscatedOrDestructive(rawCmd) {
		return false, "Command contains obfuscated, encoded, or restricted destructive payload (Zero-Trust Block)"
	}

	// 3. Strict Playbook Whitelist Validation
	// Raw un-whitelisted arbitrary commands are blocked by default for HITL Review
	return false, fmt.Sprintf("Command '%s' is not in Registered Playbook Whitelist. Routed to HITL Approval.", command)
}

// isObfuscatedOrDestructive detects obfuscation techniques (base64, hex, variable expansion, subshell, destructive binary tokens)
func isObfuscatedOrDestructive(input string) bool {
	lower := strings.ToLower(input)

	// Obfuscation indicators
	obfuscationPatterns := []string{
		"base64 -d", "base64 --decode", "openssl enc",
		"\\x", "\\0", "eval ", "exec ", "`", "$(", "${",
		"sh -c", "bash -c", "zsh -c", "python -c", "perl -e",
		"nc -e", "netcat", "/dev/tcp/", "/dev/udp/",
		"mkfs", "dd if=", "> /dev/sd", "chmod 777 /", "chown -R",
	}
	for _, pattern := range obfuscationPatterns {
		if strings.Contains(lower, pattern) {
			return true
		}
	}

	// AST Tokenizer check for destructive binaries after whitespace & quote normalization
	normalized := strings.Join(strings.Fields(lower), " ")
	tokens := strings.Split(normalized, " ")
	if len(tokens) > 0 {
		baseBinary := tokens[0]
		// Strip leading paths
		if idx := strings.LastIndex(baseBinary, "/"); idx != -1 {
			baseBinary = baseBinary[idx+1:]
		}
		destructiveBinaries := map[string]bool{
			"rm": true, "mkfs": true, "dd": true, "fdisk": true,
			"parted": true, "format": true, "shutdown": true, "reboot": true,
			"init": true, "killall": true,
		}
		if destructiveBinaries[baseBinary] {
			if baseBinary == "rm" && (strings.Contains(normalized, "-rf") || strings.Contains(normalized, "-fr") || strings.Contains(normalized, " /")) {
				return true
			}
			if baseBinary != "rm" {
				return true
			}
		}
	}

	return false
}

// OrchestratorCommand handles remote actions.
func (h *Handler) OrchestratorCommand(c *gin.Context) {
	var req struct {
		Command string                 `json:"command"`
		Target  string                 `json:"target"`
		Params  map[string]interface{} `json:"params"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": err.Error()})
		return
	}

	// ── DUAL-LAYER SECURITY GUARDRAIL (AST TOKENIZER + PLAYBOOK WHITELIST) ──
	valid, blockReason := ValidateCommandSafety(req.Command, req.Params)
	if !valid {
		// Log security audit block in database
		if h.db != nil {
			h.db.Exec(`CREATE TABLE IF NOT EXISTS security_audit_logs (
				log_id SERIAL PRIMARY KEY,
				event_type VARCHAR(100),
				target VARCHAR(100),
				details TEXT,
				severity VARCHAR(20),
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)`)
			h.db.Exec(`INSERT INTO security_audit_logs (event_type, target, details, severity, created_at) VALUES ('COMMAND_BLOCKED_ZERO_TRUST', ?, ?, 'HIGH', NOW())`,
				req.Target, fmt.Sprintf("Blocked Command '%s': %s", req.Command, blockReason))
		}
		c.JSON(http.StatusOK, gin.H{
			"status":  "blocked",
			"mode":    "HITL_FALLBACK",
			"error":   blockReason,
			"message": "🛡️ Zero-Trust Security Guardrail: " + blockReason,
		})
		return
	}

	type FleetDevice struct {
		PCName       string `gorm:"column:pc_name"`
		IP           string `gorm:"column:ip"`
		HardwareInfo string `gorm:"column:hardware_info"`
	}
	var fd FleetDevice
	if err := h.db.Table("fleet_devices").Where("pc_name = ?", req.Target).First(&fd).Error; err != nil {
		c.JSON(http.StatusOK, gin.H{"status": "error", "message": "Device not found in fleet registry"})
		return
	}

	ip := fd.IP
	if ip == "" && fd.HardwareInfo != "" {
		var hwInfo map[string]interface{}
		if err := json.Unmarshal([]byte(fd.HardwareInfo), &hwInfo); err == nil && hwInfo != nil {
			if ipVal, ok := hwInfo["ip"].(string); ok && ipVal != "" {
				ip = ipVal
			} else if netMap, ok := hwInfo["network"].(map[string]interface{}); ok {
				if ipVal, ok := netMap["ip"].(string); ok {
					ip = ipVal
				}
			}
		}
	}
	if ip == "" {
		c.JSON(http.StatusOK, gin.H{"status": "error", "message": "Device IP address is not available"})
		return
	}

	if req.Params == nil {
		req.Params = make(map[string]interface{})
	}

	execID := fmt.Sprintf("exec_%d", time.Now().UnixNano())
	paramsBytes, _ := json.Marshal(req.Params)
	paramsHashArr := sha256.Sum256(paramsBytes)
	paramsHashHex := hex.EncodeToString(paramsHashArr[:])

	ts := time.Now().Unix()
	secretKey := agentHMACKey()
	msgToSign := fmt.Sprintf("%s:%d:%s:%s", req.Command, ts, paramsHashHex, execID)

	mac := hmac.New(sha256.New, secretKey)
	mac.Write([]byte(msgToSign))
	token := hex.EncodeToString(mac.Sum(nil))

	type AgentCommandPayload struct {
		Command     string                 `json:"command"`
		Params      map[string]interface{} `json:"params"`
		Token       string                 `json:"token"`
		Timestamp   int64                  `json:"timestamp"`
		ExecutionID string                 `json:"execution_id"`
	}

	payload := AgentCommandPayload{
		Command:     req.Command,
		Params:      req.Params,
		Token:       token,
		Timestamp:   ts,
		ExecutionID: execID,
	}

	addr := net.JoinHostPort(ip, "10000")
	conn, err := net.DialTimeout("tcp", addr, 5*time.Second)
	if err != nil {
		c.JSON(http.StatusOK, gin.H{"status": "error", "message": "Failed to connect to agent (OFFLINE): " + err.Error()})
		return
	}
	defer conn.Close()

	payloadBytes, err := json.Marshal(payload)
	if err != nil {
		c.JSON(http.StatusOK, gin.H{"status": "error", "message": "Failed to marshal payload: " + err.Error()})
		return
	}

	_, err = conn.Write(append(payloadBytes, '\n'))
	if err != nil {
		c.JSON(http.StatusOK, gin.H{"status": "error", "message": "Failed to send command payload to agent: " + err.Error()})
		return
	}

	reader := bufio.NewReader(conn)
	respBytes, err := reader.ReadBytes('\n')
	if err != nil {
		c.JSON(http.StatusOK, gin.H{"status": "error", "message": "Failed to read agent response: " + err.Error()})
		return
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(respBytes, &resp); err != nil {
		c.JSON(http.StatusOK, gin.H{"status": "error", "message": "Failed to parse agent response: " + err.Error()})
		return
	}

	c.JSON(http.StatusOK, resp)
}

// SendSocketCommand sends an HMAC-SHA256 signed command to an agent via TCP port 10000.
func SendSocketCommand(ip string, command string, params map[string]interface{}) error {
	return sendSocketCommand(ip, command, params)
}

// PushDesktopNotificationToDevice sends a desktop notification (Linux notify-send / Windows BalloonTip) to a client PC via TCP socket 10000.
func (h *Handler) PushDesktopNotificationToDevice(pcName string, title string, message string) error {
	var deviceIP string
	if h.db != nil {
		h.db.Raw(`SELECT ip FROM fleet_devices WHERE (pc_name = ? OR LOWER(pc_name) = LOWER(?)) AND ip IS NOT NULL AND ip != '' LIMIT 1`, pcName, pcName).Scan(&deviceIP)
	}

	if deviceIP == "" || deviceIP == "N/A" {
		return fmt.Errorf("device IP not found for %s", pcName)
	}

	payload := map[string]interface{}{
		"title":   title,
		"message": message,
	}

	return sendSocketCommand(deviceIP, "SHOW_NOTIFICATION", payload)
}

// PushNotificationEndpoint handles POST /api/fleet/notify to send a desktop notification to a target client PC.
func (h *Handler) PushNotificationEndpoint(c *gin.Context) {
	var req struct {
		DeviceName string `json:"device_name"`
		Title      string `json:"title"`
		Message    string `json:"message"`
	}

	if err := c.ShouldBindJSON(&req); err != nil || req.DeviceName == "" {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": "device_name required"})
		return
	}

	if req.Title == "" {
		req.Title = "⚠️ Peringatan Sistem OSI AI"
	}
	if req.Message == "" {
		req.Message = "Terdapat notifikasi baru dari NOC / Operator."
	}

	err := h.PushDesktopNotificationToDevice(req.DeviceName, req.Title, req.Message)
	if err != nil {
		c.JSON(http.StatusOK, gin.H{
			"status":  "queued",
			"message": fmt.Sprintf("Notifikasi disiapkan untuk %s (Sinyal socket port 10000 belum direspons: %v)", req.DeviceName, err),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"status":  "success",
		"message": fmt.Sprintf("Notifikasi dekstop berhasil terkirim ke %s!", req.DeviceName),
	})
}

// sendSocketCommand sends an HMAC-SHA256 signed command to an agent via TCP port 10000.
func sendSocketCommand(ip string, command string, params map[string]interface{}) error {
	if ip == "" {
		return fmt.Errorf("empty IP address")
	}

	var conn net.Conn
	var dialErr error
	for _, port := range []string{"10000", "10001"} {
		addr := net.JoinHostPort(ip, port)
		conn, dialErr = net.DialTimeout("tcp", addr, 3*time.Second)
		if dialErr == nil {
			break
		}
	}
	if dialErr != nil {
		return dialErr
	}
	defer conn.Close()

	_ = conn.SetDeadline(time.Now().Add(6 * time.Second))

	ts := time.Now().Unix()
	execID := fmt.Sprintf("cmd-%d", ts)
	secretKey := agentHMACKey()

	if params == nil {
		params = make(map[string]interface{})
	}

	paramsBytes, _ := json.Marshal(params)
	paramsHashArr := sha256.Sum256(paramsBytes)
	paramsHashHex := hex.EncodeToString(paramsHashArr[:])

	msgToSign := fmt.Sprintf("%s:%d:%s:%s", command, ts, paramsHashHex, execID)

	mac := hmac.New(sha256.New, secretKey)
	mac.Write([]byte(msgToSign))
	token := hex.EncodeToString(mac.Sum(nil))

	payload := map[string]interface{}{
		"command":      command,
		"params":       params,
		"token":        token,
		"timestamp":    ts,
		"execution_id": execID,
	}

	payloadBytes, err := json.Marshal(payload)
	if err != nil {
		return err
	}

	_, err = conn.Write(append(payloadBytes, '\n'))
	return err
}

// EvaluateConfidenceTier classifies AI recommendations into 3 dynamic execution tiers:
// 1. AUTO_EXECUTE (Confidence >= 0.92, no hallucination, critic_score <= 50) -> Low-Risk Auto Remediation
// 2. HITL_APPROVAL (Confidence 0.70 - 0.91 or critic_score > 50) -> Requires Human-In-The-Loop Approval
// 3. GUIDANCE_ONLY (Confidence < 0.70 or hallucination) -> AI Guidance Only Mode
func EvaluateConfidenceTier(confidence float64, isHallucination bool, criticScore float64) (executionMode string, requiresHITL bool, autoExecute bool, tierName string, description string) {
	confVal := confidence
	if confVal > 1.0 {
		confVal = confVal / 100.0
	}

	if isHallucination || confVal < 0.70 {
		return "GUIDANCE_ONLY", true, false, "TIER_3_GUIDANCE_ONLY", "Confidence < 70% atau terdeteksi halusinasi. AI hanya memberikan masukan saran (Guidance Mode)."
	} else if confVal >= 0.92 && !isHallucination && criticScore <= 50.0 {
		return "AUTO_EXECUTE", false, true, "TIER_1_AUTO_EXECUTE", "Confidence >= 92%. Eksekusi otomatis remediasi aman (Low-Risk Action)."
	} else {
		return "HITL_APPROVAL", true, false, "TIER_2_HITL_APPROVAL", "Confidence 70% - 91%. Membutuhkan persetujuan Human-In-The-Loop (HITL) via dashboard."
	}
}
