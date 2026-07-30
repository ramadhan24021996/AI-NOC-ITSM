package main

import (
	"fmt"
	"log"
	"strings"
	"time"
)

// NatsFailoverPool handles multi-node NATS cluster connections (Node 1: :4222, Node 2: :4223).
type NatsFailoverPool struct {
	ClusterURLs   []string
	ActiveNode    string
	Connected     bool
	ReconnectWait time.Duration
}

// NewNatsFailoverPool creates a 2-node NATS HA cluster connection pool.
func NewNatsFailoverPool(urls ...string) *NatsFailoverPool {
	if len(urls) == 0 {
		urls = []string{
			"nats://127.0.0.1:4222",
			"nats://127.0.0.1:4223",
		}
	}
	return &NatsFailoverPool{
		ClusterURLs:   urls,
		ActiveNode:    urls[0],
		Connected:     true,
		ReconnectWait: 1 * time.Second,
	}
}

// GetFailoverString returns comma-separated NATS connection pool string for Go NATS client.
func (p *NatsFailoverPool) GetFailoverString() string {
	return strings.Join(p.ClusterURLs, ",")
}

// SimulateFailover switches active node to secondary node if primary goes offline.
func (p *NatsFailoverPool) SimulateFailover(failedNode string) string {
	log.Printf("[NATS HA CLUSTER] Primary node %s down! Executing auto-failover...", failedNode)
	for _, u := range p.ClusterURLs {
		if u != failedNode {
			p.ActiveNode = u
			p.Connected = true
			log.Printf("[NATS HA CLUSTER] Switched to secondary node %s (0%% Telemetry Loss)", u)
			return u
		}
	}
	return p.ActiveNode
}

func NatsFailoverDemo() {
	pool := NewNatsFailoverPool()
	fmt.Printf("[NATS HA] Failover Pool: %s\n", pool.GetFailoverString())
	fmt.Printf("[NATS HA] Active Node: %s\n", pool.ActiveNode)
	newActive := pool.SimulateFailover("nats://127.0.0.1:4222")
	fmt.Printf("[NATS HA] Failover Target: %s\n", newActive)
}
