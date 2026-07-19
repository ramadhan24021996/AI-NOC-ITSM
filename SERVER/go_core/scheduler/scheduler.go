package scheduler

import (
	"encoding/json"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/nats-io/nats.go"

	"go_incident_analysis/SERVER/go_core/config"
)

func StartScheduler() {
	appConfig, err := config.GetConfig()
	if err != nil {
		fmt.Printf(" [SCHEDULER ERROR] Failed to load config: %v\n", err)
		os.Exit(1)
	}

	natsURL := fmt.Sprintf("nats://%s:%d", appConfig.NatsHost, appConfig.NatsPort)
	if appConfig.NatsToken != "" {
		natsURL = fmt.Sprintf("nats://%s@%s:%d", appConfig.NatsToken, appConfig.NatsHost, appConfig.NatsPort)
	}

	natsConn, err := nats.Connect(natsURL)
	if err != nil {
		fmt.Printf(" [SCHEDULER ERROR] Failed to connect to NATS: %v\n", err)
		os.Exit(1)
	}
	defer natsConn.Close()
	fmt.Printf(" [SCHEDULER] Connected to NATS at %s:%d\n", appConfig.NatsHost, appConfig.NatsPort)

	// Define periodic tasks
	cleanupTicker := time.NewTicker(10 * time.Minute)
	slaTicker := time.NewTicker(1 * time.Minute)
	aiRetryTicker := time.NewTicker(2 * time.Minute)
	verifyTicker := time.NewTicker(3 * time.Minute)
	retentionTicker := time.NewTicker(24 * time.Hour)

	// Channel to signal shutdown
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	fmt.Println(" [SCHEDULER] Distributed Scheduler started and publishing ticks...")

	// Helper to publish task event
	publishEvent := func(subject string, taskName string) {
		payload := map[string]interface{}{
			"task":      taskName,
			"timestamp": time.Now().Format(time.RFC3339),
		}
		b, err := json.Marshal(payload)
		if err == nil {
			err = natsConn.Publish(subject, b)
			if err != nil {
				fmt.Printf(" [SCHEDULER ERROR] Failed to publish %s: %v\n", subject, err)
			} else {
				fmt.Printf(" [SCHEDULER] Published tick to %s\n", subject)
			}
		}
	}

	// Trigger once at startup for initial sync
	publishEvent("scheduler.cleanup", "cleanup")
	publishEvent("scheduler.sla.check", "sla_check")
	publishEvent("scheduler.ai.retry", "ai_retry")
	publishEvent("scheduler.verification", "verification")
	publishEvent("scheduler.retention", "retention")

	for {
		select {
		case <-cleanupTicker.C:
			publishEvent("scheduler.cleanup", "cleanup")
		case <-slaTicker.C:
			publishEvent("scheduler.sla.check", "sla_check")
		case <-aiRetryTicker.C:
			publishEvent("scheduler.ai.retry", "ai_retry")
		case <-verifyTicker.C:
			publishEvent("scheduler.verification", "verification")
		case <-retentionTicker.C:
			publishEvent("scheduler.retention", "retention")
		case sig := <-sigChan:
			fmt.Printf(" [SCHEDULER] Shutting down scheduler service (signal: %v)...\n", sig)
			cleanupTicker.Stop()
			slaTicker.Stop()
			aiRetryTicker.Stop()
			verifyTicker.Stop()
			retentionTicker.Stop()
			return
		}
	}
}
