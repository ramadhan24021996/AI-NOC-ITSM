package incident

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestPlaybookHandlersValidationAndNilDB(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := &Handler{}
	r := gin.New()
	r.GET("/api/playbooks", h.GetPlaybooks)
	r.GET("/api/playbooks/catalog", h.GetPlaybookCatalog)
	r.GET("/api/playbooks/export", h.ExportPlaybooks)
	r.POST("/api/playbooks", h.SavePlaybook)
	r.POST("/api/playbooks/promote/:id", h.PromoteCatalogPlaybook)
	r.POST("/api/playbooks/:id/execute", h.ExecutePlaybook)
	r.DELETE("/api/playbooks/:id", h.DeletePlaybook)

	// 1. GET /api/playbooks -> []
	w1 := httptest.NewRecorder()
	r.ServeHTTP(w1, httptest.NewRequest(http.MethodGet, "/api/playbooks", nil))
	if w1.Code != http.StatusOK || w1.Body.String() != "[]" {
		t.Fatalf("expected 200 [], got %d: %s", w1.Code, w1.Body.String())
	}

	// 2. GET /api/playbooks/catalog -> valid object with X-Total-Count: 0
	wCat := httptest.NewRecorder()
	r.ServeHTTP(wCat, httptest.NewRequest(http.MethodGet, "/api/playbooks/catalog", nil))
	if wCat.Code != http.StatusOK || wCat.Header().Get("X-Total-Count") != "0" {
		t.Fatalf("expected 200 & X-Total-Count=0, got %d / %s", wCat.Code, wCat.Header().Get("X-Total-Count"))
	}

	// 3. Export JSON -> [] + SHA256 header
	wExp := httptest.NewRecorder()
	r.ServeHTTP(wExp, httptest.NewRequest(http.MethodGet, "/api/playbooks/export?format=json", nil))
	if wExp.Code != http.StatusOK || wExp.Body.String() != "[]" || wExp.Header().Get("X-Audit-Checksum-SHA256") == "" {
		t.Fatalf("unexpected export response: %d %s", wExp.Code, wExp.Body.String())
	}

	// 4. SavePlaybook validation & Zero-Trust blocking
	wEmpty := httptest.NewRecorder()
	reqEmpty := httptest.NewRequest(http.MethodPost, "/api/playbooks", bytes.NewBufferString(`{"name":"","script":"echo ok","target_layer":1}`))
	reqEmpty.Header.Set("Content-Type", "application/json")
	r.ServeHTTP(wEmpty, reqEmpty)
	if wEmpty.Code != http.StatusBadRequest {
		t.Fatalf("expected 400 for empty name, got %d", wEmpty.Code)
	}

	wBadLayer := httptest.NewRecorder()
	reqBadLayer := httptest.NewRequest(http.MethodPost, "/api/playbooks", bytes.NewBufferString(`{"name":"Test","script":"echo ok","target_layer":9}`))
	reqBadLayer.Header.Set("Content-Type", "application/json")
	r.ServeHTTP(wBadLayer, reqBadLayer)
	if wBadLayer.Code != http.StatusBadRequest {
		t.Fatalf("expected 400 for layer 9, got %d", wBadLayer.Code)
	}

	wDanger := httptest.NewRecorder()
	reqDanger := httptest.NewRequest(http.MethodPost, "/api/playbooks", bytes.NewBufferString(`{"name":"Danger","script":"rm -rf /tmp/*","target_layer":1}`))
	reqDanger.Header.Set("Content-Type", "application/json")
	r.ServeHTTP(wDanger, reqDanger)
	if wDanger.Code != http.StatusForbidden {
		t.Fatalf("expected 403 for destructive script, got %d: %s", wDanger.Code, wDanger.Body.String())
	}

	// 5. Nil DB returns 503 on Save, Delete, Execute, Promote
	wSaveNil := httptest.NewRecorder()
	reqSaveNil := httptest.NewRequest(http.MethodPost, "/api/playbooks", bytes.NewBufferString(`{"name":"Safe","script":"echo ok","target_layer":3}`))
	reqSaveNil.Header.Set("Content-Type", "application/json")
	r.ServeHTTP(wSaveNil, reqSaveNil)
	if wSaveNil.Code != http.StatusServiceUnavailable {
		t.Fatalf("expected 503 for nil DB SavePlaybook, got %d", wSaveNil.Code)
	}

	for _, tc := range []struct {
		method string
		url    string
		want   int
	}{
		{http.MethodPost, "/api/playbooks/abc/execute", http.StatusBadRequest},
		{http.MethodPost, "/api/playbooks/3/execute", http.StatusServiceUnavailable},
		{http.MethodDelete, "/api/playbooks/abc", http.StatusBadRequest},
		{http.MethodDelete, "/api/playbooks/3", http.StatusServiceUnavailable},
		{http.MethodPost, "/api/playbooks/promote/abc", http.StatusBadRequest},
		{http.MethodPost, "/api/playbooks/promote/3", http.StatusServiceUnavailable},
	} {
		w := httptest.NewRecorder()
		r.ServeHTTP(w, httptest.NewRequest(tc.method, tc.url, nil))
		if w.Code != tc.want {
			var body map[string]interface{}
			_ = json.Unmarshal(w.Body.Bytes(), &body)
			t.Errorf("%s %s expected %d, got %d (%v)", tc.method, tc.url, tc.want, w.Code, body)
		}
	}
}
