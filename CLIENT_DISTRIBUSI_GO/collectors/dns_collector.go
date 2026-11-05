package collectors

import (
	"time"
)

type DNSCollector struct{}

func NewDNSCollector() *DNSCollector {
	return &DNSCollector{}
}

func (d *DNSCollector) Modality() ModalityType {
	return ModalityNetwork
}

func (d *DNSCollector) Collect(deviceID string) ([]NormalizedEvent, error) {
	events := []NormalizedEvent{
		{
			EventID:    GenerateEventID(deviceID, "DNS_LOOKUP"),
			Timestamp:  time.Now().UTC().Format(time.RFC3339),
			DeviceID:   deviceID,
			Layer:      "L3",
			Modality:   ModalityNetwork,
			Source:     "DNSCollector",
			EventCode:  "DNS_RESOLVED",
			Severity:   SeverityInfo,
			DurationMS: 18,
			Metrics: map[string]interface{}{
				"resolve_time_ms": 18,
			},
			Metadata: map[string]interface{}{"domain": "internal-server.local"},
		},
	}
	return events, nil
}
