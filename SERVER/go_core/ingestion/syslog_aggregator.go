package ingestion

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net"
	"regexp"
	"strings"
	"time"

	"go_incident_analysis/SERVER/go_core/database"
)

// StartSyslogAggregator starts a UDP listener for standard Syslog (RFC3164/5424)
// and acts as a telemetry aggregator for Network Devices (Mikrotik, Cisco, Fortigate) and Nginx logs.
func StartSyslogAggregator() {
	port := 1514 // Non-privileged port for testing, usually mapped from 514 via iptables
	addr := net.UDPAddr{
		Port: port,
		IP:   net.ParseIP("0.0.0.0"),
	}

	conn, err := net.ListenUDP("udp", &addr)
	if err != nil {
		fmt.Printf(" [SYSLOG FATAL] Failed to start Syslog Aggregator on UDP %d: %v\n", port, err)
		return
	}
	fmt.Printf(" [SYSLOG] Aggregator listening on UDP %d (Ready for Cisco/Mikrotik/Nginx)\n", port)

	go func() {
		buf := make([]byte, 8192)
		for {
			n, remoteAddr, err := conn.ReadFromUDP(buf)
			if err != nil {
				continue
			}

			// Parse the syslog message
			rawMsg := string(bytes.TrimSpace(buf[:n]))
			go processSyslogMessage(rawMsg, remoteAddr.IP.String())
		}
	}()
}

func processSyslogMessage(rawMsg string, sourceIP string) {
	// Simple parsing heuristics for diagnostic purposes
	// Usually syslog looks like: <PRI>TIMESTAMP HOSTNAME APP: MESSAGE
	
	agentName := resolveHostnameByIP(sourceIP)
	layer := 3 // Network by default
	status := "INFO"
	var data map[string]interface{}
	
	// Nginx Error Log Pattern (e.g., [error] 1234#0: *5678 upstream timed out)
	if strings.Contains(rawMsg, "[error]") && strings.Contains(rawMsg, "nginx") {
		layer = 7
		status = "ERROR"
		data = map[string]interface{}{
			"service": "nginx",
			"error_detail": extractNginxError(rawMsg),
		}
		agentName = "Nginx-Server-" + sourceIP
	} else if strings.Contains(rawMsg, "OOM") || strings.Contains(rawMsg, "Out of memory") {
		layer = 1
		status = "CRITICAL"
		data = map[string]interface{}{
			"anomaly": "memory_leak",
			"raw": rawMsg,
		}
	} else if strings.Contains(rawMsg, "BGP") || strings.Contains(rawMsg, "OSPF") {
		layer = 3
		if strings.Contains(rawMsg, "Down") || strings.Contains(rawMsg, "down") {
			status = "BGP_DOWN"
		} else {
			status = "BGP_STATE_CHANGE"
		}
		data = map[string]interface{}{
			"protocol": "BGP/OSPF",
			"raw": rawMsg,
		}
	} else if strings.Contains(rawMsg, "link down") || strings.Contains(rawMsg, "down") {
		layer = 2
		status = "PORT_DOWN"
		data = map[string]interface{}{
			"raw": rawMsg,
		}
	} else {
		// Pass to new Enterprise Log Parser (Sprint F)
		enterpriseEvent := ParseEnterpriseLog(rawMsg)
		if enterpriseEvent != nil {
			item := enterpriseEvent.ConvertToTelemetry(agentName)
			item.Metadata["source_ip"] = sourceIP
			item.Metadata["raw_syslog"] = rawMsg
			publishSyslogToAI(item)
			return
		}
		
		// Ignore noisy info logs
		return
	}

	// Format as standard TelemetryItem for the Diagnostic Engine
	item := TelemetryItem{
		Type:          "telemetry",
		EventType:     "syslog_alert",
		Status:        status,
		Description:   "Syslog alert received from " + agentName,
		Layer:         layer,
		Agent:         agentName,
		Timestamp:     fmt.Sprintf("%d", time.Now().Unix()),
		SchemaVersion: "2.1.0",
		TraceID:       GenerateTraceID(),
		SpanID:        GenerateSpanID(),
		Metadata: map[string]interface{}{
			"source_ip": sourceIP,
			"raw_syslog": rawMsg,
			"requires_hitl": true,
		},
		Data: data,
	}

	// Directly publish to internal NATS for AI to analyze
	publishSyslogToAI(item)
}

func extractNginxError(msg string) string {
	// Try to strip standard syslog headers
	re := regexp.MustCompile(`\[error\](.*)`)
	matches := re.FindStringSubmatch(msg)
	if len(matches) > 0 {
		return strings.TrimSpace(matches[0])
	}
	return msg
}

func resolveHostnameByIP(ip string) string {
	var hostname string
	err := database.DB.Raw("SELECT name FROM devices WHERE ip = ? LIMIT 1", ip).Scan(&hostname).Error
	if err != nil || hostname == "" {
		return "Router_" + strings.ReplaceAll(ip, ".", "_")
	}
	return hostname
}

func publishSyslogToAI(item TelemetryItem) {
	if natsConn == nil {
		return
	}
	payloadBytes, err := json.Marshal(item)
	if err != nil {
		return
	}
	// Publish directly to ingestion channel so AI Supervisor can pick it up
	_ = natsConn.Publish("telemetry.syslog", payloadBytes)
	fmt.Printf(" [SYSLOG] Forwarded %s event from %s to AI Diagnostic Engine\n", item.Status, item.Agent)
}
