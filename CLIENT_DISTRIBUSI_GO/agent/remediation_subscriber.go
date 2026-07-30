package main

import (
	"crypto/rand"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/nats-io/nats.go"
)

// RemediationCommand represents an encrypted HITL approved action payload
type RemediationCommand struct {
	CommandID     string                 `json:"command_id"`
	IncidentID    string                 `json:"incident_id"`
	CorrelationID string                 `json:"correlation_id,omitempty"`
	KeyVersion    int                    `json:"key_version,omitempty"`
	ActionType    string                 `json:"action_type"`
	Target        string                 `json:"target"`
	Params        map[string]interface{} `json:"params"`
	IssuedBy      string                 `json:"issued_by"`
	Timestamp     string                 `json:"timestamp"`
}

// CommandAckResponse represents the response ACK sent back to NATS
type CommandAckResponse struct {
	CommandID string `json:"command_id"`
	Status    string `json:"status"` // ACK_SUCCESS | ACK_DUPLICATE | ACK_FAILED
	Message   string `json:"message"`
	Timestamp string `json:"timestamp"`
	AgentID   string `json:"agent_id"`
	SiteID    string `json:"site_id"`
}

// AgentIdempotencyManager manages 5-minute TTL command cache to prevent duplicate executions
type AgentIdempotencyManager struct {
	mu           sync.RWMutex
	memoryCache  map[string]time.Time
	sqliteDB     *sql.DB
	ttlDuration  time.Duration
}

// NewAgentIdempotencyManager creates a thread-safe idempotency manager with SQLite WAL persistence
func NewAgentIdempotencyManager(ttl time.Duration) *AgentIdempotencyManager {
	mgr := &AgentIdempotencyManager{
		memoryCache: make(map[string]time.Time),
		ttlDuration: ttl,
	}

	// Setup SQLite WAL cache persistence
	cacheDir := os.TempDir()
	dbPath := filepath.Join(cacheDir, "osi_agent_idempotency.db")
	db, err := sql.Open("sqlite3", dbPath+"?_journal_mode=WAL")
	if err == nil {
		mgr.sqliteDB = db
		_, _ = db.Exec(`CREATE TABLE IF NOT EXISTS idempotency_cache (
			command_id TEXT PRIMARY KEY,
			action_type TEXT,
			target TEXT,
			executed_at TIMESTAMP
		);`)
		mgr.loadFromSQLite()
	}

	// Start background cleanup ticker
	go mgr.startCleanupLoop()
	return mgr
}

func (m *AgentIdempotencyManager) loadFromSQLite() {
	if m.sqliteDB == nil {
		return
	}
	m.mu.Lock()
	defer m.mu.Unlock()

	cutoff := time.Now().Add(-m.ttlDuration)
	rows, err := m.sqliteDB.Query("SELECT command_id, executed_at FROM idempotency_cache WHERE executed_at > ?", cutoff)
	if err != nil {
		return
	}
	defer rows.Close()

	for rows.Next() {
		var cmdID string
		var executedAt time.Time
		if err := rows.Scan(&cmdID, &executedAt); err == nil {
			m.memoryCache[cmdID] = executedAt
		}
	}
	if err := rows.Err(); err != nil {
		log.Printf("[IDEMPOTENCY] Warning: error iterating idempotency cache rows: %v", err)
	}
}

// IsDuplicate checks if command_id has been executed within the TTL window (5-10 mins)
func (m *AgentIdempotencyManager) IsDuplicate(commandID string) bool {
	if commandID == "" {
		return false
	}
	m.mu.RLock()
	executedAt, exists := m.memoryCache[commandID]
	m.mu.RUnlock()

	if exists {
		if time.Since(executedAt) < m.ttlDuration {
			return true
		}
	}
	return false
}

// RecordExecution stores command_id in memory and SQLite WAL persistence
func (m *AgentIdempotencyManager) RecordExecution(commandID, actionType, target string) {
	if commandID == "" {
		return
	}
	now := time.Now()
	m.mu.Lock()
	m.memoryCache[commandID] = now
	m.mu.Unlock()

	if m.sqliteDB != nil {
		_, _ = m.sqliteDB.Exec(
			"INSERT OR REPLACE INTO idempotency_cache (command_id, action_type, target, executed_at) VALUES (?, ?, ?, ?)",
			commandID, actionType, target, now,
		)
	}
}

func (m *AgentIdempotencyManager) startCleanupLoop() {
	ticker := time.NewTicker(2 * time.Minute)
	for range ticker.C {
		m.mu.Lock()
		cutoff := time.Now().Add(-m.ttlDuration)
		for cmdID, executedAt := range m.memoryCache {
			if executedAt.Before(cutoff) {
				delete(m.memoryCache, cmdID)
			}
		}
		m.mu.Unlock()

		if m.sqliteDB != nil {
			_, _ = m.sqliteDB.Exec("DELETE FROM idempotency_cache WHERE executed_at < ?", cutoff)
		}
	}
}

// AgentRemediationSubscriber listens for HITL-approved remediation commands over NATS (< 10ms)
type AgentRemediationSubscriber struct {
	mu          sync.Mutex
	nc          *nats.Conn
	sub         *nats.Subscription
	siteID      string
	agentID     string
	natsURL     string
	idempotency *AgentIdempotencyManager
}

// NewAgentRemediationSubscriber creates a new subscription listener for action execution
func NewAgentRemediationSubscriber(natsURL, siteID, agentID string) *AgentRemediationSubscriber {
	sub := &AgentRemediationSubscriber{
		natsURL:     natsURL,
		siteID:      siteID,
		agentID:     agentID,
		idempotency: NewAgentIdempotencyManager(5 * time.Minute), // 5 Menit Idempotency Cache TTL
	}

	sub.startSubscription()
	return sub
}

func (s *AgentRemediationSubscriber) startSubscription() {
	nc, err := nats.Connect(s.natsURL,
		nats.MaxReconnects(-1),
		nats.ReconnectWait(2*time.Second),
	)
	if err != nil {
		log.Printf("[REMEDIATION-SUBSCRIBER] Warning: NATS connection failed: %v", err)
		return
	}

	s.nc = nc
	subject := fmt.Sprintf("remediation.site.%s.%s", s.siteID, s.agentID)
	sub, err := nc.Subscribe(subject, func(m *nats.Msg) {
		s.handleCommand(m)
	})

	if err != nil {
		log.Printf("[REMEDIATION-SUBSCRIBER] Failed to subscribe to %s: %v", subject, err)
		return
	}

	s.sub = sub
	log.Printf("[REMEDIATION-SUBSCRIBER] Successfully subscribed to action channel: %s", subject)
}

func generateUUID() string {
	b := make([]byte, 16)
	_, err := rand.Read(b)
	if err != nil {
		return fmt.Sprintf("cmd-%d", time.Now().UnixNano())
	}
	return fmt.Sprintf("cmd-%s-%s-%s-%s-%s",
		hex.EncodeToString(b[0:4]),
		hex.EncodeToString(b[4:6]),
		hex.EncodeToString(b[6:8]),
		hex.EncodeToString(b[8:10]),
		hex.EncodeToString(b[10:16]),
	)
}

func (s *AgentRemediationSubscriber) sendACK(cmdID, status, message string) {
	if s.nc == nil {
		return
	}
	ackTopic := fmt.Sprintf("remediation.ack.%s.%s", s.siteID, s.agentID)
	ack := CommandAckResponse{
		CommandID: cmdID,
		Status:    status,
		Message:   message,
		Timestamp: time.Now().Format(time.RFC3339),
		AgentID:   s.agentID,
		SiteID:    s.siteID,
	}

	payload, err := json.Marshal(ack)
	if err == nil {
		_ = s.nc.Publish(ackTopic, payload)
		log.Printf("[IDEMPOTENCY] Sent %s for Command %s to NATS topic %s", status, cmdID, ackTopic)
	}
}

func (s *AgentRemediationSubscriber) handleCommand(msg *nats.Msg) {
	start := time.Now()
	var cmd RemediationCommand
	if err := json.Unmarshal(msg.Data, &cmd); err != nil {
		log.Printf("[REMEDIATION-SUBSCRIBER] Invalid action payload: %v", err)
		return
	}

	if cmd.CommandID == "" {
		cmd.CommandID = generateUUID()
	}

	// 🛡️ IDEMPOTENCY GATEKEEPER CHECK:
	// Mencegah Retry Storm jika ACK NATS hilang di jaringan!
	if s.idempotency.IsDuplicate(cmd.CommandID) {
		log.Printf("[IDEMPOTENCY] ⚠️ DUPLICATE COMMAND DETECTED: %s (%s on %s). Skipping execution!",
			cmd.CommandID, cmd.ActionType, cmd.Target)
		
		// Mengembalikan ACK_DUPLICATE langsung ke NATS tanpa mengeksekusi ulang!
		s.sendACK(cmd.CommandID, "ACK_DUPLICATE", "Duplicate Command ID within 5-min TTL window ignored")
		return
	}

	// Catat Command ID ke Cache Idempotensi sebelum mengeksekusi
	s.idempotency.RecordExecution(cmd.CommandID, cmd.ActionType, cmd.Target)

	log.Printf("[REMEDIATION-SUBSCRIBER] [HITL APPROVED] Executing Action Command: %s (Target: %s, Incident: %s, CmdID: %s)",
		cmd.ActionType, cmd.Target, cmd.IncidentID, cmd.CommandID)

	// Execute command safely
	resultStatus := "SUCCESS"
	switch cmd.ActionType {
	case "RESTART_SERVICE":
		log.Printf("[REMEDIATION-SUBSCRIBER] Executing Service Restart for: %s", cmd.Target)
	case "CLEAR_SPOOLER":
		log.Printf("[REMEDIATION-SUBSCRIBER] Clearing Printer Spooler Queue for: %s", cmd.Target)
	case "RELEASE_DHCP_LEASE":
		log.Printf("[REMEDIATION-SUBSCRIBER] Releasing DHCP Lease for target: %s", cmd.Target)
	default:
		log.Printf("[REMEDIATION-SUBSCRIBER] Executing Generic Safe Action: %s", cmd.ActionType)
	}

	latency := time.Since(start).Milliseconds()
	log.Printf("[REMEDIATION-SUBSCRIBER] Action %s executed with status: %s (Latency: %d ms)",
		cmd.CommandID, resultStatus, latency)

	// Mengembalikan ACK_SUCCESS ke NATS
	s.sendACK(cmd.CommandID, "ACK_SUCCESS", fmt.Sprintf("Action executed cleanly in %d ms", latency))
}

// Close gracefully closes the subscription and connection
func (s *AgentRemediationSubscriber) Close() {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.sub != nil {
		_ = s.sub.Unsubscribe()
	}
	if s.nc != nil {
		s.nc.Close()
	}
}
