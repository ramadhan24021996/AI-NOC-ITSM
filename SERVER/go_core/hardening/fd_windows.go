//go:build windows
// +build windows

package hardening

import (
	"syscall"
	"unsafe"
)

var (
	modkernel32               = syscall.NewLazyDLL("kernel32.dll")
	procGetProcessHandleCount = modkernel32.NewProc("GetProcessHandleCount")
	procGetCurrentProcess     = modkernel32.NewProc("GetCurrentProcess")
)

// GetFDCount returns the active handle count of the current process on Windows
func GetFDCount() (int, error) {
	currentProcess, _, _ := procGetCurrentProcess.Call()
	var handleCount uint32
	r1, _, err := procGetProcessHandleCount.Call(currentProcess, uintptr(unsafe.Pointer(&handleCount)))
	if r1 == 0 {
		return 0, err
	}
	return int(handleCount), nil
}

// GetFDType returns the resource type name monitored
func GetFDType() string {
	return "Handles"
}
