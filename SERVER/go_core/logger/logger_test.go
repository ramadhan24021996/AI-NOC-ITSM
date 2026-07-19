package logger

import (
	"bytes"
	"encoding/json"
	"strings"
	"testing"
)

func TestStructuredLoggerPIIMasking(t *testing.T) {
	// Create logger capturing output to a local buffer
	var buf bytes.Buffer
	l := &Logger{writer: &buf}

	// Test log message containing PII
	rawMsg := "Operator logged in from 192.168.1.100 using user C:\\Users\\testuser\\AppData"
	l.Info(rawMsg, map[string]interface{}{
		"email":    "operator@domain.com",
		"password": "password=supersecret",
		"version":  1.0,
	})

	output := buf.String()
	if output == "" {
		t.Fatalf("Log output is empty")
	}

	// Parse JSON output
	var entry LogEntry
	if err := json.Unmarshal([]byte(output), &entry); err != nil {
		t.Fatalf("Log output is not valid JSON: %v", err)
	}

	// Assertions for PII masking in message
	if strings.Contains(entry.Message, "192.168.1.100") {
		t.Errorf("PII Leak: IP address was not redacted. Got: %s", entry.Message)
	}
	if strings.Contains(entry.Message, "C:\\Users") {
		t.Errorf("PII Leak: User path was not redacted. Got: %s", entry.Message)
	}

	// Assertions for PII masking in fields
	emailVal, ok := entry.Fields["email"].(string)
	if !ok || emailVal != "[EMAIL_REDACTED]" {
		t.Errorf("Expected email to be redacted, got: %v", entry.Fields["email"])
	}

	passwordVal, ok := entry.Fields["password"].(string)
	if !ok || !strings.Contains(passwordVal, "[PASSWORD_REDACTED]") {
		t.Errorf("Expected password to be redacted, got: %v", entry.Fields["password"])
	}

	// Assertions for non-PII fields
	versionVal, ok := entry.Fields["version"].(float64)
	if !ok || versionVal != 1.0 {
		t.Errorf("Expected version to be 1.0, got: %v", entry.Fields["version"])
	}

	t.Logf("Redacted Log Output: %s", output)
}
