package hardening

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"sync"
	"time"

	"go_incident_analysis/SERVER/go_core/database"
)

type GovernanceApprovalRecord struct {
	ID         int       `gorm:"column:id"`
	IncidentID string    `gorm:"column:incident_id"`
	RiskScore  float64   `gorm:"column:risk_score"`
	Severity   string    `gorm:"column:severity"`
	CreatedAt  time.Time `gorm:"column:created_at"`
}

// ApprovalTimeoutManager watches governance_approvals for SLA breaches (P0 > 120s, P1 > 300s)
type ApprovalTimeoutManager struct {
	mu            sync.Mutex
	telegramToken string
	telegramChat  string
	stopChan      chan struct{}
}

// NewApprovalTimeoutManager initializes background approval timeout watcher
func NewApprovalTimeoutManager() *ApprovalTimeoutManager {
	return &ApprovalTimeoutManager{
		telegramToken: os.Getenv("TELEGRAM_BOT_TOKEN"),
		telegramChat:  os.Getenv("TELEGRAM_SUPERVISOR_CHAT_ID"),
		stopChan:      make(chan struct{}),
	}
}

// StartWatcher launches interval watcher loop
func (m *ApprovalTimeoutManager) StartWatcher(checkInterval time.Duration) {
	ticker := time.NewTicker(checkInterval)
	go func() {
		log.Println("[APPROVAL_TIMEOUT] Approval SLA Watcher started...")
		for {
			select {
			case <-ticker.C:
				m.checkAndEscalateTimeouts()
			case <-m.stopChan:
				ticker.Stop()
				return
			}
		}
	}()
}

func (m *ApprovalTimeoutManager) checkAndEscalateTimeouts() {
	m.mu.Lock()
	defer m.mu.Unlock()

	if database.DB == nil {
		return
	}

	// Query WAITING_APPROVAL items older than SLA limits:
	// P0 / CRITICAL: > 120 seconds
	// P1 / HIGH: > 300 seconds
	query := `
		SELECT id, incident_id, risk_score, created_at, COALESCE(severity, 'P1') as severity
		FROM governance_approvals
		WHERE status = 'WAITING_APPROVAL'
		  AND (
			(COALESCE(severity, 'P1') IN ('P0', 'CRITICAL') AND created_at < NOW() - INTERVAL '120 seconds')
			OR
			(COALESCE(severity, 'P1') NOT IN ('P0', 'CRITICAL') AND created_at < NOW() - INTERVAL '300 seconds')
		  )
	`
	var records []GovernanceApprovalRecord
	if err := database.DB.Raw(query).Scan(&records).Error; err != nil || len(records) == 0 {
		return
	}

	for _, rec := range records {
		// Fail-safe auto-escalation policy:
		// Risk <= 0.20 -> ESCALATED_AUTO_APPROVE (low risk, proceed)
		// Risk > 0.20  -> ESCALATED_AUTO_REJECT  (high risk, fail-safe safety stop)
		newStatus := "ESCALATED_AUTO_APPROVE"
		if rec.RiskScore > 0.20 {
			newStatus = "ESCALATED_AUTO_REJECT"
		}

		// Update governance_approvals
		updateQuery := `UPDATE governance_approvals SET status = ?, reviewed_at = NOW(), reviewer_notes = ? WHERE id = ?`
		notes := fmt.Sprintf("AUTOMATIC SLA BREACH ESCALATION (Timeout > SLA): Auto-%s applied under Fail-Safe Policy.", newStatus)
		database.DB.Exec(updateQuery, newStatus, notes, rec.ID)

		log.Printf("[APPROVAL_TIMEOUT] SLA Breach for Incident %s (ID: %d, Risk: %.2f). Auto-Escalation: %s", rec.IncidentID, rec.ID, rec.RiskScore, newStatus)

		// Audit Trail entry
		auditQuery := `INSERT INTO ai_audit_trail (incident_id, action_type, status, details, created_at) VALUES (?, ?, ?, ?, NOW())`
		database.DB.Exec(auditQuery, rec.IncidentID, "SLA_APPROVAL_TIMEOUT_ESCALATION", newStatus, notes)

		// Telegram Alert to Supervisor Group
		m.sendTelegramSupervisorAlert(rec.IncidentID, rec.Severity, newStatus, rec.RiskScore)
	}
}

func (m *ApprovalTimeoutManager) sendTelegramSupervisorAlert(incidentID, severity, status string, riskScore float64) {
	if m.telegramToken == "" || m.telegramChat == "" {
		return
	}
	msg := fmt.Sprintf("🚨 *SUPERVISOR SLA ESCALATION ALERT*\n\nIncident: `%s`\nSeverity: *%s*\nRisk Score: *%.2f*\nResolution: *%s*\n\nReason: Approval timeout breached NOC operator SLA limits. Auto fail-safe action executed.", incidentID, severity, riskScore, status)

	url := fmt.Sprintf("https://api.telegram.org/bot%s/sendMessage", m.telegramToken)
	body, _ := json.Marshal(map[string]string{
		"chat_id":    m.telegramChat,
		"text":       msg,
		"parse_mode": "Markdown",
	})
	resp, err := http.Post(url, "application/json", bytes.NewBuffer(body))
	if err == nil && resp != nil {
		_ = resp.Body.Close()
	}
}

// Stop terminates watcher
func (m *ApprovalTimeoutManager) Stop() {
	close(m.stopChan)
}
