package api

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestChatSuggest_DynamicSuggestions(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := &Handler{}

	r := gin.New()
	r.GET("/api/dashboard_chat/suggest", h.ChatSuggest)

	t.Run("General query returns non-empty dynamic suggestions", func(t *testing.T) {
		req, _ := http.NewRequest("GET", "/api/dashboard_chat/suggest?limit=3", nil)
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

		suggestions, ok := resp["suggestions"].([]interface{})
		if !ok || len(suggestions) == 0 {
			t.Fatalf("expected non-empty suggestions array, got %v", resp["suggestions"])
		}

		if len(suggestions) > 3 {
			t.Fatalf("expected at most 3 suggestions due to limit=3, got %d", len(suggestions))
		}
	})

	t.Run("Device-specific query returns client_id in suggestions", func(t *testing.T) {
		req, _ := http.NewRequest("GET", "/api/dashboard_chat/suggest?client_id=PC-POS-01", nil)
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)

		if w.Code != http.StatusOK {
			t.Fatalf("expected status 200, got %d. Body: %s", w.Code, w.Body.String())
		}

		var resp map[string]interface{}
		_ = json.Unmarshal(w.Body.Bytes(), &resp)

		if resp["client_id"] != "PC-POS-01" {
			t.Fatalf("expected client_id PC-POS-01, got %v", resp["client_id"])
		}
	})
}
