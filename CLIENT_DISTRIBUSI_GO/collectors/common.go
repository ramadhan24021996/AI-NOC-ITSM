package collectors

import (
	"crypto/md5"
	"encoding/hex"
	"fmt"
	"time"
)

// ModalityType defines event sources
type ModalityType string

const (
	ModalityNetwork     ModalityType = "NETWORK"
	ModalityHardware    ModalityType = "HARDWARE"
	ModalityOS          ModalityType = "OS"
	ModalityBrowser     ModalityType = "BROWSER"
	ModalityApplication ModalityType = "APPLICATION"
	ModalityUser        ModalityType = "USER"
	ModalitySecurity    ModalityType = "SECURITY"
)

// SeverityLevel defines event urgency
type SeverityLevel string

const (
	SeverityInfo     SeverityLevel = "INFO"
	SeverityLow      SeverityLevel = "LOW"
	SeverityWarning  SeverityLevel = "WARNING"
	SeverityHigh     SeverityLevel = "HIGH"
	SeverityCritical SeverityLevel = "CRITICAL"
)

// NormalizedEvent is the unified telemetry schema for Fusion Stream
type NormalizedEvent struct {
	EventID    string                 `json:"event_id"`
	Timestamp  string                 `json:"timestamp"`
	DeviceID   string                 `json:"device_id"`
	Layer      string                 `json:"layer"`
	Modality   ModalityType           `json:"modality"`
	Source     string                 `json:"source"`
	EventCode  string                 `json:"event_code"`
	Severity   SeverityLevel          `json:"severity"`
	DurationMS int64                  `json:"duration_ms"`
	Metrics    map[string]interface{} `json:"metrics"`
	Metadata   map[string]interface{} `json:"metadata"`
}

// EventCollector is the common interface for all modality collectors
type EventCollector interface {
	Collect(deviceID string) ([]NormalizedEvent, error)
	Modality() ModalityType
}

func GenerateEventID(deviceID, eventCode string) string {
	ts := time.Now().UTC().Format(time.RFC3339)
	hash := md5.Sum([]byte(fmt.Sprintf("%s-%s-%s", ts, deviceID, eventCode)))
	return fmt.Sprintf("EVT-%s", hex.EncodeToString(hash[:6]))
}
