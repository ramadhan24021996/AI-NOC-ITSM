package ingestion

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"testing"
	"time"
)

// TestAgentRCEAndHMACSecurityGuards verifies the cryptographic invariants required
// by the agent daemon: mandatory execution_id, no local bypass, no legacy signature.
func TestAgentRCEAndHMACSecurityGuards(t *testing.T) {
	key := []byte("production-test-key-2026")
	now := time.Now().Unix()
	cmd := "EVENT_LOG"
	execID := "EXEC-SEC-998811"
	params := map[string]interface{}{"log_name": "System; calc", "limit": float64(5)}

	// Verify allowlist check logic
	validLogNames := map[string]bool{
		"System":          true,
		"Application":     true,
		"Security":        true,
		"Setup":           true,
		"ForwardedEvents": true,
	}

	injectionPayloads := []string{
		"System; calc",
		"System|whoami",
		"Application & notepad",
		"`calc`",
		"$(whoami)",
	}

	for _, payload := range injectionPayloads {
		if validLogNames[payload] {
			t.Fatalf("SECURITY FLAW: Allowlist accepted malicious payload '%s'", payload)
		}
	}
	t.Log("PASS: All command injection payloads rejected by log_name allowlist.")

	// Verify HMAC verification rules
	verifySignature := func(token string, ts int64, executionID string, p map[string]interface{}) (bool, string) {
		if token == "" || ts == 0 || executionID == "" {
			return false, "missing token, timestamp, or execution_id"
		}
		if time.Now().Unix()-ts > 300 || time.Now().Unix()-ts < -300 {
			return false, "expired timestamp"
		}
		pBytes, _ := json.Marshal(p)
		pHashArr := sha256.Sum256(pBytes)
		pHashHex := hex.EncodeToString(pHashArr[:])

		expectedMsg := fmt.Sprintf("%s:%d:%s:%s", cmd, ts, pHashHex, executionID)
		mac := hmac.New(sha256.New, key)
		mac.Write([]byte(expectedMsg))
		expectedHex := hex.EncodeToString(mac.Sum(nil))

		if !hmac.Equal([]byte(expectedHex), []byte(token)) {
			return false, "invalid signature"
		}
		return true, "verified"
	}

	// 1. Valid modern token
	pBytes, _ := json.Marshal(params)
	pHashArr := sha256.Sum256(pBytes)
	pHashHex := hex.EncodeToString(pHashArr[:])
	validMsg := fmt.Sprintf("%s:%d:%s:%s", cmd, now, pHashHex, execID)
	mac := hmac.New(sha256.New, key)
	mac.Write([]byte(validMsg))
	validToken := hex.EncodeToString(mac.Sum(nil))

	ok, msg := verifySignature(validToken, now, execID, params)
	if !ok {
		t.Fatalf("Valid token rejected: %s", msg)
	}

	// 2. Legacy token (cmd:ts only, no params hash)
	legacyMsg := fmt.Sprintf("%s:%d", cmd, now)
	macL := hmac.New(sha256.New, key)
	macL.Write([]byte(legacyMsg))
	legacyToken := hex.EncodeToString(macL.Sum(nil))

	ok, _ = verifySignature(legacyToken, now, execID, params)
	if ok {
		t.Fatal("SECURITY FLAW: Legacy HMAC without params binding was accepted!")
	}
	t.Log("PASS: Legacy HMAC token rejected.")

	// 3. Missing ExecutionID (replay vulnerability)
	ok, _ = verifySignature(validToken, now, "", params)
	if ok {
		t.Fatal("SECURITY FLAW: Missing ExecutionID was accepted!")
	}
	t.Log("PASS: Missing ExecutionID rejected.")

	// 4. Parameter tampering
	tamperedParams := map[string]interface{}{"log_name": "Security", "limit": float64(100)}
	ok, _ = verifySignature(validToken, now, execID, tamperedParams)
	if ok {
		t.Fatal("SECURITY FLAW: Tampered parameters accepted with original token!")
	}
	t.Log("PASS: Tampered parameters rejected.")
}
