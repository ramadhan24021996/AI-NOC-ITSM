package ingestion

import (
	"regexp"
	"strings"
	"time"
)

// EnterpriseLogEvent represents a parsed, normalized enterprise application/infrastructure log
type EnterpriseLogEvent struct {
	Component string // e.g., PostgreSQL, VMware, IIS, K8s
	Severity  string // INFO, WARN, ERROR, CRITICAL
	Message   string // Cleaned up log message
	Raw       string // Original raw log
	Context   map[string]interface{} // Extracted fields like Query Time, Pod Name, IP
}

var (
	// Database & Message Broker
	pgSlowQueryRegex = regexp.MustCompile(`duration: ([0-9.]+) ms\s+statement:\s*(.*)`)
	mysqlSlowRegex   = regexp.MustCompile(`Query_time: ([0-9.]+)\s+Lock_time: ([0-9.]+).*`)
	redisOOMRegex    = regexp.MustCompile(`OOM command not allowed when used memory > 'maxmemory'`)
	kafkaErrorRegex  = regexp.MustCompile(`\[KafkaServer id=\d+\] (error|fatal) (.*)`)

	// Web & App Servers
	iisLogRegex     = regexp.MustCompile(`\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} .* (50\d|40\d) .*`)
	javaStackRegex  = regexp.MustCompile(`java\.lang\.[a-zA-Z]+Exception: (.*)`)
	phpErrorRegex   = regexp.MustCompile(`PHP Fatal error: (.*)`)
	
	// Infrastructure & Container
	dockerOOMRegex  = regexp.MustCompile(`Container .* killed as a result of out of memory`)
	k8sCrashRegex   = regexp.MustCompile(`Back-off restarting failed container`)
	vmwareRegex     = regexp.MustCompile(`\[Vpxd.*\] (error|warning) .*`)
	adEventRegex    = regexp.MustCompile(`EventID: (4625|4740|4648)`) // Auth failure, lockout
)

// ParseEnterpriseLog classifies and extracts context from a raw log line (Sprint F)
func ParseEnterpriseLog(raw string) *EnterpriseLogEvent {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return nil
	}

	event := &EnterpriseLogEvent{
		Severity: "INFO",
		Raw:      raw,
		Context:  make(map[string]interface{}),
	}

	// 1. PostgreSQL
	if strings.Contains(raw, "PostgreSQL") || strings.Contains(raw, "postgres[") {
		event.Component = "PostgreSQL"
		if strings.Contains(raw, "fatal") || strings.Contains(raw, "error") || strings.Contains(raw, "deadlock detected") {
			event.Severity = "CRITICAL"
			event.Message = "Database Error or Deadlock detected"
			if strings.Contains(raw, "deadlock detected") {
				event.Context["issue"] = "Deadlock"
			}
			return event
		}
		if matches := pgSlowQueryRegex.FindStringSubmatch(raw); len(matches) > 2 {
			event.Severity = "WARN"
			event.Message = "Slow Query Detected"
			event.Context["duration_ms"] = matches[1]
			event.Context["query"] = matches[2]
			return event
		}
	}

	// 2. MySQL
	if strings.Contains(raw, "mysqld") {
		event.Component = "MySQL"
		if matches := mysqlSlowRegex.FindStringSubmatch(raw); len(matches) > 2 {
			event.Severity = "WARN"
			event.Message = "Slow Query Detected"
			event.Context["query_time"] = matches[1]
			event.Context["lock_time"] = matches[2]
			return event
		}
	}

	// 3. Redis
	if strings.Contains(raw, "redis-server") || redisOOMRegex.MatchString(raw) {
		event.Component = "Redis"
		if redisOOMRegex.MatchString(raw) {
			event.Severity = "CRITICAL"
			event.Message = "Redis Out of Memory"
			event.Context["issue"] = "OOM"
			return event
		}
	}

	// 4. Java / Tomcat / Spring
	if javaStackRegex.MatchString(raw) || strings.Contains(raw, "Catalina") {
		event.Component = "Java/Tomcat"
		matches := javaStackRegex.FindStringSubmatch(raw)
		if len(matches) > 1 {
			event.Severity = "ERROR"
			event.Message = "Java Exception: " + matches[1]
			if strings.Contains(raw, "OutOfMemoryError") {
				event.Severity = "CRITICAL"
				event.Context["issue"] = "Heap Exhausted"
			}
			return event
		}
	}

	// 5. IIS & .NET
	if strings.Contains(raw, "W3SVC") || iisLogRegex.MatchString(raw) {
		event.Component = "IIS"
		matches := iisLogRegex.FindStringSubmatch(raw)
		if len(matches) > 1 {
			event.Severity = "ERROR"
			event.Message = "IIS HTTP " + matches[1]
			event.Context["http_code"] = matches[1]
			return event
		}
	}

	// 6. Kubernetes
	if strings.Contains(raw, "kubelet") || k8sCrashRegex.MatchString(raw) {
		event.Component = "Kubernetes"
		if k8sCrashRegex.MatchString(raw) {
			event.Severity = "CRITICAL"
			event.Message = "Pod CrashLoopBackOff"
			event.Context["issue"] = "CrashLoopBackOff"
			return event
		}
	}

	// 7. Docker
	if strings.Contains(raw, "dockerd") || dockerOOMRegex.MatchString(raw) {
		event.Component = "Docker"
		if dockerOOMRegex.MatchString(raw) {
			event.Severity = "CRITICAL"
			event.Message = "Container OOM Killed"
			event.Context["issue"] = "OOM_Killed"
			return event
		}
	}

	// 8. Active Directory
	if strings.Contains(raw, "Active Directory") || adEventRegex.MatchString(raw) {
		event.Component = "Active Directory"
		matches := adEventRegex.FindStringSubmatch(raw)
		if len(matches) > 1 {
			event.Severity = "WARN"
			event.Message = "AD Security Event: " + matches[1]
			event.Context["event_id"] = matches[1]
			return event
		}
	}

	// Default fallback if no specific enterprise component matched
	return nil
}

// ConvertToTelemetry maps an EnterpriseLogEvent to a TelemetryItem for the Diagnostic AI
func (e *EnterpriseLogEvent) ConvertToTelemetry(sourceAgent string) TelemetryItem {
	layer := 7 // default app layer
	switch e.Component {
	case "PostgreSQL", "MySQL", "Redis":
		layer = 6
	case "Kubernetes", "Docker", "VMware":
		layer = 5
	case "Active Directory":
		layer = 4
	}

	return TelemetryItem{
		Type:          "telemetry",
		EventType:     "enterprise_log",
		Status:        e.Severity,
		Description:   e.Component + " - " + e.Message,
		Layer:         layer,
		Agent:         sourceAgent,
		Timestamp:     time.Now().Format(time.RFC3339),
		SchemaVersion: "2.1.0",
		TraceID:       GenerateTraceID(),
		SpanID:        GenerateSpanID(),
		Metadata: map[string]interface{}{
			"component":     e.Component,
			"requires_hitl": true, // Always true for diagnostic-only mode
		},
		Data: e.Context,
	}
}
