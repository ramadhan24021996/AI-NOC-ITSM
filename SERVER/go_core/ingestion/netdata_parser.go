package ingestion

import (
	"encoding/json"
	"fmt"
	"time"
)

// NetdataWebhookPayload represents the standard JSON payload sent by Netdata Alarm Export
type NetdataWebhookPayload struct {
	Host        string      `json:"host"`
	UrlHost     string      `json:"url_host"`
	Alarm       string      `json:"alarm"`
	Info        string      `json:"info"`
	ValueString string      `json:"value_string"`
	Chart       string      `json:"chart"`
	Family      string      `json:"family"`
	Status      string      `json:"status"`
	OldStatus   string      `json:"old_status"`
	Date        interface{} `json:"date"` // Usually Unix timestamp
}

// ConvertToTelemetry maps the Netdata anomaly to our OSI AIOps Telemetry format
func (n *NetdataWebhookPayload) ConvertToTelemetry(sourceIP string) TelemetryItem {
	// Standardize Status
	severity := "INFO"
	switch n.Status {
	case "CRITICAL":
		severity = "CRITICAL"
	case "WARNING":
		severity = "WARNING"
	case "CLEAR":
		severity = "RESOLVED"
	}

	// Heuristic OSI Layer Mapping based on Netdata Chart Families
	layer := 3 // Default Network / Infrastructure
	if n.Chart == "system.cpu" || n.Chart == "system.ram" || n.Chart == "system.swap" {
		layer = 4 // OS Layer
	} else if n.Family == "postgres" || n.Family == "mysql" || n.Family == "redis" {
		layer = 6 // Database Layer
	} else if n.Family == "nginx" || n.Family == "web_log" || n.Family == "httpcheck" {
		layer = 7 // Application Layer
	}

	description := fmt.Sprintf("Netdata ML/Alarm: %s - %s (Value: %s)", n.Alarm, n.Info, n.ValueString)

	return TelemetryItem{
		Type:          "telemetry",
		EventType:     "netdata_anomaly",
		Status:        severity,
		Description:   description,
		Layer:         layer,
		Agent:         n.Host,
		Timestamp:     time.Now().Format(time.RFC3339),
		SchemaVersion: "2.1.0",
		TraceID:       GenerateTraceID(),
		SpanID:        GenerateSpanID(),
		Metadata: map[string]interface{}{
			"source":        "netdata",
			"chart":         n.Chart,
			"family":        n.Family,
			"old_status":    n.OldStatus,
			"source_ip":     sourceIP,
			"requires_hitl": true, // AI cannot auto-remediate strictly based on Netdata without HITL
		},
	}
}

// ParseNetdataPayload takes raw bytes and converts to OSI Telemetry
func ParseNetdataPayload(body []byte, sourceIP string) (*TelemetryItem, error) {
	var payload NetdataWebhookPayload
	err := json.Unmarshal(body, &payload)
	if err != nil {
		return nil, err
	}

	telemetry := payload.ConvertToTelemetry(sourceIP)
	return &telemetry, nil
}
