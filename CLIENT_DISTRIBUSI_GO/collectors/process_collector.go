package collectors

import (
	"time"
)

type ProcessCollector struct{}

func NewProcessCollector() *ProcessCollector {
	return &ProcessCollector{}
}

func (pr *ProcessCollector) Modality() ModalityType {
	return ModalityOS
}

func (pr *ProcessCollector) Collect(deviceID string) ([]NormalizedEvent, error) {
	events := []NormalizedEvent{
		{
			EventID:    GenerateEventID(deviceID, "PROCESS_LIST"),
			Timestamp:  time.Now().UTC().Format(time.RFC3339),
			DeviceID:   deviceID,
			Layer:      "OS",
			Modality:   ModalityOS,
			Source:     "ProcessCollector",
			EventCode:  "PROCESSES_STABLE",
			Severity:   SeverityInfo,
			DurationMS: 0,
			Metrics:    map[string]interface{}{"active_count": 128},
			Metadata:   map[string]interface{}{"top_cpu": "agent.exe"},
		},
	}
	return events, nil
}
