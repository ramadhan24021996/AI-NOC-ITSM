package api

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestPrinterHardwareDiscovery_MultiLayerProbing(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := NewHandler(nil, nil, nil, ".", "")

	r := gin.New()
	r.GET("/api/fleet/admin/printers/hardware_discovery", h.GetPrinterHardwareDiscovery)
	r.POST("/api/fleet/admin/printers/hardware_diagnostic_test", h.RunPrinterHardwareDiagnosticTest)

	// 1. Test GET /api/fleet/admin/printers/hardware_discovery
	req, _ := http.NewRequest(http.MethodGet, "/api/fleet/admin/printers/hardware_discovery", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("Expected 200 OK, got %d: %s", w.Code, w.Body.String())
	}

	var resp struct {
		Status string                         `json:"status"`
		Data   PrinterHardwareDiscoveryReport `json:"data"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("Failed to parse JSON response: %v", err)
	}

	if resp.Status != "success" {
		t.Errorf("Expected status 'success', got '%s'", resp.Status)
	}

	t.Logf("[HARDWARE AUDIT] Host OS: %s", resp.Data.HostOS)
	t.Logf("[HARDWARE AUDIT] Total USB Devices Detected: %d", len(resp.Data.USBDevices))
	t.Logf("[HARDWARE AUDIT] CUPS Subsystem Available: %t", resp.Data.CUPSAvailable)
	t.Logf("[HARDWARE AUDIT] State Machine Stage: %s (Verdict: %s)", resp.Data.StateMachine.CurrentStage, resp.Data.StateMachine.CertificationVerdict)
	t.Logf("[HARDWARE AUDIT] Diagnostic Summary: %s", resp.Data.StateMachine.DiagnosticSummary)

	// Verify state machine integrity
	if resp.Data.StateMachine.CertificationVerdict == "" {
		t.Errorf("CertificationVerdict should not be empty")
	}

	// 2. Test POST /api/fleet/admin/printers/hardware_diagnostic_test (Device Node mode)
	bodyPayload := `{"target_type": "DEVICE_NODE", "endpoint": "/dev/usb/lp0"}`
	reqPost, _ := http.NewRequest(http.MethodPost, "/api/fleet/admin/printers/hardware_diagnostic_test", strings.NewReader(bodyPayload))
	reqPost.Header.Set("Content-Type", "application/json")
	wPost := httptest.NewRecorder()
	r.ServeHTTP(wPost, reqPost)

	if wPost.Code != http.StatusOK {
		t.Fatalf("Expected 200 OK for diagnostic test, got %d: %s", wPost.Code, wPost.Body.String())
	}

	var diagResp struct {
		Status          string `json:"status"`
		BytesGenerated  int    `json:"bytes_generated"`
		HardwarePresent bool   `json:"hardware_present"`
		ErrorMessage    string `json:"error_message"`
	}
	if err := json.Unmarshal(wPost.Body.Bytes(), &diagResp); err != nil {
		t.Fatalf("Failed to parse diagnostic test response: %v", err)
	}

	if diagResp.BytesGenerated == 0 {
		t.Errorf("ESC/POS generator should have produced bytes, got 0")
	}
	t.Logf("[HARDWARE AUDIT] ESC/POS Self-Test Bytes Generated: %d bytes (Execution Status: %s)", diagResp.BytesGenerated, diagResp.Status)
}
