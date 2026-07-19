//go:build linux

package main

import (
	"encoding/json"
	"fmt"
	"os/exec"
	"strings"
)

// DeepTelemetry defines the comprehensive endpoint observability metrics for Linux (Sprint T)
type DeepTelemetry struct {
	LinuxServices map[string]ServiceDetails `json:"linux_services"`
	TopProcesses  []ProcessDetails          `json:"top_processes"`
	EventLogs     []EventLogEntry           `json:"event_logs"`
	NetworkState  NetworkState              `json:"network_state"`
	Security      SecurityState             `json:"security_state"`
	Disk          DiskState                 `json:"disk_state"`
	UserSessions  []UserSession             `json:"user_sessions"`
}

type ServiceDetails struct {
	Status        string `json:"status"`
	StartupType   string `json:"startup_type"`
	PID           string `json:"pid,omitempty"`
	RestartCount  int    `json:"restart_count"`
	ExitCode      string `json:"exit_code"`
}

type ProcessDetails struct {
	Name        string `json:"name"`
	PID         string `json:"pid"`
	CPU         string `json:"cpu"`
	RAM         string `json:"ram"`
	ThreadCount string `json:"thread_count"`
	HandleCount string `json:"handle_count"`
}

type EventLogEntry struct {
	Source        string `json:"source"`
	EventID       string `json:"event_id"`
	Level         string `json:"level"`
	Message       string `json:"message"`
	TimeGenerated string `json:"time_generated"`
}

type NetworkState struct {
	DefaultGateway string `json:"default_gateway"`
	DNSServers     string `json:"dns_servers"`
	DHCPEnabled    bool   `json:"dhcp_enabled"`
	TCPConnections int    `json:"tcp_connections"`
	UDPListeners   int    `json:"udp_listeners"`
	FirewallStatus string `json:"firewall_status"`
}

type SecurityState struct {
	AVStatus       string `json:"av_status"`
	Firewall       string `json:"firewall"`
	AppArmor       string `json:"apparmor"`
}

type DiskState struct {
	SMARTStatus    string `json:"smart_status"`
	FreeSpace      string `json:"free_space"`
	Fragmentation  string `json:"fragmentation"`
}

type UserSession struct {
	User      string `json:"user"`
	State     string `json:"state"`
	IdleTime  string `json:"idle_time"`
}

func collectDeepTelemetry() DeepTelemetry {
	var dt DeepTelemetry

	// 1. Linux Services
	dt.LinuxServices = getLinuxServicesInfo()

	// 2. Top Processes
	dt.TopProcesses = getTopProcesses()

	// 4. Security State
	dt.Security = getSecurityState()

	// 5. Network State
	dt.NetworkState = getNetworkState()

	return dt
}

func executeBash(script string) string {
	cmd := exec.Command("bash", "-c", script)
	out, err := cmd.Output()
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(out))
}

func getLinuxServicesInfo() map[string]ServiceDetails {
	services := make(map[string]ServiceDetails)
	// Example services: sshd, nginx, docker, systemd-journald
	script := `systemctl show sshd nginx docker systemd-journald --property=Id,ActiveState,SubState,MainPID,ExecMainStatus --no-page`
	out := executeBash(script)
	
	// Poor man's parsing for systemctl show
	var currentName string
	var svc ServiceDetails
	for _, line := range strings.Split(out, "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			if currentName != "" {
				services[currentName] = svc
				currentName = ""
				svc = ServiceDetails{}
			}
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		if len(parts) == 2 {
			k, v := parts[0], parts[1]
			switch k {
			case "Id":
				currentName = v
			case "ActiveState":
				svc.Status = v
			case "MainPID":
				svc.PID = v
			case "ExecMainStatus":
				svc.ExitCode = v
			}
		}
	}
	if currentName != "" {
		services[currentName] = svc
	}
	
	return services
}

func getTopProcesses() []ProcessDetails {
	var procs []ProcessDetails
	script := `ps -eo comm,pid,pcpu,pmem,nlwp --sort=-pcpu | head -n 11 | tail -n 10 | awk '{print "{\"Name\":\""$1"\",\"Id\":\""$2"\",\"CPU\":\""$3"\",\"WorkingSet\":\""$4"\",\"ThreadCount\":\""$5"\"}"}' | jq -s '.'`
	out := executeBash(script)
	if out != "" {
		var result []map[string]interface{}
		if err := json.Unmarshal([]byte(out), &result); err == nil {
			for _, p := range result {
				name, _ := p["Name"].(string)
				procs = append(procs, ProcessDetails{
					Name:        name,
					PID:         fmt.Sprintf("%v", p["Id"]),
					CPU:         fmt.Sprintf("%v", p["CPU"]),
					RAM:         fmt.Sprintf("%v", p["WorkingSet"]),
					ThreadCount: fmt.Sprintf("%v", p["ThreadCount"]),
					HandleCount: "N/A", // Not easily available in simple ps on linux
				})
			}
		}
	}
	return procs
}

func getSecurityState() SecurityState {
	return SecurityState{
		AVStatus: executeBash(`systemctl is-active clamav-daemon || echo "Inactive"`),
		Firewall: executeBash(`ufw status | grep Status | awk '{print $2}' || iptables -L -n | wc -l`),
		AppArmor: executeBash(`aa-status --enabled && echo "Enabled" || echo "Disabled"`),
	}
}

func getNetworkState() NetworkState {
	return NetworkState{
		DefaultGateway: executeBash(`ip route | grep default | awk '{print $3}'`),
		DNSServers:     executeBash(`grep nameserver /etc/resolv.conf | awk '{print $2}' | paste -sd "," -`),
		FirewallStatus: "Check Security State",
	}
}
