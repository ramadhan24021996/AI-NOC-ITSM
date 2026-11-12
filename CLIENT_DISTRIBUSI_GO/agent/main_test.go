package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http/httptest"
	"os"
	"testing"
	"time"
)

func TestEventLogCommandInjectionAllowlist(t *testing.T) {
	injectionPayloads := []string{
		"System; calc",
		"System|whoami",
		"Application & notepad",
		"System; rm -rf /",
		"`calc`",
		"$(calc)",
		"Security | Out-File evil.txt",
		"RandomNonExistentLogChannel",
	}

	for _, payload := range injectionPayloads {
		if isAllowedEventLogName(payload) {
			t.Errorf("SECURITY VULNERABILITY: Injection payload '%s' was not rejected by allowlist!", payload)
		} else {
			t.Logf("PASS: Payload '%s' successfully blocked by allowlist", payload)
		}
	}

	validChannels := []string{"System", "Application", "Security", "Setup", "ForwardedEvents"}
	for _, ch := range validChannels {
		if !isAllowedEventLogName(ch) {
			t.Errorf("Expected valid channel '%s' to be allowed", ch)
		}
	}
}

func TestResolvePortIPInjectionPrevention(t *testing.T) {
	maliciousPorts := []string{
		"COM1; calc",
		"TCP_192.168.1.1' ; whoami",
		"PORT$(calc)",
		"192.168.1.1`dir`",
		"",
	}

	for _, p := range maliciousPorts {
		if clean, ok := sanitizePrinterPortName(p); ok {
			t.Errorf("SECURITY VULNERABILITY: Malicious portName '%s' passed validation as '%s'", p, clean)
		} else {
			t.Logf("PASS: Malicious port '%s' rejected cleanly", p)
		}
	}

	validPorts := []string{"IP_192.168.1.50", "USB001", "WSD-1234-5678.0032", "COM1:"}
	for _, vp := range validPorts {
		if _, ok := sanitizePrinterPortName(vp); !ok {
			t.Errorf("Expected valid portName '%s' to pass validation", vp)
		}
	}
}

func TestHmacVerificationHardening(t *testing.T) {
	testKey := []byte("test-agent-security-key-2026")
	now := time.Now().Unix()

	cmd := "TEST_CMD"
	execID := "EXEC-12345"
	params := map[string]interface{}{"action": "status"}
	paramsBytes, _ := json.Marshal(params)
	paramsHashArr := sha256.Sum256(paramsBytes)
	paramsHashHex := hex.EncodeToString(paramsHashArr[:])

	// 1. Valid Modern Signature: cmd:timestamp:paramsHash:executionID
	msgModern := fmt.Sprintf("%s:%d:%s:%s", cmd, now, paramsHashHex, execID)
	macM := hmac.New(sha256.New, testKey)
	macM.Write([]byte(msgModern))
	validToken := hex.EncodeToString(macM.Sum(nil))

	// 2. Legacy Signature: cmd:timestamp (tampered params not bound)
	msgLegacy := fmt.Sprintf("%s:%d", cmd, now)
	macL := hmac.New(sha256.New, testKey)
	macL.Write([]byte(msgLegacy))
	legacyToken := hex.EncodeToString(macL.Sum(nil))

	// Valid modern token MUST pass
	if ok, msg := verifyCommandHMAC(testKey, cmd, now, execID, params, validToken); !ok {
		t.Errorf("Valid modern token should be verified successfully, got error: %s", msg)
	}

	// Legacy token MUST be rejected
	if ok, _ := verifyCommandHMAC(testKey, cmd, now, execID, params, legacyToken); ok {
		t.Errorf("SECURITY VULNERABILITY: Legacy signature accepted without params hash binding!")
	}

	// Missing ExecutionID MUST be rejected
	if ok, _ := verifyCommandHMAC(testKey, cmd, now, "", params, validToken); ok {
		t.Errorf("SECURITY VULNERABILITY: Missing ExecutionID was accepted (replay attack risk)!")
	}

	// Expired timestamp MUST be rejected
	if ok, _ := verifyCommandHMAC(testKey, cmd, now-400, execID, params, validToken); ok {
		t.Errorf("SECURITY VULNERABILITY: Expired timestamp (>300s) was accepted!")
	}

	// Tampered params with valid token MUST be rejected
	tamperedParams := map[string]interface{}{"action": "delete_all"}
	if ok, _ := verifyCommandHMAC(testKey, cmd, now, execID, tamperedParams, validToken); ok {
		t.Errorf("SECURITY VULNERABILITY: Tampered params were accepted!")
	}
}

func TestExtensionAuthRejectsSecurityKeyFallback(t *testing.T) {
	masterKey := []byte("master-fleet-hmac-secret-key-2026")
	defer os.Unsetenv("OSI_EXT_TOKEN")

	// 1. When OSI_EXT_TOKEN is unset, request using master securityKey MUST be rejected
	os.Unsetenv("OSI_EXT_TOKEN")
	req1 := httptest.NewRequest("POST", "/ext-telemetry", nil)
	req1.Header.Set("X-OSI-Token", string(masterKey))
	if verifyExtensionRequestAuth(req1, masterKey) {
		t.Errorf("SECURITY VULNERABILITY: Browser extension auth fell back to master securityKey when OSI_EXT_TOKEN was unset!")
	}

	// 2. When OSI_EXT_TOKEN is set to the same value as securityKey, MUST be rejected
	os.Setenv("OSI_EXT_TOKEN", string(masterKey))
	req2 := httptest.NewRequest("POST", "/ext-telemetry", nil)
	req2.Header.Set("X-OSI-Token", string(masterKey))
	if verifyExtensionRequestAuth(req2, masterKey) {
		t.Errorf("SECURITY VULNERABILITY: Browser extension auth accepted OSI_EXT_TOKEN equal to master securityKey!")
	}

	// 3. When OSI_EXT_TOKEN is set to a separate dedicated secret, valid token MUST pass
	dedicatedToken := "dedicated-browser-extension-token-only-98765"
	os.Setenv("OSI_EXT_TOKEN", dedicatedToken)
	req3 := httptest.NewRequest("POST", "/ext-telemetry", nil)
	req3.Header.Set("X-OSI-Token", dedicatedToken)
	if !verifyExtensionRequestAuth(req3, masterKey) {
		t.Errorf("Expected valid dedicated OSI_EXT_TOKEN to pass authentication")
	}
}
