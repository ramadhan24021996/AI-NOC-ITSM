package ingestion

import (
	"regexp"
	"strings"
	"time"
)

// EnterpriseLogEvent represents a parsed, normalized enterprise application/infrastructure log
type EnterpriseLogEvent struct {
	Component string                 // e.g., PostgreSQL, VMware, IIS, K8s, Nginx, Cisco, WindowsSecurity
	Severity  string                 // INFO, WARN, ERROR, CRITICAL
	Message   string                 // Cleaned up log message
	Raw       string                 // Original raw log
	Context   map[string]interface{} // Extracted fields like Query Time, Pod Name, IP, EventID
}

var (
	// Database & Message Broker
	pgSlowQueryRegex = regexp.MustCompile(`duration: ([0-9.]+) ms\s+statement:\s*(.*)`)
	mysqlSlowRegex   = regexp.MustCompile(`Query_time: ([0-9.]+)\s+Lock_time: ([0-9.]+).*`)
	redisOOMRegex    = regexp.MustCompile(`OOM command not allowed when used memory > 'maxmemory'`)
	kafkaErrorRegex  = regexp.MustCompile(`\[KafkaServer id=\d+\] (error|fatal) (.*)`)

	// Web & App Servers
	nginx50xRegex   = regexp.MustCompile(`\s(500|502|503|504)\s.*(?:upstream timed out|connect\(\) failed|no live upstreams)`)
	apacheErrRegex  = regexp.MustCompile(`\[(:?error|crit|alert|emerg)\] \[pid \d+\] (.*)`)
	iisLogRegex     = regexp.MustCompile(`\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} .* (50\d|40\d) .*`)
	javaStackRegex  = regexp.MustCompile(`java\.lang\.[a-zA-Z]+Exception: (.*)`)
	phpErrorRegex   = regexp.MustCompile(`PHP Fatal error: (.*)`)
	
	// Infrastructure & Container
	dockerOOMRegex  = regexp.MustCompile(`Container .* killed as a result of out of memory`)
	k8sCrashRegex   = regexp.MustCompile(`Back-off restarting failed container`)
	vmwareRegex     = regexp.MustCompile(`\[Vpxd.*\] (error|warning) .*`)
	
	// Windows Security & System Event IDs
	winSecEventRegex = regexp.MustCompile(`EventID:\s*(4625|4740|4648|1102|7036)`)
	
	// Network & Syslog
	ciscoSyslogRegex = regexp.MustCompile(`%(LINK|LINEPROTO|BGP|OSPF)-\d-([A-Z0-9_]+): (.*)`)
)

// ParseEnterpriseLog classifies and extracts context from a raw log line (Sprint F & P0 Expansion)
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

	// 2. Nginx / Web Gateway
	if strings.Contains(raw, "nginx") || nginx50xRegex.MatchString(raw) {
		event.Component = "Nginx"
		if matches := nginx50xRegex.FindStringSubmatch(raw); len(matches) > 1 {
			event.Severity = "CRITICAL"
			event.Message = "Nginx Gateway Error HTTP " + matches[1]
			event.Context["http_code"] = matches[1]
			return event
		}
	}

	// 3. Apache HTTPD
	if strings.Contains(raw, "[error]") || strings.Contains(raw, "[crit]") || apacheErrRegex.MatchString(raw) {
		event.Component = "Apache"
		if matches := apacheErrRegex.FindStringSubmatch(raw); len(matches) > 2 {
			event.Severity = "ERROR"
			event.Message = "Apache Error: " + matches[2]
			return event
		}
	}

	// 4. Redis
	if strings.Contains(raw, "redis-server") || redisOOMRegex.MatchString(raw) {
		event.Component = "Redis"
		if redisOOMRegex.MatchString(raw) {
			event.Severity = "CRITICAL"
			event.Message = "Redis Out of Memory"
			event.Context["issue"] = "OOM"
			return event
		}
	}

	// 5. Windows Security & System Events
	if strings.Contains(raw, "EventID") || winSecEventRegex.MatchString(raw) {
		event.Component = "WindowsSecurity"
		if matches := winSecEventRegex.FindStringSubmatch(raw); len(matches) > 1 {
			eventID := matches[1]
			event.Context["event_id"] = eventID
			switch eventID {
			case "4625":
				event.Severity = "WARN"
				event.Message = "Failed User Logon Attempt (Event 4625)"
			case "4740":
				event.Severity = "CRITICAL"
				event.Message = "User Account Locked Out (Event 4740)"
			case "1102":
				event.Severity = "CRITICAL"
				event.Message = "Audit Log Cleared (Event 1102)"
			case "7036":
				event.Severity = "INFO"
				event.Message = "Service Status Changed (Event 7036)"
			default:
				event.Severity = "WARN"
				event.Message = "Windows Event ID " + eventID
			}
			return event
		}
	}

	// 6. Network & Cisco Syslog
	if ciscoSyslogRegex.MatchString(raw) {
		event.Component = "CiscoSyslog"
		matches := ciscoSyslogRegex.FindStringSubmatch(raw)
		if len(matches) > 3 {
			event.Severity = "WARN"
			if strings.Contains(matches[2], "DOWN") || strings.Contains(matches[2], "FAIL") {
				event.Severity = "CRITICAL"
			}
			event.Message = matches[1] + " " + matches[2] + ": " + matches[3]
			event.Context["facility"] = matches[1]
			event.Context["mnemonic"] = matches[2]
			return event
		}
	}

	// 7. Kubernetes
	if strings.Contains(raw, "kubelet") || k8sCrashRegex.MatchString(raw) {
		event.Component = "Kubernetes"
		if k8sCrashRegex.MatchString(raw) {
			event.Severity = "CRITICAL"
			event.Message = "Pod CrashLoopBackOff"
			event.Context["issue"] = "CrashLoopBackOff"
			return event
		}
	}

	// 8. Docker
	if strings.Contains(raw, "dockerd") || dockerOOMRegex.MatchString(raw) {
		event.Component = "Docker"
		if dockerOOMRegex.MatchString(raw) {
			event.Severity = "CRITICAL"
			event.Message = "Container OOM Killed"
			event.Context["issue"] = "OOM_Killed"
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
	case "WindowsSecurity", "Active Directory":
		layer = 4
	case "CiscoSyslog", "Nginx", "Apache":
		layer = 3
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
			"requires_hitl": true,
		},
		Data: e.Context,
	}
}
