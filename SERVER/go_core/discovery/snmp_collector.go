package discovery

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/gosnmp/gosnmp"
	"github.com/nats-io/nats.go"
	"go_incident_analysis/SERVER/go_core/database"
)

type SNMPMetric struct {
	Timestamp string  `json:"timestamp"`
	Source    string  `json:"source"`
	Host      string  `json:"host"`
	OID       string  `json:"oid"`
	Value     float64 `json:"value"`
	Severity  string  `json:"severity"`
}

var OIDMap = map[string]string{
	"1.3.6.1.2.1.25.3.3.1.2": "CPU_Load",
	"1.3.6.1.2.1.2.2.1.10":   "ifInOctets",
	"1.3.6.1.2.1.2.2.1.16":   "ifOutOctets",
	"1.3.6.1.2.1.2.2.1.8":    "ifOperStatus",
}

func StartSNMPCollector(nc *nats.Conn, community string) {
	fmt.Println("[SNMP] Collector engine started.")

	go func() {
		for {
			if database.DB != nil {
				var dbDevices []database.Device
				database.DB.Where("status = ?", "ONLINE").Find(&dbDevices)
				for _, d := range dbDevices {
					if d.IP != "" {
						pollDevice(nc, d.IP, community)
					}
				}
			}
			time.Sleep(60 * time.Second) // Poll every 60 seconds
		}
	}()
}

func pollDevice(nc *nats.Conn, ip string, community string) {
	gosnmp.Default.Target = ip
	gosnmp.Default.Community = community
	gosnmp.Default.Timeout = time.Duration(2 * time.Second)

	err := gosnmp.Default.Connect()
	if err != nil {
		fmt.Printf("[SNMP] Connect() err: %v\n", err)
		return
	}
	defer gosnmp.Default.Conn.Close()

	oids := []string{"1.3.6.1.2.1.2.2.1.8.1"} // Interface 1 status
	result, err := gosnmp.Default.Get(oids)
	if err != nil {
		// Log but continue, could be timeout
		return
	}

	for _, variable := range result.Variables {
		val := 0.0
		switch variable.Type {
		case gosnmp.Integer:
			val = float64(variable.Value.(int))
		case gosnmp.OctetString:
			// Convert bytes if needed
		}

		severity := "LOW"
		if val != 1 { // ifOperStatus != up
			severity = "CRITICAL"
		}

		metric := SNMPMetric{
			Timestamp: time.Now().Format(time.RFC3339),
			Source:    "snmp",
			Host:      ip,
			OID:       variable.Name,
			Value:     val,
			Severity:  severity,
		}
		
		payload, _ := json.Marshal(metric)
		nc.Publish("telemetry.snmp", payload)
	}
}
