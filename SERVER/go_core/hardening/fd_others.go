//go:build !windows
// +build !windows

package hardening

import (
	"os"
)

// GetFDCount returns the active file descriptor count of the current process on Unix/Linux systems
func GetFDCount() (int, error) {
	files, err := os.ReadDir("/proc/self/fd")
	if err != nil {
		return 0, err
	}
	return len(files), nil
}

// GetFDType returns the resource type name monitored
func GetFDType() string {
	return "File Descriptors"
}
