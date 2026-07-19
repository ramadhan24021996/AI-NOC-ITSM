package discovery

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/nats-io/nats.go"
	"gopkg.in/mcuadros/go-syslog.v2"
)

type SyslogMessage struct {
	Timestamp string `json:"timestamp"`
	Source    string `json:"source"`
	Host      string `json:"host"`
	Severity  string `json:"severity"`
	Facility  string `json:"facility"`
	Message   string `json:"message"`
}

func StartSyslogReceiver(nc *nats.Conn, port string) {
	channel := make(syslog.LogPartsChannel)
	handler := syslog.NewChannelHandler(channel)

	server := syslog.NewServer()
	server.SetFormat(syslog.Automatic)
	server.SetHandler(handler)
	
	err := server.ListenUDP("0.0.0.0:" + port)
	if err != nil {
		fmt.Printf("[Syslog] Error starting receiver on port %s: %v\n", port, err)
		return
	}
	server.ListenTCP("0.0.0.0:" + port)
	server.Boot()

	fmt.Printf("[Syslog] Receiver started on port %s\n", port)

	go func(channel syslog.LogPartsChannel) {
		for logParts := range channel {
			// Extract standard Syslog parts
			msgStr, _ := logParts["content"].(string)
			host, _ := logParts["hostname"].(string)
			sev, _ := logParts["severity"].(int)
			fac, _ := logParts["facility"].(int)

			if host == "" {
				host, _ = logParts["client"].(string)
			}

			severityStr := mapSeverity(sev)
			
			syslogMsg := SyslogMessage{
				Timestamp: time.Now().Format(time.RFC3339),
				Source:    "syslog",
				Host:      host,
				Severity:  severityStr,
				Facility:  fmt.Sprintf("%d", fac),
				Message:   msgStr,
			}

			payload, _ := json.Marshal(syslogMsg)
			err := nc.Publish("telemetry.syslog", payload)
			if err != nil {
				fmt.Printf("[Syslog] Publish error: %v\n", err)
			}
		}
	}(channel)

	server.Wait()
}

func mapSeverity(sev int) string {
	switch sev {
	case 0, 1, 2:
		return "CRITICAL"
	case 3:
		return "HIGH"
	case 4:
		return "MEDIUM"
	default:
		return "LOW"
	}
}
