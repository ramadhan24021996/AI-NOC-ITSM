package api

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestGetAgentDeepDiagnostics_USBDeviceDetection(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := &Handler{}

	r := gin.New()
	r.GET("/api/agent_deep_diagnostics/:device", h.GetAgentDeepDiagnostics)

	t.Run("Deep Diagnostics returns non-empty usb_devices containing peripherals", func(t *testing.T) {
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

		usbDevices, ok := agentData["usb_devices"].([]interface{})
		if !ok || len(usbDevices) == 0 {
			t.Fatalf("expected non-empty usb_devices array in agent_data, got %v", agentData["usb_devices"])
		}

		hasMouseOrKeyboard := false
		for _, dev := range usbDevices {
			if devMap, ok := dev.(map[string]interface{}); ok {
				desc, _ := devMap["description"].(string)
				devType, _ := devMap["type"].(string)
				devClass, _ := devMap["Class"].(string)
				if desc != "" || devType != "" || devClass != "" {
					hasMouseOrKeyboard = true
					break
				}
			}
		}

		if !hasMouseOrKeyboard {
			t.Fatalf("expected USB devices to contain descriptive fields, got: %v", usbDevices)
		}
	})
}
