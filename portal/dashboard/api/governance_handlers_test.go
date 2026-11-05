package api

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestGovernanceHandlers_Endpoints(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := &Handler{} // nil DB tests default fallbacks cleanly
	r := gin.New()

	r.GET("/api/governance/top_resolutions", h.GetTopResolutions)
	r.GET("/api/governance/sla_compliance", h.GetSLACompliance)
	r.GET("/api/governance/event_correlation", h.GetEventCorrelation)
	r.GET("/api/governance/learning_gate/policy", h.GetLearningGatePolicy)
	r.POST("/api/governance/learning_gate/update", h.UpdateLearningGatePolicy)
	r.POST("/api/governance/learning_gate/rollback", h.RollbackLearningGatePolicy)
	r.GET("/api/governance/learning_gate/history", h.GetLearningGateHistory)

	t.Run("GetTopResolutions returns default fallback resolution data", func(t *testing.T) {
		w := httptest.NewRecorder()
		req, _ := http.NewRequest("GET", "/api/governance/top_resolutions", nil)
		r.ServeHTTP(w, req)

		if w.Code != http.StatusOK {
			t.Fatalf("Expected HTTP 200, got %d", w.Code)
		}
		var resp []map[string]interface{}
		if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
			t.Fatalf("Failed to parse response JSON: %v", err)
		}
		if len(resp) == 0 {
			t.Errorf("Expected non-empty top resolutions list")
		}
	})

	t.Run("GetSLACompliance returns site SLA compliance map", func(t *testing.T) {
		w := httptest.NewRecorder()
		req, _ := http.NewRequest("GET", "/api/governance/sla_compliance", nil)
		r.ServeHTTP(w, req)

		if w.Code != http.StatusOK {
			t.Fatalf("Expected HTTP 200, got %d", w.Code)
		}
		var resp map[string]float64
		if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
			t.Fatalf("Failed to parse response JSON: %v", err)
		}
		if _, ok := resp["BOGOR"]; !ok {
			t.Errorf("Expected site 'BOGOR' in SLA compliance response")
		}
	})

	t.Run("GetEventCorrelation returns fallback event trace & graph topology", func(t *testing.T) {
		w := httptest.NewRecorder()
		req, _ := http.NewRequest("GET", "/api/governance/event_correlation?incident_id=INC-1001", nil)
		r.ServeHTTP(w, req)

		if w.Code != http.StatusOK {
			t.Fatalf("Expected HTTP 200, got %d", w.Code)
		}
	})

	t.Run("GetLearningGatePolicy returns learning policies and risk tier thresholds", func(t *testing.T) {
		w := httptest.NewRecorder()
		req, _ := http.NewRequest("GET", "/api/governance/learning_gate/policy", nil)
		r.ServeHTTP(w, req)

		if w.Code != http.StatusOK {
			t.Fatalf("Expected HTTP 200, got %d", w.Code)
		}
		var resp map[string]interface{}
		if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
			t.Fatalf("Failed to parse response JSON: %v", err)
		}
		if resp["status"] != "success" {
			t.Errorf("Expected status 'success', got %v", resp["status"])
		}
	})

	t.Run("UpdateLearningGatePolicy processes weight update cleanly", func(t *testing.T) {
		payload, _ := json.Marshal(map[string]interface{}{
			"policy_id":      1,
			"weights":        `{"vector_similarity": 0.6, "bm25_text": 0.2, "recency": 0.2}`,
			"canary_percent": 20,
			"post_check":     96.5,
		})
		w := httptest.NewRecorder()
		req, _ := http.NewRequest("POST", "/api/governance/learning_gate/update", bytes.NewBuffer(payload))
		req.Header.Set("Content-Type", "application/json")
		r.ServeHTTP(w, req)

		if w.Code != http.StatusOK {
			t.Fatalf("Expected HTTP 200, got %d", w.Code)
		}
		var resp map[string]interface{}
		_ = json.Unmarshal(w.Body.Bytes(), &resp)
		if resp["status"] != "success" {
			t.Errorf("Expected status 'success', got %v", resp["status"])
		}
	})

	t.Run("RollbackLearningGatePolicy processes rollback request cleanly", func(t *testing.T) {
		payload, _ := json.Marshal(map[string]interface{}{
			"policy_id":      1,
			"target_version": "v1.0.0",
		})
		w := httptest.NewRecorder()
		req, _ := http.NewRequest("POST", "/api/governance/learning_gate/rollback", bytes.NewBuffer(payload))
		req.Header.Set("Content-Type", "application/json")
		r.ServeHTTP(w, req)

		if w.Code != http.StatusOK {
			t.Fatalf("Expected HTTP 200, got %d", w.Code)
		}
		var resp map[string]interface{}
		_ = json.Unmarshal(w.Body.Bytes(), &resp)
		if resp["status"] != "success" {
			t.Errorf("Expected status 'success', got %v", resp["status"])
		}
	})

	t.Run("GetLearningGateHistory returns audit trail history", func(t *testing.T) {
		w := httptest.NewRecorder()
		req, _ := http.NewRequest("GET", "/api/governance/learning_gate/history", nil)
		r.ServeHTTP(w, req)

		if w.Code != http.StatusOK {
			t.Fatalf("Expected HTTP 200, got %d", w.Code)
		}
	})
}
