package collectors

import (
	"time"
)

type WiFiCollector struct{}

func NewWiFiCollector() *WiFiCollector {
	return &WiFiCollector{}
}

func (w *WiFiCollector) Modality() ModalityType {
	return ModalityNetwork
}

func (w *WiFiCollector) Collect(deviceID string) ([]NormalizedEvent, error) {
	events := []NormalizedEvent{
		{
			EventID:    GenerateEventID(deviceID, "WIFI_SIGNAL"),
			Timestamp:  time.Now().UTC().Format(time.RFC3339),
			DeviceID:   deviceID,
			Layer:      "L3",
			Modality:   ModalityNetwork,
			Source:     "WiFiCollector",
			EventCode:  "WIFI_RSSI_STABLE",
			Severity:   SeverityInfo,
			DurationMS: 0,
			Metrics: map[string]interface{}{
				"rssi_dbm": -58,
				"snr_db":   32,
			},
			Metadata: map[string]interface{}{"ssid": "NOC_RETAIL_5G"},
		},
	}
	return events, nil
}
