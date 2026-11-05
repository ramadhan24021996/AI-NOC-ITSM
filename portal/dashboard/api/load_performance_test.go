package api

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
)

// TestDashboardLoad_ConcurrentRequests benchmarks key endpoints under simulated concurrent load.
func TestDashboardLoad_ConcurrentRequests(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := NewHandler(nil, nil, nil, ".", "")
	r := gin.New()
	h.RegisterRoutes(r)

	endpoints := []string{
		"/health",
		"/api/system/health",
		"/api/system/runtime_monitor",
		"/api/system/agent_health",
		"/api/storage/stats",
		"/api/kb_stats",
		"/api/governance/sla_compliance",
	}

	concurrencyLevels := []int{10, 50, 100}

	for _, concurrency := range concurrencyLevels {
		t.Run(fmt.Sprintf("Concurrency_%d", concurrency), func(t *testing.T) {
			var wg sync.WaitGroup
			var successCount int64
			var errorCount int64

			startTime := time.Now()

			for i := 0; i < concurrency; i++ {
				wg.Add(1)
				go func(workerID int) {
					defer wg.Done()
					ep := endpoints[workerID%len(endpoints)]
					req, _ := http.NewRequest("GET", ep, nil)
					w := httptest.NewRecorder()

					r.ServeHTTP(w, req)

					if w.Code == http.StatusOK {
						atomic.AddInt64(&successCount, 1)
					} else {
						atomic.AddInt64(&errorCount, 1)
					}
				}(i)
			}

			wg.Wait()
			elapsed := time.Since(startTime)

			t.Logf("Concurrency: %d | Success: %d | Errors: %d | Elapsed: %v | Avg Latency: %v",
				concurrency, successCount, errorCount, elapsed, elapsed/time.Duration(concurrency))

			if errorCount > 0 {
				t.Errorf("Load test failed with %d errors under concurrency %d", errorCount, concurrency)
			}
		})
	}
}
