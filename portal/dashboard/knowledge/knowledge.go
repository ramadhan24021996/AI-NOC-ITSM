package knowledge

import (
	"encoding/csv"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

// KnowledgeItem represents a single issue-resolution entry in the custom knowledge base.
type KnowledgeItem struct {
	ID               string   `json:"id"`
	Category         string   `json:"category"`
	Keywords         []string `json:"keywords"`
	Symptom          string   `json:"symptom"`
	RootCause        string   `json:"root_cause"`
	RemediationSteps []string `json:"remediation_steps"`
}

// KnowledgeEngine manages isolated RAG matching without touching existing core databases.
type KnowledgeEngine struct {
	mu           sync.RWMutex
	items        []KnowledgeItem
	filePath     string
	watchDir     string
	processedDir string
}

var GlobalEngine = &KnowledgeEngine{
	items: []KnowledgeItem{},
}

// Init initializes the knowledge engine and starts the dedicated Watch Folder background worker.
func (e *KnowledgeEngine) Init(dataDir string) {
	e.mu.Lock()

	if dataDir == "" {
		dataDir = "."
	}
	e.filePath = filepath.Join(dataDir, "custom_knowledge.json")
	e.watchDir = filepath.Join(dataDir, "knowledge_imports")
	e.processedDir = filepath.Join(e.watchDir, "processed")

	// Auto-create watch folder and processed subfolder
	_ = os.MkdirAll(e.watchDir, 0755)
	_ = os.MkdirAll(e.processedDir, 0755)

	if _, err := os.Stat(e.filePath); os.IsNotExist(err) {
		// Create default initial knowledge file if missing
		e.items = []KnowledgeItem{
			{
				ID:        "KB-NET-001",
				Category:  "NETWORK",
				Keywords:  []string{"koneksi", "network", "ping", "rto", "terputus", "wifi", "lan", "disconnect", "unreachable"},
				Symptom:   "Koneksi Jaringan Terputus / Respon Lambat (Ping RTO)",
				RootCause: "Disrupsi Jalur Gateway Router / Cable LAN Longgar",
				RemediationSteps: []string{
					"Periksa fisik kabel LAN di bagian belakang PC Klien.",
					"Matikan & nyalakan kembali Wi-Fi / Adapter Jaringan (tunggu 5 detik).",
					"Lakukan Restart pada PC Klien jika koneksi belum pulih.",
					"Klik 'Hubungi NOC' jika masalah masih berlanjut.",
				},
			},
			{
				ID:        "KB-SYS-001",
				Category:  "SYSTEM",
				Keywords:  []string{"lemot", "slow", "lag", "ram", "cpu", "memori", "hang", "freeze", "macet"},
				Symptom:   "Performa PC Klien Sangat Lambat (High CPU/RAM Usage)",
				RootCause: "Penumpukan Alokasi Memori RAM / Proses Background Membengkak",
				RemediationSteps: []string{
					"Tutup tab browser atau aplikasi kerja yang tidak digunakan.",
					"Periksa Task Manager untuk melihat aplikasi yang menggunakan RAM tinggi.",
					"Lakukan restart PC Klien untuk membersihkan alokasi cache RAM.",
				},
			},
			{
				ID:        "KB-PRN-001",
				Category:  "HARDWARE",
				Keywords:  []string{"printer", "print", "cetak", "spooler", "paper", "macet", "kertas"},
				Symptom:   "Printer Offline / Dokumen Tidak Dapat Dicetak",
				RootCause: "Service Print Spooler Terhenti / Kabel USB Printer Lepas",
				RemediationSteps: []string{
					"Pastikan kabel USB printer terhubung dengan baik ke PC.",
					"Pastikan tombol Power printer dalam posisi menyala.",
					"Restart service Print Spooler atau restart PC Klien.",
				},
			},
		}
		e.saveToFileLocked()
	} else {
		data, err := os.ReadFile(e.filePath)
		if err == nil {
			var loaded []KnowledgeItem
			if jsonErr := json.Unmarshal(data, &loaded); jsonErr == nil {
				e.items = loaded
			}
		}
	}
	e.mu.Unlock()

	// Start background watcher loop (Scans knowledge_imports folder every 10s)
	go e.startFolderWatcherLoop()
}

// startFolderWatcherLoop scans the knowledge_imports folder for CSV/JSON files automatically.
func (e *KnowledgeEngine) startFolderWatcherLoop() {
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()

	// Perform initial scan immediately on startup
	e.scanAndImportWatchFolder()

	for range ticker.C {
		e.scanAndImportWatchFolder()
	}
}

// scanAndImportWatchFolder checks for new files in knowledge_imports/
func (e *KnowledgeEngine) scanAndImportWatchFolder() {
	if e.watchDir == "" {
		return
	}

	files, err := os.ReadDir(e.watchDir)
	if err != nil {
		return
	}

	for _, entry := range files {
		if entry.IsDir() {
			continue
		}

		filename := entry.Name()
		ext := strings.ToLower(filepath.Ext(filename))
		if ext != ".csv" && ext != ".json" && ext != ".txt" {
			continue
		}

		fullPath := filepath.Join(e.watchDir, filename)
		fmt.Printf("[KNOWLEDGE WATCHER] Found new knowledge import file: %s\n", filename)

		importedItems, parseErr := e.parseImportFile(fullPath, ext)
		if parseErr == nil && len(importedItems) > 0 {
			count, _ := e.ImportItems(importedItems)
			fmt.Printf("[KNOWLEDGE WATCHER] Successfully imported %d items from %s!\n", count, filename)
		} else if parseErr != nil {
			fmt.Printf("[KNOWLEDGE WATCHER] Error parsing %s: %v\n", filename, parseErr)
		}

		// Move processed file to knowledge_imports/processed/
		destName := fmt.Sprintf("%s_%d%s", strings.TrimSuffix(filename, ext), time.Now().Unix(), ext)
		destPath := filepath.Join(e.processedDir, destName)
		_ = os.Rename(fullPath, destPath)
	}
}

// parseImportFile converts CSV or JSON files into KnowledgeItem objects
func (e *KnowledgeEngine) parseImportFile(filePath string, ext string) ([]KnowledgeItem, error) {
	fileData, err := os.ReadFile(filePath)
	if err != nil {
		return nil, err
	}

	if ext == ".json" {
		var items []KnowledgeItem
		err := json.Unmarshal(fileData, &items)
		return items, err
	}

	// Parse CSV or delimited text
	r := csv.NewReader(strings.NewReader(string(fileData)))
	r.FieldsPerRecord = -1

	rows, err := r.ReadAll()
	if err != nil || len(rows) < 2 {
		return nil, fmt.Errorf("invalid CSV or empty content")
	}

	header := rows[0]
	colIdx := map[string]int{
		"symptom":     -1,
		"root_cause":  -1,
		"remediation": -1,
		"keywords":    -1,
		"category":    -1,
	}

	for idx, colName := range header {
		cleanCol := strings.ToLower(strings.TrimSpace(colName))
		if strings.Contains(cleanCol, "gejala") || strings.Contains(cleanCol, "symptom") || strings.Contains(cleanCol, "issue") || strings.Contains(cleanCol, "masalah") {
			colIdx["symptom"] = idx
		} else if strings.Contains(cleanCol, "penyebab") || strings.Contains(cleanCol, "cause") || strings.Contains(cleanCol, "akar") {
			colIdx["root_cause"] = idx
		} else if strings.Contains(cleanCol, "solusi") || strings.Contains(cleanCol, "penanganan") || strings.Contains(cleanCol, "step") || strings.Contains(cleanCol, "remediation") {
			colIdx["remediation"] = idx
		} else if strings.Contains(cleanCol, "kata") || strings.Contains(cleanCol, "keyword") || strings.Contains(cleanCol, "tag") {
			colIdx["keywords"] = idx
		} else if strings.Contains(cleanCol, "kategori") || strings.Contains(cleanCol, "category") || strings.Contains(cleanCol, "tipe") {
			colIdx["category"] = idx
		}
	}

	var items []KnowledgeItem
	for i := 1; i < len(rows); i++ {
		row := rows[i]
		if len(row) == 0 {
			continue
		}

		symptom := getColVal(row, colIdx["symptom"])
		rootCause := getColVal(row, colIdx["root_cause"])
		remediation := getColVal(row, colIdx["remediation"])
		keywordsRaw := getColVal(row, colIdx["keywords"])
		category := getColVal(row, colIdx["category"])

		if symptom == "" && rootCause == "" {
			continue
		}

		if category == "" {
			category = "GENERAL"
		}

		var steps []string
		if remediation != "" {
			// Split by newline or pipe or semicolon
			rawSteps := strings.FieldsFunc(remediation, func(r rune) bool {
				return r == '\n' || r == '|' || r == ';'
			})
			for _, st := range rawSteps {
				cleanSt := strings.TrimSpace(st)
				if cleanSt != "" {
					steps = append(steps, cleanSt)
				}
			}
		}

		var kws []string
		if keywordsRaw != "" {
			for _, kw := range strings.Split(keywordsRaw, ",") {
				cleanKw := strings.TrimSpace(kw)
				if cleanKw != "" {
					kws = append(kws, cleanKw)
				}
			}
		} else {
			// Auto generate keywords from symptom
			kws = strings.Fields(strings.ToLower(symptom))
		}

		items = append(items, KnowledgeItem{
			ID:               fmt.Sprintf("KB-AUTO-%d-%d", time.Now().Unix(), i),
			Category:         strings.ToUpper(category),
			Keywords:         kws,
			Symptom:          symptom,
			RootCause:        rootCause,
			RemediationSteps: steps,
		})
	}

	return items, nil
}

func getColVal(row []string, idx int) string {
	if idx >= 0 && idx < len(row) {
		return strings.TrimSpace(row[idx])
	}
	return ""
}

// Match performs keyword-based semantic matching for a user query or incident description.
func (e *KnowledgeEngine) Match(query string) *KnowledgeItem {
	e.mu.RLock()
	defer e.mu.RUnlock()

	if len(e.items) == 0 || strings.TrimSpace(query) == "" {
		return nil
	}

	lowerQuery := strings.ToLower(query)
	var bestItem *KnowledgeItem
	highestScore := 0

	for i := range e.items {
		item := &e.items[i]
		score := 0

		for _, kw := range item.Keywords {
			if kw != "" && strings.Contains(lowerQuery, strings.ToLower(kw)) {
				score += 2
			}
		}

		if item.Symptom != "" && strings.Contains(lowerQuery, strings.ToLower(item.Symptom)) {
			score += 5
		}

		if score > highestScore {
			highestScore = score
			bestItem = item
		}
	}

	if highestScore >= 2 {
		return bestItem
	}
	return nil
}

// ImportItems batch upserts custom knowledge items and persists them to the dedicated JSON file.
func (e *KnowledgeEngine) ImportItems(newItems []KnowledgeItem) (int, error) {
	e.mu.Lock()
	defer e.mu.Unlock()

	addedCount := 0
	for _, newItem := range newItems {
		if newItem.ID == "" {
			newItem.ID = fmt.Sprintf("KB-CUST-%d", len(e.items)+1)
		}
		// Overwrite existing or append
		found := false
		for i, existing := range e.items {
			if existing.ID == newItem.ID || (existing.Symptom != "" && existing.Symptom == newItem.Symptom) {
				e.items[i] = newItem
				found = true
				addedCount++
				break
			}
		}
		if !found {
			e.items = append(e.items, newItem)
			addedCount++
		}
	}

	err := e.saveToFileLocked()
	return addedCount, err
}

// GetItems returns all loaded knowledge items.
func (e *KnowledgeEngine) GetItems() []KnowledgeItem {
	e.mu.RLock()
	defer e.mu.RUnlock()
	return e.items
}

func (e *KnowledgeEngine) saveToFileLocked() error {
	data, err := json.MarshalIndent(e.items, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(e.filePath, data, 0644)
}
