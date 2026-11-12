package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"regexp"
	"strings"
	"time"
)

var validWindowsEventLogNames = map[string]bool{
	"System":          true,
	"Application":     true,
	"Security":        true,
	"Setup":           true,
	"ForwardedEvents": true,
	"Microsoft-Windows-Diagnostics-Performance/Operational": true,
	"Microsoft-Windows-TaskScheduler/Operational":           true,
	"Microsoft-Windows-WindowsUpdateClient/Operational":     true,
	"Microsoft-Windows-DNS-Client/Operational":              true,
}

var validPortNameRegex = regexp.MustCompile(`^[a-zA-Z0-9_\-\. :]+$`)

// isAllowedEventLogName checks whether logName is in the strict allowlist of Windows Event Log channels.
func isAllowedEventLogName(logName string) bool {
	return validWindowsEventLogNames[logName]
}

// sanitizePrinterPortName validates portName against an allowlist regex and escapes single quotes.
// Returns (sanitized, true) if valid, or ("", false) if rejected.
func sanitizePrinterPortName(portName string) (string, bool) {
	if portName == "" || !validPortNameRegex.MatchString(portName) {
		return "", false
	}
	return strings.ReplaceAll(portName, "'", "''"), true
}

// verifyCommandHMAC validates the command signature, timestamp window (300s), and mandatory executionID.
func verifyCommandHMAC(secret []byte, cmd string, ts int64, executionID string, params map[string]interface{}, token string) (bool, string) {
	if token == "" || ts == 0 || strings.TrimSpace(executionID) == "" {
		return false, "Unauthorized execution: missing required token, timestamp, or execution_id"
	}
	now := time.Now().Unix()
	diff := now - ts
	if diff < -300 || diff > 300 {
		return false, "Unauthorized execution: expired signature token"
	}
	paramsBytes, _ := json.Marshal(params)
	paramsHashArr := sha256.Sum256(paramsBytes)
	paramsHashHex := hex.EncodeToString(paramsHashArr[:])

	msgModern := fmt.Sprintf("%s:%d:%s:%s", cmd, ts, paramsHashHex, executionID)
	macM := hmac.New(sha256.New, secret)
	macM.Write([]byte(msgModern))
	if !hmac.Equal([]byte(hex.EncodeToString(macM.Sum(nil))), []byte(token)) {
		return false, "Unauthorized execution: invalid HMAC signature token"
	}
	return true, ""
}
