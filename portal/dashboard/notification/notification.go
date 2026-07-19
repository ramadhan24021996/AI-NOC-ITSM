package notification

import (
	"fmt"
	"time"

	"github.com/nats-io/nats.go"
	"gorm.io/gorm"
)

// StartOutboxDispatcher polls the database for pending approval outbox records
// and publishes them to NATS.
func StartOutboxDispatcher(db *gorm.DB, natsConn *nats.Conn) {
	ticker := time.NewTicker(500 * time.Millisecond)
	go func() {
		for range ticker.C {
			if natsConn == nil {
				continue
			}

			var pending []struct {
				ID          uint64 `gorm:"column:id"`
				EventType   string `gorm:"column:event_type"`
				AggregateID int64  `gorm:"column:aggregate_id"`
				Payload     string `gorm:"column:payload"`
				RetryCount  int    `gorm:"column:retry_count"`
			}
			err := db.Raw("SELECT id, event_type, aggregate_id, payload, retry_count FROM approval_outbox WHERE status = 'PENDING' ORDER BY id ASC LIMIT 50").Scan(&pending).Error
			if err != nil {
				continue
			}

			for _, outbox := range pending {
				err := natsConn.Publish(outbox.EventType, []byte(outbox.Payload))
				if err != nil {
					newRetry := outbox.RetryCount + 1
					status := "PENDING"
					if newRetry >= 5 {
						status = "FAILED"
					}
					_ = db.Exec("UPDATE approval_outbox SET retry_count = ?, last_error = ?, status = ? WHERE id = ?", newRetry, err.Error(), status, outbox.ID).Error
					fmt.Printf("[OUTBOX] Failed to publish outbox event %d: %v (Attempt %d)\n", outbox.ID, err, newRetry)
					continue
				}

				err = db.Exec("UPDATE approval_outbox SET status = 'SENT', publish_ack = TRUE, sent_at = NOW() WHERE id = ?", outbox.ID).Error
				if err != nil {
					fmt.Printf("[OUTBOX] Failed to mark outbox event %d as sent: %v\n", outbox.ID, err)
				} else {
					fmt.Printf("[OUTBOX] Dispatched event ID %d to subject %s\n", outbox.ID, outbox.EventType)
				}
			}
		}
	}()
}
