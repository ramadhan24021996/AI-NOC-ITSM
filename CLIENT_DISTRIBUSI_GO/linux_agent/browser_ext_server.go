//go:build linux

package main

/*
 * browser_ext_server.go — Linux
 * ================================
 * Modul ini bertanggung jawab atas dua hal:
 *
 * 1. HTTP Listener (Port 10001, 127.0.0.1 saja):
 *    Menerima kiriman data JSON dari Ekstensi Browser (Chrome/Edge/Firefox).
 *    Data yang diterima langsung diteruskan (relay) ke Master Server menggunakan
 *    IP dan Security Key yang sama dengan agent utama — tanpa ekstensi perlu tahu IP server.
 *
 * 2. Auto-Installer Policy (Linux):
 *    Saat agent dijalankan sebagai root (systemd), agent akan otomatis menyuntikkan
 *    file JSON Policy ke /etc/opt/chrome/policies/managed/ dan /etc/opt/edge/policies/managed/
 *    agar browser secara paksa menginstal ekstensi perusahaan (tanpa campur tangan user).
 *
 * ARSITEKTUR KOMUNIKASI:
 *   [Browser Extension] --POST--> [127.0.0.1:10001/ext-telemetry] --relay--> [MASTER_IP:80/browser-events]
 *
 * KONFIGURASI EXTENSION ID (Tanpa Recompile):
 *   Extension ID dibaca dari file: /etc/osi-agent/ext_id.txt
 *   Cara mengisi: echo "abcdefghijklmnopqrstuvwxyz123456" | sudo tee /etc/osi-agent/ext_id.txt
 *   Atau dibuat otomatis saat install oleh INSTALL_AGENT.sh
 */

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"
)

// ── Konstanta Statis Ekstensi ──────────────────────────────────────────────
const (
	ExtUpdateURL = "https://clients2.google.com/service/update2/crx"
	ExtLocalPort = 10001
)

// extChromeID adalah variabel runtime — dibaca dari file konfigurasi, bukan hardcode.
// Ini memungkinkan penggantian Extension ID tanpa recompile agent.
var extChromeID string

// loadExtensionID membaca Extension ID dari file /etc/osi-agent/ext_id.txt
// Fungsi ini dipanggil saat agent startup, sama seperti pola loadServerIP().
func loadExtensionID() {
	idPath := companyDir + "/ext_id.txt"
	if data, err := os.ReadFile(idPath); err == nil {
		id := strings.TrimSpace(string(data))
		if id != "" {
			extChromeID = id
			fmt.Printf("[EXT-CONFIG] ✓ Extension ID berhasil dimuat dari %s: %s\n", idPath, extChromeID)
			return
		}
	}
	// Fallback: cek environment variable (berguna untuk Docker/CI)
	if envID := os.Getenv("OSI_EXT_ID"); envID != "" {
		extChromeID = strings.TrimSpace(envID)
		fmt.Printf("[EXT-CONFIG] Extension ID dimuat dari ENV OSI_EXT_ID: %s\n", extChromeID)
		return
	}
	fmt.Printf("[EXT-CONFIG] PERINGATAN: File ext_id.txt tidak ditemukan di %s.\n", idPath)
	fmt.Println("[EXT-CONFIG]   Auto-install ekstensi browser dinonaktifkan.")
	fmt.Println("[EXT-CONFIG]   Untuk mengaktifkan: echo '<ID_EKSTENSI>' | sudo tee " + idPath)
}

// ── 1. HTTP LISTENER: Menerima data dari Browser Extension ─────────────────

// Helper to validate and set CORS header strictly for Chrome/Mozilla extension origins
func setExtensionCORS(w http.ResponseWriter, r *http.Request) bool {
	origin := r.Header.Get("Origin")
	if origin == "" {
		return true
	}
	isExtension := strings.HasPrefix(origin, "chrome-extension://") || strings.HasPrefix(origin, "moz-extension://")
	if !isExtension {
		return false
	}
	if extChromeID != "" && !strings.Contains(origin, extChromeID) {
		return false
	}
	w.Header().Set("Access-Control-Allow-Origin", origin)
	w.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
	return true
}

func startBrowserExtensionServer() {
	mux := http.NewServeMux()

	// Health-check endpoint (dipakai popup.js ekstensi untuk tampilkan status ONLINE/OFFLINE)
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		if !setExtensionCORS(w, r) {
			http.Error(w, "Forbidden: Invalid extension origin", http.StatusForbidden)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"ok","agent":"OSI-LINUX"}`))
	})

	// Endpoint utama: menerima batch event dari background.js ekstensi
	mux.HandleFunc("/ext-telemetry", func(w http.ResponseWriter, r *http.Request) {
		if !setExtensionCORS(w, r) {
			http.Error(w, "Forbidden: Invalid extension origin", http.StatusForbidden)
			return
		}

		// Preflight CORS
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusOK)
			return
		}
		if r.Method != http.MethodPost {
			http.Error(w, "Method Not Allowed", http.StatusMethodNotAllowed)
			return
		}

		body, err := io.ReadAll(io.LimitReader(r.Body, 1<<20)) // max 1MB
		if err != nil {
			http.Error(w, "Bad Request", http.StatusBadRequest)
			return
		}

		// Parse batch events dari ekstensi
		var payload struct {
			Events []map[string]interface{} `json:"events"`
		}
		if err := json.Unmarshal(body, &payload); err != nil {
			http.Error(w, "Invalid JSON", http.StatusBadRequest)
			return
		}

		// Relay setiap event ke Master Server secara concurrent
		for _, event := range payload.Events {
			// Tambahkan identitas agent agar server tahu dari mana datangnya
			event["relay_agent"]    = agentName
			event["relay_agent_id"] = agentUUID
			event["relay_source"]   = "browser_extension_linux"
			eventCopy := event // closure safety
			go sendHTTPEvent("/browser-events", eventCopy)
		}

		w.WriteHeader(http.StatusAccepted)
		_, _ = w.Write([]byte(`{"status":"accepted"}`))
		fmt.Printf("[EXT-SERVER] Relayed %d browser event(s) to master server.\n", len(payload.Events))
	})

	// Listen HANYA di localhost — ekstensi tidak bisa diakses dari luar jaringan
	listenAddr := fmt.Sprintf("127.0.0.1:%d", ExtLocalPort)
	srv := &http.Server{
		Addr:         listenAddr,
		Handler:      mux,
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 5 * time.Second,
	}

	fmt.Printf("[EXT-SERVER] Browser Extension Listener started at http://%s\n", listenAddr)
	if err := srv.ListenAndServe(); err != nil {
		fmt.Printf("[EXT-SERVER] ERROR: %v\n", err)
	}
}

// ── 2. AUTO-INSTALLER: Injeksi Policy Chrome/Edge di Linux ─────────────────

func autoInstallExtensionLinux() {
	// Muat Extension ID dari file konfigurasi terlebih dahulu
	loadExtensionID()

	if extChromeID == "" {
		fmt.Println("[EXT-POLICY] Auto-install dilewati: Extension ID tidak tersedia.")
		return
	}

	// Hanya jalankan jika agent berjalan sebagai root (UID 0)
	if os.Getuid() != 0 {
		fmt.Println("[EXT-POLICY] Skipping auto-install: agent tidak berjalan sebagai root.")
		return
	}

	policyContent := map[string]interface{}{
		"ExtensionInstallForcelist": []string{
			extChromeID + ";" + ExtUpdateURL,
		},
	}

	policyJSON, err := json.MarshalIndent(policyContent, "", "  ")
	if err != nil {
		fmt.Printf("[EXT-POLICY] ERROR marshal policy JSON: %v\n", err)
		return
	}

	// Target direktori policy untuk Chrome dan Edge di Linux
	targets := []struct {
		browser string
		dir     string
	}{
		{"Chrome", "/etc/opt/chrome/policies/managed"},
		{"Chromium", "/etc/chromium/policies/managed"},
		{"Edge", "/etc/opt/edge/policies/managed"},
	}

	for _, t := range targets {
		if err := os.MkdirAll(t.dir, 0755); err != nil {
			fmt.Printf("[EXT-POLICY] Gagal membuat direktori %s (%s): %v\n", t.dir, t.browser, err)
			continue
		}

		filePath := t.dir + "/osi_agent_force_install.json"
		if err := os.WriteFile(filePath, policyJSON, 0644); err != nil {
			fmt.Printf("[EXT-POLICY] Gagal menulis policy %s (%s): %v\n", filePath, t.browser, err)
		} else {
			fmt.Printf("[EXT-POLICY] ✓ Force-install policy ditulis untuk %s: %s\n", t.browser, filePath)
		}
	}
}
