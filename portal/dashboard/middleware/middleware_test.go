package middleware_test

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
	"go_incident_analysis/portal/dashboard/middleware"
)

// ─── helpers ────────────────────────────────────────────────────────────────

func minimalRouter() *gin.Engine {
	gin.SetMode(gin.TestMode)
	r := gin.New()
	r.Use(middleware.AuthMiddleware(nil))
	r.GET("/health", func(c *gin.Context) { c.Status(http.StatusOK) })
	r.GET("/api/protected", func(c *gin.Context) { c.Status(http.StatusOK) })
	r.POST("/api/protected", func(c *gin.Context) { c.Status(http.StatusOK) })
	return r
}

func csrfRouter() *gin.Engine {
	gin.SetMode(gin.TestMode)
	r := gin.New()
	r.Use(middleware.AuthMiddleware(nil))
	r.Use(middleware.CSRFMiddleware())
	r.POST("/api/auth/login", func(c *gin.Context) { c.Status(http.StatusOK) })
	r.POST("/api/protected", func(c *gin.Context) { c.Status(http.StatusOK) })
	return r
}

// ─── K-04: default-deny ─────────────────────────────────────────────────────

// test_K04_public_health_no_token: /health must pass without token.
func Test_K04_PublicHealthNoToken(t *testing.T) {
	r := minimalRouter()
	w := httptest.NewRecorder()
	r.ServeHTTP(w, httptest.NewRequest(http.MethodGet, "/health", nil))
	if w.Code != http.StatusOK {
		t.Errorf("expected 200 for /health, got %d", w.Code)
	}
}

// test_K04_protected_no_token: non-public route → 401 without token.
func Test_K04_ProtectedNoToken(t *testing.T) {
	r := minimalRouter()
	w := httptest.NewRecorder()
	r.ServeHTTP(w, httptest.NewRequest(http.MethodGet, "/api/protected", nil))
	if w.Code != http.StatusUnauthorized {
		t.Errorf("expected 401 for /api/protected, got %d", w.Code)
	}
}

// test_K04_notify_requires_auth: /api/fleet/notify must NOT bypass auth.
func Test_K04_NotifyRequiresAuth(t *testing.T) {
	r := minimalRouter()
	w := httptest.NewRecorder()
	r.ServeHTTP(w, httptest.NewRequest(http.MethodGet, "/api/fleet/notify", nil))
	if w.Code != http.StatusUnauthorized {
		t.Errorf("K-04: /api/fleet/notify should return 401, got %d", w.Code)
	}
}

// test_K04_ws_logs_requires_auth: /ws/logs must require auth.
func Test_K04_WsLogsRequiresAuth(t *testing.T) {
	r := minimalRouter()
	w := httptest.NewRecorder()
	r.ServeHTTP(w, httptest.NewRequest(http.MethodGet, "/ws/logs", nil))
	if w.Code != http.StatusUnauthorized {
		t.Errorf("K-04: /ws/logs should return 401, got %d", w.Code)
	}
}

// test_K04_isPublicPath: IsPublicPath exact contract.
func Test_K04_IsPublicPath(t *testing.T) {
	cases := []struct {
		path   string
		expect bool
	}{
		{"/", true},
		{"/health", true},
		{"/api/auth/login", true},
		{"/static/app.js", true},
		{"/api/fleet/notify", false},
		{"/api/jarvis/query", false},
		{"/api/fleet/ota", false},
		{"/api/protected", false},
		{"/ws/logs", false},
		{"/ws/client_chat", false},
	}
	for _, tc := range cases {
		if got := middleware.IsPublicPath(tc.path); got != tc.expect {
			t.Errorf("IsPublicPath(%q) = %v, want %v", tc.path, got, tc.expect)
		}
	}
}

// test_K04_csrf_login_exempt: /api/auth/login must NOT get a CSRF-403.
func Test_K04_CsrfLoginExempt(t *testing.T) {
	r := csrfRouter()
	w := httptest.NewRecorder()
	r.ServeHTTP(w, httptest.NewRequest(http.MethodPost, "/api/auth/login", nil))
	if w.Code == http.StatusForbidden {
		t.Errorf("K-04: CSRF middleware wrongly rejected /api/auth/login with 403")
	}
}
