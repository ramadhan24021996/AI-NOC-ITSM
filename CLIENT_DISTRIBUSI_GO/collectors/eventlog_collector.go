package collectors

import (
	"time"
)

type EventLogCollector struct{}

func NewEventLogCollector() *EventLogCollector {
	return &EventLogCollector{}
}

func (e *EventLogCollector) Modality() ModalityType {
	return ModalityOS
}

func (e *EventLogCollector) Collect(deviceID string) ([]NormalizedEvent, error) {
	events := []NormalizedEvent{
		{
			EventID:    GenerateEventID(deviceID, "EVENTLOG_OK"),
			Timestamp:  time.Now().UTC().Format(time.RFC3339),
			DeviceID:   deviceID,
			Layer:      "OS",
			Modality:   ModalityOS,
			Source:     "EventViewer",
			EventCode:  "SYS_SERVICE_RUNNING",
			Severity:   SeverityInfo,
			DurationMS: 0,
			Metrics:    map[string]interface{}{},
			Metadata:   map[string]interface{}{"channel": "System", "event_id": 7036},
		},
	}
	return events, nil
}
