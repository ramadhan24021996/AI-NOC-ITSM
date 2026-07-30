// portal/main.go
// ---------------
// Single Entry Point untuk Go Portal Server.
// Dipindahkan dari dashboard_server.go agar tanggung jawab inisialisasi
// dan routing bisa dibaca dengan jelas tanpa menelusuri 1.690 baris.
//
// Alur Startup:
//   1. Load Config
//   2. Init Database
//   3. Init Redis & NATS
//   4. Start Background Workers (Telemetry, HealthCheck, RLOF Decay)
//   5. Setup Gin Router & Register Routes
//   6. Serve HTTP
package main

import (
	"fmt"
	"os"
)

// main adalah entry point tunggal portal.
// Semua logika ada di fungsi-fungsi terpisah di dashboard_server.go.
// File ini hanya sebagai "wiring" yang bersih dan mudah dibaca.
func main() {
	fmt.Println("╔═══════════════════════════════════════════════════╗")
	fmt.Println("║       AI-NOC-ITSM Portal Server                  ║")
	fmt.Println("║       Pragmatic Modularization — Phase 3          ║")
	fmt.Println("╚═══════════════════════════════════════════════════╝")

	// Delegasikan inisialisasi ke runPortal() di dashboard_server.go
	// agar dashboard_server.go tetap berisi semua handler & logika.
	if err := runPortal(); err != nil {
		fmt.Printf("[FATAL] Portal failed to start: %v\n", err)
		os.Exit(1)
	}
}
