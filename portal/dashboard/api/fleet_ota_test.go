package api

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestFleetOTAHandlers(t *testing.T) {
	gin.SetMode(gin.TestMode)
	tmpDir := t.TempDir()
	otaDir := filepath.Join(tmpDir, "CLIENT_DISTRIBUSI_GO", "05_SIAP_DISTRIBUSI")
	if err := os.MkdirAll(otaDir, 0o755); err != nil {
		t.Fatalf("failed to create temp OTA dir: %v", err)
	}
	if err := os.WriteFile(filepath.Join(otaDir, "agent.exe"), []byte("MZ-windows-agent-binary-fixture"), 0o644); err != nil {
		t.Fatalf("failed to write agent.exe fixture: %v", err)
	}
	if err := os.WriteFile(filepath.Join(otaDir, "osi_linux_agent"), []byte("ELF-linux-agent-binary-fixture"), 0o755); err != nil {
		t.Fatalf("failed to write osi_linux_agent fixture: %v", err)
	}
	h := &Handler{baseDir: tmpDir}

	r := gin.New()
	r.POST("/api/fleet/ota/trigger", h.TriggerOTAUpdate)
	r.GET("/api/fleet/ota/download", h.DownloadOTABinary)

	t.Run("TriggerOTAUpdate accepts device_name and returns SHA256 payload", func(t *testing.T) {
		body, _ := json.Marshal(map[string]string{"device_name": "PC-POS-01"})
		req, _ := http.NewRequest("POST", "/api/fleet/ota/trigger", bytes.NewBuffer(body))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)

		if w.Code != http.StatusOK {
			t.Fatalf("expected HTTP 200, got %d. Body: %s", w.Code, w.Body.String())
		}

		var resp map[string]interface{}
		if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
			t.Fatalf("failed to parse JSON response: %v", err)
		}

		if resp["status"] != "success" {
			t.Errorf("expected status 'success', got %v", resp["status"])
		}
		if resp["sha256"] == nil || resp["sha256"] == "" {
			t.Errorf("expected non-empty sha256 hash in response")
		}
	})

	t.Run("TriggerOTAUpdate accepts pc_name field fallback", func(t *testing.T) {
		body, _ := json.Marshal(map[string]string{"pc_name": "LINUX-AGENT-01"})
		req, _ := http.NewRequest("POST", "/api/fleet/ota/trigger", bytes.NewBuffer(body))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)

		if w.Code != http.StatusOK {
			t.Fatalf("expected HTTP 200, got %d. Body: %s", w.Code, w.Body.String())
		}
	})

	t.Run("DownloadOTABinary serves binary with application/octet-stream", func(t *testing.T) {
		req, _ := http.NewRequest("GET", "/api/fleet/ota/download?platform=linux", nil)
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)

		if w.Code != http.StatusOK {
			t.Fatalf("expected HTTP 200, got %d. Body: %s", w.Code, w.Body.String())
		}

		ct := w.Header().Get("Content-Type")
		if ct != "application/octet-stream" {
			t.Errorf("expected Content-Type application/octet-stream, got %s", ct)
		}
	})
}
