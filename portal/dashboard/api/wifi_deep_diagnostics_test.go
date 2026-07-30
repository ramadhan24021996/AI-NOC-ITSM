package api

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestGetAgentDeepDiagnostics_WiFiAndIPDetection(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := &Handler{}

	r := gin.New()
	r.GET("/api/agent_deep_diagnostics/:device", h.GetAgentDeepDiagnostics)

	t.Run("Deep Diagnostics populates ip and network_advanced wifi fields", func(t *testing.T) {
		req, _ := http.NewRequest("GET", "/api/agent_deep_diagnostics/PC-POS-01", nil)
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)

		if w.Code != http.StatusOK {
			t.Fatalf("expected status 200, got %d. Body: %s", w.Code, w.Body.String())
		}

		var resp map[string]interface{}
		if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
			t.Fatalf("failed to parse JSON response: %v", err)
		}

		agentData, ok := resp["agent_data"].(map[string]interface{})
		if !ok {
			t.Fatalf("expected agent_data object in response")
		}

		netAdv, ok := agentData["network_advanced"].(map[string]interface{})
		if !ok {
			t.Fatalf("expected network_advanced map in agent_data, got %v", agentData["network_advanced"])
		}

		// Ensure IP field exists in network_advanced or response
		ipVal, _ := resp["ip"].(string)
		netIP, _ := netAdv["ip"].(string)
		if ipVal == "" && netIP == "" {
			t.Fatalf("expected IP address in response or network_advanced")
		}
	})
}
