package collectors

import (
	"time"
)

type SecurityCollector struct{}

func NewSecurityCollector() *SecurityCollector {
	return &SecurityCollector{}
}

func (s *SecurityCollector) Modality() ModalityType {
	return ModalitySecurity
}

func (s *SecurityCollector) Collect(deviceID string) ([]NormalizedEvent, error) {
	events := []NormalizedEvent{
		{
			EventID:    GenerateEventID(deviceID, "SECURITY_SCAN"),
			Timestamp:  time.Now().UTC().Format(time.RFC3339),
			DeviceID:   deviceID,
			Layer:      "L8",
			Modality:   ModalitySecurity,
			Source:     "DefenderAV",
			EventCode:  "SECURITY_DEFENDER_OK",
			Severity:   SeverityInfo,
			DurationMS: 0,
			Metrics:    map[string]interface{}{"threats_found": 0},
			Metadata:   map[string]interface{}{"status": "PROTECTED"},
		},
	}
	return events, nil
}
