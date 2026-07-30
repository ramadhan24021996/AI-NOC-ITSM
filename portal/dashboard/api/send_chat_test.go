package api

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestSendChatMessage_ValidationAndResponse(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := &Handler{}

	r := gin.New()
	r.POST("/api/dashboard_chat/send", h.SendChatMessage)

	t.Run("Missing client_id or message returns 400 Bad Request", func(t *testing.T) {
		req, _ := http.NewRequest("POST", "/api/dashboard_chat/send", bytes.NewBufferString(`{"sender":"operator"}`))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)

		if w.Code != http.StatusBadRequest {
			t.Fatalf("expected status 400, got %d. Body: %s", w.Code, w.Body.String())
		}
	})

	t.Run("Valid payload without DB returns 200 with fallback data object", func(t *testing.T) {
		payload := `{"client_id":"CLIENT-01","sender":"operator","message":"Halo tes chat"}`
		req, _ := http.NewRequest("POST", "/api/dashboard_chat/send", bytes.NewBufferString(payload))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)

		if w.Code != http.StatusOK {
			t.Fatalf("expected status 200, got %d. Body: %s", w.Code, w.Body.String())
		}

		var resp map[string]interface{}
		if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
			t.Fatalf("failed to parse JSON response: %v", err)
		}

		if resp["status"] != "success" {
			t.Fatalf("expected status: success, got %v", resp["status"])
		}

		data, ok := resp["data"].(map[string]interface{})
		if !ok {
			t.Fatalf("expected data object in response, got %v", resp["data"])
		}

		if data["client_id"] != "CLIENT-01" || data["message"] != "Halo tes chat" {
			t.Fatalf("unexpected data contents: %v", data)
		}
	})
}
