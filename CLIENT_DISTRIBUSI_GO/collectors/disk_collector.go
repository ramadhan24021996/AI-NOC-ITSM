package collectors

import (
	"time"
)

type DiskCollector struct{}

func NewDiskCollector() *DiskCollector {
	return &DiskCollector{}
}

func (d *DiskCollector) Modality() ModalityType {
	return ModalityHardware
}

func (d *DiskCollector) Collect(deviceID string) ([]NormalizedEvent, error) {
	events := []NormalizedEvent{
		{
			EventID:    GenerateEventID(deviceID, "DISK_HEALTH"),
			Timestamp:  time.Now().UTC().Format(time.RFC3339),
			DeviceID:   deviceID,
			Layer:      "L7",
			Modality:   ModalityHardware,
			Source:     "DiskCollector",
			EventCode:  "DISK_SMART_OK",
			Severity:   SeverityInfo,
			DurationMS: 0,
			Metrics: map[string]interface{}{
				"used_pct": 54.0,
				"iops":     450,
			},
			Metadata: map[string]interface{}{"drive": "C:", "health": "PASSED"},
		},
	}
	return events, nil
}
