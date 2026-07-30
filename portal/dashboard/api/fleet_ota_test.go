package api

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestFleetOTAHandlers(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := &Handler{}

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
