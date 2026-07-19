//go:build windows
// +build windows

package ingestion

import (
	"context"
	"net"
)

func listenSOReuseport(network, address string) (net.Listener, error) {
	// Windows does not support SO_REUSEPORT. Fall back to standard net.Listen.
	var lc net.ListenConfig
	return lc.Listen(context.Background(), network, address)
}
