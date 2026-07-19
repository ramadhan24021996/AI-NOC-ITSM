//go:build !windows
// +build !windows

package main

import (
	"os/exec"
)

// SetSysProcAttr does nothing on Unix/Linux systems where CreationFlags are not supported
func SetSysProcAttr(cmd *exec.Cmd) {
	// No-op for Unix/Linux
}
