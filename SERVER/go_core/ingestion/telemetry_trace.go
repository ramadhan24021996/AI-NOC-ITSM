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
	if item.CorrelationID == "" {
		item.CorrelationID = "corr_" + item.TraceID
	}
	item.Metadata["correlation_id"] = item.CorrelationID
	item.Metadata["n8n_webhook_id"] = "wh_" + item.CorrelationID
}

// GenerateCorrelationHeaders builds standard enterprise observability & n8n deduplication headers map
func GenerateCorrelationHeaders(traceID string) map[string]string {
	if traceID == "" {
		traceID = GenerateTraceID()
	}
	corrID := "corr_" + traceID
	return map[string]string{
		"X-Correlation-ID":     corrID,
		"X-N8N-WEBHOOK-ID":     "wh_" + corrID,
		"X-Trace-ID":           traceID,
		"X-Enterprise-Context": "AIOps-v3.0",
	}
}
