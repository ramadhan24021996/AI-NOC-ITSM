package collectors

import (
	"time"
)

type CPUCollector struct{}

func NewCPUCollector() *CPUCollector {
	return &CPUCollector{}
}

func (c *CPUCollector) Modality() ModalityType {
	return ModalityHardware
}

func (c *CPUCollector) Collect(deviceID string) ([]NormalizedEvent, error) {
	// Sample CPU telemetry collector
	events := []NormalizedEvent{
		{
			EventID:    GenerateEventID(deviceID, "CPU_METRICS"),
			Timestamp:  time.Now().UTC().Format(time.RFC3339),
			DeviceID:   deviceID,
			Layer:      "L7",
			Modality:   ModalityHardware,
			Source:     "CPUCollector",
			EventCode:  "CPU_LOAD_NORMAL",
			Severity:   SeverityInfo,
			DurationMS: 0,
			Metrics: map[string]interface{}{
				"usage_pct":   42.5,
				"cores_count": 8,
			},
			Metadata: map[string]interface{}{"status": "HEALTHY"},
		},
	}
	return events, nil
}
