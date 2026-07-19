//go:build windows
// +build windows

package main

import (
	"os/exec"
	"syscall"
)

// SetSysProcAttr configures SysProcAttr to launch a subprocess in a new console on Windows
func SetSysProcAttr(cmd *exec.Cmd) {
	cmd.SysProcAttr = &syscall.SysProcAttr{
		CreationFlags: 0x00000010, // CREATE_NEW_CONSOLE
	}
}
