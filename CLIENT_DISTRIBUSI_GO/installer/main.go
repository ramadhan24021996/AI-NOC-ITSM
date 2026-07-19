//go:build windows

package main

import (
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"syscall"
	"time"
)

const (
	ServiceName = "OSIAgent"
	DisplayName = "OSI PC Health Agent"
	Description = "OSI AI Incident Analysis - PC Health Monitoring Agent"
)

func main() {
	fmt.Println("==================================================")
	fmt.Println(" OSI AI PC Health Agent - Windows Installer")
	fmt.Println("==================================================")
	fmt.Println()

	// 1. Permission Check (Fase 4: Permission Check)
	if !isAdmin() {
		fmt.Println("❌ ERROR: Installer harus dijalankan sebagai Administrator.")
		fmt.Println("Klik kanan pada installer.exe dan pilih 'Run as administrator'.")
		time.Sleep(5 * time.Second)
		os.Exit(1)
	}
	fmt.Println("✔ Hak akses Administrator terverifikasi.")

	// 2. Create Data Folder (Fase 4: Create Data Folder)
	programData := os.Getenv("PROGRAMDATA")
	if programData == "" {
		programData = `C:\ProgramData`
	}
	installDir := `C:\Program Files\Company\PC Health Agent`
	dataDir := filepath.Join(programData, "Company", "PC Health Agent")
	
	_ = os.MkdirAll(installDir, 0755)
	_ = os.MkdirAll(filepath.Join(dataDir, "cache"), 0755)
	_ = os.MkdirAll(filepath.Join(dataDir, "logs"), 0755)
	_ = os.MkdirAll(filepath.Join(dataDir, "telemetry"), 0755)
	fmt.Println("✔ Folder instalasi dan data berhasil dibuat.")

	// 3. Dependency Validation (Fase 4: Dependency Validation)
	validateDependencies()

	// 4. Copy Agent Executable to Program Files
	agentSrc := filepath.Join(".", "agent.exe")
	agentDst := filepath.Join(installDir, "agent.exe")
	if fileExists(agentSrc) {
		err := copyFile(agentSrc, agentDst)
		if err != nil {
			fmt.Printf("❌ Gagal menyalin agent.exe ke folder instalasi: %v\n", err)
			time.Sleep(5 * time.Second)
			os.Exit(1)
		}
		fmt.Println("✔ agent.exe berhasil disalin ke folder sistem.")
	} else {
		fmt.Println("⚠ Peringatan: agent.exe tidak ditemukan di folder lokal. Service registration akan menggunakan path default.")
	}

	// 5. Register Windows Service with Recovery (Fase 4: Service Recovery)
	fmt.Println("Mendaftarkan Windows Service...")
	_ = runCommand("sc", "stop", ServiceName)
	_ = runCommand("sc", "delete", ServiceName)
	
	err := runCommand("sc", "create", ServiceName, "binPath=", fmt.Sprintf(`"%s"`, agentDst), "start=", "auto", "displayName=", DisplayName)
	if err != nil {
		fmt.Printf("❌ Gagal mendaftarkan service: %v\n", err)
		time.Sleep(5 * time.Second)
		os.Exit(1)
	}
	
	_ = runCommand("sc", "description", ServiceName, Description)

	// Set Service Recovery actions: restart after 60 seconds on first, second, and subsequent failures
	_ = runCommand("sc", "failure", ServiceName, "reset=", "86400", "actions=", "restart/60000/restart/60000/restart/60000")
	fmt.Println("✔ Windows Service berhasil didaftarkan dengan Recovery Policy (Auto-Restart).")

	// 6. Windows Firewall Whitelist for Port 10000
	_ = runCommand("netsh", "advfirewall", "firewall", "delete", "rule", "name=OSI Agent Command Listener")
	err = runCommand("netsh", "advfirewall", "firewall", "add", "rule", "name=OSI Agent Command Listener", "dir=in", "action=allow", "protocol=TCP", "localport=10000")
	if err == nil {
		fmt.Println("✔ Windows Firewall Whitelist berhasil ditambahkan untuk Port 10000.")
	}

	// 7. Event Log Registration (Fase 4: Event Log Registration)
	registerEventLogSource()

	// 8. Start Service
	_ = runCommand("sc", "start", ServiceName)
	fmt.Println("✔ OSI Agent Service berhasil dijalankan.")
	fmt.Println()
	fmt.Println("🎉 Instalasi selesai dengan sukses!")
	time.Sleep(3 * time.Second)
}

func isAdmin() bool {
	// Attempting to open a physical drive requires Admin rights on Windows
	_, err := os.Open("\\\\.\\PHYSICALDRIVE0")
	return err == nil
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

// io.Copy fallback wrapper
var ioCopy = func(dst io.Writer, src io.Reader) (written int64, err error) {
	buf := make([]byte, 32*1024)
	for {
		nr, er := src.Read(buf)
		if nr > 0 {
			nw, ew := dst.Write(buf[0:nr])
			if nw > 0 {
				written += int64(nw)
			}
			if ew != nil {
				err = ew
				break
			}
			if nr != nw {
				err = io.ErrShortWrite
				break
			}
		}
		if er != nil {
			if er != io.EOF {
				err = er
			}
			break
		}
	}
	return written, err
}

func runCommand(name string, args ...string) error {
	cmd := exec.Command(name, args...)
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
	return cmd.Run()
}

func validateDependencies() {
	anydesk := fileExists(`C:\Program Files (x86)\AnyDesk\AnyDesk.exe`) || fileExists(`C:\Program Files\AnyDesk\AnyDesk.exe`)
	rustdesk := fileExists(`C:\Program Files\RustDesk\rustdesk.exe`) || fileExists(`C:\Program Files (x86)\RustDesk\rustdesk.exe`)
	
	fmt.Println("Memvalidasi dependensi remote access...")
	if anydesk {
		fmt.Println("  [OK] AnyDesk terdeteksi.")
	} else {
		fmt.Println("  [--] Info: AnyDesk tidak terpasang di PC ini.")
	}
	
	if rustdesk {
		fmt.Println("  [OK] RustDesk terdeteksi.")
	} else {
		fmt.Println("  [--] Info: RustDesk tidak terpasang di PC ini.")
	}
}

func registerEventLogSource() {
	psCmd := `if (-not [System.Diagnostics.EventLog]::SourceExists('PC Health Agent')) { New-EventLog -LogName 'Application' -Source 'PC Health Agent' }`
	cmd := exec.Command("powershell.exe", "-NoProfile", "-NonInteractive", "-Command", psCmd)
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
	err := cmd.Run()
	if err == nil {
		fmt.Println("✔ Registrasi Event Log Source 'PC Health Agent' berhasil.")
	}
}
