package ingestion

import (
	"encoding/json"
	"fmt"
	"strings"
	"time"
)

// TopologyDiscoveryPayload represents connection mappings discovered by the Agent (netstat/eBPF)
type TopologyDiscoveryPayload struct {
	SourceHost     string `json:"source_host"`
	SourceIP       string `json:"source_ip"`
	ProcessName    string `json:"process_name"`
	TargetIP       string `json:"target_ip"`
	TargetPort     string `json:"target_port"`
	Protocol       string `json:"protocol"`
	ConnectionState string `json:"connection_state"`
}

// ConvertToTelemetry converts a network connection into a dynamic SDM edge for the AI Core
func (t *TopologyDiscoveryPayload) ConvertToTelemetry() TelemetryItem {
	// Predict component name based on common ports
	targetComponent := "Unknown_Service"
	layer := 3 // Network
	switch t.TargetPort {
	case "5432":
		targetComponent = "PostgreSQL"
		layer = 6
	case "3306":
		targetComponent = "MySQL"
		layer = 6
	case "6379":
		targetComponent = "Redis"
		layer = 6
	case "80", "443", "8080":
		targetComponent = "Web_Server"
		layer = 7
	}

	description := fmt.Sprintf("Auto-Discovery: %s (%s) connected to %s:%s", t.ProcessName, t.SourceHost, t.TargetIP, t.TargetPort)

	return TelemetryItem{
		Type:          "telemetry",
		EventType:     "topology_discovery",
		Status:        "INFO",
		Description:   description,
		Layer:         layer,
		Agent:         t.SourceHost,
		Timestamp:     time.Now().Format(time.RFC3339),
		SchemaVersion: "2.1.0",
		TraceID:       GenerateTraceID(),
		SpanID:        GenerateSpanID(),
		Metadata: map[string]interface{}{
			"source_component": t.ProcessName,
			"target_component": targetComponent,
			"target_ip":        t.TargetIP,
			"target_port":      t.TargetPort,
			"protocol":         t.Protocol,
			"is_dynamic_edge":  true,
		},
	}
}

// ParseTopologyPayload handles the JSON processing of auto-discovery data
func ParseTopologyPayload(body []byte) (*TelemetryItem, error) {
	var payload TopologyDiscoveryPayload
	err := json.Unmarshal(body, &payload)
	if err != nil {
		return nil, err
	}

	// Only process established connections to avoid noise
	if strings.ToUpper(payload.ConnectionState) != "ESTABLISHED" {
		return nil, fmt.Errorf("ignoring non-established connection")
	}

	telemetry := payload.ConvertToTelemetry()
	return &telemetry, nil
}
