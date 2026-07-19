//go:build windows

package main

import (
	"crypto/ecdsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"encoding/pem"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"
)

const (
	ServiceName = "OSIAgent"
)

func getUpdateURL() string {
	programData := os.Getenv("PROGRAMDATA")
	if programData == "" {
		programData = `C:\ProgramData`
	}
	configIPPath := filepath.Join(programData, "Company", "PC Health Agent", "config", "server_ip.txt")
	masterIP := "127.0.0.1"
	if data, err := os.ReadFile(configIPPath); err == nil {
		cleaned := strings.TrimSpace(string(data))
		if cleaned != "" {
			masterIP = cleaned
		}
	} else if envMaster := os.Getenv("MASTER_IP"); envMaster != "" {
		masterIP = envMaster
	}
	// Use Nginx standard port 80 routing or dashboard direct port depending on network
	// As we moved agent to port 80, we route it there, but dashboard backend might be different.
	// For now, assuming Nginx redirects /api/fleet to dashboard or we just use 8099/9999.
	// Let's use 80 for proxy or fallback to the masterIP.
	return fmt.Sprintf("http://%s:80/api/fleet/update/manifest", masterIP)
}

type Manifest struct {
	Version      string `json:"version"`
	MinOSVersion string `json:"min_os_version"`
	URL          string `json:"url"`
	SHA256       string `json:"sha256"`
	Signature    string `json:"signature"`
}

const otaPublicKeyPEM = `-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAERFhI5EqVzH0Mx5LfstWtTd+sMgFZ
CEB1fhquk1B+ogfLH1xYAIYGjjJL39RU35K4X+2ndMjweWtsXssbRfrNnw==
-----END PUBLIC KEY-----`

func main() {
	fmt.Println("==================================================")
	fmt.Println(" OSI Agent OTA Updater Service")
	fmt.Println("==================================================")

	updateURL := getUpdateURL()
	fmt.Printf("Mencari pembaruan di: %s\n", updateURL)

	// 1. Fetch Manifest
	manifest, err := fetchManifest(updateURL)
	if err != nil {
		fmt.Printf("❌ Gagal mengambil manifest pembaruan: %v\n", err)
		os.Exit(1)
	}

	// 2. Version Compatibility Check (Fase 4: Version Compatibility)
	if manifest.Version == "2.0.0-Go" { // Already up to date
		fmt.Println("✔ Sistem sudah menggunakan versi terbaru.")
		os.Exit(0)
	}
	fmt.Printf("Pembaruan baru tersedia: Versi %s\n", manifest.Version)

	// 3. Resume Download File (Fase 4: Resume Download)
	programData := os.Getenv("PROGRAMDATA")
	if programData == "" {
		programData = `C:\ProgramData`
	}
	tempDir := filepath.Join(programData, "Company", "PC Health Agent", "temp")
	_ = os.MkdirAll(tempDir, 0755)
	
	tempFile := filepath.Join(tempDir, "agent_new.exe")
	err = downloadFileWithResume(manifest.URL, tempFile)
	if err != nil {
		fmt.Printf("❌ Gagal mendownload file: %v\n", err)
		os.Exit(1)
	}
	fmt.Println("✔ Download selesai.")

	// 4. Digital Signature/SHA-256 Checksum Validation (Fase 4: Digital Signature Verification)
	err = verifyChecksum(tempFile, manifest.SHA256)
	if err != nil {
		fmt.Printf("❌ ERROR: Verifikasi integritas biner gagal: %v\n", err)
		_ = os.Remove(tempFile)
		os.Exit(1)
	}
	fmt.Println("✔ Verifikasi checksum SHA-256 sukses.")

	// Verify ECDSA Signature
	err = verifySignature(manifest.SHA256, manifest.Signature)
	if err != nil {
		fmt.Printf("❌ ERROR: Verifikasi Signature ECDSA gagal: %v\n", err)
		_ = os.Remove(tempFile)
		os.Exit(1)
	}
	fmt.Println("✔ Verifikasi ECDSA OTA Signature sukses.")

	// 5. Swap Binary with Rollback Logic (Fase 4: Rollback)
	installDir := `C:\Program Files\Company\PC Health Agent`
	currentAgent := filepath.Join(installDir, "agent.exe")
	backupAgent := filepath.Join(installDir, "agent_backup.exe")

	fmt.Println("Menghentikan service agent lama...")
	_ = runCommand("sc", "stop", ServiceName)
	time.Sleep(1 * time.Second)

	// Rename current to backup
	if fileExists(currentAgent) {
		_ = os.Remove(backupAgent)
		err = os.Rename(currentAgent, backupAgent)
		if err != nil {
			fmt.Printf("❌ Gagal backup agent lama: %v\n", err)
			_ = runCommand("sc", "start", ServiceName) // restart current
			os.Exit(1)
		}
	}

	// Copy new to current
	err = copyFile(tempFile, currentAgent)
	if err != nil {
		fmt.Printf("❌ Gagal menyalin biner baru: %v. Mencoba rollback...\n", err)
		rollback(backupAgent, currentAgent)
		os.Exit(1)
	}
	_ = os.Remove(tempFile)

	// Start and Validate new Agent
	fmt.Println("Memulai service agent baru...")
	err = runCommand("sc", "start", ServiceName)
	if err != nil {
		fmt.Println("❌ Gagal menjalankan service baru. Memulai rollback...")
		rollback(backupAgent, currentAgent)
		os.Exit(1)
	}

	// Wait and verify if new service remains active (Fail-safe check)
	time.Sleep(3 * time.Second)
	if !isServiceRunning(ServiceName) {
		fmt.Println("❌ Service baru crash setelah startup. Memulai rollback otomatis...")
		rollback(backupAgent, currentAgent)
		os.Exit(1)
	}

	// Clean backup on complete success
	_ = os.Remove(backupAgent)
	fmt.Println("🎉 Pembaruan berhasil diselesaikan!")
}

func fetchManifest(url string) (*Manifest, error) {
	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Get(url)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("server returned status: %d", resp.StatusCode)
	}

	var m Manifest
	err = json.NewDecoder(resp.Body).Decode(&m)
	if err != nil {
		return nil, err
	}
	return &m, nil
}

func downloadFileWithResume(url, filepath string) error {
	var startBytes int64 = 0
	if info, err := os.Stat(filepath); err == nil {
		startBytes = info.Size()
	}

	client := &http.Client{}
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return err
	}

	if startBytes > 0 {
		req.Header.Set("Range", "bytes="+strconv.FormatInt(startBytes, 10)+"-")
		fmt.Printf("Melanjutkan download dari byte %d...\n", startBytes)
	} else {
		fmt.Println("Memulai download biner baru...")
	}

	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	var out *os.File
	if startBytes > 0 && resp.StatusCode == http.StatusPartialContent {
		out, err = os.OpenFile(filepath, os.O_APPEND|os.O_WRONLY, 0644)
	} else {
		out, err = os.Create(filepath)
	}
	if err != nil {
		return err
	}
	defer out.Close()

	_, err = io.Copy(out, resp.Body)
	return err
}

func verifyChecksum(filepath, expectedHash string) error {
	f, err := os.Open(filepath)
	if err != nil {
		return err
	}
	defer f.Close()

	hasher := sha256.New()
	if _, err := io.Copy(hasher, f); err != nil {
		return err
	}

	calculatedHash := hex.EncodeToString(hasher.Sum(nil))
	if strings.ToLower(calculatedHash) != strings.ToLower(expectedHash) {
		return fmt.Errorf("checksum mismatch: got %s, expected %s", calculatedHash, expectedHash)
	}
	return nil
}

func verifySignature(expectedHashHex, signatureBase64 string) error {
	block, _ := pem.Decode([]byte(otaPublicKeyPEM))
	if block == nil {
		return fmt.Errorf("failed to decode public key PEM")
	}
	pub, err := x509.ParsePKIXPublicKey(block.Bytes)
	if err != nil {
		return err
	}
	ecdsaPub, ok := pub.(*ecdsa.PublicKey)
	if !ok {
		return fmt.Errorf("not an ECDSA public key")
	}
	
	hashBytes, err := hex.DecodeString(expectedHashHex)
	if err != nil {
		return err
	}
	
	sigBytes, err := base64.StdEncoding.DecodeString(signatureBase64)
	if err != nil {
		return err
	}
	
	valid := ecdsa.VerifyASN1(ecdsaPub, hashBytes, sigBytes)
	if !valid {
		return fmt.Errorf("invalid ECDSA signature")
	}
	return nil
}

func rollback(backupPath, currentPath string) {
	_ = runCommand("sc", "stop", ServiceName)
	time.Sleep(1 * time.Second)
	if fileExists(backupPath) {
		_ = os.Remove(currentPath)
		_ = os.Rename(backupPath, currentPath)
		_ = runCommand("sc", "start", ServiceName)
		fmt.Println("✔ Rollback ke versi sebelumnya berhasil diselesaikan.")
	} else {
		fmt.Println("❌ Gagal rollback: Biner backup tidak ditemukan!")
	}
}

func isServiceRunning(name string) bool {
	cmd := exec.Command("sc", "query", name)
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
	out, err := cmd.Output()
	if err != nil {
		return false
	}
	return strings.Contains(string(out), "RUNNING")
}

func fileExists(path string) bool {
	info, err := os.Stat(path)
	if err != nil {
		return false
	}
	return !info.IsDir()
}

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()

	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer out.Close()

	_, err = io.Copy(out, in)
	return err
}

func runCommand(name string, args ...string) error {
	cmd := exec.Command(name, args...)
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
	return cmd.Run()
}
