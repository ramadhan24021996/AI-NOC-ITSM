package api

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestSkeletonHandlers_RefactoredLogic(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := &Handler{}

	r := gin.New()
	r.GET("/api/kb_stats", h.GetKBStats)
	r.GET("/api/governance/sla_compliance", h.GetSLACompliance)
	r.GET("/api/dashboard_chat/device_context/:client_id", h.GetChatDeviceContext)
	r.POST("/api/printers/delete", h.DeletePrinter)
	r.DELETE("/api/printers/:id", h.DeletePrinterByID)
	r.DELETE("/api/fleet/admin/sites/delete/:site_id", h.DeleteFleetSite)
	r.GET("/api/rca/trace/:id", h.GetDecisionTrace)
	r.POST("/api/offline/diagnose", h.OfflineDiagnose)

	t.Run("GetKBStats returns valid layer stats", func(t *testing.T) {
		req, _ := http.NewRequest("GET", "/api/kb_stats", nil)
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)

		if w.Code != http.StatusOK {
			t.Fatalf("expected status 200, got %d", w.Code)
		}

		var stats []map[string]interface{}
		if err := json.Unmarshal(w.Body.Bytes(), &stats); err != nil {
			t.Fatalf("failed to parse JSON: %v", err)
		}
		if len(stats) == 0 {
			t.Fatalf("expected non-empty layer stats")
		}
	})

	t.Run("GetSLACompliance returns SLA map", func(t *testing.T) {
		req, _ := http.NewRequest("GET", "/api/governance/sla_compliance", nil)
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)

		if w.Code != http.StatusOK {
			t.Fatalf("expected status 200, got %d", w.Code)
		}

		var slaMap map[string]float64
		if err := json.Unmarshal(w.Body.Bytes(), &slaMap); err != nil {
			t.Fatalf("failed to parse JSON: %v", err)
		}
	})

	t.Run("GetChatDeviceContext returns incident context for client", func(t *testing.T) {
		req, _ := http.NewRequest("GET", "/api/dashboard_chat/device_context/POS-JAKARTA-01", nil)
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)

		if w.Code != http.StatusOK {
			t.Fatalf("expected status 200, got %d", w.Code)
		}

		var resp map[string]interface{}
		_ = json.Unmarshal(w.Body.Bytes(), &resp)

		if resp["client_id"] != "POS-JAKARTA-01" {
			t.Fatalf("expected client_id POS-JAKARTA-01, got %v", resp["client_id"])
		}
	})

	t.Run("DeletePrinter validation handles missing printer name", func(t *testing.T) {
		req, _ := http.NewRequest("POST", "/api/printers/delete", bytes.NewBufferString("{}"))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)

		if w.Code != http.StatusBadRequest {
			t.Fatalf("expected status 400 for missing printer, got %d", w.Code)
		}
	})

	t.Run("GetDecisionTrace returns valid nodes & edges", func(t *testing.T) {
		req, _ := http.NewRequest("GET", "/api/rca/trace/101", nil)
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)

		if w.Code != http.StatusOK {
			t.Fatalf("expected status 200, got %d", w.Code)
		}

		var resp map[string]interface{}
		_ = json.Unmarshal(w.Body.Bytes(), &resp)

		nodes, ok := resp["nodes"].([]interface{})
		if !ok || len(nodes) == 0 {
			t.Fatalf("expected non-empty nodes in trace")
		}
	})

	t.Run("OfflineDiagnose generates dynamic 5 Whys analysis", func(t *testing.T) {
		req, _ := http.NewRequest("POST", "/api/offline/diagnose", bytes.NewBufferString(`{"question":"Mengapa printer thermal offline?"}`))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)

		if w.Code != http.StatusOK {
			t.Fatalf("expected status 200, got %d", w.Code)
		}

		var resp map[string]interface{}
		_ = json.Unmarshal(w.Body.Bytes(), &resp)

		if resp["success"] != true {
			t.Fatalf("expected success true")
		}
		if resp["5_whys_analysis"] == nil {
			t.Fatalf("expected 5_whys_analysis field")
		}
	})
}
