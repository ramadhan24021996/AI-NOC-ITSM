package ingestion

// K-03 regression tests: ingestion endpoints must reject unauthenticated
// requests (fail-closed, P8) and never accept the legacy literal key.

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestK03_TelemetryRequiresAuth(t *testing.T) {
	old := securityKey
	securityKey = []byte("runtime-test-key")
	defer func() { securityKey = old }()

	cases := []struct {
		name   string
		header string
		want   int
	}{
		{"missing header", "", http.StatusUnauthorized},
		{"legacy literal key", "Bearer SIAP_DISTRIBUSI_SECRET_KEY", http.StatusUnauthorized},
		{"wrong token", "Bearer nope", http.StatusUnauthorized},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodPost, "/issues", strings.NewReader(`{}`))
			if c.header != "" {
				req.Header.Set("Authorization", c.header)
			}
			rec := httptest.NewRecorder()
			handleHTTPTelemetryEvent(rec, req)
			if rec.Code != c.want {
				t.Fatalf("K-03 VIOLATION: %s -> %d, want %d", c.name, rec.Code, c.want)
			}
		})
	}
}

func TestK03_TelemetryBodyLimit(t *testing.T) {
	old := securityKey
	securityKey = []byte("runtime-test-key")
	defer func() { securityKey = old }()

	big := `{"x":"` + strings.Repeat("a", 2<<20) + `"}`
	req := httptest.NewRequest(http.MethodPost, "/telemetry", strings.NewReader(big))
	req.Header.Set("Authorization", "Bearer runtime-test-key")
	rec := httptest.NewRecorder()
	handleHTTPTelemetryEvent(rec, req)
	if rec.Code != http.StatusRequestEntityTooLarge {
		t.Fatalf("T-16: 2MB body -> %d, want 413", rec.Code)
	}
}

func TestK03_WebhooksRequireToken(t *testing.T) {
	handlers := map[string]http.HandlerFunc{
		"/api/v1/netdata":  handleNetdataWebhook,
		"/api/v1/topology": handleTopologyWebhook,
	}
	for path, h := range handlers {
		// Fail-closed when WEBHOOK_TOKEN is unset.
		t.Setenv("WEBHOOK_TOKEN", "")
		req := httptest.NewRequest(http.MethodPost, path, strings.NewReader(`{}`))
		req.Header.Set("X-Webhook-Token", "anything")
		rec := httptest.NewRecorder()
		h(rec, req)
		if rec.Code != http.StatusUnauthorized {
			t.Fatalf("%s with unset WEBHOOK_TOKEN -> %d, want 401", path, rec.Code)
		}

		t.Setenv("WEBHOOK_TOKEN", "wh-secret")
		for _, hdr := range []string{"", "wrong"} {
			req := httptest.NewRequest(http.MethodPost, path, strings.NewReader(`{}`))
			if hdr != "" {
				req.Header.Set("X-Webhook-Token", hdr)
			}
			rec := httptest.NewRecorder()
			h(rec, req)
			if rec.Code != http.StatusUnauthorized {
				t.Fatalf("%s token=%q -> %d, want 401", path, hdr, rec.Code)
			}
			if rec.Header().Get("Access-Control-Allow-Origin") == "*" {
				t.Fatalf("%s still sends wildcard CORS (S-05)", path)
			}
		}

		// Valid token passes auth (payload {} may then be rejected as 400, not 401).
		req = httptest.NewRequest(http.MethodPost, path, strings.NewReader(`{}`))
		req.Header.Set("Authorization", "Bearer wh-secret")
		rec = httptest.NewRecorder()
		h(rec, req)
		if rec.Code == http.StatusUnauthorized {
			t.Fatalf("%s valid token rejected", path)
		}
	}
}
