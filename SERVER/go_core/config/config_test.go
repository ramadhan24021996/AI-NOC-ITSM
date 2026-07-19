package config

import (
	"os"
	"testing"
)

func TestConfigLoad(t *testing.T) {
	// Clean up environment variables
	os.Setenv("ORCHESTRATOR_HOST", "127.0.0.99")
	defer os.Unsetenv("ORCHESTRATOR_HOST")

	cfg, err := GetConfig()
	if err != nil {
		t.Fatalf("Failed to load config: %v", err)
	}

	if cfg.OrchestratorHost != "127.0.0.99" {
		t.Errorf("Expected OrchestratorHost to be '127.0.0.99', got '%s'", cfg.OrchestratorHost)
	}

	// Verify DB details are decrypted
	if cfg.DBUser != "postgres" {
		t.Errorf("Expected decrypted DBUser to be 'postgres', got '%s'", cfg.DBUser)
	}

	if cfg.DBPass != "postgres" {
		t.Errorf("Expected decrypted DBPass to be 'postgres', got '%s'", cfg.DBPass)
	}

	t.Logf("Config loaded successfully: OrchestratorPort=%d, DBName=%s", cfg.OrchestratorPort, cfg.DBName)
}
