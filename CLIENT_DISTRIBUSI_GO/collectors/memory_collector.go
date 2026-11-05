package collectors

import (
	"time"
)

type MemoryCollector struct{}

func NewMemoryCollector() *MemoryCollector {
	return &MemoryCollector{}
}

func (m *MemoryCollector) Modality() ModalityType {
	return ModalityHardware
}

func (m *MemoryCollector) Collect(deviceID string) ([]NormalizedEvent, error) {
	events := []NormalizedEvent{
		{
			EventID:    GenerateEventID(deviceID, "MEMORY_METRICS"),
			Timestamp:  time.Now().UTC().Format(time.RFC3339),
			DeviceID:   deviceID,
			Layer:      "L7",
			Modality:   ModalityHardware,
			Source:     "MemoryCollector",
			EventCode:  "MEMORY_STATUS_NORMAL",
			Severity:   SeverityInfo,
			DurationMS: 0,
			Metrics: map[string]interface{}{
				"used_pct":   68.2,
				"free_mb":    5120,
				"total_mb":   16384,
			},
			Metadata: map[string]interface{}{"paging_faults": 12},
		},
	}
	return events, nil
}
