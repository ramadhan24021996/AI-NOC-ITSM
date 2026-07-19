package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

var (
	OrchestratorHost string
	OrchestratorPort int
	SecurityKey      []byte
	IngestDir        string
	ArchiveDir       string
)

func getEnv(key, fallback string) string {
	if value, exists := os.LookupEnv(key); exists {
		return value
	}
	return fallback
}

func initEnv() {
	OrchestratorHost = getEnv("DB_HOST", "postgres")
	if OrchestratorHost == "postgres" || OrchestratorHost == "" {
		// If running locally, default to 127.0.0.1
		OrchestratorHost = "127.0.0.1"
	}
	OrchestratorPort = 18800 // Ingestion Server Port

	// Locate Project Root to load security key
	SecurityKey = []byte(getEnv("OSI_SECURITY_KEY", "gAAAAABqBKK7az-y_l5fNA2vSgnwxIN0eaZWvqXhTwjWTXhGxXtzff4_iHYcL1u5VrmlwwnSxvwWNnlscwcn0Ph81c7PUGS9Ag=="))

	// Resolve Ingest directories
	ftpBasePaths := []string{
		`D:\FTP_Share\DATA\JSON`,
		filepath.Join(".", "server", "ftp_share", "DATA", "JSON"),
		filepath.Join(".", "ftp_share", "DATA", "JSON"),
	}

	for _, path := range ftpBasePaths {
		if _, err := os.Stat(path); err == nil {
			IngestDir = path
			break
		}
	}

	if IngestDir == "" {
		IngestDir = ftpBasePaths[1] // Fallback
		_ = os.MkdirAll(IngestDir, 0755)
	}

	ArchiveDir = filepath.Join(IngestDir, "processed")
	_ = os.MkdirAll(ArchiveDir, 0755)

	fmt.Printf("[COLLECTOR] Monitoring directory: %s\n", IngestDir)
	fmt.Printf("[COLLECTOR] Forwarding Target: %s:%d\n", OrchestratorHost, OrchestratorPort)
}

func forwardToOrchestrator(payload []byte) bool {
	serverAddr := net.JoinHostPort(OrchestratorHost, strconv.Itoa(OrchestratorPort))
	conn, err := net.DialTimeout("tcp", serverAddr, 5*time.Second)
	if err != nil {
		fmt.Printf("[COLLECTOR ERROR] Socket connection to orchestrator failed: %v\n", err)
		return false
	}
	defer conn.Close()

	_ = conn.SetWriteDeadline(time.Now().Add(5 * time.Second))
	_, err = conn.Write(append(payload, '\n'))
	return err == nil
}

func processTelemetryFiles() {
	err := filepath.Walk(IngestDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return nil
		}

		// Skip folders and process only json files
		if info.IsDir() {
			// Skip the processed archive directory
			if info.Name() == "processed" {
				return filepath.SkipDir
			}
			return nil
		}

		if !strings.HasSuffix(strings.ToLower(info.Name()), ".json") {
			return nil
		}

		fmt.Printf("[COLLECTOR] Processing file: %s\n", info.Name())

		fileBytes, err := os.ReadFile(path)
		if err != nil {
			fmt.Printf("[COLLECTOR ERROR] Failed to read %s: %v\n", info.Name(), err)
			return nil
		}

		var payload map[string]interface{}
		if err := json.Unmarshal(fileBytes, &payload); err != nil {
			fmt.Printf("[COLLECTOR ERROR] Corrupted JSON in %s, skipping.\n", info.Name())
			return nil
		}

		// Decrypt/Base64 decode if it contains encrypted_data
		if encData, ok := payload["encrypted_data"].(string); ok {
			decBytes, err := base64.StdEncoding.DecodeString(encData)
			if err != nil {
				decBytes, err = base64.RawStdEncoding.DecodeString(encData)
			}
			if err != nil {
				fmt.Printf("[COLLECTOR ERROR] Failed base64 decode in %s: %v\n", info.Name(), err)
				return nil
			}

			var decPayload map[string]interface{}
			if err := json.Unmarshal(decBytes, &decPayload); err != nil {
				fmt.Printf("[COLLECTOR ERROR] Failed to parse decrypted JSON in %s: %v\n", info.Name(), err)
				return nil
			}
			payload = decPayload
		}

		// Normalize fields
		agent, ok := payload["agent"].(string)
		if !ok || agent == "" {
			if agentName, ok := payload["agent_name"].(string); ok && agentName != "" {
				payload["agent"] = agentName
				agent = agentName
			} else if agentID, ok := payload["agent_id"].(string); ok && agentID != "" {
				payload["agent"] = agentID
				agent = agentID
			} else if compName, ok := payload["computer_name"].(string); ok && compName != "" {
				payload["agent"] = compName
				agent = compName
			} else {
				payload["agent"] = "Unknown_Device"
				agent = "Unknown_Device"
			}
		}

		if _, ok := payload["layer"]; !ok {
			payload["layer"] = 7
		}
		payload["is_distributor_agent"] = true

		if _, ok := payload["schema_version"]; !ok {
			payload["schema_version"] = "1.0.0"
		}

		// Normalize timestamp
		tsVal, ok := payload["timestamp"]
		tsStr := ""
		if ok {
			if tNum, ok := tsVal.(float64); ok {
				tsStr = strconv.FormatInt(int64(tNum), 10)
			} else if tStr, ok := tsVal.(string); ok {
				tsStr = tStr
			}
		}
		if tsStr == "" {
			tsStr = strconv.FormatInt(time.Now().Unix(), 10)
			payload["timestamp"] = tsStr
		}

		// Standardize status
		if status, ok := payload["status"].(string); !ok || strings.TrimSpace(status) == "" {
			status = "OK"
			if printers, ok := payload["printers"].(map[string]interface{}); ok {
				p1, _ := printers["printer_1_status"].(string)
				p2, _ := printers["printer_2_status"].(string)
				if (p1 != "" && p1 != "OK") || (p2 != "" && p2 != "OK") {
					status = "WARNING"
				}
			}
			payload["status"] = status
		}

		// Standardize metadata
		metadata := make(map[string]interface{})
		reservedKeys := map[string]bool{
			"agent":                true,
			"layer":                true,
			"status":               true,
			"timestamp":            true,
			"token":                true,
			"schema_version":       true,
			"type":                 true,
			"event_id":             true,
			"correlation_id":       true,
			"tenant_id":            true,
			"is_distributor_agent": true,
		}

		for k, v := range payload {
			if !reservedKeys[k] {
				metadata[k] = v
				delete(payload, k)
			}
		}
		payload["metadata"] = metadata

		// Compute HMAC Token
		msgToSign := fmt.Sprintf("%s:%s", agent, tsStr)
		mac := hmac.New(sha256.New, SecurityKey)
		mac.Write([]byte(msgToSign))
		token := hex.EncodeToString(mac.Sum(nil))
		payload["token"] = token

		// Forward payload
		payloadBytes, err := json.Marshal(payload)
		if err != nil {
			return nil
		}

		success := forwardToOrchestrator(payloadBytes)
		if success {
			// Archive processed file
			relPath, _ := filepath.Rel(IngestDir, filepath.Dir(path))
			targetDir := ArchiveDir
			if relPath != "." && relPath != "" {
				targetDir = filepath.Join(ArchiveDir, relPath)
				_ = os.MkdirAll(targetDir, 0755)
			}

			archivePath := filepath.Join(targetDir, info.Name())
			if _, err := os.Stat(archivePath); err == nil {
				// Avoid duplicate filename collision in archive
				ext := filepath.Ext(info.Name())
				base := strings.TrimSuffix(info.Name(), ext)
				ts := time.Now().Format("20060102_150405")
				archivePath = filepath.Join(targetDir, fmt.Sprintf("%s_%s%s", base, ts, ext))
			}

			err = os.Rename(path, archivePath)
			if err != nil {
				// Fallback to copy and delete
				if copyFile(path, archivePath) {
					_ = os.Remove(path)
				}
			}
			fmt.Printf("[COLLECTOR] Success: Telemetry from %s processed and archived.\n", info.Name())
		} else {
			fmt.Printf("[COLLECTOR] Failed to forward %s, keeping in queue.\n", info.Name())
		}

		return nil
	})

	if err != nil {
		fmt.Printf("[COLLECTOR ERROR] Walk failed: %v\n", err)
	}
}

func copyFile(src, dst string) bool {
	in, err := os.Open(src)
	if err != nil {
		return false
	}
	defer in.Close()

	out, err := os.Create(dst)
	if err != nil {
		return false
	}
	defer out.Close()

	_, err = io.Copy(out, in)
	return err == nil
}

func cleanOldArchives() {
	cutoff := time.Now().Add(-24 * time.Hour)
	err := filepath.Walk(ArchiveDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return nil
		}
		if !info.IsDir() && strings.HasSuffix(strings.ToLower(info.Name()), ".json") {
			if info.ModTime().Before(cutoff) {
				_ = os.Remove(path)
				fmt.Printf("[COLLECTOR] Cleaned up old archive file: %s\n", info.Name())
			}
		}
		return nil
	})
	if err != nil {
		fmt.Printf("[COLLECTOR ERROR] Archive clean failed: %v\n", err)
	}
}

func main() {
	initEnv()
	fmt.Println("[COLLECTOR] Telemetry Ingestor Loop started. Checking every 2 seconds.")

	for {
		processTelemetryFiles()
		cleanOldArchives()
		time.Sleep(2 * time.Second)
	}
}
