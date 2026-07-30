package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/nats-io/nats.go"
)

// TelemetryEvent represents a production telemetry payload sent over NATS JetStream
type TelemetryEvent struct {
	AgentID       string                 `json:"agent"`
	SiteID        string                 `json:"site_id"`
	EventType     string                 `json:"event_type"`
	Status        string                 `json:"status"`
	Layer         int                    `json:"layer"`
	TraceID       string                 `json:"trace_id,omitempty"`
	SpanID        string                 `json:"span_id,omitempty"`
	CorrelationID string                 `json:"correlation_id,omitempty"`
	KeyVersion    int                    `json:"key_version,omitempty"`
	Data          map[string]interface{} `json:"data"`
	Timestamp     string                 `json:"timestamp"`
}

// AgentTelemetryPublisher handles NATS JetStream event publishing with local disk queue fallback
type AgentTelemetryPublisher struct {
	mu           sync.Mutex
	nc           *nats.Conn
	js           nats.JetStreamContext
	siteID       string
	agentID      string
	natsURL      string
	queuePath    string
	offlineQueue []TelemetryEvent
	isConnected  bool
}

// NewAgentTelemetryPublisher creates a production-ready telemetry publisher
func NewAgentTelemetryPublisher(natsURL, siteID, agentID string) *AgentTelemetryPublisher {
	execDir, _ := os.Executable()
	baseDir := filepath.Dir(execDir)
	queueDir := filepath.Join(baseDir, "cache")
	_ = os.MkdirAll(queueDir, 0755)

	pub := &AgentTelemetryPublisher{
		natsURL:      natsURL,
		siteID:       siteID,
		agentID:      agentID,
		queuePath:    filepath.Join(queueDir, "offline_telemetry.json"),
		offlineQueue: make([]TelemetryEvent, 0),
	}

	pub.loadOfflineQueue()
	pub.connectNATS()

	return pub
}

func (p *AgentTelemetryPublisher) connectNATS() {
	opts := nats.Options{
		Servers:        []string{p.natsURL, "nats://127.0.0.1:4222", "nats://127.0.0.1:4223", "nats://127.0.0.1:4224"},
		NoRandomize:    false,
		AllowReconnect: true,
		MaxReconnect:   -1,
		ReconnectWait:  2 * time.Second,
		Timeout:        3 * time.Second,
		DisconnectedErrCB: func(nc *nats.Conn, err error) {
			p.mu.Lock()
			p.isConnected = false
			p.mu.Unlock()
			log.Println("[AGENT-TELEMETRY] NATS Disconnected. Switching to Local Disk Queue.")
		},
		ReconnectedCB: func(nc *nats.Conn) {
			p.mu.Lock()
			p.isConnected = true
			p.mu.Unlock()
			log.Println("[AGENT-TELEMETRY] NATS Reconnected. Replaying offline queue...")
			go p.replayOfflineQueue()
		},
	}

	nc, err := opts.Connect()
	if err != nil {
		log.Printf("[AGENT-TELEMETRY] Initial NATS connection warning: %v. Relying on local queue.", err)
		p.isConnected = false
		return
	}

	js, err := nc.JetStream()
	if err != nil {
		log.Printf("[AGENT-TELEMETRY] JetStream context warning: %v", err)
	}

	p.nc = nc
	p.js = js
	p.isConnected = true
	log.Println("[AGENT-TELEMETRY] NATS JetStream Telemetry Publisher connected successfully.")
}

// PublishEvent pushes instant telemetry event (< 5ms) or buffers to disk if offline
func (p *AgentTelemetryPublisher) PublishEvent(eventType, status string, layer int, data map[string]interface{}) error {
	event := TelemetryEvent{
		AgentID:   p.agentID,
		SiteID:    p.siteID,
		EventType: eventType,
		Status:    status,
		Layer:     layer,
		Data:      data,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	}

	p.mu.Lock()
	defer p.mu.Unlock()

	if p.isConnected && p.nc != nil && p.nc.IsConnected() {
		subject := fmt.Sprintf("telemetry.site.%s.%s", p.normalizeToken(p.siteID), p.normalizeSeverity(status))
		payloadBytes, err := json.Marshal(event)
		if err == nil {
			errPub := p.nc.Publish(subject, payloadBytes)
			if errPub == nil {
				return nil
			}
		}
	}

	// Offline or publish error -> buffer to local queue ring buffer (max 500 events & 48h retention)
	if len(p.offlineQueue) >= 500 {
		p.offlineQueue = p.offlineQueue[1:] // Drop oldest event
	}
	p.offlineQueue = append(p.offlineQueue, event)
	p.pruneExpiredEventsLocked()
	p.saveOfflineQueueLocked()
	log.Printf("[AGENT-TELEMETRY] Event buffered to local disk (Queue Size: %d)", len(p.offlineQueue))

	return nil
}

func (p *AgentTelemetryPublisher) pruneExpiredEventsLocked() {
	// Gap 3 / L7: Auto-Prune events older than 48 hours & Watermark Alert if disk file > 500MB
	cutoff := time.Now().UTC().Add(-48 * time.Hour)
	valid := make([]TelemetryEvent, 0)
	for _, ev := range p.offlineQueue {
		if t, err := time.Parse(time.RFC3339, ev.Timestamp); err == nil {
			if t.After(cutoff) {
				valid = append(valid, ev)
			}
		} else {
			valid = append(valid, ev)
		}
	}
	p.offlineQueue = valid

	if info, err := os.Stat(p.queuePath); err == nil {
		if info.Size() > 500*1024*1024 { // 500MB Watermark Limit
			log.Printf("[AGENT-TELEMETRY] WARNING: Offline buffer size (%d bytes) exceeds 500MB watermark! Truncating queue.", info.Size())
			p.offlineQueue = p.offlineQueue[len(p.offlineQueue)/2:]
		}
	}
}

func (p *AgentTelemetryPublisher) replayOfflineQueue() {
	p.mu.Lock()
	defer p.mu.Unlock()

	if len(p.offlineQueue) == 0 || p.nc == nil || !p.nc.IsConnected() {
		return
	}

	replayed := 0
	remaining := make([]TelemetryEvent, 0)

	for _, event := range p.offlineQueue {
		subject := fmt.Sprintf("telemetry.site.%s.%s", p.normalizeToken(p.siteID), p.normalizeSeverity(event.Status))
		bytes, err := json.Marshal(event)
		if err == nil && p.nc.Publish(subject, bytes) == nil {
			replayed++
		} else {
			remaining = append(remaining, event)
		}
	}

	p.offlineQueue = remaining
	p.saveOfflineQueueLocked()
	log.Printf("[AGENT-TELEMETRY] Offline queue replay completed. Replayed: %d, Remaining: %d", replayed, len(p.offlineQueue))
}

func (p *AgentTelemetryPublisher) loadOfflineQueue() {
	data, err := os.ReadFile(p.queuePath)
	if err != nil {
		return
	}
	var queue []TelemetryEvent
	if json.Unmarshal(data, &queue) == nil {
		p.offlineQueue = queue
		p.pruneExpiredEventsLocked()
	}
}

func (p *AgentTelemetryPublisher) saveOfflineQueueLocked() {
	bytes, err := json.Marshal(p.offlineQueue)
	if err == nil {
		_ = os.WriteFile(p.queuePath, bytes, 0644)
	}
}

func (p *AgentTelemetryPublisher) normalizeToken(s string) string {
	if s == "" {
		return "default-site"
	}
	return filepath.Base(s)
}

func (p *AgentTelemetryPublisher) normalizeSeverity(status string) string {
	switch status {
	case "CRITICAL", "ERROR", "FATAL":
		return "critical"
	case "WARNING", "WARN":
		return "warning"
	default:
		return "normal"
	}
}

// Close gracefully closes the NATS connection
func (p *AgentTelemetryPublisher) Close() {
	p.mu.Lock()
	defer p.mu.Unlock()

	if p.nc != nil {
		p.nc.Close()
	}
}
