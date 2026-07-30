package api

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestGetAgentDeepDiagnostics_LiveBrowserTabsDetection(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := &Handler{}

	r := gin.New()
	r.GET("/api/agent_deep_diagnostics/:device", h.GetAgentDeepDiagnostics)

	t.Run("Deep Diagnostics returns live open browser tabs and focused tab", func(t *testing.T) {
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

		urlHistory, ok := agentData["browser_url_history_10min"].([]interface{})
		if !ok || len(urlHistory) == 0 {
			t.Fatalf("expected non-empty browser_url_history_10min (live tabs) in agent_data, got %v", agentData["browser_url_history_10min"])
		}

		currentURL := agentData["current_browser_url"]
		if currentURL == nil {
			t.Fatalf("expected non-nil current_browser_url (focused live tab) in agent_data")
		}
	})
}
