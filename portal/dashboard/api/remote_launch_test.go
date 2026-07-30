package api

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestRemoteLaunch_ValidationAndPayload(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := &Handler{}

	r := gin.New()
	r.POST("/api/remote/launch/:type", h.RemoteLaunch)
	r.GET("/api/remote/launch", h.RemoteLaunch)

	t.Run("Missing target device returns 400 Bad Request", func(t *testing.T) {
		req, _ := http.NewRequest("POST", "/api/remote/launch/rdp", bytes.NewBufferString("{}"))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)

		if w.Code != http.StatusBadRequest {
			t.Fatalf("expected status 400 for missing target, got %d. Body: %s", w.Code, w.Body.String())
		}
	})

	t.Run("Valid RustDesk launch request produces valid launcher_payload", func(t *testing.T) {
		req, _ := http.NewRequest("POST", "/api/remote/launch/rustdesk", bytes.NewBufferString(`{"pc_name":"PC-POS-01","ip":"192.168.1.100"}`))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)

		if w.Code != http.StatusOK {
			t.Fatalf("expected status 200, got %d. Body: %s", w.Code, w.Body.String())
		}

		var resp map[string]interface{}
		if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
			t.Fatalf("failed to parse response JSON: %v", err)
		}

		if resp["status"] != "success" {
			t.Fatalf("expected status: success, got %v", resp["status"])
		}

		payload, ok := resp["launcher_payload"].(map[string]interface{})
		if !ok {
			t.Fatalf("expected launcher_payload object, got %v", resp["launcher_payload"])
		}

		if payload["tool"] != "rustdesk" {
			t.Fatalf("expected tool rustdesk in launcher_payload, got %v", payload["tool"])
		}
	})

	t.Run("RDP launch request GET query parameter test", func(t *testing.T) {
		req, _ := http.NewRequest("GET", "/api/remote/launch?type=rdp&ip=10.0.0.5&pc_name=SRV-01", nil)
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)

		if w.Code != http.StatusOK {
			t.Fatalf("expected status 200, got %d. Body: %s", w.Code, w.Body.String())
		}

		var resp map[string]interface{}
		_ = json.Unmarshal(w.Body.Bytes(), &resp)

		if resp["tool"] != "rdp" || resp["target"] != "10.0.0.5" {
			t.Fatalf("unexpected response attributes: %v", resp)
		}
	})
}
