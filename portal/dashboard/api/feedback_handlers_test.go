package api

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestGetFeedbackStatsDefaultsAndNonNil(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := &Handler{}
	r := gin.New()
	r.GET("/api/feedback/stats", h.GetFeedbackStats)

	w := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/api/feedback/stats", nil)
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("invalid JSON response: %v", err)
	}
	if acc, ok := resp["accuracy_rate"].(float64); !ok || acc != 0.0 {
		t.Fatalf("expected accuracy_rate=0.0 when no feedback evaluated, got %v", resp["accuracy_rate"])
	}
	if q, ok := resp["queue"].([]interface{}); !ok || q == nil {
		t.Fatalf("expected non-nil empty slice for queue, got %T (%v)", resp["queue"], resp["queue"])
	}
}

func TestGetFeedbackAndExportNonNullAndCSVSanitization(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := &Handler{}
	r := gin.New()
	r.GET("/api/feedback", h.GetFeedback)
	r.GET("/api/feedback/export", h.ExportFeedbackHistory)

	// GET /api/feedback -> []
	w1 := httptest.NewRecorder()
	r.ServeHTTP(w1, httptest.NewRequest(http.MethodGet, "/api/feedback", nil))
	if w1.Code != http.StatusOK || w1.Body.String() != "[]" {
		t.Fatalf("expected 200 [], got %d: %s", w1.Code, w1.Body.String())
	}

	// GET /api/feedback/export?format=json -> [] + checksum header
	w2 := httptest.NewRecorder()
	r.ServeHTTP(w2, httptest.NewRequest(http.MethodGet, "/api/feedback/export?format=json", nil))
	if w2.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w2.Code)
	}
	if w2.Body.String() != "[]" {
		t.Fatalf("expected empty JSON array [], got %q", w2.Body.String())
	}
	if w2.Header().Get("X-Audit-Checksum-SHA256") == "" {
		t.Fatal("missing X-Audit-Checksum-SHA256 header")
	}

	// CSV formula sanitization checks
	cases := map[string]string{
		"=CMD|' /C calc'!A0": "'=CMD|' /C calc'!A0",
		"+1+2":               "'+1+2",
		"-2+3":               "'-2+3",
		"@SUM(1,2)":          "'@SUM(1,2)",
		"  =evil":            "'  =evil",
		"<nil>":              "",
		"normal text":        "normal text",
	}
	for in, want := range cases {
		if got := sanitizeCSVCell(in); got != want {
			t.Errorf("sanitizeCSVCell(%q) = %q, want %q", in, got, want)
		}
	}
	if got := sanitizeCSVCell(nil); got != "" {
		t.Errorf("sanitizeCSVCell(nil) = %q, want empty", got)
	}
}

func TestFeedbackMutationValidation(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := &Handler{}
	r := gin.New()
	r.POST("/api/feedback", h.SubmitFeedback)
	r.POST("/api/feedback/approve", h.ApproveFeedback)
	r.POST("/api/feedback/reject", h.RejectFeedback)

	// Invalid incident_id -> 400 across all 3 endpoints
	for _, path := range []string{"/api/feedback", "/api/feedback/approve", "/api/feedback/reject"} {
		w := httptest.NewRecorder()
		req := httptest.NewRequest(http.MethodPost, path, bytes.NewBufferString(`{"incident_id":0}`))
		req.Header.Set("Content-Type", "application/json")
		r.ServeHTTP(w, req)
		if w.Code != http.StatusBadRequest {
			t.Errorf("%s with incident_id=0 expected 400, got %d: %s", path, w.Code, w.Body.String())
		}
	}

	// Valid incident_id with nil DB -> 503 for approve/reject
	for _, path := range []string{"/api/feedback/approve", "/api/feedback/reject"} {
		w := httptest.NewRecorder()
		req := httptest.NewRequest(http.MethodPost, path, bytes.NewBufferString(`{"incident_id":123,"rejection_reason":"test"}`))
		req.Header.Set("Content-Type", "application/json")
		r.ServeHTTP(w, req)
		if w.Code != http.StatusServiceUnavailable {
			t.Errorf("%s with nil db expected 503, got %d: %s", path, w.Code, w.Body.String())
		}
	}
}
