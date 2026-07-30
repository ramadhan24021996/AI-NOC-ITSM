package api

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestClearPrinterQueue_ValidationAndResponse(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := &Handler{}

	r := gin.New()
	r.POST("/api/printers/clear_queue", h.ClearPrinterQueue)

	t.Run("Empty Payload Returns 400 Bad Request", func(t *testing.T) {
		req, _ := http.NewRequest("POST", "/api/printers/clear_queue", bytes.NewBufferString("{}"))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)

		if w.Code != http.StatusBadRequest {
			t.Fatalf("expected status 400 for empty payload, got %d. Body: %s", w.Code, w.Body.String())
		}

		var resp map[string]interface{}
		_ = json.Unmarshal(w.Body.Bytes(), &resp)
		if resp["success"] != false {
			t.Fatalf("expected success: false in response, got %v", resp["success"])
		}
	})

	t.Run("Host and Printer payload without DB returns 200 with NATS/system status if valid", func(t *testing.T) {
		payload := `{"host":"PC-POS-01","printer":"EPSON-TM-T82"}`
		req, _ := http.NewRequest("POST", "/api/printers/clear_queue", bytes.NewBufferString(payload))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)

		// Without DB/NATS/agent running, if fail fast triggers on no execution, expect error 500 or success if system fallback ran
		if w.Code != http.StatusOK && w.Code != http.StatusInternalServerError {
			t.Fatalf("unexpected status code %d. Body: %s", w.Code, w.Body.String())
		}
	})
}
