package collectors

import (
	"time"
)

type PrinterCollector struct{}

func NewPrinterCollector() *PrinterCollector {
	return &PrinterCollector{}
}

func (p *PrinterCollector) Modality() ModalityType {
	return ModalityHardware
}

func (p *PrinterCollector) Collect(deviceID string) ([]NormalizedEvent, error) {
	events := []NormalizedEvent{
		{
			EventID:    GenerateEventID(deviceID, "PRINTER_SPOOLER"),
			Timestamp:  time.Now().UTC().Format(time.RFC3339),
			DeviceID:   deviceID,
			Layer:      "L7",
			Modality:   ModalityHardware,
			Source:     "PrintSpooler",
			EventCode:  "PRINTER_READY",
			Severity:   SeverityInfo,
			DurationMS: 0,
			Metrics:    map[string]interface{}{"queue_jobs": 0},
			Metadata:   map[string]interface{}{"printer_name": "POS_Thermal_Printer"},
		},
	}
	return events, nil
}
