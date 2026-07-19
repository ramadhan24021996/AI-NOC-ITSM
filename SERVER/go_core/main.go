package main

import (
	"fmt"
	"go_incident_analysis/SERVER/go_core/ingestion"
	"go_incident_analysis/SERVER/go_core/discovery"
	"go_incident_analysis/SERVER/go_core/scheduler"
	"os"
	"github.com/nats-io/nats.go"
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
		nc, err := nats.Connect("nats://nats:4222") // Default docker network NATS URL
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
