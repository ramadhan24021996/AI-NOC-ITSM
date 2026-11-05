package api

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"sort"
	"sync"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
	"go_incident_analysis/portal/dashboard/incident"
)

// TestProductionHTTPLoad_RealNetworkStack Benchmarks real TCP socket HTTP requests over full Gin stack.
func TestProductionHTTPLoad_RealNetworkStack(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := NewHandler(nil, nil, nil, ".", "")
	incH := incident.NewHandler(nil, nil, nil, ".")

	r := gin.New()
	r.Use(gin.Recovery())
	h.RegisterRoutes(r)
	incH.RegisterRoutes(r)

	// Launch actual local TCP HTTP server
	ts := httptest.NewServer(r)
	defer ts.Close()

	client := &http.Client{
		Timeout: 5 * time.Second,
		Transport: &http.Transport{
			MaxIdleConns:        500,
			MaxIdleConnsPerHost: 500,
			IdleConnTimeout:     30 * time.Second,
		},
	}

	endpoints := []string{
		"/api/top_status",
		"/api/system/health",
		"/api/activity-log",
		"/api/kb_stats",
		"/api/ai_config",
		"/api/governance/sops",
		"/api/system/runtime_monitor",
		"/api/storage/stats",
		"/api/fleet/config/global",
		"/api/governance/sla_compliance",
	}

	concurrencies := []int{10, 50, 100, 250, 500}

	t.Log("=========================================================================================")
	t.Log("REAL TCP HTTP LOAD BENCHMARK (Full Network Socket -> Gin Engine -> Middleware -> Handler)")
	t.Log("=========================================================================================")

	for _, conc := range concurrencies {
		t.Run(fmt.Sprintf("Concurrency_%d", conc), func(t *testing.T) {
			var wg sync.WaitGroup
			latencies := make([]time.Duration, conc)
			errors := 0
			var mu sync.Mutex

			start := time.Now()
			for i := 0; i < conc; i++ {
				wg.Add(1)
				url := ts.URL + endpoints[i%len(endpoints)]
				go func(idx int, reqURL string) {
					defer wg.Done()
					t0 := time.Now()
					resp, err := client.Get(reqURL)
					dur := time.Since(t0)

					mu.Lock()
					defer mu.Unlock()
					latencies[idx] = dur
					if err != nil || resp.StatusCode != http.StatusOK {
						errors++
					}
					if resp != nil && resp.Body != nil {
						resp.Body.Close()
					}
				}(i, url)
			}
			wg.Wait()
			totalElapsed := time.Since(start)

			sort.Slice(latencies, func(i, j int) bool {
				return latencies[i] < latencies[j]
			})

			p50 := latencies[conc*50/100]
			p95 := latencies[conc*95/100]
			p99 := latencies[conc*99/100]
			min := latencies[0]
			max := latencies[conc-1]
			rps := float64(conc) / totalElapsed.Seconds()

			t.Logf("Conc: %3d | RPS: %8.2f | Errors: %d | Elapsed: %10v | P50: %8v | P95: %8v | P99: %8v | Min: %8v | Max: %8v",
				conc, rps, errors, totalElapsed, p50, p95, p99, min, max)

			if errors > 0 {
				t.Fatalf("Load test failed at concurrency %d with %d errors", conc, errors)
			}
		})
	}
}
