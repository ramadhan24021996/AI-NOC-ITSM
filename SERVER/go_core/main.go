package main

import (
	"fmt"
	"github.com/nats-io/nats.go"
	"go_incident_analysis/SERVER/go_core/discovery"
	"go_incident_analysis/SERVER/go_core/ingestion"
	"go_incident_analysis/SERVER/go_core/scheduler"
	"os"
)

func main() {
	role := os.Getenv("ROLE")
	if role == "scheduler" {
		fmt.Println("====================================================")
		fmt.Println(" OSI COGNITIVE REASONING GLOBAL SCHEDULER SERVICE")
		fmt.Println("====================================================")
		scheduler.StartScheduler()
		return
	}

	fmt.Println("====================================================")
	fmt.Println(" OSI COGNITIVE REASONING CORE INGESTION SERVER (Go)")
	fmt.Println("====================================================")

	// Start Enterprise Discovery Engine
	go func() {
		natsHost := os.Getenv("NATS_HOST")
		if natsHost == "" {
			natsHost = "nats"
		}
		natsPort := os.Getenv("NATS_PORT")
		if natsPort == "" {
			natsPort = "4222"
		}
		natsToken := os.Getenv("NATS_TOKEN")
		if natsToken == "" {
			natsToken = os.Getenv("OSI_SECURITY_KEY")
		}
		natsURL := fmt.Sprintf("nats://%s:%s", natsHost, natsPort)
		if natsToken != "" {
			natsURL = fmt.Sprintf("nats://%s@%s:%s", natsToken, natsHost, natsPort)
		}
		nc, err := nats.Connect(natsURL)
		if err == nil {
			fmt.Println("[Discovery] NATS connected, starting collectors...")
			go discovery.StartSyslogReceiver(nc, "5514")
			go discovery.StartSNMPCollector(nc, "public")
		} else {
			fmt.Printf("[Discovery] Failed to connect NATS: %v\n", err)
		}
	}()

	ingestion.StartIngestionServer()
}
