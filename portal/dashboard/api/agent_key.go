package api

import (
	"fmt"
	"os"

	"go_incident_analysis/SERVER/go_core/security"
)

// agentHMACKey returns the runtime agent command-signing key ([K-01]).
// It never falls back to a literal. With no key it returns nil, which makes
// every signature invalid so agents reject the command (fail-closed, P8).
func agentHMACKey() []byte {
	sm, err := security.GetSecurityManager()
	if err != nil || sm == nil || len(sm.GetKey()) == 0 {
		fmt.Fprintf(os.Stderr, "[SECURITY] agent HMAC key unavailable: %v; command will be rejected\n", err)
		return nil
	}
	return sm.GetKey()
}
