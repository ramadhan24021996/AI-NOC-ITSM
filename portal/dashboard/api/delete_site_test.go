package api

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestDeleteSite_ValidationAndResponse(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := &Handler{}

	r := gin.New()
	r.DELETE("/api/fleet/admin/sites/:id", h.DeleteSite)

	t.Run("Missing site_id returns 400 Bad Request", func(t *testing.T) {
		req, _ := http.NewRequest("DELETE", "/api/fleet/admin/sites/", bytes.NewBufferString("{}"))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)

		if w.Code != http.StatusBadRequest && w.Code != http.StatusNotFound {
			t.Fatalf("expected 400 or 404 for missing site_id, got %d", w.Code)
		}
	})

	t.Run("Valid site_id without DB returns 200 with fallback response", func(t *testing.T) {
		req, _ := http.NewRequest("DELETE", "/api/fleet/admin/sites/SITE-JAKARTA", nil)
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

		if resp["site_id"] != "SITE-JAKARTA" {
			t.Fatalf("expected site_id SITE-JAKARTA, got %v", resp["site_id"])
		}
	})
}
