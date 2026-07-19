//go:build !windows
package api

import "os/exec"

func SetSysProcAttr(cmd *exec.Cmd) {}
