//go:build windows

package main

/*
 * browser_ext_server.go — Windows
 * ================================
 * Modul ini bertanggung jawab atas dua hal:
 *
 * 1. HTTP Listener (Port 10001, 127.0.0.1 saja):
 *    Menerima kiriman data JSON dari Ekstensi Browser (Chrome/Edge/Firefox).
 *    Data yang diterima langsung diteruskan (relay) ke Master Server menggunakan
 *    IP dan Security Key yang sama dengan agent utama — tanpa ekstensi perlu tahu IP server.
 *
 * 2. Auto-Installer Policy (Windows Registry):
 *    Saat agent dijalankan sebagai Administrator, agent akan otomatis menulis ke Registry
 *    Windows di lokasi HKEY_LOCAL_MACHINE untuk memaksa browser menginstal ekstensi
 *    perusahaan secara silent (tanpa campur tangan user).
 *
 * ARSITEKTUR KOMUNIKASI:
 *   [Browser Extension] --POST--> [127.0.0.1:10001/ext-telemetry] --relay--> [MASTER_IP:80/browser-events]
 *
 * KONFIGURASI EXTENSION ID (Tanpa Recompile):
 *   Extension ID dibaca dari file: C:\ProgramData\OSI-Agent\ext_id.txt
 *   File ini dapat diisi otomatis oleh INSTALL_AGENT.bat saat proses instalasi.
 *   Jika file tidak ada, auto-install browser extension dinonaktifkan.
 */

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
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

// loadExtensionID membaca Extension ID dari file C:\ProgramData\OSI-Agent\ext_id.txt
// Fungsi ini dipanggil saat agent startup, sama seperti pola loadServerIP().
func loadExtensionID() {
	// Path config: %PROGRAMDATA%\OSI-Agent\ext_id.txt
	// Sama dengan lokasi companyDir pada agent Windows
	programData := os.Getenv("PROGRAMDATA")
	if programData == "" {
		programData = `C:\ProgramData`
	}
	idPath := filepath.Join(programData, "OSI-Agent", "ext_id.txt")

	if data, err := os.ReadFile(idPath); err == nil {
		id := strings.TrimSpace(string(data))
		if id != "" {
			extChromeID = id
			fmt.Printf("[EXT-CONFIG] ✓ Extension ID berhasil dimuat dari %s: %s\n", idPath, extChromeID)
			return
		}
	}

	// Fallback: cek environment variable (berguna untuk GPO/MDM deployment)
	if envID := os.Getenv("OSI_EXT_ID"); envID != "" {
		extChromeID = strings.TrimSpace(envID)
		fmt.Printf("[EXT-CONFIG] Extension ID dimuat dari ENV OSI_EXT_ID: %s\n", extChromeID)
		return
	}

	fmt.Printf("[EXT-CONFIG] PERINGATAN: File ext_id.txt tidak ditemukan di %s.\n", idPath)
	fmt.Println("[EXT-CONFIG]   Auto-install ekstensi browser dinonaktifkan.")
	fmt.Println("[EXT-CONFIG]   Untuk mengaktifkan: tulis Extension ID ke " + idPath)
}

// ── 1. HTTP LISTENER: Menerima data dari Browser Extension ─────────────────

func startBrowserExtensionServer() {
	mux := http.NewServeMux()

	// Health-check endpoint (dipakai popup.js ekstensi untuk tampilkan status ONLINE/OFFLINE)
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"ok","agent":"OSI-WINDOWS"}`))
	})

	// Endpoint utama: menerima batch event dari background.js ekstensi
	mux.HandleFunc("/ext-telemetry", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type")

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
			event["relay_agent"]    = agentName
			event["relay_agent_id"] = agentUUID
			event["relay_source"]   = "browser_extension_windows"
			eventCopy := event
			go sendHTTPEvent("/browser-events", eventCopy)
		}

		w.WriteHeader(http.StatusAccepted)
		_, _ = w.Write([]byte(`{"status":"accepted"}`))
		fmt.Printf("[EXT-SERVER] Relayed %d browser event(s) to master server.\n", len(payload.Events))
	})

	// Listen HANYA di localhost — tidak dapat diakses dari jaringan luar
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

// ── 2. AUTO-INSTALLER: Injeksi Policy via Windows Registry ─────────────────

func autoInstallExtensionWindows() {
	// Muat Extension ID dari file konfigurasi terlebih dahulu
	loadExtensionID()

	if extChromeID == "" {
		fmt.Println("[EXT-POLICY] Auto-install dilewati: Extension ID tidak tersedia.")
		return
	}

	// Format nilai registry: "ID_EKSTENSI;URL_UPDATE"
	extEntry := extChromeID + ";" + ExtUpdateURL

	// Target registry untuk Chrome dan Edge
	registryTargets := []struct {
		browser string
		keyPath string
	}{
		{
			"Google Chrome",
			`HKEY_LOCAL_MACHINE\Software\Policies\Google\Chrome\ExtensionInstallForcelist`,
		},
		{
			"Microsoft Edge",
			`HKEY_LOCAL_MACHINE\Software\Policies\Microsoft\Edge\ExtensionInstallForcelist`,
		},
	}

	for _, target := range registryTargets {
		// Gunakan `reg add` yang tersedia di semua versi Windows tanpa library tambahan.
		// /f = force overwrite, /t = type string, /v = value name, /d = data
		cmd := exec.Command(
			"reg", "add", target.keyPath,
			"/v", "1",
			"/t", "REG_SZ",
			"/d", extEntry,
			"/f",
		)

		output, err := cmd.CombinedOutput()
		if err != nil {
			fmt.Printf("[EXT-POLICY] Gagal inject registry %s (%s): %v\n  Output: %s\n",
				target.keyPath, target.browser, err, string(output))
		} else {
			fmt.Printf("[EXT-POLICY] ✓ Force-install policy ditulis untuk %s.\n  Registry: %s\n",
				target.browser, target.keyPath)
		}
	}
}

// ── 3. HELPER: Simpan Extension ID dari luar (dipanggil oleh INSTALL_AGENT.bat) ──
// Fungsi ini bisa dipanggil via command-line flag saat install untuk menulis ext_id.txt
func saveExtensionIDToConfig(extID string) error {
	programData := os.Getenv("PROGRAMDATA")
	if programData == "" {
		programData = `C:\ProgramData`
	}
	dir := filepath.Join(programData, "OSI-Agent")
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}
	idPath := filepath.Join(dir, "ext_id.txt")
	return os.WriteFile(idPath, []byte(strings.TrimSpace(extID)+"\n"), 0644)
}
