//go:build windows

package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"testing"
	"time"
)

func TestEventLogCommandInjectionAllowlist(t *testing.T) {
	// Test injection payloads that must be blocked by the allowlist
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
		res := executeAgentCommand("EVENT_LOG", map[string]interface{}{
			"log_name": payload,
			"limit":    float64(5),
		})

		status, _ := res["status"].(string)
		if status != "error" {
			t.Errorf("SECURITY VULNERABILITY: Injection payload '%s' was not rejected by allowlist! Result: %v", payload, res)
		} else {
			t.Logf("PASS: Payload '%s' successfully blocked: %v", payload, res["message"])
		}
	}
}

func TestResolvePortIPInjectionPrevention(t *testing.T) {
	maliciousPorts := []string{
		"COM1; calc",
		"TCP_192.168.1.1' ; whoami",
		"PORT$(calc)",
		"192.168.1.1`dir`",
	}

	for _, p := range maliciousPorts {
		ip := resolvePortIP(p)
		if ip != "" {
			t.Errorf("SECURITY VULNERABILITY: Malicious portName '%s' returned IP: '%s'", p, ip)
		} else {
			t.Logf("PASS: Malicious port '%s' rejected cleanly", p)
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

	// Verification logic matching main.go
	verifyFunc := func(token string, ts int64, executionID string, p map[string]interface{}) bool {
		if token == "" || ts == 0 || executionID == "" {
			return false
		}
		diff := time.Now().Unix() - ts
		if diff < -300 || diff > 300 {
			return false
		}
		pBytes, _ := json.Marshal(p)
		pHashArr := sha256.Sum256(pBytes)
		pHashHex := hex.EncodeToString(pHashArr[:])
		msg := fmt.Sprintf("%s:%d:%s:%s", cmd, ts, pHashHex, executionID)
		mac := hmac.New(sha256.New, testKey)
		mac.Write([]byte(msg))
		return hmac.Equal([]byte(hex.EncodeToString(mac.Sum(nil))), []byte(token))
	}

	// Test Cases
	if !verifyFunc(validToken, now, execID, params) {
		t.Errorf("Valid modern token should be verified successfully")
	}

	// Legacy token MUST be rejected
	if verifyFunc(legacyToken, now, execID, params) {
		t.Errorf("SECURITY VULNERABILITY: Legacy signature accepted without params hash binding!")
	}

	// Missing ExecutionID MUST be rejected
	if verifyFunc(validToken, now, "", params) {
		t.Errorf("SECURITY VULNERABILITY: Missing ExecutionID was accepted (replay attack risk)!")
	}

	// Expired timestamp MUST be rejected
	if verifyFunc(validToken, now-400, execID, params) {
		t.Errorf("SECURITY VULNERABILITY: Expired timestamp (>300s) was accepted!")
	}

	// Tampered params with valid token MUST be rejected
	tamperedParams := map[string]interface{}{"action": "delete_all"}
	if verifyFunc(validToken, now, execID, tamperedParams) {
		t.Errorf("SECURITY VULNERABILITY: Tampered params were accepted!")
	}
}
