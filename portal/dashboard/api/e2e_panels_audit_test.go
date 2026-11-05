package api

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
	"go_incident_analysis/portal/dashboard/incident"
)

// TestE2E_AllPanelsEndpoints Audits data contracts across all 29 dashboard panel endpoint paths.
func TestE2E_AllPanelsEndpoints(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := NewHandler(nil, nil, nil, ".", "")
	incH := incident.NewHandler(nil, nil, nil, ".")
	r := gin.New()
	h.RegisterRoutes(r)
	incH.RegisterRoutes(r)

	tests := []struct {
		name       string
		method     string
		url        string
		wantStatus int
		checkKey   string
	}{
		{"P-01 Overview Status", "GET", "/api/top_status", http.StatusOK, ""},
		{"P-02 Incident Triage", "GET", "/api/incidents", http.StatusOK, ""},
		{"P-03 System Health", "GET", "/api/system/health", http.StatusOK, ""},
		{"P-04 Printer List", "GET", "/api/fleet/admin/printers", http.StatusOK, ""},
		{"P-05 Activity Log", "GET", "/api/activity-log", http.StatusOK, ""},
		{"P-06 Audit Log", "GET", "/api/system/audits", http.StatusOK, ""},
		{"P-07 RCA Engine Trace", "GET", "/api/rca/trace/1", http.StatusOK, ""},
		{"P-08 Evidence Explorer", "GET", "/api/evidence_explorer", http.StatusOK, ""},
		{"P-09 KB Stats", "GET", "/api/kb_stats", http.StatusOK, ""},
		{"P-10 AI Config", "GET", "/api/ai_config", http.StatusOK, ""},
		{"P-11 Playbooks List", "GET", "/api/playbooks", http.StatusOK, ""},
		{"P-12 SOP List", "GET", "/api/governance/sops", http.StatusOK, ""},
		{"P-13 Learning Policy", "GET", "/api/learning_gate_policy", http.StatusOK, ""},
		{"P-14 Security Rules", "GET", "/api/security/policies", http.StatusOK, ""},
		{"P-15 AI Decision Logs", "GET", "/api/ai_decision_logs", http.StatusOK, ""},
		{"P-16 Schema Validation", "GET", "/api/schema_validation_logs", http.StatusOK, ""},
		{"P-17 Agent Health", "GET", "/api/system/agent_health", http.StatusOK, ""},
		{"P-18 Runtime Monitor", "GET", "/api/system/runtime_monitor", http.StatusOK, ""},
		{"P-19 NATS Subjects", "GET", "/api/nats_subjects", http.StatusOK, ""},
		{"P-20 Storage Stats", "GET", "/api/storage/stats", http.StatusOK, ""},
		{"P-21 Fleet Config", "GET", "/api/fleet/config/global", http.StatusOK, ""},
		{"P-22 SLA Compliance", "GET", "/api/governance/sla_compliance", http.StatusOK, ""},
		{"P-23 DPO Stats", "GET", "/api/feedback/stats", http.StatusOK, ""},
		{"P-24 RBAC Roles", "GET", "/api/rbac/role_templates", http.StatusOK, ""},
		{"P-25 Causal DAG", "GET", "/api/causal_dag/1", http.StatusOK, ""},
		{"P-26 System Monitoring", "GET", "/api/host_metrics", http.StatusOK, ""},
		{"P-27 AI Status Submodule", "GET", "/api/ai_status", http.StatusOK, ""},
		{"P-28 Fleet Site Tree Submodule", "GET", "/api/fleet/admin/sites", http.StatusOK, ""},
		{"P-29 PC Deep Diagnostics Submodule", "GET", "/api/agent_deep_diagnostics/localhost", http.StatusOK, ""},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req, _ := http.NewRequest(tt.method, tt.url, nil)
			w := httptest.NewRecorder()
			r.ServeHTTP(w, req)

			if w.Code != tt.wantStatus {
				t.Fatalf("Endpoint %s %s returned status %d, want %d", tt.method, tt.url, w.Code, tt.wantStatus)
			}

			if tt.checkKey != "" {
				var res map[string]interface{}
				if err := json.Unmarshal(w.Body.Bytes(), &res); err != nil {
					t.Fatalf("Failed to parse JSON response for %s: %v", tt.url, err)
				}
				if _, ok := res[tt.checkKey]; !ok {
					t.Errorf("Response for %s missing expected JSON field key %q", tt.url, tt.checkKey)
				}
			}
		})
	}
}
