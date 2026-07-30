package api

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestUpdateChatSessionStatus_ValidationAndResponse(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := &Handler{}

	r := gin.New()
	r.POST("/api/dashboard_chat/sessions/:client_id/status", h.UpdateChatSessionStatus)

	t.Run("Missing client_id returns 400 Bad Request", func(t *testing.T) {
		req, _ := http.NewRequest("POST", "/api/dashboard_chat/sessions//status", bytes.NewBufferString(`{"status":"CLOSED"}`))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)

		if w.Code != http.StatusBadRequest && w.Code != http.StatusNotFound {
			t.Fatalf("expected 400 or 404 for missing client_id, got %d", w.Code)
		}
	})

	t.Run("Valid client_id updates session status", func(t *testing.T) {
		req, _ := http.NewRequest("POST", "/api/dashboard_chat/sessions/CLIENT-01/status", bytes.NewBufferString(`{"status":"CLOSED"}`))
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

		if resp["client_id"] != "CLIENT-01" {
			t.Fatalf("expected client_id CLIENT-01, got %v", resp["client_id"])
		}

		if resp["session_status"] != "CLOSED" {
			t.Fatalf("expected session_status CLOSED, got %v", resp["session_status"])
		}
	})
}
