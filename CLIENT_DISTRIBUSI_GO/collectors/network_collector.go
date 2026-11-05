package collectors

import (
	"time"
)

type NetworkCollector struct{}

func NewNetworkCollector() *NetworkCollector {
	return &NetworkCollector{}
}

func (n *NetworkCollector) Modality() ModalityType {
	return ModalityNetwork
}

func (n *NetworkCollector) Collect(deviceID string) ([]NormalizedEvent, error) {
	events := []NormalizedEvent{
		{
			EventID:    GenerateEventID(deviceID, "NETWORK_PING"),
			Timestamp:  time.Now().UTC().Format(time.RFC3339),
			DeviceID:   deviceID,
			Layer:      "L3",
			Modality:   ModalityNetwork,
			Source:     "NetworkCollector",
			EventCode:  "PING_RTT_NORMAL",
			Severity:   SeverityInfo,
			DurationMS: 12,
			Metrics: map[string]interface{}{
				"rtt_ms":      12,
				"packet_loss": 0.0,
			},
			Metadata: map[string]interface{}{"gateway": "10.20.0.1"},
		},
	}
	return events, nil
}
