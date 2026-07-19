package hardening

import (
	"database/sql"
	"fmt"
	"net/http"
	_ "net/http/pprof"
	"os"
	"runtime"
	"sync"
	"time"

	"github.com/go-redis/redis/v8"
)

// GoSafe runs a function in a new goroutine with panic recovery and crash dump logging
func GoSafe(fn func(), logWarn func(category, msg string)) {
	go func() {
		defer func() {
			if r := recover(); r != nil {
				stack := make([]byte, 8192)
				stack = stack[:runtime.Stack(stack, false)]
				errStr := fmt.Sprintf("=== CRASH DUMP ===\nTimestamp: %s\nPanic: %v\nStack Trace:\n%s\n",
					time.Now().Format(time.RFC3339), r, stack)

				// Log warning
				if logWarn != nil {
					logWarn("CRITICAL", fmt.Sprintf("Recovered from panic: %v (Crash dump written)", r))
				} else {
					fmt.Fprintf(os.Stderr, "[PANIC] %s", errStr)
				}

				// Write crash dump to file
				dumpFile := fmt.Sprintf("crash_dump_%d.log", time.Now().UnixNano())
				_ = os.WriteFile(dumpFile, []byte(errStr), 0644)
			}
		}()
		fn()
	}()
}

// MonitorResources runs a periodic check on Goroutines, Memory, FDs/Handles, DB pool, and Redis pool connections
func MonitorResources(
	db *sql.DB,
	rdb *redis.Client,
	getWSCnt func() int,
	logWarn func(category, msg string),
	interval time.Duration,
) {
	GoSafe(func() {
		ticker := time.NewTicker(interval)
		var lastGoroutines int
		var lastAlloc uint64

		for range ticker.C {
			// 1. Goroutine Monitoring
			goroutines := runtime.NumGoroutine()
			if goroutines > 5000 {
				logWarn("HARDENING", fmt.Sprintf("CRITICAL: High goroutine count detected: %d", goroutines))
			} else if lastGoroutines > 0 && goroutines > lastGoroutines+200 {
				logWarn("HARDENING", fmt.Sprintf("WARNING: Possible goroutine leak. Count spiked from %d to %d", lastGoroutines, goroutines))
			}
			lastGoroutines = goroutines

			// 2. Memory Leak Monitoring
			var m runtime.MemStats
			runtime.ReadMemStats(&m)
			if m.Alloc > 500*1024*1024 {
				logWarn("HARDENING", fmt.Sprintf("WARNING: High memory allocation: %d MB", m.Alloc/1024/1024))
			} else if lastAlloc > 0 && m.Alloc > lastAlloc+50*1024*1024 {
				logWarn("HARDENING", fmt.Sprintf("WARNING: Memory spike detected. Increased from %d MB to %d MB", lastAlloc/1024/1024, m.Alloc/1024/1024))
			}
			lastAlloc = m.Alloc

			// 3. File Descriptor / Handle Monitoring
			fdCount, err := GetFDCount()
			if err == nil {
				fdType := GetFDType()
				if fdCount > 1500 {
					logWarn("HARDENING", fmt.Sprintf("WARNING: High %s count: %d", fdType, fdCount))
				}
			}

			// 4. Database Connection Pool Monitoring
			if db != nil {
				dbStats := db.Stats()
				if dbStats.InUse > 40 && dbStats.InUse >= dbStats.MaxOpenConnections-5 {
					logWarn("HARDENING", fmt.Sprintf("WARNING: Database connection pool exhaustion. InUse: %d/%d, WaitDuration: %v",
						dbStats.InUse, dbStats.MaxOpenConnections, dbStats.WaitDuration))
				}
			}

			// 5. Redis Connection Pool Monitoring
			if rdb != nil {
				rdbStats := rdb.PoolStats()
				if rdbStats.TotalConns > 80 && rdbStats.IdleConns < 5 {
					logWarn("HARDENING", fmt.Sprintf("WARNING: Redis connection pool warning. Total: %d, Idle: %d, Hits: %d, Timeouts: %d",
						rdbStats.TotalConns, rdbStats.IdleConns, rdbStats.Hits, rdbStats.Timeouts))
				}
			}

			// 6. WebSocket Leak Detection
			if getWSCnt != nil {
				wsCnt := getWSCnt()
				if wsCnt > 100 {
					logWarn("HARDENING", fmt.Sprintf("WARNING: Unusually high number of active WebSockets: %d", wsCnt))
				}
			}
		}
	}, logWarn)
}

// StartPprofServer starts local profiling server on localhost:6060
var pprofOnce sync.Once

func StartPprofServer() {
	pprofOnce.Do(func() {
		go func() {
			// Bind only to localhost for security
			_ = http.ListenAndServe("127.0.0.1:6060", nil)
		}()
	})
}
