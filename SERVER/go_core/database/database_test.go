package database

import (
	"testing"
)

func TestInitDatabase(t *testing.T) {
	// Initialize database
	db, err := InitDatabase()
	if err != nil {
		t.Fatalf("Failed to initialize database: %v", err)
	}

	sqlDB, err := db.DB()
	if err != nil {
		t.Fatalf("Failed to access underlying sql.DB: %v", err)
	}

	err = sqlDB.Ping()
	if err != nil {
		t.Fatalf("Failed to ping database: %v", err)
	}

	t.Log("Successfully connected and pinged database!")

	// Query some sites
	var sites []FleetSite
	result := db.Limit(5).Find(&sites)
	if result.Error != nil {
		t.Logf("Warning: Failed to query fleet_sites: %v", result.Error)
	} else {
		t.Logf("Query fleet_sites succeeded, found %d sites:", len(sites))
		for _, s := range sites {
			t.Logf(" - Site: %s (Gateway: %s)", s.SiteName, s.RouterIP)
		}
	}

	// Query some devices
	var devices []Device
	result = db.Limit(5).Find(&devices)
	if result.Error != nil {
		t.Logf("Warning: Failed to query devices: %v", result.Error)
	} else {
		t.Logf("Query devices succeeded, found %d devices:", len(devices))
		for _, d := range devices {
			t.Logf(" - Device: %s (IP: %s, Status: %s)", d.Name, d.IP, d.Status)
		}
	}

	// Query some fleet_devices
	var fleetDevices []FleetDevice
	result = db.Limit(5).Find(&fleetDevices)
	if result.Error != nil {
		t.Logf("Warning: Failed to query fleet_devices: %v", result.Error)
	} else {
		t.Logf("Query fleet_devices succeeded, found %d PCs:", len(fleetDevices))
		for _, fd := range fleetDevices {
			t.Logf(" - PC: %s (Status: %s, RustDeskID: %s)", fd.PCName, fd.Status, fd.RustdeskID)
		}
	}
}

func TestCheckDatabaseHealth(t *testing.T) {
	// Initialize database first
	_, err := InitDatabase()
	if err != nil {
		t.Fatalf("Failed to initialize database: %v", err)
	}

	err = CheckDatabaseHealth()
	if err != nil {
		t.Fatalf("Database health check failed: %v", err)
	}
	t.Log("Database connection is healthy!")
}
