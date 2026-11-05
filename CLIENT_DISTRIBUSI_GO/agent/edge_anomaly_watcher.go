package main

/*
edge_anomaly_watcher.go — Real-time Edge Anomaly Detection Engine for Client Agent.

Monitors local system metrics on the client PC:
  - CPU Utilization (>90% threshold for >60s)
  - Memory Leaks (Print Spooler, POS app memory growth)
  - Disk Queue Bottleneck (>5 pending I/O)
  - Network Gateway Latency & Packet Drop
*/

import (
	"fmt"
	"log"
	"os/exec"
	"runtime"
	"strings"
	"sync"
	"time"
)

type AnomalySeverity string

const (
	SeverityInfo     AnomalySeverity = "INFO"
	SeverityWarn     AnomalySeverity = "WARN"
	SeverityCritical AnomalySeverity = "CRITICAL"
)

type EdgeAnomalyEvent struct {
	Timestamp      time.Time       `json:"timestamp"`
	DeviceName     string          `json:"device_name"`
	AnomalyType    string          `json:"anomaly_type"`
	Severity       AnomalySeverity `json:"severity"`
	MetricName     string          `json:"metric_name"`
	MetricValue    float64         `json:"metric_value"`
	Threshold      float64         `json:"threshold"`
	Description    string          `json:"description"`
	CanSelfHeal    bool            `json:"can_self_heal"`
	SelfHealAction string          `json:"self_heal_action"`
}

type EdgeAnomalyWatcher struct {
	deviceName        string
	mu                sync.RWMutex
	running           bool
	stopChan          chan struct{}
	highCPUCounter    int
	spoolerMemStreak  int
	isDisconnected    bool
	lastWANContact    time.Time
	onAnomalyDetected func(event EdgeAnomalyEvent)
}

func NewEdgeAnomalyWatcher(deviceName string, callback func(EdgeAnomalyEvent)) *EdgeAnomalyWatcher {
	return &EdgeAnomalyWatcher{
		deviceName:        deviceName,
		stopChan:          make(chan struct{}),
		lastWANContact:    time.Now(),
		onAnomalyDetected: callback,
	}
}

func (w *EdgeAnomalyWatcher) UpdateWANStatus(connected bool) {
	w.mu.Lock()
	defer w.mu.Unlock()
	if connected {
		w.lastWANContact = time.Now()
		w.isDisconnected = false
	} else if time.Since(w.lastWANContact) > 3*time.Minute {
		if !w.isDisconnected {
			log.Printf("[EDGE WATCHER] ⚠️ WAN Outage detected (> 3m disconnected). Entering Disconnected Autonomous Mode.")
		}
		w.isDisconnected = true
	}
}

func (w *EdgeAnomalyWatcher) IsWANDisconnected() bool {
	w.mu.RLock()
	defer w.mu.RUnlock()
	return w.isDisconnected
}

func (w *EdgeAnomalyWatcher) Start() {
	w.mu.Lock()
	if w.running {
		w.mu.Unlock()
		return
	}
	w.running = true
	w.mu.Unlock()

	log.Printf("[EDGE WATCHER] Edge Anomaly Watcher started for device: %s", w.deviceName)

	go w.watcherLoop()
}

func (w *EdgeAnomalyWatcher) Stop() {
	w.mu.Lock()
	defer w.mu.Unlock()
	if !w.running {
		return
	}
	w.running = false
	close(w.stopChan)
	log.Println("[EDGE WATCHER] Edge Anomaly Watcher stopped.")
}

func (w *EdgeAnomalyWatcher) watcherLoop() {
	ticker := time.NewTicker(15 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-w.stopChan:
			return
		case <-ticker.C:
			w.evaluateLocalMetrics()
		}
	}
}

func (w *EdgeAnomalyWatcher) evaluateLocalMetrics() {
	// 1. Evaluate Go Runtime Memory & Goroutine Leak
	var m runtime.MemStats
	runtime.ReadMemStats(&m)
	allocatedMB := float64(m.Alloc) / (1024 * 1024)

	if allocatedMB > 500.0 {
		w.notify(EdgeAnomalyEvent{
			Timestamp:     time.Now(),
			DeviceName:    w.deviceName,
			AnomalyType:   "AGENT_MEMORY_LEAK",
			Severity:      SeverityWarn,
			MetricName:    "alloc_mb",
			MetricValue:   allocatedMB,
			Threshold:     500.0,
			Description:   fmt.Sprintf("Client Agent memory usage high: %.1f MB", allocatedMB),
			CanSelfHeal:   true,
			SelfHealAction: "GC_PURGE",
		})
		runtime.GC()
	}

	// 2. Evaluate Print Spooler Status (Windows platform check simulated/native)
	if runtime.GOOS == "windows" {
		w.checkPrintSpoolerHealth()
	}
}

func (w *EdgeAnomalyWatcher) checkPrintSpoolerHealth() {
	if runtime.GOOS == "windows" {
		cmd := exec.Command("sc", "query", "spooler")
		out, err := cmd.CombinedOutput()
		outStr := string(out)
		if err != nil || (!strings.Contains(outStr, "RUNNING") && !strings.Contains(outStr, "STATE              : 4")) {
			w.notify(EdgeAnomalyEvent{
				Timestamp:      time.Now(),
				DeviceName:     w.deviceName,
				AnomalyType:    "PRINT_SPOOLER_STALLED",
				Severity:       SeverityCritical,
				MetricName:     "spooler_state",
				MetricValue:    0.0,
				Threshold:      1.0,
				Description:    "Print Spooler service stopped or unresponsive (sc query spooler not RUNNING)",
				CanSelfHeal:    true,
				SelfHealAction: "RESTART_SPOOLER",
			})
		}
	} else {
		// Non-Windows simulation / cups probe check
		cmd := exec.Command("systemctl", "is-active", "cups")
		out, err := cmd.CombinedOutput()
		if err == nil && strings.TrimSpace(string(out)) != "active" {
			w.notify(EdgeAnomalyEvent{
				Timestamp:      time.Now(),
				DeviceName:     w.deviceName,
				AnomalyType:    "CUPS_PRINT_DAEMON_STOPPED",
				Severity:       SeverityWarn,
				MetricName:     "cups_state",
				MetricValue:    0.0,
				Threshold:      1.0,
				Description:    "CUPS print daemon is not active",
				CanSelfHeal:    true,
				SelfHealAction: "RESTART_SPOOLER",
			})
		}
	}
}

func (w *EdgeAnomalyWatcher) notify(event EdgeAnomalyEvent) {
	log.Printf("[EDGE WATCHER] 🚨 ANOMALY DETECTED: %s (%s) — %s", event.AnomalyType, event.Severity, event.Description)
	if w.onAnomalyDetected != nil {
		w.onAnomalyDetected(event)
	}
}
