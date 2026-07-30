package config

import (
	"os"
	"testing"
)

func TestConfigLoad(t *testing.T) {
	// Clean up and set environment variables for deterministic test
	os.Setenv("ORCHESTRATOR_HOST", "127.0.0.99")
	os.Setenv("DB_USER", "postgres")
	os.Setenv("DB_PASSWORD", "postgres")
	defer os.Unsetenv("ORCHESTRATOR_HOST")

	cfg, err := GetConfig()
	if err != nil {
		t.Fatalf("Failed to load config: %v", err)
	}

	if cfg.OrchestratorHost != "127.0.0.99" {
		t.Errorf("Expected OrchestratorHost to be '127.0.0.99', got '%s'", cfg.OrchestratorHost)
	}

	// Verify DB details are set correctly
	if cfg.DBUser != "postgres" {
		t.Errorf("Expected DBUser to be 'postgres', got '%s'", cfg.DBUser)
	}

	if cfg.DBPass != "postgres" {
		t.Errorf("Expected DBPass to be 'postgres', got '%s'", cfg.DBPass)
	}

	t.Logf("Config loaded successfully: OrchestratorPort=%d, DBName=%s", cfg.OrchestratorPort, cfg.DBName)
}
