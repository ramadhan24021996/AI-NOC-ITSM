package api

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestGetAgentDeepDiagnostics_ComprehensiveAudit(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := &Handler{}

	r := gin.New()
	r.GET("/api/agent_deep_diagnostics/:device", h.GetAgentDeepDiagnostics)

	t.Run("Verify all 10 sections in GetAgentDeepDiagnostics response payload", func(t *testing.T) {
		req, _ := http.NewRequest("GET", "/api/agent_deep_diagnostics/PC-STORE-01", nil)
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)

		if w.Code != http.StatusOK {
			t.Fatalf("expected HTTP 200, got %d. Body: %s", w.Code, w.Body.String())
		}

		var resp map[string]interface{}
		if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
			t.Fatalf("failed to parse JSON response: %v", err)
		}

		// 1. Top Level Fields
		if resp["device"] == nil || resp["device"] == "" {
			t.Errorf("missing device field in top-level response")
		}
		if resp["ip"] == nil || resp["ip"] == "" {
			t.Errorf("missing ip field in top-level response")
		}
		if resp["status"] == nil || resp["status"] == "" {
			t.Errorf("missing status field in top-level response")
		}

		agentData, ok := resp["agent_data"].(map[string]interface{})
		if !ok {
			t.Fatalf("missing agent_data object in response")
		}

		// 2. Section 1: System Health Core Metrics
		if agentData["cpu_usage"] == nil || agentData["ram_usage"] == nil || agentData["disk_usage"] == nil {
			t.Errorf("missing CPU/RAM/Disk metrics in agent_data")
		}
		if agentData["os_version"] == nil || agentData["os_version"] == "" {
			t.Errorf("missing os_version in agent_data")
		}

		// 3. Section 2: Network Monitoring & Wi-Fi
		netAdv, ok := agentData["network_advanced"].(map[string]interface{})
		if !ok {
			t.Errorf("missing network_advanced in agent_data")
		} else {
			if netAdv["ip"] == nil || netAdv["ip"] == "" {
				t.Errorf("missing IP in network_advanced")
			}
		}

		// 4. Section 3: Web App Usage & URL Monitoring
		if agentData["browser_url_history_10min"] == nil {
			t.Errorf("missing browser_url_history_10min (live tabs) in agent_data")
		}
		if agentData["current_browser_url"] == nil {
			t.Errorf("missing current_browser_url in agent_data")
		}

		// 5. Section 4: Printers & Peripheral Detection
		if agentData["printers"] == nil {
			t.Errorf("missing printers in agent_data")
		}

		// 6. Section 5: USB Devices & Peripheral Detection
		usbDevs, ok := agentData["usb_devices"].([]interface{})
		if !ok || len(usbDevs) == 0 {
			t.Errorf("missing or empty usb_devices in agent_data")
		}

		// 7. Section 6: Windows Services
		if agentData["service_status"] == nil {
			t.Errorf("missing service_status in agent_data")
		}

		// 8. Section 7: Remote Access (RustDesk / AnyDesk)
		if agentData["rustdesk"] == nil || agentData["anydesk"] == nil {
			t.Errorf("missing RustDesk/AnyDesk in agent_data")
		}

		// 9. Section 8: Recent Activity
		if agentData["recent_activity"] == nil {
			t.Errorf("missing recent_activity in agent_data")
		}

		// 10. Section 9 & 10: Data Source & Updated At
		if agentData["data_source"] == nil || agentData["updated_at"] == nil {
			t.Errorf("missing data_source or updated_at in agent_data")
		}
	})
}
