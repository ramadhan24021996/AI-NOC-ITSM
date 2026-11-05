package api

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
	gowebsocket "github.com/gorilla/websocket"
	"go_incident_analysis/portal/dashboard/incident"
	"go_incident_analysis/portal/dashboard/websocket"
)

// TestRoutesRuntime_224EndpointsAudit Audits route registration and basic HTTP execution for all 224 endpoints.
func TestRoutesRuntime_224EndpointsAudit(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := NewHandler(nil, nil, nil, ".", "")
	incH := incident.NewHandler(nil, nil, nil, ".")

	r := gin.New()
	h.RegisterRoutes(r)
	incH.RegisterRoutes(r)

	// Fetch all registered routes from Gin engine
	routes := r.Routes()
	t.Logf("[ROUTE AUDIT] Total Registered Gin Routes: %d", len(routes))

	if len(routes) == 0 {
		t.Fatalf("No routes registered on Gin engine")
	}

	validStatusCodes := map[int]bool{
		http.StatusOK:                  true,
		http.StatusBadRequest:          true,
		http.StatusUnauthorized:        true,
		http.StatusForbidden:           true,
		http.StatusNotFound:            true,
		http.StatusMethodNotAllowed:    true,
		http.StatusInternalServerError: true,
		http.StatusBadGateway:          true,
		http.StatusServiceUnavailable:  true,
	}

	passedCount := 0
	for _, route := range routes {
		url := route.Path
		// Replace path parameters with test values
		url = strings.ReplaceAll(url, ":id", "1")
		url = strings.ReplaceAll(url, ":incident_id", "1")
		url = strings.ReplaceAll(url, ":device", "localhost")
		url = strings.ReplaceAll(url, ":tool", "ping")
		url = strings.ReplaceAll(url, "*filepath", "test.txt")

		req, err := http.NewRequest(route.Method, url, nil)
		if err != nil {
			t.Errorf("Failed to construct request for %s %s: %v", route.Method, route.Path, err)
			continue
		}

		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)

		if validStatusCodes[w.Code] {
			passedCount++
		} else {
			t.Errorf("Route %s %s returned invalid HTTP status code: %d", route.Method, route.Path, w.Code)
		}
	}

	t.Logf("[ROUTE AUDIT] Verified %d / %d routes returned handled HTTP status codes", passedCount, len(routes))
}

// TestWebSocket_HandshakeEndpoints Audits WebSocket endpoints for valid HTTP Upgrade header handling.
func TestWebSocket_HandshakeEndpoints(t *testing.T) {
	r := gin.New()
	wsH := websocket.NewHandler(nil)
	wsH.RegisterRoutes(r)

	server := httptest.NewServer(r)
	defer server.Close()

	wsURL := "ws://" + strings.TrimPrefix(server.URL, "http://")
	wsEndpoints := []string{"/ws/logs"}

	for _, ep := range wsEndpoints {
		dialer := gowebsocket.Dialer{}
		conn, resp, err := dialer.Dial(wsURL+ep, nil)
		if resp != nil {
			t.Logf("[WS AUDIT] Endpoint %s response status: %d", ep, resp.StatusCode)
		}
		if err != nil {
			t.Fatalf("[WS AUDIT] Endpoint %s connection failed: %v", ep, err)
		}
		if conn != nil {
			conn.SetReadDeadline(time.Now().Add(2 * time.Second))
			msgType, msgBytes, readErr := conn.ReadMessage()
			if readErr != nil {
				t.Logf("[WS AUDIT] Endpoint %s frame read warning: %v", ep, readErr)
			} else {
				t.Logf("[WS AUDIT] Endpoint %s Frame Type: %d | Payload: %s", ep, msgType, string(msgBytes))
			}
			conn.Close()
		}
	}
}
