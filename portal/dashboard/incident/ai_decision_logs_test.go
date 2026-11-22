package incident

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestAIDecisionLogsNilDBAndDefaults(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := &Handler{}
	r := gin.New()
	r.GET("/api/ai_decision_logs", h.GetAIDecisionLogs)
	r.GET("/api/ai_decision_logs/stats", h.GetAIDecisionLogStats)
	r.GET("/api/ai_decision_logs/:id/audit", h.GetAIDecisionLogDetailAudit)
	r.GET("/api/ai_decision_logs/export", h.ExportAIDecisionLogs)

	// List returns [] + X-Total-Count: 0
	w1 := httptest.NewRecorder()
	r.ServeHTTP(w1, httptest.NewRequest(http.MethodGet, "/api/ai_decision_logs", nil))
	if w1.Code != http.StatusOK || w1.Body.String() != "[]" {
		t.Fatalf("expected 200 [], got %d: %s", w1.Code, w1.Body.String())
	}
	if w1.Header().Get("X-Total-Count") != "0" {
		t.Fatalf("expected X-Total-Count=0, got %q", w1.Header().Get("X-Total-Count"))
	}

	// Stats returns zeroed metrics object
	w2 := httptest.NewRecorder()
	r.ServeHTTP(w2, httptest.NewRequest(http.MethodGet, "/api/ai_decision_logs/stats", nil))
	if w2.Code != http.StatusOK {
		t.Fatalf("expected 200 stats, got %d", w2.Code)
	}
	var stats map[string]interface{}
	if err := json.Unmarshal(w2.Body.Bytes(), &stats); err != nil {
		t.Fatalf("invalid stats JSON: %v", err)
	}
	if stats["total_filtered"] != float64(0) {
		t.Fatalf("expected total_filtered=0, got %v", stats["total_filtered"])
	}

	// Detail audit invalid ID -> 400; valid ID with nil DB -> 503
	wBad := httptest.NewRecorder()
	r.ServeHTTP(wBad, httptest.NewRequest(http.MethodGet, "/api/ai_decision_logs/abc/audit", nil))
	if wBad.Code != http.StatusBadRequest {
		t.Fatalf("expected 400 for invalid id, got %d", wBad.Code)
	}
	wNil := httptest.NewRecorder()
	r.ServeHTTP(wNil, httptest.NewRequest(http.MethodGet, "/api/ai_decision_logs/42/audit", nil))
	if wNil.Code != http.StatusServiceUnavailable {
		t.Fatalf("expected 503 for nil db, got %d", wNil.Code)
	}

	// Export JSON returns [] + SHA256 header
	wExp := httptest.NewRecorder()
	r.ServeHTTP(wExp, httptest.NewRequest(http.MethodGet, "/api/ai_decision_logs/export?format=json", nil))
	if wExp.Code != http.StatusOK || wExp.Body.String() != "[]" {
		t.Fatalf("expected 200 [] export, got %d: %s", wExp.Code, wExp.Body.String())
	}
	if wExp.Header().Get("X-Audit-Checksum-SHA256") == "" {
		t.Fatal("missing X-Audit-Checksum-SHA256 header")
	}
}

func TestSanitizeDecisionCSVCell(t *testing.T) {
	cases := map[string]string{
		"=HYPERLINK(\"x\")": "'=HYPERLINK(\"x\")",
		"+cmd":              "'+cmd",
		"-cmd":              "'-cmd",
		"@SUM(1,2)":         "'@SUM(1,2)",
		"  =evil":           "'  =evil",
		"normal decision":   "normal decision",
	}
	for in, want := range cases {
		if got := sanitizeDecisionCSVCell(in); got != want {
			t.Errorf("sanitizeDecisionCSVCell(%q) = %q, want %q", in, got, want)
		}
	}
}
