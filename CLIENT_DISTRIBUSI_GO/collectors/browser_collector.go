package collectors

import (
	"time"
)

type BrowserCollector struct{}

func NewBrowserCollector() *BrowserCollector {
	return &BrowserCollector{}
}

func (b *BrowserCollector) Modality() ModalityType {
	return ModalityBrowser
}

func (b *BrowserCollector) Collect(deviceID string) ([]NormalizedEvent, error) {
	events := []NormalizedEvent{
		{
			EventID:    GenerateEventID(deviceID, "BROWSER_HEARTBEAT"),
			Timestamp:  time.Now().UTC().Format(time.RFC3339),
			DeviceID:   deviceID,
			Layer:      "L1",
			Modality:   ModalityBrowser,
			Source:     "ChromeExtension",
			EventCode:  "BROWSER_OK",
			Severity:   SeverityInfo,
			DurationMS: 0,
			Metrics: map[string]interface{}{
				"heap_mb": 142,
			},
			Metadata: map[string]interface{}{"active_tab": "NOC Dashboard"},
		},
	}
	return events, nil
}
