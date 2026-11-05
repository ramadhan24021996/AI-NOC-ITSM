package main

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
)

// TestJarvisAPIRoutes_Registration tests that all JARVIS Voice API routes are correctly wired.
func TestJarvisAPIRoutes_Registration(t *testing.T) {
	gin.SetMode(gin.TestMode)
	r := gin.New()
	RegisterJarvisAPIRoutes(r)

	routes := r.Routes()
	expectedRoutes := map[string]string{
		"/api/jarvis/voice/query":        "POST",
		"/api/jarvis/voice/duplex":       "GET",
		"/api/jarvis/health":             "GET",
		"/api/jarvis/proactive/announce": "POST",
	}

	foundCount := 0
	for _, route := range routes {
		if expectedMethod, exists := expectedRoutes[route.Path]; exists {
			if route.Method == expectedMethod {
				foundCount++
			}
		}
	}

	if foundCount != len(expectedRoutes) {
		t.Errorf("Expected %d registered routes, found %d", len(expectedRoutes), foundCount)
	}
}

// TestJarvisVoiceProxy_MockServer tests request proxying to a mock Python JARVIS Voice server.
func TestJarvisVoiceProxy_MockServer(t *testing.T) {
	gin.SetMode(gin.TestMode)

	// Create mock Python Voice Server
	mockPythonServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/jarvis/voice/query":
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusOK)
			_ = json.NewEncoder(w).Encode(map[string]interface{}{
				"answer_text":  "Halo, sistem jaringan beroperasi normal.",
				"avatar_state": "SPEAKING",
				"intent":       "NETWORK_STATUS",
				"target_panel": "p-agent_health",
			})
		case "/jarvis/health":
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusOK)
			_ = json.NewEncoder(w).Encode(map[string]interface{}{
				"status": "healthy",
				"engine": "v11.3-jarvis-voice",
			})
		default:
			w.WriteHeader(http.StatusNotFound)
		}
	}))
	defer mockPythonServer.Close()

	// Set JARVIS_VOICE_API_URL to point to mock server
	oldEnv := os.Getenv("JARVIS_VOICE_API_URL")
	os.Setenv("JARVIS_VOICE_API_URL", mockPythonServer.URL)
	defer os.Setenv("JARVIS_VOICE_API_URL", oldEnv)

	r := gin.New()
	RegisterJarvisAPIRoutes(r)

	// Test 1: POST /api/jarvis/voice/query
	queryBody, _ := json.Marshal(map[string]string{
		"question":   "Bagaimana status jaringan?",
		"session_id": "test-session-123",
	})
	req, _ := http.NewRequest("POST", "/api/jarvis/voice/query", bytes.NewBuffer(queryBody))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("Expected status HTTP 200, got %d", w.Code)
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("Failed to parse response JSON: %v", err)
	}
	if resp["answer_text"] != "Halo, sistem jaringan beroperasi normal." {
		t.Errorf("Unexpected answer_text: %v", resp["answer_text"])
	}

	// Test 2: GET /api/jarvis/health
	reqHealth, _ := http.NewRequest("GET", "/api/jarvis/health", nil)
	wHealth := httptest.NewRecorder()
	r.ServeHTTP(wHealth, reqHealth)

	if wHealth.Code != http.StatusOK {
		t.Fatalf("Expected status HTTP 200 for health, got %d", wHealth.Code)
	}
}

// TestJarvisVoiceProxy_UnreachableServer tests fallback handling when Python Voice server is down.
func TestJarvisVoiceProxy_UnreachableServer(t *testing.T) {
	gin.SetMode(gin.TestMode)

	// Point to non-existent server port
	oldEnv := os.Getenv("JARVIS_VOICE_API_URL")
	os.Setenv("JARVIS_VOICE_API_URL", "http://127.0.0.1:59999")
	defer os.Setenv("JARVIS_VOICE_API_URL", oldEnv)

	r := gin.New()
	RegisterJarvisAPIRoutes(r)

	req, _ := http.NewRequest("GET", "/api/jarvis/health", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	// Should return 503 Service Unavailable, not crash or 502
	if w.Code != http.StatusServiceUnavailable {
		t.Errorf("Expected 503 Service Unavailable when server is unreachable, got %d", w.Code)
	}

	if !strings.Contains(w.Body.String(), "Sistem otak JARVIS (Python AI Core) tidak dapat dijangkau") {
		t.Errorf("Expected friendly error message, got %s", w.Body.String())
	}
}

// TestTriggerJarvisProactiveAnnounce tests asynchronous proactive alert dispatching.
func TestTriggerJarvisProactiveAnnounce(t *testing.T) {
	mockPythonServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"skipped":      false,
			"text":         "Perhatian: Terdeteksi printer spooler crash pada POS-JKT-01",
			"audio_b64":    "UklGRgAAAABXQVZFZm10...",
			"audio_format": "mp3",
		})
	}))
	defer mockPythonServer.Close()

	oldEnv := os.Getenv("JARVIS_VOICE_API_URL")
	os.Setenv("JARVIS_VOICE_API_URL", mockPythonServer.URL)
	defer os.Setenv("JARVIS_VOICE_API_URL", oldEnv)

	// Trigger proactive announce
	TriggerJarvisProactiveAnnounce("SPOOLER_CRASH", "HIGH", "Spooler Crash", "Service spooler stopped", "POS-JKT-01", "INC-9901", "SITE-JKT", nil)

	// Allow non-blocking goroutine time to complete
	time.Sleep(100 * time.Millisecond)
}
