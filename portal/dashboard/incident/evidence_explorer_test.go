package incident

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
)

func TestEvidenceExplorer_NilDB(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := &Handler{db: nil}
	r := gin.New()
	r.GET("/api/evidence_explorer", h.GetEvidenceExplorer)
	r.GET("/api/evidence/explorer", h.GetEvidenceExplorer)
	r.GET("/api/evidence_explorer/:incident_id", h.GetEvidenceExplorerDetail)
	r.GET("/api/evidence/explorer/:incident_id", h.GetEvidenceExplorerDetail)

	t.Run("GetEvidenceExplorer nil DB returns safe fallback", func(t *testing.T) {
		w := httptest.NewRecorder()
		req, _ := http.NewRequest("GET", "/api/evidence_explorer", nil)
		r.ServeHTTP(w, req)

		if w.Code != http.StatusOK {
			t.Fatalf("Expected HTTP 200, got %d", w.Code)
		}

		var resp map[string]interface{}
		if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
			t.Fatalf("JSON parse error: %v", err)
		}

		readiness, ok := resp["readiness"].(map[string]interface{})
		if !ok {
			t.Fatalf("Expected readiness object in response")
		}
		if readiness["status"] != "NO EVIDENCE DATA" {
			t.Errorf("Expected status 'NO EVIDENCE DATA', got %v", readiness["status"])
		}
		if readiness["conflicts"].(float64) != 0 {
			t.Errorf("Expected 0 conflicts, got %v", readiness["conflicts"])
		}
	})

	t.Run("GetEvidenceExplorer alias route works", func(t *testing.T) {
		w := httptest.NewRecorder()
		req, _ := http.NewRequest("GET", "/api/evidence/explorer", nil)
		r.ServeHTTP(w, req)

		if w.Code != http.StatusOK {
			t.Fatalf("Expected HTTP 200 on alias route, got %d", w.Code)
		}
	})

	t.Run("GetEvidenceExplorerDetail rejects invalid incident_id", func(t *testing.T) {
		w := httptest.NewRecorder()
		req, _ := http.NewRequest("GET", "/api/evidence_explorer/not-a-number", nil)
		r.ServeHTTP(w, req)

		if w.Code != http.StatusBadRequest {
			t.Fatalf("Expected HTTP 400 for non-numeric incident_id, got %d", w.Code)
		}
	})

	t.Run("GetEvidenceExplorerDetail nil DB returns 503", func(t *testing.T) {
		w := httptest.NewRecorder()
		req, _ := http.NewRequest("GET", "/api/evidence_explorer/101", nil)
		r.ServeHTTP(w, req)

		if w.Code != http.StatusServiceUnavailable {
			t.Fatalf("Expected HTTP 503 for nil DB, got %d", w.Code)
		}
	})
}

func TestEvidenceExplorer_Rule6Logic(t *testing.T) {
	now := time.Now()
	before := now.Add(-10 * time.Minute)
	after := now.Add(10 * time.Minute)

	t.Run("Rule 6 satisfied when T_post >= T_exec", func(t *testing.T) {
		st := rule6State{
			ExecAt: &before,
			PostAt: &after,
			Bound:  !after.Before(before),
		}
		if !st.satisfied() {
			t.Errorf("Expected Rule #6 to be satisfied when T_post >= T_exec")
		}
	})

	t.Run("Rule 6 not satisfied when T_post < T_exec", func(t *testing.T) {
		st := rule6State{
			ExecAt: &after,
			PostAt: &before,
			Bound:  !before.Before(after),
		}
		if st.satisfied() {
			t.Errorf("Expected Rule #6 to fail when T_post < T_exec")
		}
	})

	t.Run("Rule 6 satisfied when decision passed in ADR", func(t *testing.T) {
		st := rule6State{
			DecisionPassed: true,
		}
		if !st.satisfied() {
			t.Errorf("Expected Rule #6 to be satisfied via decision_passed")
		}
	})
}

func TestKnowledgeGraph_NilDB(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := &Handler{db: nil}
	r := gin.New()
	r.GET("/api/knowledge_graph", h.GetKnowledgeGraph)

	w := httptest.NewRecorder()
	req, _ := http.NewRequest("GET", "/api/knowledge_graph", nil)
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("Expected HTTP 200, got %d", w.Code)
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("JSON parse error: %v", err)
	}

	if _, ok := resp["centrality"]; !ok {
		t.Errorf("Expected centrality key in response")
	}
	if _, ok := resp["rca_path"]; !ok {
		t.Errorf("Expected rca_path key in response")
	}
	if resp["active_incident"] != "Tidak ada insiden aktif" {
		t.Errorf("Expected active_incident to be 'Tidak ada insiden aktif', got %v", resp["active_incident"])
	}
}

func TestSandboxVerifyAndRemediate_Rule6(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := &Handler{db: nil}
	r := gin.New()
	r.POST("/api/incident/sandbox_verify", h.SandboxVerifyIncident)
	r.POST("/api/incident/remediate", h.RemediateIncident)

	t.Run("SandboxVerify passes safe printer spooler incident", func(t *testing.T) {
		body := strings.NewReader(`{"incident_id":"1042","device_name":"PC-FINANCE-01","description":"Print spooler stuck"}`)
		w := httptest.NewRecorder()
		req, _ := http.NewRequest("POST", "/api/incident/sandbox_verify", body)
		req.Header.Set("Content-Type", "application/json")
		r.ServeHTTP(w, req)

		if w.Code != http.StatusOK {
			t.Fatalf("Expected HTTP 200, got %d", w.Code)
		}
		var resp map[string]interface{}
		if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
			t.Fatalf("JSON parse error: %v", err)
		}
		if resp["status"] != "PASSED" {
			t.Errorf("Expected status PASSED, got %v", resp["status"])
		}
		if resp["action_code"] != "ACT_RESET_PRINTER_DRIVER" {
			t.Errorf("Expected ACT_RESET_PRINTER_DRIVER, got %v", resp["action_code"])
		}
		if resp["rule6_gate"] != "LOCKED_UNTIL_DUAL_EVIDENCE" {
			t.Errorf("Expected rule6_gate LOCKED_UNTIL_DUAL_EVIDENCE, got %v", resp["rule6_gate"])
		}
	})

	t.Run("SandboxVerify blocks destructive payload", func(t *testing.T) {
		body := strings.NewReader(`{"incident_id":"1042","device_name":"PC-FINANCE-01","action_code":"rm -rf /"}`)
		w := httptest.NewRecorder()
		req, _ := http.NewRequest("POST", "/api/incident/sandbox_verify", body)
		req.Header.Set("Content-Type", "application/json")
		r.ServeHTTP(w, req)

		if w.Code != http.StatusForbidden {
			t.Fatalf("Expected HTTP 403 for destructive payload, got %d", w.Code)
		}
	})

	t.Run("RemediateIncident locks status in PENDING_VERIFICATION per Rule #6", func(t *testing.T) {
		body := strings.NewReader(`{"incident_id":"1042","device_name":"PC-FINANCE-01","description":"DNS failure on gateway"}`)
		w := httptest.NewRecorder()
		req, _ := http.NewRequest("POST", "/api/incident/remediate", body)
		req.Header.Set("Content-Type", "application/json")
		r.ServeHTTP(w, req)

		if w.Code != http.StatusAccepted {
			t.Fatalf("Expected HTTP 202 Accepted, got %d", w.Code)
		}
		var resp map[string]interface{}
		if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
			t.Fatalf("JSON parse error: %v", err)
		}
		if resp["status"] != StatePendingVerification {
			t.Errorf("Rule #6 violation: expected status PENDING_VERIFICATION, got %v", resp["status"])
		}
	})
}
