package ai

import (
	"testing"
)

func TestCorrelateIncidentsSignatures(t *testing.T) {
	sup := NewAISupervisor(nil)

	tests := []struct {
		name         string
		alerts       []string
		expectedCode string
	}{
		{
			name:         "Network Gateway Down",
			alerts:       []string{"gateway unreachable", "pc_client offline"},
			expectedCode: "NETWORK_GATEWAY_DOWN",
		},
		{
			name:         "DB Pool Exhausted",
			alerts:       []string{"postgres connection pool exhausted", "deadlock detected"},
			expectedCode: "DATABASE_POOL_EXHAUSTED",
		},
		{
			name:         "Storage Capacity Exhausted",
			alerts:       []string{"disk full on /var/log", "storage 100%"},
			expectedCode: "STORAGE_CAPACITY_EXHAUSTED",
		},
		{
			name:         "Memory Leak OOM Killed",
			alerts:       []string{"out of memory", "oom killer invoked"},
			expectedCode: "MEMORY_LEAK_OOM_KILLED",
		},
		{
			name:         "DNS Resolution Failure",
			alerts:       []string{"bind9 dns resolution failed"},
			expectedCode: "DNS_RESOLUTION_FAILURE",
		},
		{
			name:         "DHCP Lease Exhaustion",
			alerts:       []string{"dhcp lease expired no ip allocated"},
			expectedCode: "DHCP_LEASE_EXHAUSTION",
		},
		{
			name:         "SSL Certificate Expired",
			alerts:       []string{"ssl certificate expired handshake failed"},
			expectedCode: "SSL_CERTIFICATE_EXPIRED",
		},
		{
			name:         "Print Spooler Crash",
			alerts:       []string{"print spooler service stopped spoolsv"},
			expectedCode: "PRINT_SPOOLER_SERVICE_CRASH",
		},
		{
			name:         "NATS Broker Disconnect",
			alerts:       []string{"nats broker disconnected jetstream timeout"},
			expectedCode: "MESSAGE_BROKER_NATS_DISCONNECT",
		},
		{
			name:         "Container Runtime Crash",
			alerts:       []string{"docker daemon container exited crashloopbackoff"},
			expectedCode: "CONTAINER_RUNTIME_CRASH",
		},
		{
			name:         "CPU Compute Exhaustion",
			alerts:       []string{"cpu 100% high load average"},
			expectedCode: "CPU_COMPUTE_EXHAUSTION",
		},
		{
			name:         "Client Service Stopped",
			alerts:       []string{"pc_client heartbeat missing"},
			expectedCode: "CLIENT_SERVICE_STOPPED",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			code, desc := sup.CorrelateIncidents(tt.alerts)
			if code != tt.expectedCode {
				t.Errorf("Expected code %s, got %s (desc: %s)", tt.expectedCode, code, desc)
			} else {
				t.Logf("PASS [%s] => Code: %s | Description: %s", tt.name, code, desc)
			}
		})
	}
}
