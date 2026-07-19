package ingestion

import (
	"crypto/rand"
	"encoding/hex"
)

// GenerateTraceID generates a 16-byte hex string (W3C Trace Context)
func GenerateTraceID() string {
	b := make([]byte, 16)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}

// GenerateSpanID generates an 8-byte hex string (W3C Trace Context)
func GenerateSpanID() string {
	b := make([]byte, 8)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}

// InjectOTelContext adds TraceID and SpanID to a TelemetryItem if missing
func InjectOTelContext(item *TelemetryItem) {
	if item.TraceID == "" {
		item.TraceID = GenerateTraceID()
	}
	if item.SpanID == "" {
		item.SpanID = GenerateSpanID()
	}
	// Propagate TraceID to metadata for backward compatibility / indexing
	if item.Metadata == nil {
		item.Metadata = make(map[string]interface{})
	}
	item.Metadata["trace_id"] = item.TraceID
	item.Metadata["span_id"] = item.SpanID
}
