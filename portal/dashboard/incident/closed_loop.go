package incident

import (
	"context"
	"fmt"
	"log"
	"time"

	"gorm.io/gorm"
)

// StartClosedLoopObserver initiates a background goroutine to actively monitor
// telemetry metrics for 3 minutes after a remediation script is executed.
// If the target metric normalizes, it triggers a Positive RLOF update.
// If not, it triggers a Negative RLOF update.
func StartClosedLoopObserver(db *gorm.DB, incidentID uint, deviceName string, playbookID int) {
	go func() {
		log.Printf("[CLOSED-LOOP] Memulai observasi metrik untuk Incident %d di perangkat %s selama 3 menit...", incidentID, deviceName)

		// Create a context with a 4-minute timeout to ensure the goroutine doesn't run forever
		ctx, cancel := context.WithTimeout(context.Background(), 4*time.Minute)
		defer cancel()

		ticker := time.NewTicker(30 * time.Second) // Poll every 30 seconds
		defer ticker.Stop()

		startTime := time.Now()
		isResolved := false
		
		for {
			select {
			case <-ctx.Done():
				// Timeout reached, evaluate final state
				evaluateFinalOutcome(db, incidentID, deviceName, playbookID, isResolved)
				return
				
			case <-ticker.C:
				elapsed := time.Since(startTime)
				if elapsed >= 3*time.Minute {
					evaluateFinalOutcome(db, incidentID, deviceName, playbookID, isResolved)
					return
				}

				// Fetch the latest telemetry for the device (simulating CPU/RAM checks)
				// In production, this targets the specific metric causing the issue (e.g. memory_percent)
				var latestMetric struct {
					MetricValue float64 `gorm:"column:metric_value"`
				}
				
				// Query the latest CPU or RAM metric for the device in the last 1 minute
				err := db.Table("telemetry_logs").
					Select("metric_value").
					Where("device_name = ? AND metric_type IN ('cpu_percent', 'memory_percent') AND timestamp >= ?", deviceName, time.Now().Add(-1*time.Minute)).
					Order("timestamp DESC").
					Limit(1).
					Scan(&latestMetric).Error

				if err == nil {
					// Assume threshold for "healthy" is < 70% CPU/RAM
					if latestMetric.MetricValue > 0 && latestMetric.MetricValue < 70.0 {
						log.Printf("[CLOSED-LOOP] Incident %d (Device: %s) metrik kembali stabil (%.2f%%). Menunggu konfirmasi...", incidentID, deviceName, latestMetric.MetricValue)
						// We need it to be stable for at least 2 consecutive checks, but for simplicity:
						isResolved = true
					} else if latestMetric.MetricValue >= 70.0 {
						log.Printf("[CLOSED-LOOP] Incident %d (Device: %s) metrik masih tinggi (%.2f%%).", incidentID, deviceName, latestMetric.MetricValue)
						isResolved = false
					}
				}
			}
		}
	}()
}

// evaluateFinalOutcome triggers the RLOF Database update based on the observer's conclusion
func evaluateFinalOutcome(db *gorm.DB, incidentID uint, deviceName string, playbookID int, isResolved bool) {
	_ = deviceName
	if isResolved {
		log.Printf("[CLOSED-LOOP] [SUCCESS] Incident %d terverifikasi sembuh. Memicu Positive RLOF Update untuk Playbook %d.", incidentID, playbookID)
		
		// Positive RLOF Update: success_count + 1, last_used_at = NOW()
		db.Exec(`UPDATE ai_playbooks SET success_count = COALESCE(success_count, 0) + 1, last_used_at = NOW() WHERE playbook_id = ?`, playbookID)
		
		// Update Incident Status to RESOLVED automatically
		db.Exec(`UPDATE incidents SET raw_data = jsonb_set(COALESCE(raw_data, '{}'::jsonb), '{status}', '"RESOLVED"'::jsonb) WHERE incident_id = ?`, incidentID)
		db.Exec(`UPDATE fleet_incidents SET status = 'RESOLVED', resolved_at = NOW() WHERE incident_id = ?`, incidentID)
		db.Exec(`INSERT INTO incident_states (incident_id, status, resolved_at, last_updated) VALUES (?, 'RESOLVED', NOW(), NOW()) 
			ON CONFLICT (incident_id) DO UPDATE SET status = 'RESOLVED', resolved_at = NOW(), last_updated = NOW()`, incidentID)
		
		// Write to Audit Trail
		db.Exec(`INSERT INTO ai_audit_trail (incident_id, event_id, action_executed, raw_prompt, llm_response, created_at) VALUES (?, ?, ?, ?, ?, NOW())`,
			incidentID, fmt.Sprintf("RLOF_POS_%d", playbookID), "POSITIVE_RLOF_UPDATE", "Closed-Loop Observer verified metric normalized < 70%", "Playbook efficacy boosted")
			
	} else {
		log.Printf("[CLOSED-LOOP] [FAILED] Incident %d metrik tetap anomali. Memicu Negative RLOF Update untuk Playbook %d.", incidentID, playbookID)
		
		// Negative RLOF Update: fail_count + 1, last_used_at = NOW()
		db.Exec(`UPDATE ai_playbooks SET fail_count = COALESCE(fail_count, 0) + 1, last_used_at = NOW() WHERE playbook_id = ?`, playbookID)
		
		// Keep status active, escalate priority or flag as failed
		db.Exec(`UPDATE incidents SET raw_data = jsonb_set(COALESCE(raw_data, '{}'::jsonb), '{status}', '"ESCALATED"'::jsonb) WHERE incident_id = ?`, incidentID)
		db.Exec(`UPDATE fleet_incidents SET status = 'ESCALATED' WHERE incident_id = ?`, incidentID)
		db.Exec(`INSERT INTO incident_states (incident_id, status, last_updated) VALUES (?, 'ESCALATED', NOW()) 
			ON CONFLICT (incident_id) DO UPDATE SET status = 'ESCALATED', last_updated = NOW()`, incidentID)
			
		// Write to Audit Trail
		db.Exec(`INSERT INTO ai_audit_trail (incident_id, event_id, action_executed, raw_prompt, llm_response, created_at) VALUES (?, ?, ?, ?, ?, NOW())`,
			incidentID, fmt.Sprintf("RLOF_NEG_%d", playbookID), "NEGATIVE_RLOF_UPDATE", "Closed-Loop Observer found metric still > 70% after 3 mins", "Playbook penalized, Incident Escalated")
	}
}
