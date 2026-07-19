package ingestion

// dedup_filter.go
//
// OSI AI Ops — Event Deduplication & Alert Suppression Filter
// Sprint 3: Gap 5 (Grafana/MikroTik Alert Storm Prevention)
//
// Tujuan:
//   Mencegah AI Supervisor (osi-python-ai-core) menerima banjir alert
//   yang identik dalam waktu singkat (misal: MikroTik flapping, link up/down
//   berulang, atau Grafana mengirim alert yang sama setiap 30 detik).
//
// Cara kerja:
//   - Setiap event yang masuk ke publishToBroker() dibuatkan fingerprint
//     berdasarkan: SiteID + PCName + EventType + Priority
//   - Jika fingerprint yang sama sudah terlihat dalam DedupWindow (default: 5 menit),
//     event tersebut ditekan (suppressed) dan TIDAK dikirim ke NATS
//   - Counter suppression dicatat di log untuk audit
//   - Fingerprint yang sudah melewati DedupWindow otomatis dihapus dari memori
//
// Trade-off yang disadari:
//   - False suppression: alert ke-2 yang berbeda tapi punya fingerprint sama
//     akan ikut tertahan. Ini adalah tradeoff yang DISENGAJA untuk menjaga
//     kesehatan AI budget & NATS throughput pada skala enterprise.
//   - Window 5 menit dapat dikonfigurasi via env LLM_DEDUP_WINDOW_SEC

import (
	"fmt"
	"os"
	"strconv"
	"sync"
	"time"
)

// ── Konfigurasi ───────────────────────────────────────────────────────────────

var (
	dedupWindowSec = func() int {
		v, err := strconv.Atoi(os.Getenv("LLM_DEDUP_WINDOW_SEC"))
		if err != nil || v < 10 {
			return 300 // default: 5 menit
		}
		return v
	}()
)

// ── DedupFilter ──────────────────────────────────────────────────────────────

// dedupEntry menyimpan waktu event pertama kali diterima dan hitungan suppression
type dedupEntry struct {
	firstSeen   time.Time
	suppressCnt int64
}

// DedupFilter adalah in-memory filter yang mencegah alert storm ke NATS.
// Thread-safe menggunakan sync.RWMutex.
type DedupFilter struct {
	mu      sync.RWMutex
	seen    map[string]*dedupEntry
	window  time.Duration
	stopped chan struct{}
}

// globalDedupFilter adalah instance singleton yang digunakan oleh publishToBroker.
var globalDedupFilter = newDedupFilter(time.Duration(dedupWindowSec) * time.Second)

func newDedupFilter(window time.Duration) *DedupFilter {
	df := &DedupFilter{
		seen:    make(map[string]*dedupEntry),
		window:  window,
		stopped: make(chan struct{}),
	}
	go df.cleanupLoop()
	return df
}

// IsDuplicate memeriksa apakah event adalah duplikat dalam window.
// Mengembalikan true jika event harus ditekan (tidak dikirim ke NATS).
func (df *DedupFilter) IsDuplicate(fingerprint string) bool {
	df.mu.Lock()
	defer df.mu.Unlock()

	entry, exists := df.seen[fingerprint]
	if exists && time.Since(entry.firstSeen) < df.window {
		// Duplikat dalam window — tekan
		entry.suppressCnt++
		return true
	}

	// Baru / sudah melewati window — catat dan izinkan
	df.seen[fingerprint] = &dedupEntry{
		firstSeen:   time.Now(),
		suppressCnt: 0,
	}
	return false
}

// Stats mengembalikan jumlah fingerprint aktif dan total event yang ditekan.
func (df *DedupFilter) Stats() (active int, totalSuppressed int64) {
	df.mu.RLock()
	defer df.mu.RUnlock()
	for _, e := range df.seen {
		active++
		totalSuppressed += e.suppressCnt
	}
	return
}

// cleanupLoop menghapus fingerprint yang sudah kadaluarsa dari memori setiap menit.
// Ini mencegah memory leak jika ada ribuan perangkat berbeda yang mengirim event.
func (df *DedupFilter) cleanupLoop() {
	ticker := time.NewTicker(1 * time.Minute)
	defer ticker.Stop()
	for {
		select {
		case <-ticker.C:
			df.mu.Lock()
			now := time.Now()
			purged := 0
			for k, e := range df.seen {
				if now.Sub(e.firstSeen) > df.window {
					delete(df.seen, k)
					purged++
				}
			}
			df.mu.Unlock()
			if purged > 0 {
				fmt.Printf(" [DEDUP] Purged %d expired fingerprints from memory.\n", purged)
			}
		case <-df.stopped:
			return
		}
	}
}

// ── Helper: Fingerprint Builder ──────────────────────────────────────────────

// buildFingerprint membuat fingerprint unik dari field kunci sebuah event.
// Fingerprint dibuat seringan mungkin (concatenasi string) untuk menghindari
// overhead hashing yang tidak perlu di hot-path.
//
// Format: "<site>|<pcname>|<eventtype>|<priority>"
func buildFingerprint(siteID, pcName, eventType, priority string) string {
	return siteID + "|" + pcName + "|" + eventType + "|" + priority
}
