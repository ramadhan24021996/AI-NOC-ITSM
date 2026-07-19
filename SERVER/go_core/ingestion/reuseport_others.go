//go:build !windows
// +build !windows

package ingestion

import (
	"context"
	"net"
	"syscall"
)

const soReusePort = 15 // syscall.SO_REUSEPORT on Linux

func listenSOReuseport(network, address string) (net.Listener, error) {
	lc := net.ListenConfig{
		Control: func(network, address string, c syscall.RawConn) error {
			var opErr error
			err := c.Control(func(fd uintptr) {
				opErr = syscall.SetsockoptInt(int(fd), syscall.SOL_SOCKET, soReusePort, 1)
			})
			if err != nil {
				return err
			}
			return opErr
		},
	}
	return lc.Listen(context.Background(), network, address)
}
