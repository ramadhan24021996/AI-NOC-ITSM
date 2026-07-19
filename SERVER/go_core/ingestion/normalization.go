package ingestion

import (
	"context"
	"encoding/json"
	"fmt"
	"math"
	"strconv"
	"strings"
	"time"

	"github.com/go-redis/redis/v8"
)

var ctx = context.Background()

type NormalizationEngine struct {
	rdb *redis.Client
}

func NewNormalizationEngine(rdb *redis.Client) *NormalizationEngine {
	return &NormalizationEngine{rdb: rdb}
}

// NormalizeTimestamp standardizes timestamps to YYYY-MM-DD HH:MM:SS format and corrects clock drift > 5s
func (ne *NormalizationEngine) NormalizeTimestamp(tsRaw interface{}, agent string) string {
	nowUTC := time.Now().UTC()
	if tsRaw == nil {
		return nowUTC.Format("2006-01-02 15:04:05")
	}

	var dt time.Time
	var parseErr error

	// Handle float/int timestamp
	switch v := tsRaw.(type) {
	case int:
		dt = time.Unix(int64(v), 0).UTC()
	case int64:
		dt = time.Unix(v, 0).UTC()
	case float64:
		dt = time.Unix(int64(v), 0).UTC()
	case string:
		// Try parsing ISO format e.g., '2026-05-26T14:21:57.123456'
		cleanStr := strings.ReplaceAll(v, "Z", "")
		cleanStr = strings.ReplaceAll(cleanStr, "T", " ")
		if strings.Contains(cleanStr, ".") {
			cleanStr = strings.Split(cleanStr, ".")[0]
		}
		cleanStr = strings.TrimSpace(cleanStr)

		// Check if it's a numeric string
		if sec, err := strconv.ParseFloat(cleanStr, 64); err == nil {
			dt = time.Unix(int64(sec), 0).UTC()
		} else {
			dt, parseErr = time.Parse("2006-01-02 15:04:05", cleanStr)
		}
	default:
		return nowUTC.Format("2006-01-02 15:04:05")
	}

	if parseErr != nil || dt.IsZero() {
		return nowUTC.Format("2006-01-02 15:04:05")
	}

	// Clock drift checks
	diffUTC := nowUTC.Sub(dt).Seconds()
	diffLocal := time.Since(dt.Local()).Seconds()

	drift := diffUTC
	if math.Abs(diffLocal) < math.Abs(diffUTC) {
		drift = diffLocal
	}

	if math.Abs(drift) > 5.0 {
		fmt.Printf(" [NORMALIZER WARNING] Clock drift detected for agent '%s': %.2fs. Auto-correcting to server UTC.\n", agent, drift)
		if ne.rdb != nil {
			ne.rdb.HIncrBy(ctx, "metrics:clock_drift_count", agent, 1)
			ne.rdb.HSet(ctx, "metrics:last_clock_drift", agent, strconv.FormatFloat(drift, 'f', 2, 64))
		}
		return nowUTC.Format("2006-01-02 15:04:05")
	}

	return dt.Format("2006-01-02 15:04:05")
}

// NormalizeMetrics normalizes unit measurements and standardizes metric keys
func (ne *NormalizationEngine) NormalizeMetrics(metadata map[string]interface{}) map[string]interface{} {
	normalized := make(map[string]interface{})
	for key, value := range metadata {
		normKey := strings.ToLower(strings.TrimSpace(key))

		var numVal float64
		var isNumeric bool

		switch v := value.(type) {
		case int:
			numVal = float64(v)
			isNumeric = true
		case int64:
			numVal = float64(v)
			isNumeric = true
		case float64:
			numVal = v
			isNumeric = true
		case string:
			if parsed, err := strconv.ParseFloat(strings.TrimSpace(v), 64); err == nil {
				numVal = parsed
				isNumeric = true
			}
		}

		if !isNumeric {
			normalized[key] = value
			continue
		}

		// Unit conversions & Standardizations
		if strings.Contains(normKey, "freephysicalmemory") || strings.Contains(normKey, "free_ram") {
			// If value is extremely large, it's in KB, convert to MB
			if numVal > 100000 {
				numVal = numVal / 1024.0
			}
			normalized["free_ram_mb"] = math.Round(numVal*100) / 100
		} else if strings.Contains(normKey, "freespace") || strings.Contains(normKey, "free_disk") {
			// If value is in bytes, convert to GB
			if numVal > 100000000 {
				numVal = numVal / (1024.0 * 1024.0 * 1024.0)
			}
			normalized["free_disk_gb"] = math.Round(numVal*100) / 100
		} else if strings.Contains(normKey, "cpu") {
			normalized["cpu_percent"] = math.Round(numVal*100) / 100
		} else if strings.Contains(normKey, "memory") || strings.Contains(normKey, "ram") {
			normalized["memory_percent"] = math.Round(numVal*100) / 100
		} else if strings.Contains(normKey, "latency") {
			normalized["latency_ms"] = math.Round(numVal*100) / 100
		} else if strings.Contains(normKey, "packet_loss") {
			normalized["packet_loss"] = math.Round(numVal*100) / 100
		} else {
			normalized[key] = math.Round(numVal*100) / 100
		}
	}
	return normalized
}

// IsNoise determines if the telemetry is noisy (i.e. no significant change in metrics)
func (ne *NormalizationEngine) IsNoise(agentName string, normalizedMetrics map[string]interface{}) bool {
	if ne.rdb == nil {
		return false
	}

	cacheKey := fmt.Sprintf("last_metrics:%s", agentName)
	lastDataRaw, err := ne.rdb.Get(ctx, cacheKey).Result()
	if err == redis.Nil {
		// Cache missing, save current and process it
		if bytes, err := json.Marshal(normalizedMetrics); err == nil {
			ne.rdb.SetEX(ctx, cacheKey, string(bytes), 10*time.Minute)
		}
		return false
	} else if err != nil {
		fmt.Printf(" [NORMALIZER WARNING] Redis cache check failed: %v\n", err)
		return false
	}

	var lastMetrics map[string]interface{}
	if err := json.Unmarshal([]byte(lastDataRaw), &lastMetrics); err != nil {
		return false
	}

	significantChange := false
	for key, value := range normalizedMetrics {
		val, ok := value.(float64)
		if !ok {
			continue
		}

		prevValRaw, exists := lastMetrics[key]
		if !exists {
			significantChange = true
			break
		}

		prevVal, ok := prevValRaw.(float64)
		if !ok {
			significantChange = true
			break
		}

		// Check for significant changes
		diff := math.Abs(val - prevVal)
		if strings.Contains(key, "cpu") || strings.Contains(key, "memory") {
			if diff >= 2.0 {
				significantChange = true
				break
			}
		} else if strings.Contains(key, "latency") {
			if diff >= 5.0 {
				significantChange = true
				break
			}
		} else if strings.Contains(key, "disk") {
			if diff >= 0.1 {
				significantChange = true
				break
			}
		} else {
			if diff > 0.0 {
				significantChange = true
				break
			}
		}
	}

	if significantChange {
		// Update cache with new values
		if bytes, err := json.Marshal(normalizedMetrics); err == nil {
			ne.rdb.SetEX(ctx, cacheKey, string(bytes), 10*time.Minute)
		}
		return false
	}

	return true
}

// IsExpired filters out telemetry older than 10 minutes (600 seconds)
func (ne *NormalizationEngine) IsExpired(tsStr string) bool {
	dt, err := time.Parse("2006-01-02 15:04:05", tsStr)
	if err != nil {
		return false
	}

	nowUTC := time.Now().UTC()
	nowLocal := time.Now()

	diffUTC := nowUTC.Sub(dt).Seconds()
	diffLocal := nowLocal.Sub(dt).Seconds()

	// Accept if difference is between -60 and 600 seconds
	if (-60 <= diffUTC && diffUTC <= 600) || (-60 <= diffLocal && diffLocal <= 600) {
		return false
	}

	return true
}

// Process processes raw telemetry payload, returning the normalized dict or nil if filtered
func (ne *NormalizationEngine) Process(payload map[string]interface{}) map[string]interface{} {
	agent, ok := payload["agent"].(string)
	if !ok || agent == "" {
		return nil
	}

	// 1. Normalize timestamp
	tsRaw := payload["timestamp"]
	normalizedTS := ne.NormalizeTimestamp(tsRaw, agent)

	// 2. Check expiration
	if ne.IsExpired(normalizedTS) {
		fmt.Printf(" [NORMALIZER] Filtered expired telemetry from %s (timestamp: %s)\n", agent, normalizedTS)
		return nil
	}

	// 3. Normalize metrics
	rawMetadata := make(map[string]interface{})
	if metaRaw, ok := payload["metadata"].(map[string]interface{}); ok {
		for k, v := range metaRaw {
			rawMetadata[k] = v
		}
	}
	if healthRaw, ok := payload["health"].(map[string]interface{}); ok {
		for k, v := range healthRaw {
			rawMetadata[k] = v
		}
	}
	if dataRaw, ok := payload["data"].(map[string]interface{}); ok {
		for k, v := range dataRaw {
			rawMetadata[k] = v
		}
	}

	normalizedMeta := ne.NormalizeMetrics(rawMetadata)

	// 4. Filter noise
	payload["is_noise"] = ne.IsNoise(agent, normalizedMeta)
	payload["timestamp"] = normalizedTS
	payload["metadata"] = normalizedMeta

	return payload
}
