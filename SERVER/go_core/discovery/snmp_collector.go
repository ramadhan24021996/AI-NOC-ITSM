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
	Metric    string  `json:"metric"`
	Value     float64 `json:"value"`
	Severity  string  `json:"severity"`
}

var OIDMap = map[string]string{
	"1.3.6.1.2.1.25.3.3.1.2.1": "CPU_Load",
	"1.3.6.1.2.1.2.2.1.8.1":    "ifOperStatus_1",
	"1.3.6.1.2.1.2.2.1.10.1":   "ifInOctets_1",
	"1.3.6.1.2.1.2.2.1.16.1":   "ifOutOctets_1",
	"1.3.6.1.2.1.2.2.1.14.1":   "ifInErrors_1",
	"1.3.6.1.2.1.2.2.1.19.1":   "ifOutDiscards_1",
}

func StartSNMPCollector(nc *nats.Conn, community string) {
	fmt.Println("[SNMP] Enterprise Collector engine started.")

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
			time.Sleep(30 * time.Second) // Poll every 30 seconds for live monitoring
		}
	}()
}

func pollDevice(nc *nats.Conn, ip string, community string) {
	snmp := &gosnmp.GoSNMP{
		Target:    ip,
		Port:      161,
		Community: community,
		Version:   gosnmp.Version2c,
		Timeout:   time.Duration(2 * time.Second),
		Retries:   1,
	}

	err := snmp.Connect()
	if err != nil {
		fmt.Printf("[SNMP] Connect(%s) err: %v\n", ip, err)
		return
	}
	defer snmp.Conn.Close()

	oids := []string{
		"1.3.6.1.2.1.2.2.1.8.1",  // ifOperStatus interface 1
		"1.3.6.1.2.1.25.3.3.1.2.1", // CPU load
		"1.3.6.1.2.1.2.2.1.14.1", // ifInErrors
	}
	
	result, err := snmp.Get(oids)
	if err != nil {
		return
	}

	for _, variable := range result.Variables {
		val := 0.0
		switch variable.Type {
		case gosnmp.Integer, gosnmp.Counter32, gosnmp.Counter64, gosnmp.Gauge32:
			val = float64(gosnmp.ToBigInt(variable.Value).Int64())
		}

		metricName := OIDMap[variable.Name]
		if metricName == "" {
			metricName = variable.Name
		}

		severity := "OK"
		if variable.Name == "1.3.6.1.2.1.2.2.1.8.1" && val != 1 { // ifOperStatus != UP
			severity = "CRITICAL"
		} else if variable.Name == "1.3.6.1.2.1.25.3.3.1.2.1" && val > 85.0 {
			severity = "WARNING"
		}

		metric := SNMPMetric{
			Timestamp: time.Now().Format(time.RFC3339),
			Source:    "snmp_engine",
			Host:      ip,
			OID:       variable.Name,
			Metric:    metricName,
			Value:     val,
			Severity:  severity,
		}

		if nc != nil {
			payload, _ := json.Marshal(metric)
			_ = nc.Publish("telemetry.snmp", payload)
		}
	}
}
