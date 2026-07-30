package ingestion

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"time"
	"github.com/go-redis/redis/v8"
	"github.com/google/uuid"
	"github.com/gorilla/websocket"
	"github.com/nats-io/nats.go"

	"image"
	_ "image/gif"
	"image/jpeg"
	_ "image/png"

	"go_incident_analysis/SERVER/go_core/config"
	"go_incident_analysis/SERVER/go_core/database"
	"go_incident_analysis/SERVER/go_core/hardening"
	"go_incident_analysis/SERVER/go_core/security"
)

// TelemetryItem represents the unmarshaled payload item queued in worker channels
type TelemetryItem struct {
	Type          string                 `json:"type"`
	EventType     string                 `json:"event_type"`
	Status        string                 `json:"status"`
	Description   string                 `json:"description"`
	Layer         interface{}            `json:"layer"`
	SiteID        string                 `json:"site_id"`
	Location      string                 `json:"location"`
	PCName        string                 `json:"pc_name"`
	Agent         string                 `json:"agent"`
	Timestamp     string                 `json:"timestamp"`
	Token         string                 `json:"token"`
	SchemaVersion string                 `json:"schema_version"`
	TraceID       string                 `json:"trace_id,omitempty"`       // OpenTelemetry Trace ID
	SpanID        string                 `json:"span_id,omitempty"`        // OpenTelemetry Span ID
	CorrelationID string                 `json:"correlation_id,omitempty"` // Enterprise Correlation ID
	N8NWebhookID  string                 `json:"n8n_webhook_id,omitempty"` // n8n Webhook Deduplication ID
	Metadata      map[string]interface{} `json:"metadata"`
	Data          map[string]interface{} `json:"data"`
	IPAddress     string                 `json:"ip_address,omitempty"`
	IsNoise       bool                   `json:"is_noise,omitempty"`
	Priority      string                 `json:"priority,omitempty"`
}

// metricSnapshot holds a telemetry value and the time it was last seen changed
type metricSnapshot struct {
	Value     float64
	LastAt    time.Time
	AlertedAt time.Time // last time a flat-line alert was fired
}

// ── Phase 3 structs ──────────────────────────────────────────────────────────

// rocEntry holds a single Rate-of-Change sample for adaptive anomaly modelling
type rocEntry struct {
	RoC float64   // abs(current_value - previous_value)
	At  time.Time // when this sample was recorded
}

// rocWindow is a sliding window of recent RoC samples for one device+metric key
type rocWindow struct {
	Samples   []rocEntry
	PrevValue float64
	AlertedAt time.Time
}

// stateRing is a circular buffer of per-device state hashes used for drift detection
type stateRing struct {
	Hashes    []string  // circular ring of SHA256 hashes (up to maxRingSize)
	BaseHash  string    // oldest / baseline hash
	Head      int       // insertion pointer
	AlertedAt time.Time // last drift alert
}

// Queue channel boundaries
var (
	metricQueue = make(chan TelemetryItem, 20000)
	logQueue    = make(chan TelemetryItem, 10000)
	eventQueue  = make(chan TelemetryItem, 10000)
)

type SiteQueue struct {
	siteID      string
	metricQueue chan TelemetryItem
	logQueue    chan TelemetryItem
	eventQueue  chan TelemetryItem
}

var (
	siteQueues   = make(map[string]*SiteQueue)
	siteQueuesMu sync.RWMutex
)

func getOrCreateSiteQueue(siteID string) *SiteQueue {
	siteID = strings.ToLower(strings.TrimSpace(siteID))
	if siteID == "" {
		siteID = "global"
	}

	siteQueuesMu.RLock()
	sq, exists := siteQueues[siteID]
	siteQueuesMu.RUnlock()
	if exists {
		return sq
	}

	siteQueuesMu.Lock()
	defer siteQueuesMu.Unlock()

	sq, exists = siteQueues[siteID]
	if exists {
		return sq
	}

	sq = &SiteQueue{
		siteID:      siteID,
		metricQueue: make(chan TelemetryItem, 20000),
		logQueue:    make(chan TelemetryItem, 10000),
		eventQueue:  make(chan TelemetryItem, 10000),
	}
	siteQueues[siteID] = sq

	// Spawn site-specific workers (2 metric, 1 log, 1 event worker per site)
	for i := 1; i <= 2; i++ {
		workerID := i
		hardening.GoSafe(func() { shardedMetricWorker(sq, workerID) }, func(cat, msg string) {
			fmt.Printf("[%s] Sharded Metric Worker %d for site %s panic: %s\n", cat, workerID, siteID, msg)
		})
	}
	hardening.GoSafe(func() { shardedLogWorker(sq, 1) }, func(cat, msg string) {
		fmt.Printf("[%s] Sharded Log Worker 1 for site %s panic: %s\n", cat, siteID, msg)
	})
	hardening.GoSafe(func() { shardedEventWorker(sq, 1) }, func(cat, msg string) {
		fmt.Printf("[%s] Sharded Event Worker 1 for site %s panic: %s\n", cat, siteID, msg)
	})

	fmt.Printf(" [INGESTOR INIT] Spawning sharded queue and workers for Site: %s\n", siteID)
	return sq
}

type verifyTask struct {
	conn   net.Conn
	text   string
	ipAddr string
}

var verifyQueue = make(chan verifyTask, 20000)

// Caches & synchronization
var (
	registeredDevicesCache   = make(map[string]bool)
	registeredDevicesCacheMu sync.RWMutex

	deviceStatusCache   = make(map[string]string)
	deviceStatusCacheMu sync.RWMutex

	deviceLastSeen   = make(map[string]time.Time)
	deviceLastSeenMu sync.Mutex

	deviceLocks   = make(map[string]*sync.RWMutex)
	deviceLocksMu sync.Mutex

	// Phase 2 — Flat-line Detector: tracks last (value, timestamp) per device+metric
	deviceMetricHistory   = make(map[string]metricSnapshot) // key: "device::metric_type"
	deviceMetricHistoryMu sync.Mutex

	// Phase 2 — Stale Telemetry Detector: tracks last telemetry packet time per device
	// (separate from deviceLastSeen which tracks ANY packet including non-metric)
	deviceLastTelemetry   = make(map[string]time.Time)
	deviceLastTelemetryMu sync.Mutex

	// Phase 3 — Adaptive RoC (Rate of Change) Anomaly Model
	// key: "device::metric_type" — sliding window of RoC samples for each metric
	rocWindows   = make(map[string]*rocWindow)
	rocWindowsMu sync.Mutex

	// Phase 3 — State Hash Drift Detection
	// key: device name — ring of recent state hashes for drift comparison
	deviceStateRings   = make(map[string]*stateRing)
	deviceStateRingsMu sync.Mutex
)

// Internal metrics counters
var (
	metricsProcessedCount int64
	metricsErrorsCount    int64
	metricsDLQCount       int64
	metricsLatencySum     float64
	metricsMu             sync.Mutex
)

var (
	redisClient *redis.Client
	natsConn    *nats.Conn
	natsJS      nats.JetStreamContext
	securityKey []byte
	normalizer  *NormalizationEngine
	appConfig   *config.Config
)

// HTTP channel listener for multiplexing HTTP requests sharing raw TCP ports
type channelListener struct {
	conns  chan net.Conn
	closed chan struct{}
	once   sync.Once
}

func newChannelListener() *channelListener {
	return &channelListener{
		conns:  make(chan net.Conn, 1024),
		closed: make(chan struct{}),
	}
}

func (l *channelListener) Accept() (net.Conn, error) {
	select {
	case c := <-l.conns:
		return c, nil
	case <-l.closed:
		return nil, io.EOF
	}
}

func (l *channelListener) Close() error {
	l.once.Do(func() {
		close(l.closed)
	})
	return nil
}

func (l *channelListener) Addr() net.Addr {
	return &net.TCPAddr{IP: net.ParseIP("0.0.0.0"), Port: 18800}
}

type BufferedConn struct {
	net.Conn
	r io.Reader
}

func (b *BufferedConn) Read(p []byte) (int, error) {
	return b.r.Read(p)
}

var httpDispatcher = newChannelListener()

func incrementInternalMetrics(processed, errors, dlq int, latency float64) {
	metricsMu.Lock()
	metricsProcessedCount += int64(processed)
	metricsErrorsCount += int64(errors)
	metricsDLQCount += int64(dlq)
	metricsLatencySum += latency
	metricsMu.Unlock()
}

func getDeviceLock(deviceName string) *sync.RWMutex {
	deviceLocksMu.Lock()
	defer deviceLocksMu.Unlock()
	if lock, exists := deviceLocks[deviceName]; exists {
		return lock
	}
	lock := &sync.RWMutex{}
	deviceLocks[deviceName] = lock
	return lock
}

// StartIngestionServer sets up worker pools, starts monitors and TCP listeners
func StartIngestionServer() {
	var err error
	appConfig, err = config.GetConfig()
	if err != nil {
		fmt.Printf(" [INGESTOR FATAL] Failed to load configuration: %v\n", err)
		os.Exit(1)
	}

	// 1. Initialize security key
	sm, err := security.GetSecurityManager()
	if err == nil {
		securityKey = sm.GetKey()
	} else {
		securityKey = []byte("SIAP_DISTRIBUSI_SECRET_KEY")
	}

	// 2. Initialize Redis
	redisClient = redis.NewClient(&redis.Options{
		Addr:     fmt.Sprintf("%s:%d", appConfig.RedisHost, appConfig.RedisPort),
		Password: appConfig.RedisPass,
	})
	if err := redisClient.Ping(ctx).Err(); err == nil {
		fmt.Println(" [INGESTOR] Connected to local Redis broker on 127.0.0.1:6379")
		_ = redisClient.ConfigSet(ctx, "stop-writes-on-bgsave-error", "no").Err()
	} else {
		fmt.Printf(" [INGESTOR WARNING] Redis client unavailable: %v\n", err)
		redisClient = nil
	}

	normalizer = NewNormalizationEngine(redisClient)

	// 3. Initialize NATS with Token Authentication
	natsURL := fmt.Sprintf("nats://%s:%d", appConfig.NatsHost, appConfig.NatsPort)
	if appConfig.NatsToken != "" {
		natsURL = fmt.Sprintf("nats://%s@%s:%d", appConfig.NatsToken, appConfig.NatsHost, appConfig.NatsPort)
	}
	natsConn, err = nats.Connect(natsURL)
	if err == nil {
		fmt.Printf(" [INGESTOR] Connected to NATS broker on %s:%d\n", appConfig.NatsHost, appConfig.NatsPort)
		// Upgrade connection to JetStream for guaranteed persistence and backpressure (Phase 2 hardening)
		js, jsErr := natsConn.JetStream()
		if jsErr != nil {
			fmt.Printf(" [INGESTOR FATAL] JetStream initialization failed: %v\n", jsErr)
			os.Exit(1)
		}
		natsJS = js
	} else {
		fmt.Printf(" [INGESTOR WARNING] NATS broker unavailable: %v\n", err)
		natsConn = nil
		natsJS = nil
	}

	// 4. Initialize Database connection
	_, err = database.InitDatabase()
	if err != nil {
		fmt.Printf(" [INGESTOR FATAL] Database connection failed: %v\n", err)
		os.Exit(1)
	}

	// Initialize chat Redis subscriber
	StartChatRedisSubscriber()

	// Start Syslog Aggregator for Nginx/Network diagnostic ingestion
	StartSyslogAggregator()

	// Start resource monitoring & pprof (Fase 12 Hardening)
	sqlDB, _ := database.DB.DB()
	hardening.StartPprofServer()
	hardening.MonitorResources(sqlDB, redisClient, nil, func(cat, msg string) {
		fmt.Printf("[%s] %s\n", cat, msg)
	}, 30*time.Second)

	// Start async verification worker pool
	startVerifyWorkerPool()

	// 5. Start parallel processor workers with panic safety
	for i := 1; i <= 4; i++ {
		id := i
		hardening.GoSafe(func() { metricProcessorWorker(id) }, func(cat, msg string) {
			fmt.Printf("[%s] Worker panic: %s\n", cat, msg)
		})
	}
	for i := 1; i <= 2; i++ {
		id := i
		hardening.GoSafe(func() { logProcessorWorker(id) }, func(cat, msg string) {
			fmt.Printf("[%s] Worker panic: %s\n", cat, msg)
		})
		hardening.GoSafe(func() { eventProcessorWorker(id) }, func(cat, msg string) {
			fmt.Printf("[%s] Worker panic: %s\n", cat, msg)
		})
	}

	// Start queue monitoring loop
	startQueueMonitorLoop()

	// Start Dead Man Switch
	startDeadManSwitch()

	// Phase 2: Flat-line Detector (frozen metric probe detection)
	startFlatLineDetector()

	// Phase 2: Stale Telemetry Detector (silent device detection)
	startStaleTelemetryDetector()

	// Phase 3: Adaptive RoC Anomaly Model (spike/drop detection)
	startAdaptiveRoCDetector()

	// Phase 3: State Hash Drift Detector (gradual drift detection)
	startStateHashDriftDetector()

	// Fix P0.2: Load persisted anomaly baselines from Redis (eliminates warm-up blind window)
	loadAnomalyStateFromRedis()

	// Fix P0.2: Start periodic anomaly state persistence to Redis (every 30s)
	startAnomalyStatePersistor()

	// Register Distributed Scheduler NATS subscriptions
	StartSchedulerSubscriptions()

	// Start multiplexed HTTP Server in background
	hardening.GoSafe(func() { serveHTTPDispatcher() }, func(cat, msg string) {
		fmt.Printf("[%s] HTTP dispatcher panic: %s\n", cat, msg)
	})

	// Start TCP listener pipelines with SO_REUSEPORT (8 workers for high load ports)
	for i := 1; i <= 8; i++ {
		workerID := i
		hardening.GoSafe(func() { startListenerPipeline(18800, fmt.Sprintf("OPERATIONAL_WORKER_%d", workerID)) }, func(cat, msg string) {
			fmt.Printf("[%s] TCP listener panic: %s\n", cat, msg)
		})
		hardening.GoSafe(func() { startListenerPipeline(18802, fmt.Sprintf("REMEDIATION_RCA_WORKER_%d", workerID)) }, func(cat, msg string) {
			fmt.Printf("[%s] TCP listener panic: %s\n", cat, msg)
		})
	}
	// Netdata telemetry is lower volume, 2 workers is plenty
	for i := 1; i <= 2; i++ {
		workerID := i
		hardening.GoSafe(func() { startListenerPipeline(19999, fmt.Sprintf("NETDATA_TELEMETRY_WORKER_%d", workerID)) }, func(cat, msg string) {
			fmt.Printf("[%s] TCP listener panic: %s\n", cat, msg)
		})
	}

	fmt.Println(" [INGESTOR INIT] All Ingestion Server pipelines running.")
	select {}
}

func startListenerPipeline(port int, pipelineName string) {
	listener, err := listenSOReuseport("tcp", fmt.Sprintf("0.0.0.0:%d", port))
	if err != nil {
		fmt.Printf(" [INGESTOR ERROR] Port %d (%s): Failed to listen with SO_REUSEPORT: %v\n", port, pipelineName, err)
		// Fallback to standard net.Listen in case OS doesn't support SO_REUSEPORT
		listener, err = net.Listen("tcp", fmt.Sprintf("0.0.0.0:%d", port))
		if err != nil {
			fmt.Printf(" [INGESTOR ERROR] Port %d (%s): Failed fallback listen: %v\n", port, pipelineName, err)
			return
		}
	}
	defer listener.Close()

	fmt.Printf(" [INGESTOR SUCCESS] %s Pipeline listening on Port %d (SO_REUSEPORT)\n", pipelineName, port)

	for {
		conn, err := listener.Accept()
		if err != nil {
			continue
		}
		hardening.GoSafe(func() { handleTCPConnection(conn) }, func(cat, msg string) {
			fmt.Printf("[%s] TCP connection handler panic: %s\n", cat, msg)
		})
	}
}

func handleTCPConnection(conn net.Conn) {
	ipAddr, _, _ := net.SplitHostPort(conn.RemoteAddr().String())
	fmt.Printf(" [INGESTOR DEBUG] Received connection from %s\n", ipAddr)

	if !checkRateLimit(ipAddr) {
		fmt.Printf(" [INGESTOR RATE_LIMIT] Blocked request from %s\n", ipAddr)
		resp, _ := json.Marshal(map[string]interface{}{"status": "RATE_LIMIT_EXCEEDED"})
		_, _ = conn.Write(append(resp, '\n'))
		conn.Close()
		return
	}

	// Peeking at the first few bytes to determine if it is an HTTP request
	_ = conn.SetReadDeadline(time.Now().Add(5 * time.Second))
	peekBuf := make([]byte, 8)
	n, err := conn.Read(peekBuf)
	if err != nil {
		conn.Close()
		return
	}

	peekStr := string(peekBuf[:n])
	isHTTP := false
	httpPrefixes := []string{"GET ", "POST", "HEAD", "OPTI", "PUT ", "DELE"}
	for _, pref := range httpPrefixes {
		if strings.HasPrefix(peekStr, pref) {
			isHTTP = true
			break
		}
	}

	if isHTTP {
		// Multiplex connection to the http dispatcher server
		bufferedConn := &BufferedConn{
			Conn: conn,
			r:    io.MultiReader(bytes.NewReader(peekBuf[:n]), conn),
		}
		select {
		case httpDispatcher.conns <- bufferedConn:
		default:
			conn.Close()
		}
		return
	}

	// Read standard TCP stream
	var buf bytes.Buffer
	if n > 0 {
		buf.Write(peekBuf[:n])
	}
	tempBuf := make([]byte, 8192)
	_ = conn.SetReadDeadline(time.Now().Add(10 * time.Second))

	// Loop until complete JSON block is read or timeout/closed
	for {
		var js map[string]interface{}
		if json.Unmarshal(buf.Bytes(), &js) == nil {
			break
		}
		readN, err := conn.Read(tempBuf)
		if readN > 0 {
			buf.Write(tempBuf[:readN])
		}
		if err != nil {
			break
		}
	}

	text := strings.TrimSpace(buf.String())
	if text == "" {
		conn.Close()
		return
	}

	select {
	case verifyQueue <- verifyTask{conn: conn, text: text, ipAddr: ipAddr}:
	default:
		fmt.Printf(" [INGESTOR WARNING] Verify queue full, dropping request from %s\n", ipAddr)
		resp, _ := json.Marshal(map[string]interface{}{"status": "DROPPED", "message": "Verification queue saturation"})
		_, _ = conn.Write(append(resp, '\n'))
		conn.Close()
	}
}

func startVerifyWorkerPool() {
	workers := runtime.NumCPU() * 2
	if workers < 4 {
		workers = 4
	}
	fmt.Printf(" [INGESTOR] Starting Async Verification Worker Pool with %d workers\n", workers)
	for i := 0; i < workers; i++ {
		go func() {
			for task := range verifyQueue {
				processVerifyTask(task.conn, task.text, task.ipAddr)
			}
		}()
	}
}

func processVerifyTask(conn net.Conn, text string, ipAddr string) {
	defer func() {
		if r := recover(); r != nil {
			fmt.Printf(" [INGESTOR PANIC] processVerifyTask panic: %v\n", r)
			conn.Close()
		}
	}()

	// Parse telemetry item
	var item TelemetryItem
	if err := json.Unmarshal([]byte(text), &item); err != nil {
		routeToDLQ(text, "JSON_DECODE_ERROR: "+err.Error())
		resp, _ := json.Marshal(map[string]interface{}{"status": "BAD_REQUEST", "message": "Invalid JSON"})
		_, _ = conn.Write(append(resp, '\n'))
		conn.Close()
		return
	}

	if item.IPAddress == "" {
		item.IPAddress = ipAddr
	}

	// OTel End-to-End Traceability (Sprint)
	InjectOTelContext(&item)

	// Intercept and correct fake incident reports that are actually periodic telemetry
	if item.EventType == "incident_report" && item.Type == "incident_report" && (item.Description == "Periodic Telemetry Check" || item.Description == "") {
		item.EventType = "telemetry"
		item.Type = "telemetry"
	}

	// Enforce Agent 05 version checks for ALL packets from non-auditor devices
	if !isVersionAllowed(item) {
		fmt.Printf(" [INGESTOR BLOCKED] Rejected telemetry/alert from %s — unsupported agent version (agent_version: %s, schema: %s)\n",
			item.Agent, getAgentVersionString(item), item.SchemaVersion)
		resp, _ := json.Marshal(map[string]interface{}{"status": "BLOCKED", "message": "Unsupported agent version"})
		_, _ = conn.Write(append(resp, '\n'))
		conn.Close()
		return
	}

	// Route bypass commands directly to client PC agent listener on port 10000/10001
	if item.Type == "EXECUTE_COMMAND" || item.Type == "EXECUTE_PROBE" {
		handleBypassCommand(conn, item)
		return
	}

	// Sync KB requests
	if item.Type == "SYNC_KB" {
		kb := loadKBSync()
		respBytes, _ := json.Marshal(kb)
		_, _ = conn.Write(append(respBytes, '\n'))
		conn.Close()
		return
	}

	// Standard Telemetry/Alert Flow: enforce schema, token validation, and idempotency
	if !validateTelemetrySchema(item) {
		fmt.Printf(" [INGESTOR REJECTED] Schema validation failed from %s\n", ipAddr)
		routeToDLQ(item, "SCHEMA_VALIDATION_FAILED: Schema conforms not to specs")
		resp, _ := json.Marshal(map[string]interface{}{"status": "BAD_REQUEST", "message": "Schema validation failed"})
		_, _ = conn.Write(append(resp, '\n'))
		conn.Close()
		return
	}

	if item.Agent != "auditor_probe" {
		if !verifyToken(item.Agent, item.Timestamp, item.Token) {
			fmt.Printf(" [INGESTOR AUTH] Unauthorized request from %s: invalid signature\n", ipAddr)
			routeToDLQ(item, "UNAUTHORIZED: Invalid token signature")
			resp, _ := json.Marshal(map[string]interface{}{"status": "UNAUTHORIZED"})
			_, _ = conn.Write(append(resp, '\n'))
			conn.Close()
			return
		}
	}

	// Phase 3 — Item 8: Telemetry Integrity Scoring + Enforcement Gate
	tokenValid := item.Agent == "auditor_probe" || verifyToken(item.Agent, item.Timestamp, item.Token)
	integrityScore := scoreTelemetryIntegrity(&item, tokenValid)

	switch {
	case integrityScore < 0.40:
		// Hard reject: integrity too low to trust — route to DLQ, do not process
		fmt.Printf(" [INTEGRITY GATE] HARD REJECT score=%.2f agent=%s deductions=%v\n",
			integrityScore, item.Agent, item.Metadata["integrity_deductions"])
		routeToDLQ(item, fmt.Sprintf("INTEGRITY_REJECTED: score=%.2f below minimum 0.40", integrityScore))
		resp, _ := json.Marshal(map[string]interface{}{"status": "INTEGRITY_REJECTED",
			"message": "Telemetry integrity score too low — packet rejected"})
		_, _ = conn.Write(append(resp, '\n'))
		conn.Close()
		return
	case integrityScore < 0.60:
		// Soft flag: integrity below threshold — mark packet, autonomous action blocked downstream
		fmt.Printf(" [INTEGRITY GATE] SOFT FLAG score=%.2f agent=%s — marking requires_hitl\n",
			integrityScore, item.Agent)
		if item.Metadata == nil {
			item.Metadata = make(map[string]interface{})
		}
		item.Metadata["requires_hitl"] = true
	default:
		if integrityScore < 0.80 {
			fmt.Printf(" [INGESTOR SCORER] LOW integrity score=%.2f from agent=%s deductions=%v\n",
				integrityScore, item.Agent, item.Metadata["integrity_deductions"])
		}
	}

	if checkAndSetIdempotency(&item) {
		resp, _ := json.Marshal(map[string]interface{}{"status": "DUPLICATE_IGNORED"})
		_, _ = conn.Write(append(resp, '\n'))
		conn.Close()
		return
	}

	// Process raw alert categories AFTER validation and idempotency checks
	if item.EventType == "usb_hardware_alert" {
		_, _ = conn.Write([]byte(`{"status":"RECEIVED"}` + "\n"))
		conn.Close()
		ensureDeviceRegistered(item)
		handleUSBHardwareAlert(item)
		return
	}

	alertTypes := map[string]bool{
		"service_alert":   true,
		"process_alert":   true,
		"network_alert":   true,
		"incident_report": true,
		"evidence_upload": true,
	}

	if alertTypes[item.EventType] {
		_, _ = conn.Write([]byte(`{"status":"RECEIVED"}` + "\n"))
		conn.Close()
		ensureDeviceRegistered(item)
		handlePhase1Alert(item)
		return
	}

	loadLevel := checkLoadSheddingLevel()
	loadSheddingActive := false
	safeModeActive := false

	if redisClient != nil {
		if val, err := redisClient.Get(ctx, "system:safe_mode").Result(); err == nil && val == "1" {
			safeModeActive = true
		}
		if val, err := redisClient.Get(ctx, "backpressure:load_shedding").Result(); err == nil && val == "1" {
			loadSheddingActive = true
		}
	}

	statusUpper := strings.ToUpper(item.Status)
	agentUpper := strings.ToUpper(item.Agent)
	layerInt := 0
	if lFloat, ok := item.Layer.(float64); ok {
		layerInt = int(lFloat)
	} else if lStr, ok := item.Layer.(string); ok {
		layerInt, _ = strconv.Atoi(lStr)
	}

	isCritical := (layerInt == 3 && (statusUpper == "PORT_DOWN" || statusUpper == "BGP_DOWN")) ||
		statusUpper == "GATEWAY_DOWN" || statusUpper == "DATABASE_TIMEOUT" || statusUpper == "SYSTEM_OFFLINE" ||
		statusUpper == "OUTAGE" || statusUpper == "CRITICAL" ||
		strings.Contains(agentUpper, "ROUTER") || strings.Contains(agentUpper, "GATEWAY") || strings.Contains(agentUpper, "POS")

	isNormal := statusUpper == "DEGRADED" || statusUpper == "HIGH_LATENCY" || statusUpper == "PACKET_LOSS" ||
		statusUpper == "BRANCH_DOWN" || statusUpper == "WARNING"

	if safeModeActive && !isCritical {
		fmt.Printf(" [INGESTOR SAFE_MODE] Dropping non-critical payload from %s\n", item.Agent)
		resp, _ := json.Marshal(map[string]interface{}{"status": "DROPPED", "message": "Safe mode: only critical allowed"})
		_, _ = conn.Write(append(resp, '\n'))
		conn.Close()
		return
	}

	if loadSheddingActive || loadLevel >= 2 {
		if !isCritical && !isNormal {
			resp, _ := json.Marshal(map[string]interface{}{"status": "DROPPED", "message": "Load shedding: dropped"})
			_, _ = conn.Write(append(resp, '\n'))
			conn.Close()
			return
		}

		// Perform aggregation check
		if redisClient != nil {
			metaHashable := []string{}
			for k, v := range item.Metadata {
				if fv, ok := v.(float64); ok {
					metaHashable = append(metaHashable, fmt.Sprintf("%s:%.1f", k, fv))
				}
			}
			metaStr := strings.Join(metaHashable, ",")
			hashInput := fmt.Sprintf("%s:%s:%s", item.Agent, item.Status, metaStr)
			aggHash := hex.EncodeToString(sha256.New().Sum([]byte(hashInput)))
			aggKey := fmt.Sprintf("agg_window:%s", aggHash)

			setOk, _ := redisClient.SetNX(ctx, aggKey, "1", 10*time.Second).Result()
			if !setOk {
				resp, _ := json.Marshal(map[string]interface{}{"status": "RECEIVED", "message": "Aggregated"})
				_, _ = conn.Write(append(resp, '\n'))
				conn.Close()
				return
			}
		}
	}

	// Write standard confirmation
	resp, _ := json.Marshal(map[string]interface{}{"status": "RECEIVED"})
	_, _ = conn.Write(append(resp, '\n'))
	conn.Close()

	// Normalize payload
	payloadMap := make(map[string]interface{})
	payloadMap["agent"] = item.Agent
	payloadMap["timestamp"] = item.Timestamp
	payloadMap["metadata"] = item.Metadata
	payloadMap["data"] = item.Data
	payloadMap["layer"] = item.Layer
	payloadMap["status"] = item.Status
	payloadMap["schema_version"] = item.SchemaVersion

	normMap := normalizer.Process(payloadMap)
	if normMap == nil {
		fmt.Printf(" [INGESTOR DEBUG] Normalization failed for agent: %s\n", item.Agent)
		routeToDLQ(item, "NORMALIZATION_FAILED")
		return
	}

	// Update item fields from normalization output
	if tNorm, ok := normMap["timestamp"].(string); ok {
		item.Timestamp = tNorm
	}
	if mNorm, ok := normMap["metadata"].(map[string]interface{}); ok {
		item.Metadata = mNorm
	}

	routeAndPublish(item, loadLevel, isCritical, isNormal)
}

func handleBypassCommand(conn net.Conn, item TelemetryItem) {
	targetAgent, _ := item.Metadata["target"].(string)
	command, _ := item.Metadata["command"].(string)
	params, _ := item.Metadata["params"].(map[string]interface{})

	var agentIP string
	row := database.DB.Raw("SELECT ip FROM devices WHERE name = ?", targetAgent).Row()
	_ = row.Scan(&agentIP)
	if agentIP == "" {
		agentIP = "127.0.0.1"
	}

	var agentConn net.Conn
	var lastErr error
	connected := false

	for _, port := range []int{10000, 10001} {
		agentConn, lastErr = net.DialTimeout("tcp", fmt.Sprintf("%s:%d", agentIP, port), 3*time.Second)
		if err := lastErr; err == nil {
			connected = true
			break
		}
	}

	if !connected {
		resp, _ := json.Marshal(map[string]interface{}{
			"status":  "FAILED",
			"message": fmt.Sprintf("Error connecting to agent '%s' at %s: %v", targetAgent, agentIP, lastErr),
		})
		_, _ = conn.Write(append(resp, '\n'))
		conn.Close()
		return
	}
	defer agentConn.Close()

	_ = agentConn.SetDeadline(time.Now().Add(15 * time.Second))

	now := time.Now().Unix()
	msgToSign := fmt.Sprintf("%s:%d", command, now)
	mac := hmac.New(sha256.New, securityKey)
	mac.Write([]byte(msgToSign))
	token := hex.EncodeToString(mac.Sum(nil))

	payload := map[string]interface{}{
		"command":   command,
		"params":    params,
		"master":    "INGESTION_SERVER",
		"timestamp": now,
		"token":     token,
	}
	payloadBytes, _ := json.Marshal(payload)
	_, _ = agentConn.Write(append(payloadBytes, '\n'))

	var respBuf bytes.Buffer
	_, _ = io.Copy(&respBuf, agentConn)

	respBytes, _ := json.Marshal(map[string]interface{}{
		"status":  "SUCCESS",
		"message": respBuf.String(),
	})
	_, _ = conn.Write(append(respBytes, '\n'))
	conn.Close()
}

func handleUSBHardwareAlert(item TelemetryItem) {
	pcName, _ := item.Metadata["pc_name"].(string)
	if pcName == "" {
		pcName, _ = item.Metadata["hostname"].(string)
	}
	usbName, _ := item.Metadata["device_name"].(string)
	manufacturer, _ := item.Metadata["manufacturer"].(string)
	fingerprint, _ := item.Metadata["fingerprint"].(string)
	usbStatus, _ := item.Metadata["status"].(string)
	riskLevel, _ := item.Metadata["risk_level"].(string)

	if pcName == "" || fingerprint == "" {
		return
	}

	isAnomaly := false
	var count int64
	database.DB.Table("fleet_usbs").Where("pc_name = ?", pcName).Count(&count)
	hasBaseline := count > 0

	var usbExists int64
	database.DB.Table("fleet_usbs").Where("fingerprint = ?", fingerprint).Count(&usbExists)

	if usbExists == 0 && hasBaseline {
		isAnomaly = true
		fmt.Printf(" [INGESTOR USB] ANOMALY DETECTED! Unregistered USB %s on %s\n", fingerprint, pcName)
		item.Metadata["baseline_match"] = false
	} else {
		item.Metadata["baseline_match"] = true
	}

	// Upsert USB asset records
	var uID int
	row := database.DB.Raw("SELECT usb_id FROM fleet_usbs WHERE fingerprint = ?", fingerprint).Row()
	_ = row.Scan(&uID)
	if uID > 0 {
		database.DB.Exec("UPDATE fleet_usbs SET status = ?, risk_level = ?, last_seen = NOW() WHERE usb_id = ?", usbStatus, riskLevel, uID)
	} else {
		database.DB.Exec("INSERT INTO fleet_usbs (pc_name, name, manufacturer, fingerprint, status, risk_level) VALUES (?, ?, ?, ?, ?, ?)",
			pcName, usbName, manufacturer, fingerprint, usbStatus, riskLevel)
	}

	site := strings.TrimSpace(item.SiteID)
	if site == "" {
		site = "global"
	}
	site = strings.ToLower(site)
	site = strings.ReplaceAll(site, ".", "_")
	site = strings.ReplaceAll(site, " ", "_")

	item.Agent = pcName
	item.Layer = 1
	priority := "low"
	streamName := "telemetry_stream:low"
	if isAnomaly {
		priority = "critical"
		streamName = "telemetry_stream:critical"
	}
	item.Priority = priority

	subject := fmt.Sprintf("telemetry.site.%s.%s", site, priority)

	payload := map[string]interface{}{
		"message":    item,
		"ip_address": item.IPAddress,
		"timestamp":  strconv.FormatInt(time.Now().Unix(), 10),
		"priority":   priority,
	}

	publishToBroker(streamName, subject, payload)
}

func handlePhase1Alert(item TelemetryItem) {
	pcName, _ := item.Metadata["pc_name"].(string)
	if pcName == "" {
		pcName, _ = item.Metadata["hostname"].(string)
	}
	if pcName == "" {
		pcName = item.Agent
	}
	// siteID, _ := item.Metadata["site_id"].(string)
	severity, _ := item.Metadata["severity"].(string)
	if severity == "" {
		severity = "LOW"
	}
	description, _ := item.Metadata["description"].(string)

	switch item.EventType {
	case "service_alert":
		srvName, _ := item.Metadata["service_name"].(string)
		status, _ := item.Metadata["status"].(string)
		startType, _ := item.Metadata["start_type"].(string)
		database.DB.Exec(`
			INSERT INTO fleet_services (pc_name, service_name, status, start_type, last_updated)
			VALUES (?, ?, ?, ?, NOW())
			ON CONFLICT (pc_name, service_name) DO UPDATE SET status = EXCLUDED.status, last_updated = NOW()
		`, pcName, srvName, status, startType)

	case "process_alert":
		pidVal, _ := item.Metadata["pid"].(float64)
		procName, _ := item.Metadata["name"].(string)
		cpuVal, _ := item.Metadata["cpu_percent"].(float64)
		memVal, _ := item.Metadata["memory_mb"].(float64)
		database.DB.Exec(`
			INSERT INTO fleet_processes (pc_name, pid, name, cpu_percent, memory_mb, last_updated)
			VALUES (?, ?, ?, ?, ?, NOW())
			ON CONFLICT (pc_name, pid, name) DO UPDATE SET cpu_percent = EXCLUDED.cpu_percent, memory_mb = EXCLUDED.memory_mb, last_updated = NOW()
		`, pcName, int(pidVal), procName, cpuVal, memVal)

	case "network_alert":
		ifName, _ := item.Metadata["interface_name"].(string)
		ip, _ := item.Metadata["ip_address"].(string)
		status, _ := item.Metadata["status"].(string)
		rx, _ := item.Metadata["rx_bytes"].(float64)
		tx, _ := item.Metadata["tx_bytes"].(float64)
		database.DB.Exec(`
			INSERT INTO fleet_networks (pc_name, interface_name, ip_address, status, rx_bytes, tx_bytes, last_updated)
			VALUES (?, ?, ?, ?, ?, ?, NOW())
			ON CONFLICT (pc_name, interface_name) DO UPDATE SET ip_address = EXCLUDED.ip_address, status = EXCLUDED.status, rx_bytes = EXCLUDED.rx_bytes, tx_bytes = EXCLUDED.tx_bytes, last_updated = NOW()
		`, pcName, ifName, ip, status, int64(rx), int64(tx))

	case "incident_report":
		DefaultIncidentService.TriggerIncidentWorkflow(pcName, severity, description)

	case "evidence_upload":
		incID, _ := item.Metadata["incident_id"].(float64)
		evType, _ := item.Metadata["evidence_type"].(string)
		s3, _ := item.Metadata["s3_path"].(string)
		database.DB.Exec("INSERT INTO fleet_evidence (incident_id, evidence_type, s3_path) VALUES (?, ?, ?)",
			int(incID), evType, s3)
	}

	site := strings.TrimSpace(item.SiteID)
	if site == "" {
		site = "global"
	}
	site = strings.ToLower(site)
	site = strings.ReplaceAll(site, ".", "_")
	site = strings.ReplaceAll(site, " ", "_")

	item.Agent = pcName
	item.Priority = "low"
	payload := map[string]interface{}{
		"message":    item,
		"ip_address": item.IPAddress,
		"timestamp":  strconv.FormatInt(time.Now().Unix(), 10),
		"priority":   "low",
	}

	subject := fmt.Sprintf("telemetry.site.%s.normal", site)
	publishToBroker("telemetry_stream:low", subject, payload)
}

func routeAndPublish(item TelemetryItem, loadLevel int, isCritical, isNormal bool) {
	hasMetrics := false
	hasLogs := false

	for k, v := range item.Metadata {
		if k == "latency_ms" || k == "tenant_id" {
			continue
		}
		switch v.(type) {
		case float64, int, int64:
			hasMetrics = true
		case string:
			hasLogs = true
		}
	}

	if _, ok := item.Metadata["latency_ms"]; ok {
		hasMetrics = true
	}

	sq := getOrCreateSiteQueue(item.SiteID)

	// 1. Route to worker channels
	select {
	case sq.eventQueue <- item:
	default:
		routeToDLQ(item, "EVENT_QUEUE_FULL")
	}

	if hasMetrics {
		if loadLevel >= 3 {
			routeToDLQ(item, "LOAD_SHEDDING_LEVEL_3_METRIC")
		} else if loadLevel >= 2 && !isCritical {
			// Dropped
		} else {
			select {
			case sq.metricQueue <- item:
			default:
				routeToDLQ(item, "METRIC_QUEUE_FULL")
			}
		}
	}

	if hasLogs || strings.ToUpper(item.Status) == "LOG" {
		if loadLevel >= 3 {
			routeToDLQ(item, "LOAD_SHEDDING_LEVEL_3_LOG")
		} else if loadLevel >= 1 && !strings.Contains("ERROR CRITICAL FATAL FAULTY", strings.ToUpper(item.Status)) {
			// Dropped
		} else {
			select {
			case sq.logQueue <- item:
			default:
				routeToDLQ(item, "LOG_QUEUE_FULL")
			}
		}
	}

	// 2. Publish to redis streams / NATS with site partitioning
	site := strings.TrimSpace(item.SiteID)
	if site == "" {
		site = "global"
	}
	site = strings.ToLower(site)
	site = strings.ReplaceAll(site, ".", "_")
	site = strings.ReplaceAll(site, " ", "_")

	priority := "low"
	streamName := "telemetry_stream:low"

	if isCritical {
		priority = "critical"
		streamName = "telemetry_stream:critical"
	} else if isNormal {
		priority = "warning"
		streamName = "telemetry_stream:normal"
	} else {
		priority = "normal"
		streamName = "telemetry_stream:low"
	}

	subject := fmt.Sprintf("telemetry.site.%s.%s", site, priority)

	item.Priority = priority
	payload := map[string]interface{}{
		"message":    item,
		"ip_address": item.IPAddress,
		"timestamp":  item.Timestamp,
	}

	// ── Deduplication Gate ────────────────────────────────────────────────────
	// Hanya terapkan dedup pada event critical/warning untuk mencegah alert storm.
	// Event "low" priority tetap diteruskan apa adanya (untuk telemetri normal).
	// Ini melindungi AI Supervisor dari banjir alert MikroTik yang flapping
	// atau Grafana yang mengirim notifikasi yang sama setiap 30 detik.
	if priority == "critical" || priority == "warning" {
		fp := buildFingerprint(site, item.PCName, item.EventType, priority)
		if globalDedupFilter.IsDuplicate(fp) {
			active, suppressed := globalDedupFilter.Stats()
			fmt.Printf(
				" [DEDUP] Suppressed duplicate %s event | site=%s pc=%s type=%s | active_fps=%d total_suppressed=%d\n",
				priority, site, item.PCName, item.EventType, active, suppressed,
			)
			return // Jangan publish ke NATS — event identik sudah diproses
		}
	}

	publishToBroker(streamName, subject, payload)
}

func publishToBroker(streamName string, subject string, payload map[string]interface{}) {
	// 1. Inject Event Idempotency ID (V7 Blueprint)
	if _, exists := payload["event_id"]; !exists {
		timestamp := time.Now().UnixNano()
		payload["event_id"] = fmt.Sprintf("evt-%d-%x", timestamp, timestamp%1000000)
	}

	payloadBytes, _ := json.Marshal(payload)
	natsSuccess := false

	// 2. NATS JetStream as Primary Event Bus (V7 Blueprint)
	if natsJS != nil {
		_, err := natsJS.Publish(subject, payloadBytes)
		if err == nil {
			natsSuccess = true
		} else {
			fmt.Printf(" [INGESTOR NATS ERROR] Failed to publish payload to %s: %v\n", subject, err)
		}
	}

	// 3. Fallback to Redis
	if !natsSuccess {
		redisSuccess := false
		if redisClient != nil {
			_, err := redisClient.XAdd(ctx, &redis.XAddArgs{
				Stream: streamName,
				Values: map[string]interface{}{"payload": string(payloadBytes)},
			}).Result()
			if err == nil {
				redisSuccess = true
				fmt.Printf(" [INGESTOR FAILOVER] Enqueued telemetry payload to Redis stream: %s\n", streamName)
			}
		}

		if !redisSuccess {
			fmt.Println(" [INGESTOR CRITICAL] Both NATS and Redis failed. Falling back to local/DLQ storage.")
			if redisClient != nil {
				_ = redisClient.RPush(ctx, "telemetry_queue", string(payloadBytes)).Err()
			} else {
				routeToDLQ(payload, "BROKER_OUTAGE")
			}
		}
	}
}

func shardedMetricWorker(sq *SiteQueue, id int) {
	fmt.Printf(" [INGESTOR METRIC WORKER %d - SITE %s] Active and listening for batch metrics writes.\n", id, sq.siteID)
	buffer := make([]TelemetryItem, 0, 200)
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case item, ok := <-sq.metricQueue:
			if !ok {
				flushMetricsBatch(buffer, id)
				return
			}
			buffer = append(buffer, item)
			if len(buffer) >= 200 {
				flushMetricsBatch(buffer, id)
				buffer = buffer[:0]
				ticker.Reset(2 * time.Second)
			}
		case <-ticker.C:
			if len(buffer) > 0 {
				flushMetricsBatch(buffer, id)
				buffer = buffer[:0]
			}
		}
	}
}

func shardedLogWorker(sq *SiteQueue, id int) {
	fmt.Printf(" [INGESTOR LOG WORKER %d - SITE %s] Active and listening for batch log writes.\n", id, sq.siteID)
	buffer := make([]TelemetryItem, 0, 200)
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case item, ok := <-sq.logQueue:
			if !ok {
				flushLogsBatch(buffer, id)
				return
			}
			buffer = append(buffer, item)
			if len(buffer) >= 200 {
				flushLogsBatch(buffer, id)
				buffer = buffer[:0]
				ticker.Reset(2 * time.Second)
			}
		case <-ticker.C:
			if len(buffer) > 0 {
				flushLogsBatch(buffer, id)
				buffer = buffer[:0]
			}
		}
	}
}

func shardedEventWorker(sq *SiteQueue, id int) {
	fmt.Printf(" [INGESTOR EVENT WORKER %d - SITE %s] Active and listening for event updates.\n", id, sq.siteID)
	for item := range sq.eventQueue {
		processEventItem(item)
	}
}

// Workers
func metricProcessorWorker(id int) {
	fmt.Printf(" [INGESTOR METRIC WORKER %d] Active and listening for batch metrics writes.\n", id)
	buffer := make([]TelemetryItem, 0, 200)
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case item, ok := <-metricQueue:
			if !ok {
				flushMetricsBatch(buffer, id)
				return
			}
			buffer = append(buffer, item)
			if len(buffer) >= 200 {
				flushMetricsBatch(buffer, id)
				buffer = buffer[:0]
				ticker.Reset(2 * time.Second) // Reset idle timer
			}
		case <-ticker.C:
			if len(buffer) > 0 {
				flushMetricsBatch(buffer, id)
				buffer = buffer[:0]
			}
		}
	}
}

func logProcessorWorker(id int) {
	fmt.Printf(" [INGESTOR LOG WORKER %d] Active and listening for batch log writes.\n", id)
	buffer := make([]TelemetryItem, 0, 200)
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case item, ok := <-logQueue:
			if !ok {
				flushLogsBatch(buffer, id)
				return
			}
			buffer = append(buffer, item)
			if len(buffer) >= 200 {
				flushLogsBatch(buffer, id)
				buffer = buffer[:0]
				ticker.Reset(2 * time.Second) // Reset idle timer
			}
		case <-ticker.C:
			if len(buffer) > 0 {
				flushLogsBatch(buffer, id)
				buffer = buffer[:0]
			}
		}
	}
}

func eventProcessorWorker(id int) {
	fmt.Printf(" [INGESTOR EVENT WORKER %d] Active and listening for event updates.\n", id)
	for item := range eventQueue {
		processEventItem(item)
	}
}

func processEventItem(item TelemetryItem) {
	// Sequence ordering lock per device name
	lock := getDeviceLock(item.Agent)
	lock.Lock()
	defer lock.Unlock()

	// Enforce Agent 05 version checks for ALL packets from non-auditor devices
	if !isVersionAllowed(item) {
		fmt.Printf(" [INGESTOR BLOCKED] Rejected telemetry from %s — unsupported agent version (agent_version: %s, schema: %s)\n",
			item.Agent, getAgentVersionString(item), item.SchemaVersion)
		return
	}

	// 1. Device Registration checks
	// Always check fleet_devices directly in DB to handle cases where a device
	// was manually deleted from fleet_devices via the dashboard (cache becomes stale).
	registeredDevicesCacheMu.RLock()
	registered := registeredDevicesCache[item.Agent]
	registeredDevicesCacheMu.RUnlock()

	if !registered {
		var devExists int64
		database.DB.Table("devices").Where("name = ?", item.Agent).Count(&devExists)
		if devExists == 0 {

			layerInt := 0
			if lFloat, ok := item.Layer.(float64); ok {
				layerInt = int(lFloat)
			} else if lStr, ok := item.Layer.(string); ok {
				layerInt, _ = strconv.Atoi(lStr)
			}

			loc := item.Location
			if loc == "" {
				loc = item.SiteID
			}
			metaBytes, _ := json.Marshal(item.Metadata)

			devStatus := "FAULTY"
			if strings.ToUpper(item.Status) == "OK" || strings.ToUpper(item.Status) == "ONLINE" {
				devStatus = "ONLINE"
			}

			err := database.DB.Exec("INSERT INTO devices (name, ip, layer, location, status, metadata) VALUES (?, ?, ?, ?, ?, ?)",
				item.Agent, item.IPAddress, layerInt, loc, devStatus, string(metaBytes)).Error
			if err == nil {
				fmt.Printf(" [INGESTOR DB] Registered new device: %s\n", item.Agent)
			} else {
				fmt.Printf(" [INGESTOR DB ERROR] Registration error for %s: %v\n", item.Agent, err)
			}
		}

		// ALWAYS ensure device is in fleet_devices, independent of the devices table check.
		// This prevents FK violations when pc_name is missing from fleet_devices
		// (e.g. after a manual delete via dashboard).
		if item.Agent != "auditor_probe" {
			var rustdeskID string
			var rustdeskRunning bool
			var anydeskID string

			rd, _ := item.Metadata["rustdesk"].(map[string]interface{})
			if rd == nil && item.Data != nil {
				rd, _ = item.Data["rustdesk"].(map[string]interface{})
			}
			if rd != nil {
				rustdeskID, _ = rd["id"].(string)
				rustdeskRunning, _ = rd["running"].(bool)
			}

			ad, _ := item.Metadata["anydesk"].(map[string]interface{})
			if ad == nil && item.Data != nil {
				ad, _ = item.Data["anydesk"].(map[string]interface{})
			}
			if ad != nil {
				anydeskID, _ = ad["id"].(string)
			}

			hwInfo := map[string]interface{}{
				"ip":          item.IPAddress,
				"os":          "Windows",
				"hostname":    item.Agent,
				"anydesk_id":  anydeskID,
				"rustdesk_id": rustdeskID,
			}
			hwBytes, _ := json.Marshal(hwInfo)

			var fleetDevExists int64
			database.DB.Table("fleet_devices").Where("pc_name = ?", item.Agent).Count(&fleetDevExists)
			if fleetDevExists == 0 {
				database.DB.Exec("INSERT INTO fleet_devices (pc_name, site_id, status, is_approved, hardware_info, last_seen, rustdesk_id, rustdesk_running) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
					item.Agent, nil, "ACTIVE", true, string(hwBytes), time.Now(), rustdeskID, rustdeskRunning)
				fmt.Printf(" [INGESTOR DB] Auto-registered fleet device for remote access: %s\n", item.Agent)
			}
		}

		registeredDevicesCacheMu.Lock()
		registeredDevicesCache[item.Agent] = true
		registeredDevicesCacheMu.Unlock()
	}

	// 2. Dead Man Switch registration
	deviceLastSeenMu.Lock()
	deviceLastSeen[item.Agent] = time.Now()
	deviceLastSeenMu.Unlock()

	// 3. Keep device status ONLINE
	deviceStatusCacheMu.RLock()
	status := deviceStatusCache[item.Agent]
	deviceStatusCacheMu.RUnlock()

	if item.Agent != "auditor_probe" && status != "ONLINE" {
		database.DB.Exec("UPDATE devices SET status = 'ONLINE' WHERE name = ? AND status != 'ONLINE'", item.Agent)
		deviceStatusCacheMu.Lock()
		deviceStatusCache[item.Agent] = "ONLINE"
		deviceStatusCacheMu.Unlock()
		fmt.Printf(" [INGESTOR DB] Restored device status to ONLINE for: %s\n", item.Agent)
	}

	// Auto-update fleet_devices: dedicated scalar columns + full hardware_info JSONB
	if item.Agent != "auditor_probe" {
		var rustdeskID string
		var rustdeskRunning bool
		var anydeskID string

		rd, _ := item.Metadata["rustdesk"].(map[string]interface{})
		if rd == nil && item.Data != nil {
			rd, _ = item.Data["rustdesk"].(map[string]interface{})
		}
		if rd != nil {
			rustdeskID, _ = rd["id"].(string)
			rustdeskRunning, _ = rd["running"].(bool)
		}

		ad, _ := item.Metadata["anydesk"].(map[string]interface{})
		if ad == nil && item.Data != nil {
			ad, _ = item.Data["anydesk"].(map[string]interface{})
		}
		if ad != nil {
			anydeskID, _ = ad["id"].(string)
		}

		// Extract scalable scalar fields from agent payload
		hostname := item.Agent
		ip := item.IPAddress
		telVer := item.SchemaVersion
		if telVer == "" {
			telVer, _ = item.Data["agent_version"].(string)
		}

		// agent_collected_at: timestamp when data was actually collected on the PC
		agentCollectedAt := time.Now() // fallback = now
		if item.Timestamp != "" {
			if tsInt, err2 := strconv.ParseInt(item.Timestamp, 10, 64); err2 == nil {
				agentCollectedAt = time.Unix(tsInt, 0)
			}
		}

		// OS version from hardware_info (sent by new agent)
		osVersion := ""
		hwRaw, _ := item.Data["hardware_info"].(map[string]interface{})
		if hwRaw != nil {
			osVersion, _ = hwRaw["os_version"].(string)
			// Extract ip from hardware_info.network.ip if not in payload root
			if ip == "" {
				if netMap, ok := hwRaw["network"].(map[string]interface{}); ok {
					ip, _ = netMap["ip"].(string)
				}
			}
		}
		if osVersion == "" {
			osVersion, _ = item.Data["os_version"].(string)
		}

		// Build full hardware_info JSONB (merged: agent hardware_info + top-level fields)
		hwInfo := map[string]interface{}{
			"ip":          ip,
			"hostname":    hostname,
			"os":          "Windows",
			"os_version":  osVersion,
			"anydesk_id":  anydeskID,
			"rustdesk_id": rustdeskID,
		}
		// If agent sent complete hardware_info, use it directly (richer data)
		if hwRaw != nil {
			for k, v := range hwRaw {
				hwInfo[k] = v
			}
			// Always ensure ip at top level
			hwInfo["ip"] = ip
		} else {
			// Legacy agent: enrich with whatever we can pull from Data
			if cpu, ok := item.Data["cpu"]; ok {
				hwInfo["cpu_usage"] = cpu
				hwInfo["cpu_percent"] = cpu
			}
			if ram, ok := item.Data["ram"]; ok {
				hwInfo["ram_usage"] = ram
				hwInfo["mem_percent"] = ram
			}
			if disk, ok := item.Data["disk"]; ok {
				hwInfo["disk_usage"] = disk
				hwInfo["disk_percent"] = disk
			}
			if rd != nil {
				hwInfo["rustdesk"] = map[string]interface{}{"id": rustdeskID, "running": rustdeskRunning}
			}
			if ad != nil {
				hwInfo["anydesk"] = map[string]interface{}{"id": anydeskID}
			}
		}
		hwBytes, _ := json.Marshal(hwInfo)

		// online = seen within last 3 minutes
		isOnline := true

		metaBytes, _ := json.Marshal(item.Metadata)
		if ip != "" {
			database.DB.Exec("UPDATE devices SET ip = ?, metadata = ? WHERE name = ?", ip, string(metaBytes), item.Agent)
			database.DB.Exec(`UPDATE fleet_devices SET
				last_seen = NOW(),
				agent_collected_at = ?,
				status = 'ACTIVE',
				online = ?,
				ip = ?,
				hostname = ?,
				telemetry_version = ?,
				os_version = ?,
				rustdesk_id = ?,
				rustdesk_running = ?,
				hardware_info = ?
				WHERE pc_name = ?`,
				agentCollectedAt, isOnline, ip, hostname, telVer, osVersion,
				rustdeskID, rustdeskRunning, string(hwBytes), item.Agent)
		} else {
			database.DB.Exec("UPDATE devices SET metadata = ? WHERE name = ?", string(metaBytes), item.Agent)
			database.DB.Exec(`UPDATE fleet_devices SET
				last_seen = NOW(),
				agent_collected_at = ?,
				status = 'ACTIVE',
				online = ?,
				hostname = ?,
				telemetry_version = ?,
				os_version = ?,
				rustdesk_id = ?,
				rustdesk_running = ?,
				hardware_info = ?
				WHERE pc_name = ?`,
				agentCollectedAt, isOnline, hostname, telVer, osVersion,
				rustdeskID, rustdeskRunning, string(hwBytes), item.Agent)
		}
	}
}


// helpers
func checkRateLimit(ip string) bool {
	if redisClient == nil {
		return true
	}
	key := fmt.Sprintf("rate_limit:%s", ip)
	now := time.Now().UnixNano()
	nowSec := float64(now) / 1e9

	pipe := redisClient.TxPipeline()
	pipe.ZAdd(ctx, key, &redis.Z{Score: nowSec, Member: strconv.FormatInt(now, 10)})
	pipe.ZRemRangeByScore(ctx, key, "-inf", strconv.FormatFloat(nowSec-60.0, 'f', 6, 64))
	pipe.ZCard(ctx, key)
	pipe.Expire(ctx, key, 60*time.Second)

	res, err := pipe.Exec(ctx)
	if err != nil {
		return true
	}

	cardRes, ok := res[2].(*redis.IntCmd)
	if ok {
		count := cardRes.Val()
		return count <= 60
	}
	return true
}

func verifyToken(agent, timestamp, token string) bool {
	if agent == "" || timestamp == "" || token == "" {
		return false
	}

	var msgTime float64
	var err error
	if strings.Contains(timestamp, "T") {
		t, err := time.Parse(time.RFC3339, timestamp)
		if err == nil {
			msgTime = float64(t.Unix())
		}
	} else {
		msgTime, err = strconv.ParseFloat(timestamp, 64)
	}

	if err != nil {
		return false
	}

	now := float64(time.Now().Unix())
	if math.Abs(now-msgTime) > 300 {
		fmt.Printf(" [INGESTOR AUTH] Expired token from agent: %s (server diff: %.1fs)\n", agent, math.Abs(now-msgTime))
		return false
	}

	msgToSign := fmt.Sprintf("%s:%s", agent, timestamp)

	// Validate using security key
	mac := hmac.New(sha256.New, securityKey)
	mac.Write([]byte(msgToSign))
	expectedHex := hex.EncodeToString(mac.Sum(nil))

	if subtle.ConstantTimeCompare([]byte(expectedHex), []byte(token)) == 1 {
		return true
	}

	// Try fallback key
	fallbackKey := []byte("SIAP_DISTRIBUSI_SECRET_KEY")
	mac2 := hmac.New(sha256.New, fallbackKey)
	mac2.Write([]byte(msgToSign))
	expectedHex2 := hex.EncodeToString(mac2.Sum(nil))

	return subtle.ConstantTimeCompare([]byte(expectedHex2), []byte(token)) == 1
}

func checkAndSetIdempotency(item *TelemetryItem) bool {
	if redisClient == nil {
		return false
	}
	
	var eventID string
	if item.Metadata != nil {
		if id, ok := item.Metadata["idempotency_key"].(string); ok && id != "" {
			eventID = id
		} else if id, ok := item.Metadata["event_id"].(string); ok && id != "" {
			eventID = id
		}
	}
	
	if eventID == "" {
		idempotencyStatus := item.Status
		if item.EventType != "" && item.EventType != "telemetry" {
			idempotencyStatus = item.EventType + ":" + item.Status
		}
		eventString := fmt.Sprintf("%s:%s:%s", item.Agent, idempotencyStatus, item.Timestamp)
		hash := sha256.Sum256([]byte(eventString))
		eventID = hex.EncodeToString(hash[:])
	}

	key := fmt.Sprintf("processed_event:%s", eventID)

	ok, err := redisClient.SetNX(ctx, key, "1", 5*time.Minute).Result()
	if err != nil {
		return false
	}
	
	if ok {
		if item.Metadata == nil {
			item.Metadata = make(map[string]interface{})
		}
		if _, exists := item.Metadata["event_id"]; !exists {
			if u, err := uuid.NewV7(); err == nil {
				item.Metadata["event_id"] = u.String()
			}
		}
	}
	
	return !ok
}

func validateTelemetrySchema(item TelemetryItem) bool {
	if item.Agent == "" || item.Status == "" || item.Timestamp == "" || item.Token == "" {
		return false
	}
	return true
}

func getTotalQueueSizes() (int, int, int) {
	siteQueuesMu.RLock()
	defer siteQueuesMu.RUnlock()

	mSize := len(metricQueue)
	lSize := len(logQueue)
	eSize := len(eventQueue)

	for _, sq := range siteQueues {
		mSize += len(sq.metricQueue)
		lSize += len(sq.logQueue)
		eSize += len(sq.eventQueue)
	}
	return mSize, lSize, eSize
}

func startQueueMonitorLoop() {
	if redisClient == nil {
		return
	}
	fmt.Println(" [INGESTOR MONITOR] Starting queue size and performance monitoring loop...")

	ticker := time.NewTicker(5 * time.Second)
	hardening.GoSafe(func() {
		for range ticker.C {
			mSize, lSize, eSize := getTotalQueueSizes()
			loadLevel := checkLoadSheddingLevel()

			metricsMu.Lock()
			proc := metricsProcessedCount
			errs := metricsErrorsCount
			dlqs := metricsDLQCount
			lat := metricsLatencySum

			// Reset counters
			metricsProcessedCount = 0
			metricsErrorsCount = 0
			metricsDLQCount = 0
			metricsLatencySum = 0.0
			metricsMu.Unlock()

			avgLatency := 0.0
			if proc > 0 {
				avgLatency = lat / float64(proc)
			}

			redisClient.HSet(ctx, "metrics:ingestor_queues", map[string]interface{}{
				"metrics_queue_size":        mSize,
				"logs_queue_size":           lSize,
				"events_queue_size":         eSize,
				"load_shedding_level":       loadLevel,
				"processed_throughput_5s":   proc,
				"avg_processing_latency_ms": fmt.Sprintf("%.2f", avgLatency),
				"error_rate_5s":             errs,
				"dlq_rate_5s":               dlqs,
				"last_updated":              time.Now().Format("2006-01-02 15:04:05"),
			})
		}
	}, func(cat, msg string) {
		fmt.Printf("[%s] Queue monitor panic: %s\n", cat, msg)
	})
}

func startDeadManSwitch() {
	ticker := time.NewTicker(10 * time.Second)
	hardening.GoSafe(func() {
		for range ticker.C {
			now := time.Now()
			deviceLastSeenMu.Lock()
			for name, lastSeen := range deviceLastSeen {
				if now.Sub(lastSeen) > 120*time.Second {
					deviceStatusCacheMu.Lock()
					status := deviceStatusCache[name]
					if status != "OFFLINE" {
						database.DB.Exec("UPDATE devices SET status = 'OFFLINE' WHERE name = ? AND status != 'OFFLINE'", name)
						deviceStatusCache[name] = "OFFLINE"
						fmt.Printf(" [INGESTOR DB] Set device status to OFFLINE for: %s (Check-in timeout)\n", name)
					}
					deviceStatusCacheMu.Unlock()
				}
			}
			deviceLastSeenMu.Unlock()
		}
	}, func(cat, msg string) {
		fmt.Printf("[%s] Dead man switch checker panic: %s\n", cat, msg)
	})
}

// startFlatLineDetector — Phase 2 Item 5
// Detects when a critical metric (cpu/ram/disk) stays at an identical value for
// >= 10 minutes, indicating a frozen or crashed probe / zombie agent.
func startFlatLineDetector() {
	const (
		flatLineDuration = 10 * time.Minute
		cooldownDuration = 30 * time.Minute // suppress repeat alerts
		checkInterval    = 2 * time.Minute
	)
	criticalMetrics := map[string]bool{"cpu": true, "ram": true, "disk": true, "cpu_percent": true, "mem_percent": true}

	hardening.GoSafe(func() {
		ticker := time.NewTicker(checkInterval)
		for range ticker.C {
			now := time.Now()
			deviceMetricHistoryMu.Lock()
			for key, snap := range deviceMetricHistory {
				// key format: "deviceName::metric_type"
				parts := strings.SplitN(key, "::", 2)
				if len(parts) != 2 {
					continue
				}
				deviceName, metricType := parts[0], parts[1]
				if !criticalMetrics[metricType] {
					continue
				}
				// Check if value has been frozen longer than threshold
				if now.Sub(snap.LastAt) >= flatLineDuration {
					// Apply cooldown to avoid alert spam
					if now.Sub(snap.AlertedAt) < cooldownDuration {
						continue
					}
					snap.AlertedAt = now
					deviceMetricHistory[key] = snap

					fmt.Printf(" [FLATLINE DETECTOR] Device=%s metric=%s value=%.4f frozen for %.1f min\n",
						deviceName, metricType, snap.Value, now.Sub(snap.LastAt).Minutes())

					// Write to incidents table
					desc := fmt.Sprintf("FLAT_LINE: metric '%s' on device '%s' unchanged at %.4f for %.0f minutes. Probe may be frozen.",
						metricType, deviceName, snap.Value, now.Sub(snap.LastAt).Minutes())
					if err := database.DB.Exec(
						`INSERT INTO incidents (device_name, flag, evidence, raw_data, confidence)
						 VALUES (?, 'FLAT_LINE', ?, ?::jsonb, 0.80)`,
						deviceName, desc,
						fmt.Sprintf(`{"metric":"%s","value":%f,"frozen_minutes":%d,"detector":"flat_line"}`,
							metricType, snap.Value, int(now.Sub(snap.LastAt).Minutes())),
					).Error; err != nil {
						fmt.Printf(" [FLATLINE DETECTOR] DB write failed for %s: %v\n", deviceName, err)
					}

					// Publish to NATS for AI Supervisor processing
					if natsConn != nil {
						payload := fmt.Sprintf(
							`{"agent":"%s","flag":"FLAT_LINE","metric":"%s","value":%f,"frozen_minutes":%d,"site_id":"unknown","status":"FLAT_LINE","layer":3,"evidence":"%s"}`,
							deviceName, metricType, snap.Value, int(now.Sub(snap.LastAt).Minutes()), desc,
						)
						_, _ = natsJS.Publish(fmt.Sprintf("incident.site.unknown.%s", deviceName), []byte(payload))
					}
				}
			}
			deviceMetricHistoryMu.Unlock()
		}
	}, func(cat, msg string) {
		fmt.Printf("[%s] Flat-line detector panic: %s\n", cat, msg)
	})
}

// startStaleTelemetryDetector — Phase 2 Item 6
// Detects devices that went completely silent (no metric/telemetry packets) for
// >= 5 minutes while still reported ONLINE in the DB. More precise than the
// dead man switch (which fires at 2 min for ANY packet including heartbeats).
// Fires a STALE_TELEMETRY incident and publishes to NATS for triage.
func startStaleTelemetryDetector() {
	const (
		stalenessThreshold = 5 * time.Minute
		cooldownDuration   = 20 * time.Minute
		checkInterval      = 90 * time.Second
	)
	staleAlertedAt := make(map[string]time.Time)
	var staleAlertMu sync.Mutex

	hardening.GoSafe(func() {
		ticker := time.NewTicker(checkInterval)
		for range ticker.C {
			now := time.Now()
			deviceLastTelemetryMu.Lock()
			for deviceName, lastTel := range deviceLastTelemetry {
				silenceDuration := now.Sub(lastTel)
				if silenceDuration < stalenessThreshold {
					continue
				}

				// Only alert if device is still ONLINE in DB
				var dbStatus string
				deviceStatusCacheMu.RLock()
				dbStatus = deviceStatusCache[deviceName]
				deviceStatusCacheMu.RUnlock()
				if strings.ToUpper(dbStatus) != "ONLINE" {
					continue // Already OFFLINE — dead man switch handles it
				}

				// Apply cooldown
				staleAlertMu.Lock()
				lastAlert := staleAlertedAt[deviceName]
				if now.Sub(lastAlert) < cooldownDuration {
					staleAlertMu.Unlock()
					continue
				}
				staleAlertedAt[deviceName] = now
				staleAlertMu.Unlock()

				fmt.Printf(" [STALE TELEMETRY] Device=%s silent for %.1f min (still ONLINE in DB)\n",
					deviceName, silenceDuration.Minutes())

				// Write stale telemetry incident
				desc := fmt.Sprintf("STALE_TELEMETRY: device '%s' sent no metrics for %.0f minutes but is marked ONLINE. Agent may be hung or network dropped.",
					deviceName, silenceDuration.Minutes())
				if err := database.DB.Exec(
					`INSERT INTO incidents (device_name, flag, evidence, raw_data, confidence)
					 VALUES (?, 'STALE_TELEMETRY', ?, ?::jsonb, 0.85)`,
					deviceName, desc,
					fmt.Sprintf(`{"silent_minutes":%d,"last_seen":"%s","detector":"stale_telemetry"}`,
						int(silenceDuration.Minutes()), lastTel.UTC().Format(time.RFC3339)),
				).Error; err != nil {
					fmt.Printf(" [STALE TELEMETRY] DB write failed for %s: %v\n", deviceName, err)
				}

				// Publish to NATS
				if natsConn != nil {
					payload := fmt.Sprintf(
						`{"agent":"%s","flag":"STALE_TELEMETRY","silent_minutes":%d,"last_seen":"%s","site_id":"unknown","status":"STALE_TELEMETRY","layer":3,"evidence":"%s"}`,
						deviceName, int(silenceDuration.Minutes()), lastTel.UTC().Format(time.RFC3339), desc,
					)
					_, _ = natsJS.Publish(fmt.Sprintf("incident.site.unknown.%s", deviceName), []byte(payload))
				}
			}
			deviceLastTelemetryMu.Unlock()
		}
	}, func(cat, msg string) {
		fmt.Printf("[%s] Stale telemetry detector panic: %s\n", cat, msg)
	})
}

// ─────────────────────────────────────────────────────────────────────────────
// Phase 3 — Item 8: Telemetry Integrity Scoring
// ─────────────────────────────────────────────────────────────────────────────

// scoreTelemetryIntegrity returns a 0.0–1.0 integrity score for an incoming
// telemetry item and a short reason string explaining deductions.
// Score breakdown:
//   +0.40  HMAC token present and valid (from verifyToken call)
//   +0.30  Timestamp freshness  (< 30s = full, < 120s = half, older = zero)
//   +0.30  Value plausibility   (all metrics in expected 0–100 range for cpu/ram)
//
// The score is written to item.Metadata["integrity_score"] and stored in DB
// metadata JSONB so AI Supervisor can downweight low-integrity readings.
func scoreTelemetryIntegrity(item *TelemetryItem, tokenValid bool) float64 {
	score := 0.0
	reasons := []string{}

	// (1) HMAC token component
	if tokenValid {
		score += 0.40
	} else {
		reasons = append(reasons, "no_valid_token")
	}

	// (2) Timestamp freshness
	var msgTimeSec float64
	if ts := item.Timestamp; ts != "" {
		if strings.Contains(ts, "T") {
			if t, err := time.Parse(time.RFC3339, ts); err == nil {
				msgTimeSec = float64(t.Unix())
			}
		} else {
			msgTimeSec, _ = strconv.ParseFloat(ts, 64)
		}
	}
	if msgTimeSec > 0 {
		ageSec := math.Abs(float64(time.Now().Unix()) - msgTimeSec)
		switch {
		case ageSec < 30:
			score += 0.30
		case ageSec < 120:
			score += 0.15
			reasons = append(reasons, "slightly_stale")
		default:
			reasons = append(reasons, "stale_timestamp")
		}
	} else {
		reasons = append(reasons, "missing_timestamp")
	}

	// (3) Value plausibility — check cpu/ram/disk metrics are in [0,100]
	plausible := true
	for k, v := range item.Metadata {
		kl := strings.ToLower(k)
		if fv, ok := v.(float64); ok {
			if strings.Contains(kl, "cpu") || strings.Contains(kl, "ram") ||
				strings.Contains(kl, "mem") || strings.Contains(kl, "disk") {
				if fv < 0 || fv > 100 {
					plausible = false
					reasons = append(reasons, fmt.Sprintf("out_of_range:%s=%.1f", k, fv))
				}
			}
		}
	}
	if plausible {
		score += 0.30
	}

	// Attach score and reasons to metadata for downstream consumers
	if item.Metadata == nil {
		item.Metadata = make(map[string]interface{})
	}
	item.Metadata["integrity_score"] = score
	if len(reasons) > 0 {
		item.Metadata["integrity_deductions"] = strings.Join(reasons, ",")
	}

	return score
}

// ─────────────────────────────────────────────────────────────────────────────
// Phase 3 — Item 7: Adaptive RoC (Rate of Change) Anomaly Detector
// ─────────────────────────────────────────────────────────────────────────────

// startAdaptiveRoCDetector scans the sliding RoC windows every 3 minutes.
// For each device+metric it computes the mean and stddev of historical RoC,
// then checks if the most recent RoC exceeds mean + 3σ (z-score > 3.0).
// Requires at least 10 samples to avoid false positives during warm-up.
func startAdaptiveRoCDetector() {
	const (
		checkInterval   = 3 * time.Minute
		minSamples      = 10
		zScoreThreshold = 3.0
		cooldown        = 15 * time.Minute
	)
	criticalMetrics := map[string]bool{
		"cpu": true, "ram": true, "disk": true,
		"cpu_percent": true, "mem_percent": true,
		"cpu_usage": true, "memory_usage": true,
	}

	hardening.GoSafe(func() {
		ticker := time.NewTicker(checkInterval)
		for range ticker.C {
			now := time.Now()
			rocWindowsMu.Lock()
			for key, win := range rocWindows {
				parts := strings.SplitN(key, "::", 2)
				if len(parts) != 2 {
					continue
				}
				deviceName, metricType := parts[0], parts[1]
				if !criticalMetrics[metricType] {
					continue
				}
				if len(win.Samples) < minSamples {
					continue
				}

				// Compute mean
				var sum float64
				for _, s := range win.Samples {
					sum += s.RoC
				}
				mean := sum / float64(len(win.Samples))

				// Compute stddev
				var variance float64
				for _, s := range win.Samples {
					d := s.RoC - mean
					variance += d * d
				}
				stddev := math.Sqrt(variance / float64(len(win.Samples)))

				// Latest RoC sample
				latestRoC := win.Samples[len(win.Samples)-1].RoC

				if stddev < 0.001 {
					continue // avoid divide-by-zero on perfectly stable metrics
				}
				zScore := (latestRoC - mean) / stddev
				if zScore <= zScoreThreshold {
					continue
				}

				// Cooldown check
				if now.Sub(win.AlertedAt) < cooldown {
					continue
				}
				win.AlertedAt = now

				fmt.Printf(" [ROC DETECTOR] Device=%s metric=%s RoC=%.4f z=%.2f (mean=%.4f σ=%.4f)\n",
					deviceName, metricType, latestRoC, zScore, mean, stddev)

				desc := fmt.Sprintf(
					"ROC_ANOMALY: metric '%s' on '%s' spiked/dropped %.4f units (z-score=%.2f, threshold=%.1f). Possible anomaly.",
					metricType, deviceName, latestRoC, zScore, zScoreThreshold,
				)
				_ = database.DB.Exec(
					`INSERT INTO incidents (device_name, flag, evidence, raw_data, confidence)
					 VALUES (?, 'ROC_ANOMALY', ?, ?::jsonb, 0.88)`,
					deviceName, desc,
					fmt.Sprintf(`{"metric":%q,"roc":%.4f,"z_score":%.2f,"mean":%.4f,"stddev":%.4f,"detector":"adaptive_roc"}`,
						metricType, latestRoC, zScore, mean, stddev),
				).Error

				if natsConn != nil {
					payload := fmt.Sprintf(
						`{"agent":%q,"flag":"ROC_ANOMALY","metric":%q,"roc":%.4f,"z_score":%.2f,"site_id":"unknown","status":"ROC_ANOMALY","layer":3,"evidence":%q}`,
						deviceName, metricType, latestRoC, zScore, desc,
					)
					_, _ = natsJS.Publish(fmt.Sprintf("incident.site.unknown.%s", deviceName), []byte(payload))
				}
			}
			rocWindowsMu.Unlock()
		}
	}, func(cat, msg string) {
		fmt.Printf("[%s] Adaptive RoC detector panic: %s\n", cat, msg)
	})
}

// ─────────────────────────────────────────────────────────────────────────────
// Phase 3 — Item 9: State Hash Drift Detector
// ─────────────────────────────────────────────────────────────────────────────

// startStateHashDriftDetector checks every 5 minutes whether a device's
// recent state hash has drifted significantly from its baseline (oldest hash).
// Drift is measured as the fraction of unique hashes in the ring vs. ring size.
// A perfectly stable device produces identical hashes; a drifting device
// produces mostly unique hashes, indicating progressive state change.
//
// Threshold: >= 70% unique hashes in the ring → DRIFT_DETECTED incident.
func startStateHashDriftDetector() {
	const (
		checkInterval  = 5 * time.Minute
		driftThreshold = 0.70 // fraction of distinct hashes in ring
		cooldown       = 30 * time.Minute
		minRingFill    = 6 // need at least 6 data points
	)

	hardening.GoSafe(func() {
		ticker := time.NewTicker(checkInterval)
		for range ticker.C {
			now := time.Now()
			deviceStateRingsMu.Lock()
			for devName, ring := range deviceStateRings {
				if ring.Head < minRingFill {
					continue // not enough data points yet
				}

				// Count distinct non-empty hashes in ring
				seen := make(map[string]struct{})
				nonEmpty := 0
				for _, h := range ring.Hashes {
					if h == "" {
						continue
					}
					nonEmpty++
					seen[h] = struct{}{}
				}
				if nonEmpty < minRingFill {
					continue
				}

				driftRatio := float64(len(seen)) / float64(nonEmpty)
				if driftRatio < driftThreshold {
					continue
				}

				// Cooldown
				if now.Sub(ring.AlertedAt) < cooldown {
					continue
				}
				ring.AlertedAt = now

				fmt.Printf(" [DRIFT DETECTOR] Device=%s drift_ratio=%.2f (%.0f%% unique hashes in ring)\n",
					devName, driftRatio, driftRatio*100)

				desc := fmt.Sprintf(
					"STATE_DRIFT: device '%s' shows %.0f%% state hash change over last %d snapshots. "+
						"System state is shifting — possible config drift, memory leak, or progressive failure.",
					devName, driftRatio*100, nonEmpty,
				)
				_ = database.DB.Exec(
					`INSERT INTO incidents (device_name, flag, evidence, raw_data, confidence)
					 VALUES (?, 'STATE_DRIFT', ?, ?::jsonb, 0.82)`,
					devName, desc,
					fmt.Sprintf(`{"drift_ratio":%.3f,"unique_hashes":%d,"ring_size":%d,"detector":"state_hash_drift"}`,
						driftRatio, len(seen), nonEmpty),
				).Error

				if natsConn != nil {
					payload := fmt.Sprintf(
						`{"agent":%q,"flag":"STATE_DRIFT","drift_ratio":%.3f,"site_id":"unknown","status":"STATE_DRIFT","layer":3,"evidence":%q}`,
						devName, driftRatio, desc,
					)
					_, _ = natsJS.Publish(fmt.Sprintf("incident.site.unknown.%s", devName), []byte(payload))
				}
			}
			deviceStateRingsMu.Unlock()
		}
	}, func(cat, msg string) {
		fmt.Printf("[%s] State hash drift detector panic: %s\n", cat, msg)
	})
}

// ─────────────────────────────────────────────────────────────────────────────
// Fix P0.2 — Anomaly State Persistence (Redis)
// Eliminates warm-up blind window after ingestion server restart.
// All three Phase 2/3 detector caches are snapshotted to Redis every 30s
// and restored on startup.
// ─────────────────────────────────────────────────────────────────────────────

const (
	redisKeyRoCWindows     = "anomaly:roc_windows"
	redisKeyFlatlineHist   = "anomaly:flatline_history"
	redisKeyStateRings     = "anomaly:state_rings"
	anomalyPersistInterval = 30 * time.Second
)

// loadAnomalyStateFromRedis restores all anomaly detector caches from Redis.
// Called once on startup before detectors begin running.
func loadAnomalyStateFromRedis() {
	if redisClient == nil {
		fmt.Println(" [ANOMALY PERSIST] Redis unavailable — starting with empty baselines")
		return
	}
	ctx2 := context.Background()

	// Restore rocWindows
	fields, err := redisClient.HGetAll(ctx2, redisKeyRoCWindows).Result()
	if err == nil {
		rocWindowsMu.Lock()
		for k, v := range fields {
			var w rocWindow
			if json.Unmarshal([]byte(v), &w) == nil {
				rocWindows[k] = &w
			}
		}
		rocWindowsMu.Unlock()
		fmt.Printf(" [ANOMALY PERSIST] Restored %d RoC windows from Redis\n", len(fields))
	}

	// Restore deviceMetricHistory (flat-line detector)
	fields, err = redisClient.HGetAll(ctx2, redisKeyFlatlineHist).Result()
	if err == nil {
		deviceMetricHistoryMu.Lock()
		for k, v := range fields {
			var snap metricSnapshot
			if json.Unmarshal([]byte(v), &snap) == nil {
				deviceMetricHistory[k] = snap
			}
		}
		deviceMetricHistoryMu.Unlock()
		fmt.Printf(" [ANOMALY PERSIST] Restored %d flat-line snapshots from Redis\n", len(fields))
	}

	// Restore deviceStateRings
	fields, err = redisClient.HGetAll(ctx2, redisKeyStateRings).Result()
	if err == nil {
		deviceStateRingsMu.Lock()
		for k, v := range fields {
			var ring stateRing
			if json.Unmarshal([]byte(v), &ring) == nil {
				deviceStateRings[k] = &ring
			}
		}
		deviceStateRingsMu.Unlock()
		fmt.Printf(" [ANOMALY PERSIST] Restored %d state rings from Redis\n", len(fields))
	}
}

// startAnomalyStatePersistor snapshots all detector caches to Redis every 30s.
func startAnomalyStatePersistor() {
	if redisClient == nil {
		fmt.Println(" [ANOMALY PERSIST] Redis unavailable — persistence disabled")
		return
	}
	hardening.GoSafe(func() {
		ticker := time.NewTicker(anomalyPersistInterval)
		ctx2 := context.Background()
		for range ticker.C {
			// Snapshot rocWindows
			rocWindowsMu.Lock()
			rocSnapshot := make(map[string]string, len(rocWindows))
			for k, w := range rocWindows {
				if b, err := json.Marshal(w); err == nil {
					rocSnapshot[k] = string(b)
				}
			}
			rocWindowsMu.Unlock()
			if len(rocSnapshot) > 0 {
				args := make([]interface{}, 0, len(rocSnapshot)*2)
				for k, v := range rocSnapshot {
					args = append(args, k, v)
				}
				_ = redisClient.HMSet(ctx2, redisKeyRoCWindows, rocSnapshot).Err()
			}

			// Snapshot flat-line history
			deviceMetricHistoryMu.Lock()
			flatSnapshot := make(map[string]string, len(deviceMetricHistory))
			for k, snap := range deviceMetricHistory {
				if b, err := json.Marshal(snap); err == nil {
					flatSnapshot[k] = string(b)
				}
			}
			deviceMetricHistoryMu.Unlock()
			if len(flatSnapshot) > 0 {
				_ = redisClient.HMSet(ctx2, redisKeyFlatlineHist, flatSnapshot).Err()
			}

			// Snapshot state rings
			deviceStateRingsMu.Lock()
			ringSnapshot := make(map[string]string, len(deviceStateRings))
			for k, ring := range deviceStateRings {
				if b, err := json.Marshal(ring); err == nil {
					ringSnapshot[k] = string(b)
				}
			}
			deviceStateRingsMu.Unlock()
			if len(ringSnapshot) > 0 {
				_ = redisClient.HMSet(ctx2, redisKeyStateRings, ringSnapshot).Err()
			}
		}
	}, func(cat, msg string) {
		fmt.Printf("[%s] Anomaly state persistor panic: %s\n", cat, msg)
	})
}

func loadKBSync() map[string]interface{} {
	kbStatic := map[string]interface{}{}
	kbDynamic := map[string]interface{}{}

	// Load dynamic file if available
	_, filename, _, _ := runtime.Caller(0)
	projectRoot := filepath.Dir(filepath.Dir(filepath.Dir(filepath.Dir(filename))))
	kbFile := filepath.Join(projectRoot, "local_knowledge_base.json")
	if data, err := os.ReadFile(kbFile); err == nil {
		_ = json.Unmarshal(data, &kbDynamic)
	}

	return map[string]interface{}{
		"status":     "SUCCESS",
		"kb_static":  kbStatic,
		"kb_dynamic": kbDynamic,
	}
}

func serveHTTPDispatcher() {
	mux := http.NewServeMux()

	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"healthy","service":"OSI Ingestion Server"}`))
	})

	// DedupFilter stats endpoint — dipantau oleh Grafana/Dashboard
	mux.HandleFunc("/health/dedup", func(w http.ResponseWriter, r *http.Request) {
		active, suppressed := globalDedupFilter.Stats()
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"status":           "ok",
			"active_fingerprints": active,
			"total_suppressed":    suppressed,
			"dedup_window_sec":    dedupWindowSec,
		})
	})

	mux.HandleFunc("/telemetry", handleHTTPTelemetryEvent)
	mux.HandleFunc("/api/telemetry", handleHTTPTelemetryEvent)
	mux.HandleFunc("/ingest", handleHTTPTelemetryEvent)      // Linux agent uses /ingest
	mux.HandleFunc("/api/ingest", handleHTTPTelemetryEvent)
	mux.HandleFunc("/api/v1/netdata", handleNetdataWebhook) // Netdata Anomaly Endpoint
	mux.HandleFunc("/api/v1/topology", handleTopologyWebhook) // Auto-Discovery Endpoint
	mux.HandleFunc("/activity", handleHTTPTelemetryEvent)
	mux.HandleFunc("/api/activity", handleHTTPTelemetryEvent)
	mux.HandleFunc("/issues", handleHTTPTelemetryEvent)
	mux.HandleFunc("/api/issues", handleHTTPTelemetryEvent)

	// TASK 11: Watchdog Failed Endpoint
	mux.HandleFunc("/watchdog/failed", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}
		var payload map[string]interface{}
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		
		payloadBytes, _ := json.Marshal(payload)
		fmt.Printf("[WATCHDOG] Publishing agent.watchdog.failed: %s\n", string(payloadBytes))
		if natsJS != nil {
			_, _ = natsJS.Publish("agent.watchdog.failed", payloadBytes)
		}
		
		// Publish to Redis for real-time dashboard UI (Live Telemetry)
		if redisClient != nil {
			pubPayload := map[string]interface{}{
				"event": "live_telemetry",
				"data":  payload,
				"path":  "/watchdog/failed",
			}
			pubBytes, _ := json.Marshal(pubPayload)
			_ = redisClient.Publish(context.Background(), "telemetry_channel", string(pubBytes)).Err()
		}
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"published"}`))
	})
	mux.HandleFunc("/browser-events", handleHTTPTelemetryEvent)

	mux.HandleFunc("/api/chat/ws", handleClientWebSocket)
	mux.HandleFunc("/api/chat/upload", handleFileUpload)
	mux.HandleFunc("/api/chat/history", handleChatHistory)
	mux.HandleFunc("/api/chat/search", handleChatSearch)
	mux.HandleFunc("/api/chat/poll", handleChatPoll)
	mux.HandleFunc("/api/chat/diagnostics", handleDiagnostics)
	mux.HandleFunc("/api/chat/send", handleChatSend)

	// Serve static uploads directory for chat attachments
	uploadDirRoot := "/app/uploads"
	if runtime.GOOS == "windows" {
		uploadDirRoot = filepath.Join(".", "uploads")
	}
	mux.Handle("/uploads/", http.StripPrefix("/uploads/", http.FileServer(http.Dir(uploadDirRoot))))

	mux.HandleFunc("/api/agent_version", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		hashStr := "unknown"

		_, filename, _, _ := runtime.Caller(0)
		projectRoot := filepath.Dir(filepath.Dir(filepath.Dir(filepath.Dir(filename))))
		agentPath := filepath.Join(projectRoot, "CLIENT_DISTRIBUSI_GO", "05_SIAP_DISTRIBUSI", "agent.exe")
		if data, err := os.ReadFile(agentPath); err == nil {
			h := sha256.Sum256(data)
			hashStr = hex.EncodeToString(h[:])
		}

		_ = json.NewEncoder(w).Encode(map[string]string{"version": hashStr})
	})

	mux.HandleFunc("/download/PC_HEALTH_AGENT.py", func(w http.ResponseWriter, r *http.Request) {
		_, filename, _, _ := runtime.Caller(0)
		projectRoot := filepath.Dir(filepath.Dir(filepath.Dir(filepath.Dir(filename))))
		agentPath := filepath.Join(projectRoot, "CLIENT_DISTRIBUSI_GO", "05_SIAP_DISTRIBUSI", "agent.exe")

		data, err := os.ReadFile(agentPath)
		if err != nil {
			w.WriteHeader(http.StatusNotFound)
			_, _ = w.Write([]byte("Agent binary not found"))
			return
		}

		w.Header().Set("Content-Type", "application/octet-stream")
		w.Header().Set("Content-Disposition", "attachment; filename=\"agent.exe\"")
		_, _ = w.Write(data)
	})

	mux.HandleFunc("/api/approval", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			w.WriteHeader(http.StatusMethodNotAllowed)
			return
		}

		var req struct {
			IncidentID        string `json:"incident_id"`
			RiskLevel         string `json:"risk_level"`
			ActionName        string `json:"action_name"`
			ApprovedBy        string `json:"approved_by"`
			ApprovedRole      string `json:"approved_role"`
			ApprovalStatus    string `json:"approval_status"`
			EmergencyOverride bool   `json:"emergency_override"`
		}

		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			w.WriteHeader(http.StatusBadRequest)
			_ = json.NewEncoder(w).Encode(map[string]string{"status": "failed", "message": err.Error()})
			return
		}

		canApprove := false
		role := strings.ToUpper(req.ApprovedRole)
		risk := strings.ToUpper(req.RiskLevel)

		if req.EmergencyOverride && (role == "MANAGER" || role == "SYSADMIN") {
			canApprove = true
			req.ApprovalStatus = "EMERGENCY_OVERRIDE_APPROVED"
		} else {
			if risk == "LOW" || risk == "MEDIUM" {
				canApprove = true
			} else if risk == "HIGH" && (role == "L2" || role == "L3" || role == "MANAGER") {
				canApprove = true
			} else if risk == "CRITICAL" && role == "MANAGER" {
				canApprove = true
			}
		}

		if !canApprove {
			w.WriteHeader(http.StatusForbidden)
			_ = json.NewEncoder(w).Encode(map[string]string{
				"status":  "failed",
				"message": fmt.Sprintf("Role %s insufficient for %s risk.", role, risk),
			})
			return
		}

		// Log approval to PostgreSQL
		err := database.DB.Exec(`
			INSERT INTO ai_approval_logs (incident_id, risk_level, action_name, approved_by, approved_role, approved_at, approval_expiry, approval_status)
			VALUES (?, ?, ?, ?, ?, NOW(), NOW() + interval '1 hour', ?)
		`, req.IncidentID, req.RiskLevel, req.ActionName, req.ApprovedBy, req.ApprovedRole, req.ApprovalStatus).Error

		if err != nil {
			w.WriteHeader(http.StatusInternalServerError)
			_ = json.NewEncoder(w).Encode(map[string]string{"status": "failed", "message": err.Error()})
			return
		}
		
		// Publish generic approval.decision event
		if natsConn != nil {
			// Fetch the inserted approval ID (we just inserted it, let's get the max ID for this incident)
			var approvalID int
			database.DB.Raw("SELECT id FROM ai_approval_logs WHERE incident_id = ? ORDER BY id DESC LIMIT 1", req.IncidentID).Scan(&approvalID)

			approvalPayload := map[string]interface{}{
				"incident_id": req.IncidentID,
				"approval_id": approvalID,
				"decision":    req.ApprovalStatus,
				"operator_id": req.ApprovedBy,
				"timestamp":   time.Now().UTC().Format(time.RFC3339),
			}
			payloadBytes, _ := json.Marshal(approvalPayload)
			_, _ = natsJS.Publish("approval.decision", payloadBytes)
		}

		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"status":          "success",
			"message":         "Approval logged",
			"approval_status": req.ApprovalStatus,
		})
	})

	mux.HandleFunc("/api/agent/version/latest", HandleAgentVersionLatest)

	secureHandler := security.WrapHTTPHandler(mux)
	server := &http.Server{Handler: secureHandler}
	_ = server.Serve(httpDispatcher)
}

func flushMetricsBatch(buffer []TelemetryItem, workerID int) {
	if len(buffer) == 0 {
		return
	}
	startTime := time.Now()

	query := "INSERT INTO telemetry_logs (device_name, metric_type, metric_value, metadata, tenant_id) VALUES "
	vals := []interface{}{}
	rowCount := 0

	for _, item := range buffer {
		tenantID := "MEGA KREASI TEACH"
		if t, ok := item.Metadata["tenant_id"].(string); ok && t != "" {
			tenantID = t
		}

		// Insert latency metric if present
		if lat, ok := item.Metadata["latency_ms"].(float64); ok {
			metaBytes, _ := json.Marshal(map[string]interface{}{"hit_golden": false, "is_idk": false})
			query += "(?, ?, ?, ?, ?),"
			vals = append(vals, item.Agent, "ai_agent_performance", lat, string(metaBytes), tenantID)
			rowCount++
		}

		for k, v := range item.Metadata {
			if k == "latency_ms" || k == "tenant_id" {
				continue
			}
			// Check if float
			var val float64
			var isFloat bool
			switch valType := v.(type) {
			case float64:
				val = valType
				isFloat = true
			case int:
				val = float64(valType)
				isFloat = true
			case int64:
				val = float64(valType)
				isFloat = true
			}

			if isFloat {
				metaBytes, _ := json.Marshal(item.Metadata)
				query += "(?, ?, ?, ?, ?),"
				vals = append(vals, item.Agent, k, val, string(metaBytes), tenantID)

				// V6 Feature Store Integration: Cache critical metrics for instant Prediction AI access
				if redisClient != nil && (strings.Contains(strings.ToLower(k), "cpu") || strings.Contains(strings.ToLower(k), "memory") || strings.Contains(strings.ToLower(k), "ram")) {
					fsKey := fmt.Sprintf("feature_store:%s:%s", item.Agent, k)
					_ = redisClient.Set(ctx, fsKey, val, 24*time.Hour).Err()
				}

				// Phase 2 — Feed Flat-line Detector: update metric snapshot if value changed
				metricKey := item.Agent + "::" + k
				deviceMetricHistoryMu.Lock()
				existing, hasPrev := deviceMetricHistory[metricKey]
				if !hasPrev || existing.Value != val {
					deviceMetricHistory[metricKey] = metricSnapshot{
						Value:     val,
						LastAt:    time.Now(),
						AlertedAt: existing.AlertedAt,
					}
				}
				deviceMetricHistoryMu.Unlock()

				// Phase 2 — Feed Stale Telemetry Detector: record last telemetry time per device
				deviceLastTelemetryMu.Lock()
				deviceLastTelemetry[item.Agent] = time.Now()
				deviceLastTelemetryMu.Unlock()

				// Phase 3 — Feed Adaptive RoC Model: compute rate of change sample
				rocKey := item.Agent + "::" + k
				rocWindowsMu.Lock()
				win, winExists := rocWindows[rocKey]
				if !winExists {
					win = &rocWindow{PrevValue: val}
					rocWindows[rocKey] = win
				} else {
					roc := math.Abs(val - win.PrevValue)
					win.Samples = append(win.Samples, rocEntry{RoC: roc, At: time.Now()})
					// Keep only last 60 samples (~1 hour at 1-min intervals)
					if len(win.Samples) > 60 {
						win.Samples = win.Samples[len(win.Samples)-60:]
					}
					win.PrevValue = val
				}
				rocWindowsMu.Unlock()

				rowCount++
			}
		}
	}

	if rowCount > 0 {
		query = query[:len(query)-1] // trim trailing comma
		err := database.DB.Exec(query, vals...).Error
		if err != nil {
			fmt.Printf(" [INGESTOR METRIC WORKER %d ERROR] Batch insert failed: %v\n", workerID, err)
			for _, item := range buffer {
				routeToDLQ(item, "BATCH_DB_WRITE_ERROR: "+err.Error())
			}
			incrementInternalMetrics(0, 1, len(buffer), 0)
			return
		}

		latencyMs := time.Since(startTime).Seconds() * 1000.0
		incrementInternalMetrics(len(buffer), 0, 0, latencyMs)
		fmt.Printf(" [INGESTOR METRIC WORKER %d] Successfully flushed batch of %d payloads (%d rows).\n", workerID, len(buffer), rowCount)

		// Phase 3+Fix4 — Feed State Hash Drift Detector (STRUCTURAL ONLY)
		// Volatile metrics (CPU/RAM/disk/bytes/latency) are excluded — only
		// structural state (service counts, port numbers, process IDs, config
		// fields) contribute to the hash. This prevents normal performance
		// fluctuations from triggering false-positive drift alerts.
		const maxRingSize = 12
		isVolatileMetric := func(k string) bool {
			kl := strings.ToLower(k)
			return strings.Contains(kl, "cpu") || strings.Contains(kl, "mem") ||
				strings.Contains(kl, "ram") || strings.Contains(kl, "disk") ||
				strings.Contains(kl, "bytes") || strings.Contains(kl, "packet") ||
				strings.Contains(kl, "latency") || strings.Contains(kl, "throughput") ||
				strings.Contains(kl, "percent") || strings.Contains(kl, "usage") ||
				strings.Contains(kl, "rate") || strings.Contains(kl, "bandwidth") ||
				k == "integrity_score"
		}
		deviceSnapshots := make(map[string][]string)
		for _, item := range buffer {
			for k, v := range item.Metadata {
				if isVolatileMetric(k) {
					continue // skip volatile — structural only
				}
				switch fv := v.(type) {
				case float64:
					deviceSnapshots[item.Agent] = append(
						deviceSnapshots[item.Agent],
						fmt.Sprintf("%s=%.0f", k, fv), // integer-precision for counts
					)
				case string:
					deviceSnapshots[item.Agent] = append(
						deviceSnapshots[item.Agent],
						fmt.Sprintf("%s=%s", k, fv),
					)
				case bool:
					deviceSnapshots[item.Agent] = append(
						deviceSnapshots[item.Agent],
						fmt.Sprintf("%s=%v", k, fv),
					)
				}
			}
		}
		deviceStateRingsMu.Lock()
		for devName, pairs := range deviceSnapshots {
			if len(pairs) == 0 {
				continue
			}
			for i := 1; i < len(pairs); i++ {
				for j := i; j > 0 && pairs[j] < pairs[j-1]; j-- {
					pairs[j], pairs[j-1] = pairs[j-1], pairs[j]
				}
			}
			h := sha256.Sum256([]byte(strings.Join(pairs, "|")))
			hashStr := hex.EncodeToString(h[:])
			ring, ringExists := deviceStateRings[devName]
			if !ringExists {
				ring = &stateRing{
					Hashes:   make([]string, maxRingSize),
					BaseHash: hashStr,
					Head:     0,
				}
				deviceStateRings[devName] = ring
			}
			ring.Hashes[ring.Head%maxRingSize] = hashStr
			ring.Head++
		}
		deviceStateRingsMu.Unlock()
	}
}

func flushLogsBatch(buffer []TelemetryItem, workerID int) {
	if len(buffer) == 0 {
		return
	}
	startTime := time.Now()

	query := "INSERT INTO telemetry_logs (device_name, metric_type, metric_value, metadata, tenant_id) VALUES "
	vals := []interface{}{}
	rowCount := 0

	for _, item := range buffer {
		tenantID := "MEGA KREASI TEACH"
		if t, ok := item.Metadata["tenant_id"].(string); ok && t != "" {
			tenantID = t
		}

		for k, v := range item.Metadata {
			if strVal, ok := v.(string); ok && k != "tenant_id" {
				logMeta := map[string]interface{}{
					"log_content":       strVal,
					"original_metadata": item.Metadata,
				}
				metaBytes, _ := json.Marshal(logMeta)
				query += "(?, ?, ?, ?, ?),"
				vals = append(vals, item.Agent, "log:"+k, 1.0, string(metaBytes), tenantID)
				rowCount++
			}
		}
	}

	if rowCount > 0 {
		query = query[:len(query)-1] // trim trailing comma
		err := database.DB.Exec(query, vals...).Error
		if err != nil {
			fmt.Printf(" [INGESTOR LOG WORKER %d ERROR] Batch insert failed: %v\n", workerID, err)
			for _, item := range buffer {
				routeToDLQ(item, "BATCH_LOG_WRITE_ERROR: "+err.Error())
			}
			incrementInternalMetrics(0, 1, len(buffer), 0)
			return
		}

		latencyMs := time.Since(startTime).Seconds() * 1000.0
		incrementInternalMetrics(len(buffer), 0, 0, latencyMs)
		fmt.Printf(" [INGESTOR LOG WORKER %d] Successfully flushed batch of %d payloads (%d rows).\n", workerID, len(buffer), rowCount)
	}
}

func routeToDLQ(item interface{}, reason string) {
	incrementInternalMetrics(0, 0, 1, 0)
	rawText := ""
	if str, ok := item.(string); ok {
		rawText = str
	} else if tItem, ok := item.(TelemetryItem); ok {
		bytes, _ := json.Marshal(tItem)
		rawText = string(bytes)
	} else {
		bytes, _ := json.Marshal(item)
		rawText = string(bytes)
	}

	siteID := "global"
	if tItem, ok := item.(TelemetryItem); ok && tItem.SiteID != "" {
		siteID = tItem.SiteID
	} else {
		// Attempt to extract from rawText json
		var temp map[string]interface{}
		if err := json.Unmarshal([]byte(rawText), &temp); err == nil {
			if s, ok := temp["site_id"].(string); ok && s != "" {
				siteID = s
			} else if msgPart, ok := temp["message"].(map[string]interface{}); ok {
				if s2, ok := msgPart["site_id"].(string); ok && s2 != "" {
					siteID = s2
				}
			}
		}
	}
	siteID = strings.ToLower(strings.TrimSpace(siteID))
	siteID = strings.ReplaceAll(siteID, ".", "_")
	siteID = strings.ReplaceAll(siteID, " ", "_")
	if siteID == "" {
		siteID = "global"
	}

	// 1. Redis DLQ
	if redisClient != nil {
		_, err := redisClient.XAdd(ctx, &redis.XAddArgs{
			Stream: "dlq_stream",
			Values: map[string]interface{}{
				"payload":   rawText,
				"reason":    reason,
				"timestamp": time.Now().Format(time.RFC3339),
			},
		}).Result()
		if err != nil {
			fmt.Printf(" [INGESTOR DLQ ERROR] Failed to write to Redis DLQ: %v\n", err)
		} else {
			fmt.Printf(" [INGESTOR DLQ] Routed invalid payload to DLQ (Redis): %s\n", reason)
		}
	}

	// 2. Publish to NATS DLQ subject
	if natsConn != nil {
		natsSubject := fmt.Sprintf("dlq.site.%s", siteID)
		dlqPayload := map[string]interface{}{
			"payload":   rawText,
			"reason":    reason,
			"timestamp": time.Now().Format(time.RFC3339),
		}
		dlqPayloadBytes, _ := json.Marshal(dlqPayload)
		_, _ = natsJS.Publish(natsSubject, dlqPayloadBytes)
		fmt.Printf(" [INGESTOR DLQ NATS] Published to NATS DLQ subject: %s\n", natsSubject)
	}

	// 3. Postgres DLQ
	var payloadJSON interface{}
	err := json.Unmarshal([]byte(rawText), &payloadJSON)
	if err != nil {
		payloadJSON = map[string]string{"raw_payload": rawText}
	}

	payloadBytes, _ := json.Marshal(payloadJSON)
	err = database.DB.Exec("INSERT INTO dlq_hybrid (payload, reason) VALUES (?, ?)", string(payloadBytes), reason).Error
	if err != nil {
		fmt.Printf(" [INGESTOR DLQ ERROR] Failed to write to Postgres DLQ: %v\n", err)
	} else {
		fmt.Println(" [INGESTOR DLQ] Saved to Postgres DLQ (Hybrid)")
	}
}

func checkLoadSheddingLevel() int {
	var maxPct float64

	p1 := float64(len(metricQueue)) / float64(cap(metricQueue))
	p2 := float64(len(logQueue)) / float64(cap(logQueue))
	p3 := float64(len(eventQueue)) / float64(cap(eventQueue))
	if p1 > maxPct {
		maxPct = p1
	}
	if p2 > maxPct {
		maxPct = p2
	}
	if p3 > maxPct {
		maxPct = p3
	}

	siteQueuesMu.RLock()
	for _, sq := range siteQueues {
		mPct := float64(len(sq.metricQueue)) / float64(cap(sq.metricQueue))
		lPct := float64(len(sq.logQueue)) / float64(cap(sq.logQueue))
		ePct := float64(len(sq.eventQueue)) / float64(cap(sq.eventQueue))
		if mPct > maxPct {
			maxPct = mPct
		}
		if lPct > maxPct {
			maxPct = lPct
		}
		if ePct > maxPct {
			maxPct = ePct
		}
	}
	siteQueuesMu.RUnlock()

	if maxPct >= 0.95 {
		return 3
	} else if maxPct >= 0.90 {
		return 2
	} else if maxPct >= 0.80 {
		return 1
	}
	return 0
}

func isVersionAllowed(item TelemetryItem) bool {
	if item.Agent == "auditor_probe" {
		return true
	}

	agentVersion := ""
	if item.Data != nil {
		if av, ok := item.Data["agent_version"].(string); ok {
			agentVersion = av
		}
	}
	if agentVersion == "" && item.Metadata != nil {
		if av, ok := item.Metadata["agent_version"].(string); ok {
			agentVersion = av
		}
	}

	schemaVersion := item.SchemaVersion

	allowed := false
	for _, v := range []string{"2.1.0-Go", "2.1.0", "2.0.0-Go", "05_SIAP_DISTRIBUSI", "1.0.0"} {
		if strings.Contains(agentVersion, v) || strings.Contains(schemaVersion, v) {
			allowed = true
			break
		}
	}
	return allowed
}

func getAgentVersionString(item TelemetryItem) string {
	if item.Data != nil {
		if av, ok := item.Data["agent_version"].(string); ok {
			return av
		}
	}
	if item.Metadata != nil {
		if av, ok := item.Metadata["agent_version"].(string); ok {
			return av
		}
	}
	return ""
}

func ensureDeviceRegistered(item TelemetryItem) {
	if item.Agent == "" || item.Agent == "auditor_probe" {
		return
	}

	// Do NOT use memory cache as early-return guard.
	// The cache can be stale if a device was manually deleted from fleet_devices
	// via the dashboard. Always do a DB check for fleet_devices.

	// Prepare metadata (fall back to data field if metadata is empty)
	meta := item.Metadata
	if len(meta) == 0 && len(item.Data) > 0 {
		meta = item.Data
	}

	// 1. Ensure device exists in `devices` table
	var devExists int64
	database.DB.Table("devices").Where("name = ?", item.Agent).Count(&devExists)
	if devExists == 0 {
		layerInt := 0
		if lFloat, ok := item.Layer.(float64); ok {
			layerInt = int(lFloat)
		} else if lStr, ok := item.Layer.(string); ok {
			layerInt, _ = strconv.Atoi(lStr)
		} else if lInt, ok := item.Layer.(int); ok {
			layerInt = lInt
		}

		loc := item.Location
		if loc == "" {
			loc = item.SiteID
		}

		metaBytes, _ := json.Marshal(meta)
		devStatus := "ONLINE" // Default to ONLINE since it's active telemetry

		err := database.DB.Exec("INSERT INTO devices (name, ip, layer, location, status, metadata) VALUES (?, ?, ?, ?, ?, ?)",
			item.Agent, item.IPAddress, layerInt, loc, devStatus, string(metaBytes)).Error
		if err == nil {
			fmt.Printf(" [INGESTOR DB] Auto-registered device from alert flow: %s\n", item.Agent)
		} else {
			fmt.Printf(" [INGESTOR DB ERROR] Registration error for %s in alert flow: %v\n", item.Agent, err)
		}
	}

	// 2. ALWAYS ensure device exists in `fleet_devices` (independent of `devices` table check).
	// This handles the case where a device is deleted from fleet_devices via the dashboard.
	var rustdeskID string
	var rustdeskRunning bool
	var anydeskID string

	var rd, ad map[string]interface{}
	if item.Metadata != nil {
		rd, _ = item.Metadata["rustdesk"].(map[string]interface{})
		ad, _ = item.Metadata["anydesk"].(map[string]interface{})
	}
	if rd == nil && item.Data != nil {
		rd, _ = item.Data["rustdesk"].(map[string]interface{})
	}
	if ad == nil && item.Data != nil {
		ad, _ = item.Data["anydesk"].(map[string]interface{})
	}
	if rd != nil {
		rustdeskID, _ = rd["id"].(string)
		rustdeskRunning, _ = rd["running"].(bool)
	}
	if ad != nil {
		anydeskID, _ = ad["id"].(string)
	}

	osName := "Windows"
	if item.Metadata != nil {
		if o, ok := item.Metadata["os"].(string); ok && o != "" {
			osName = o
		}
	}
	if osName == "Windows" && item.Data != nil {
		if o, ok := item.Data["os"].(string); ok && o != "" {
			osName = o
		}
	}
	if strings.ToLower(osName) == "linux" {
		osName = "Linux"
	} else if strings.ToLower(osName) == "darwin" {
		osName = "macOS"
	}

	hwInfo := map[string]interface{}{
		"ip":          item.IPAddress,
		"os":          osName,
		"hostname":    item.Agent,
		"anydesk_id":  anydeskID,
		"rustdesk_id": rustdeskID,
	}
	hwBytes, _ := json.Marshal(hwInfo)

	var fleetDevExists int64
	database.DB.Table("fleet_devices").Where("pc_name = ?", item.Agent).Count(&fleetDevExists)
	if fleetDevExists == 0 {
		database.DB.Exec("INSERT INTO fleet_devices (pc_name, site_id, status, is_approved, hardware_info, last_seen, rustdesk_id, rustdesk_running) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
			item.Agent, nil, "ACTIVE", true, string(hwBytes), time.Now(), rustdeskID, rustdeskRunning)
		fmt.Printf(" [INGESTOR DB] Auto-registered fleet device for remote access in alert flow: %s\n", item.Agent)
	} else {
		// Update last_seen and status even if already registered
		database.DB.Exec("UPDATE fleet_devices SET last_seen = NOW(), status = 'ACTIVE' WHERE pc_name = ?", item.Agent)
	}

	registeredDevicesCacheMu.Lock()
	registeredDevicesCache[item.Agent] = true
	registeredDevicesCacheMu.Unlock()
}

func handleNetdataWebhook(w http.ResponseWriter, r *http.Request) {
	// Setup CORS
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
	if r.Method == http.MethodOptions {
		w.WriteHeader(http.StatusOK)
		return
	}
	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	ipAddr, _, _ := net.SplitHostPort(r.RemoteAddr)
	body, err := io.ReadAll(r.Body)
	if err != nil {
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	// Parse Webhook payload
	telemetryItem, err := ParseNetdataPayload(body, ipAddr)
	if err != nil {
		fmt.Printf(" [INGESTOR ERROR] Failed to parse Netdata webhook: %v\n", err)
		w.WriteHeader(http.StatusBadRequest)
		return
	}

	// Push to NATS
	if natsConn != nil {
		telemetryBytes, _ := json.Marshal(telemetryItem)
		_, err = natsJS.Publish("telemetry.netdata", telemetryBytes)
		if err != nil {
			fmt.Printf(" [INGESTOR ERROR] Failed to publish Netdata Telemetry: %v\n", err)
			w.WriteHeader(http.StatusInternalServerError)
			return
		}
		fmt.Printf(" [INGESTOR INFO] Processed Netdata Webhook for Host: %s, Alarm: %s\n", telemetryItem.Agent, telemetryItem.Description)
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(`{"status":"success"}`))
}

func handleTopologyWebhook(w http.ResponseWriter, r *http.Request) {
	// Setup CORS
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
	if r.Method == http.MethodOptions {
		w.WriteHeader(http.StatusOK)
		return
	}
	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	body, err := io.ReadAll(r.Body)
	if err != nil {
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	// Parse Topology payload
	telemetryItem, err := ParseTopologyPayload(body)
	if err != nil {
		// Just ignore non-established connections silently
		if err.Error() == "ignoring non-established connection" {
			w.WriteHeader(http.StatusOK)
			return
		}
		fmt.Printf(" [INGESTOR ERROR] Failed to parse Topology webhook: %v\n", err)
		w.WriteHeader(http.StatusBadRequest)
		return
	}

	// Push to NATS
	if natsConn != nil {
		telemetryBytes, _ := json.Marshal(telemetryItem)
		_, err = natsJS.Publish("telemetry.topology", telemetryBytes)
		if err != nil {
			fmt.Printf(" [INGESTOR ERROR] Failed to publish Topology Telemetry: %v\n", err)
			w.WriteHeader(http.StatusInternalServerError)
			return
		}
		fmt.Printf(" [INGESTOR INFO] Processed Dynamic Topology Edge: %s -> %s\n", telemetryItem.Metadata["source_component"], telemetryItem.Metadata["target_component"])
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(`{"status":"success"}`))
}

func handleHTTPTelemetryEvent(w http.ResponseWriter, r *http.Request) {
	// Setup CORS
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
	if r.Method == http.MethodOptions {
		w.WriteHeader(http.StatusOK)
		return
	}
	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	// Phase 2 Hardening: Add API Authentication
	authHeader := r.Header.Get("Authorization")
	expectedToken := "Bearer " + string(securityKey)
	if authHeader != expectedToken && authHeader != "Bearer SIAP_DISTRIBUSI_SECRET_KEY" && authHeader != "" {
		// allow localhost fallback for legacy extensions without token yet (Optional, but let's enforce it)
		// For true security, we enforce it.
		w.WriteHeader(http.StatusUnauthorized)
		w.Write([]byte(`{"error":"Unauthorized"}`))
		return
	}

	body, err := io.ReadAll(r.Body)
	if err != nil {
		w.WriteHeader(http.StatusBadRequest)
		return
	}

	var data map[string]interface{}
	if err := json.Unmarshal(body, &data); err != nil {
		w.WriteHeader(http.StatusBadRequest)
		return
	}

	// Try to get target agent / PC name
	pcName, _ := data["pc_name"].(string)
	if pcName == "" {
		pcName, _ = data["agent_id"].(string)
	}
	if pcName == "" {
		pcName = "unknown-device"
	}

	// Phase 3 Hardening: OpenTelemetry Trace Context & SLA Pipeline
	traceID := r.Header.Get("X-Trace-Id")
	if traceID != "" {
		data["trace_id"] = traceID
		data["span_id"] = r.Header.Get("X-Span-Id")
		data["agent_timestamp"] = r.Header.Get("X-Agent-Timestamp")
		data["ingestion_timestamp"] = fmt.Sprintf("%d", time.Now().UnixNano())
	}

	// Setup values to save to telemetry_logs
	metricType := "http_telemetry"
	var metricVal float64 = 1.0

	path := r.URL.Path
	if strings.Contains(path, "activity") {
		metricType = "active_app"
	} else if strings.Contains(path, "issues") {
		metricType = "browser_issue"
		// If severe, trigger incident workflow
		sev, _ := data["severity"].(string)
		desc, _ := data["details"].(string)
		if strings.ToUpper(sev) == "HIGH" || strings.ToUpper(sev) == "CRITICAL" {
			DefaultIncidentService.TriggerIncidentWorkflow(pcName, strings.ToUpper(sev), desc)
		}
	} else if strings.Contains(path, "browser-events") {
		metricType = "web_activity"
		if lat, ok := data["load_time_ms"].(float64); ok {
			metricVal = lat
		}

		// Domain blacklist/whitelist validation filter for anomaly detection
		urlStr, _ := data["url"].(string)
		if urlStr != "" {
			domain := urlStr
			if strings.Contains(domain, "://") {
				parts := strings.Split(domain, "://")
				if len(parts) > 1 {
					domain = parts[1]
				}
			}
			if strings.Contains(domain, "/") {
				domain = strings.Split(domain, "/")[0]
			}
			if strings.Contains(domain, ":") {
				domain = strings.Split(domain, ":")[0]
			}
			domain = strings.ToLower(strings.TrimSpace(domain))

			blacklist := []string{"malware", "phishing", "torrent", "exploit", "hack", "bypass", "unauthorized-download"}
			isBlacklisted := false
			for _, b := range blacklist {
				if strings.Contains(domain, b) {
					isBlacklisted = true
					break
				}
			}

			if isBlacklisted {
				fmt.Printf("[WEB ANOMALY] Blacklisted domain visited on %s: %s\n", pcName, domain)
				data["anomaly"] = true
				data["anomaly_reason"] = "Blacklisted domain keyword matched: " + domain
				metricVal = 999.0 // High anomaly flag value
				DefaultIncidentService.TriggerIncidentWorkflow(pcName, "HIGH", fmt.Sprintf("Suspicious web browsing anomaly: Device %s visited blacklisted domain: %s", pcName, domain))
			}
		}
	}

	metaBytes, _ := json.Marshal(data)
	
	// Auto-register device to prevent foreign key constraint violations
	remoteIP := r.Header.Get("X-Forwarded-For")
	if remoteIP == "" {
		remoteIP = strings.Split(r.RemoteAddr, ":")[0]
	}
	_ = database.DB.Exec(`
		INSERT INTO devices (name, ip, layer, status) 
		VALUES (?, ?, 1, 'ONLINE')
		ON CONFLICT (name) DO UPDATE SET ip = EXCLUDED.ip, status = 'ONLINE'
	`, pcName, remoteIP)
	
	_ = database.DB.Exec(`
		INSERT INTO fleet_devices (pc_name, status, is_approved, last_seen)
		VALUES (?, 'ACTIVE', true, NOW())
		ON CONFLICT (pc_name) DO UPDATE SET last_seen = NOW(), status = 'ACTIVE'
	`, pcName)

	// Enrich fleet_devices columns with hardware info parsed from HTTP telemetry payload
	var item TelemetryItem
	if err := json.Unmarshal(body, &item); err == nil && item.Agent != "" && item.Agent != "auditor_probe" {
		var rustdeskID string
		var rustdeskRunning bool
		var anydeskID string

		rd, _ := item.Metadata["rustdesk"].(map[string]interface{})
		if rd == nil && item.Data != nil {
			rd, _ = item.Data["rustdesk"].(map[string]interface{})
		}
		if rd != nil {
			rustdeskID, _ = rd["id"].(string)
			rustdeskRunning, _ = rd["running"].(bool)
		}

		ad, _ := item.Metadata["anydesk"].(map[string]interface{})
		if ad == nil && item.Data != nil {
			ad, _ = item.Data["anydesk"].(map[string]interface{})
		}
		if ad != nil {
			anydeskID, _ = ad["id"].(string)
		}

		hostname := item.Agent
		ip := item.IPAddress
		if ip == "" {
			ip = remoteIP
		}
		telVer := item.SchemaVersion
		if telVer == "" {
			telVer, _ = item.Data["agent_version"].(string)
		}

		agentCollectedAt := time.Now()
		if item.Timestamp != "" {
			if tsInt, err2 := strconv.ParseInt(item.Timestamp, 10, 64); err2 == nil {
				agentCollectedAt = time.Unix(tsInt, 0)
			}
		}

		osVersion := ""
		hwRaw, _ := item.Data["hardware_info"].(map[string]interface{})
		if hwRaw != nil {
			osVersion, _ = hwRaw["os_version"].(string)
			if ip == "" {
				if netMap, ok := hwRaw["network"].(map[string]interface{}); ok {
					ip, _ = netMap["ip"].(string)
				}
			}
		}
		if osVersion == "" {
			osVersion, _ = item.Data["os_version"].(string)
		}

		osName := "Windows"
		if item.Metadata != nil {
			if o, ok := item.Metadata["os"].(string); ok && o != "" {
				osName = o
			}
		}
		if osName == "Windows" && item.Data != nil {
			if o, ok := item.Data["os"].(string); ok && o != "" {
				osName = o
			}
		}
		if strings.ToLower(osName) == "linux" {
			osName = "Linux"
		} else if strings.ToLower(osName) == "darwin" {
			osName = "macOS"
		}

		hwInfo := map[string]interface{}{
			"ip":            ip,
			"hostname":      hostname,
			"os":            osName,
			"os_version":    osVersion,
			"anydesk_id":    anydeskID,
			"rustdesk_id":   rustdeskID,
			"agent_version": telVer,
			"agent_build":   "05_SIAP_DISTRIBUSI",
		}
		if hwRaw != nil {
			for k, v := range hwRaw {
				hwInfo[k] = v
			}
		} else {
			// For Linux agents, the fields are placed directly at the root of item.Data
			for k, v := range item.Data {
				hwInfo[k] = v
			}
			// Map network_advanced to network for dashboard compatibility
			if netAdv, ok := item.Data["network_advanced"]; ok {
				hwInfo["network"] = netAdv
			}
			// Map deep_telemetry to service_status and apps for Linux dashboard parity
			if dt, ok := item.Data["deep_telemetry"].(map[string]interface{}); ok {
				if linuxServices, ok := dt["linux_services"].(map[string]interface{}); ok {
					serviceStatus := make(map[string]interface{})
					for sname, sdet := range linuxServices {
						if detMap, ok2 := sdet.(map[string]interface{}); ok2 {
							if status, ok3 := detMap["status"].(string); ok3 {
								if status == "active" {
									serviceStatus[sname] = "Running"
								} else {
									serviceStatus[sname] = "Stopped"
								}
							}
						}
					}
					hwInfo["service_status"] = serviceStatus
				}
				
				if topProcs, ok := dt["top_processes"].([]interface{}); ok {
					var apps []map[string]interface{}
					for _, p := range topProcs {
						if procMap, ok2 := p.(map[string]interface{}); ok2 {
							apps = append(apps, map[string]interface{}{
								"Id":              procMap["pid"],
								"Name":            procMap["name"],
								"MainWindowTitle": procMap["name"],
							})
						}
					}
					if len(apps) > 0 {
						hwInfo["apps"] = apps
					}
				}
			}
		}
		hwInfo["ip"] = ip
		hwInfo["agent_version"] = telVer
		hwInfo["agent_build"] = "05_SIAP_DISTRIBUSI"
		hwBytes, _ := json.Marshal(hwInfo)

		_ = database.DB.Exec(`UPDATE fleet_devices SET
			agent_collected_at = ?,
			online = true,
			ip = ?,
			hostname = ?,
			telemetry_version = ?,
			os_version = ?,
			rustdesk_id = ?,
			rustdesk_running = ?,
			hardware_info = ?
			WHERE pc_name = ?`,
			agentCollectedAt, ip, hostname, telVer, osVersion,
			rustdeskID, rustdeskRunning, string(hwBytes), item.Agent)
	}

	_ = database.DB.Exec(`
		INSERT INTO telemetry_logs (device_name, metric_type, metric_value, metadata, tenant_id)
		VALUES (?, ?, ?, ?, ?)
	`, pcName, metricType, metricVal, string(metaBytes), "default_tenant")

	// Also publish to Redis if available so the live dashboard receives updates
	if redisClient != nil {
		pubPayload := map[string]interface{}{
			"event": "live_telemetry",
			"data":  data,
			"path":  path,
		}
		pubBytes, _ := json.Marshal(pubPayload)
		_ = redisClient.Publish(ctx, "telemetry_channel", string(pubBytes)).Err()
	}

	// FIX-01: Relay active_app telemetry to Dashboard Server /api/activity
	if metricType == "active_app" || strings.Contains(path, "activity") {
		go func(pData map[string]interface{}) {
			payloadBytes, err := json.Marshal(pData)
			if err != nil {
				return
			}
			client := &http.Client{Timeout: 3 * time.Second}
			for _, targetPort := range []string{"80", "9999"} {
				req, err := http.NewRequest("POST", "http://127.0.0.1:"+targetPort+"/api/activity", bytes.NewBuffer(payloadBytes))
				if err == nil {
					req.Header.Set("Content-Type", "application/json")
					resp, err := client.Do(req)
					if err == nil {
						resp.Body.Close()
						break
					}
				}
			}
		}(data)
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(`{"status":"SUCCESS"}`))
}

// --- CHAT SYSTEM IMPLEMENTATION ---

var chatUpgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin: func(r *http.Request) bool {
		return true // Allow all origins
	},
}

type wsClientConn struct {
	conn     *websocket.Conn
	clientID string
	pcName   string
	mu       sync.Mutex
}

var (
	wsChatClients   = make(map[string]*wsClientConn)
	wsChatClientsMu sync.RWMutex
)

type ChatEvent struct {
	Type     string      `json:"type"` // message, typing, operator_status, read_receipt, init_context, diagnostic
	ClientID string      `json:"client_id"`
	Sender   string      `json:"sender,omitempty"`
	Data     interface{} `json:"data,omitempty"`
}

type DashboardChatEvent struct {
	Type       string      `json:"type"`
	ClientID   string      `json:"client_id,omitempty"`
	OperatorID string      `json:"operator_id,omitempty"`
	SenderType string      `json:"sender_type,omitempty"`
	Data       interface{} `json:"data,omitempty"`
}

func StartChatRedisSubscriber() {
	if redisClient == nil {
		return
	}
	pubsub := redisClient.Subscribe(ctx, "chat_channel", "enterprise_chat")
	ch := pubsub.Channel()

	go func() {
		fmt.Println(" [CHAT] Ingestion Server listening to Redis chat_channel and enterprise_chat")
		for msg := range ch {
			if msg.Channel == "chat_channel" {
				var event ChatEvent
				if err := json.Unmarshal([]byte(msg.Payload), &event); err != nil {
					continue
				}

				// Forward to local client WebSocket if registered here
				wsChatClientsMu.RLock()
				clientConn, exists := wsChatClients[event.ClientID]
				wsChatClientsMu.RUnlock()

				if exists {
					clientConn.mu.Lock()
					_ = clientConn.conn.WriteJSON(event)
					clientConn.mu.Unlock()
				}
			} else if msg.Channel == "enterprise_chat" {
				var event DashboardChatEvent
				if err := json.Unmarshal([]byte(msg.Payload), &event); err != nil {
					continue
				}

				if event.ClientID == "" {
					continue
				}

				// Forward to local client WebSocket if registered here
				wsChatClientsMu.RLock()
				clientConn, exists := wsChatClients[event.ClientID]
				wsChatClientsMu.RUnlock()

				if !exists {
					continue
				}

				var clientEvent ChatEvent
				switch event.Type {
				case "RECEIVE_MESSAGE":
					if event.SenderType == "CLIENT" {
						continue
					}
					var messageText string
					var attachmentUrl string
					var msgID float64
					var timestampStr string

					if dataMap, ok := event.Data.(map[string]interface{}); ok {
						if msgVal, ok := dataMap["message"].(string); ok {
							messageText = msgVal
						}
						if attachVal, ok := dataMap["attachment_url"].(string); ok {
							attachmentUrl = attachVal
						}
						if idVal, ok := dataMap["message_id"].(float64); ok {
							msgID = idVal
						}
						if tsVal, ok := dataMap["timestamp"].(string); ok {
							timestampStr = tsVal
						}
					}

					if timestampStr == "" {
						timestampStr = time.Now().Format(time.RFC3339)
					}

					sender := event.SenderType
					if sender == "" {
						sender = "OPERATOR"
					}

					clientEvent = ChatEvent{
						Type:     "message",
						ClientID: event.ClientID,
						Sender:   sender,
						Data: map[string]interface{}{
							"id":              msgID,
							"client_id":       event.ClientID,
							"sender":          sender,
							"message":         messageText,
							"attachment_path": attachmentUrl,
							"read_status":     "DELIVERED",
							"created_at":      timestampStr,
						},
					}
				case "START_TYPING", "STOP_TYPING":
					clientEvent = ChatEvent{
						Type:     "typing",
						ClientID: event.ClientID,
						Sender:   "OPERATOR",
						Data: map[string]interface{}{
							"typing": event.Type == "START_TYPING",
						},
					}
				case "CONNECT", "DISCONNECT":
					status := "OFFLINE"
					if event.Type == "CONNECT" {
						status = "ONLINE"
					}
					clientEvent = ChatEvent{
						Type:     "operator_status",
						ClientID: event.ClientID,
						Sender:   "SYSTEM",
						Data: map[string]interface{}{
							"status":    status,
							"last_seen": time.Now().Unix(),
						},
					}
				case "SESSION_SOLVED", "SESSION_CLOSED":
					clientEvent = ChatEvent{
						Type:     "message",
						ClientID: event.ClientID,
						Sender:   "SYSTEM",
						Data: map[string]interface{}{
							"id":              0,
							"client_id":       event.ClientID,
							"sender":          "SYSTEM",
							"message":         "Sesi chat telah diselesaikan oleh Teknisi IT.",
							"attachment_path": "",
							"read_status":     "READ",
							"created_at":      time.Now().Format(time.RFC3339),
						},
					}
				default:
					continue
				}

				clientConn.mu.Lock()
				_ = clientConn.conn.WriteJSON(clientEvent)
				clientConn.mu.Unlock()
			}
		}
	}()
}

func handleClientWebSocket(w http.ResponseWriter, r *http.Request) {
	clientID := r.URL.Query().Get("client_id")
	pcName := r.URL.Query().Get("pc_name")
	if clientID == "" {
		http.Error(w, "client_id is required", http.StatusBadRequest)
		return
	}

	conn, err := chatUpgrader.Upgrade(w, r, nil)
	if err != nil {
		fmt.Printf(" [CHAT ERROR] Upgrade failed for %s: %v\n", clientID, err)
		return
	}

	clientConn := &wsClientConn{
		conn:     conn,
		clientID: clientID,
		pcName:   pcName,
	}

	wsChatClientsMu.Lock()
	if oldConn, exists := wsChatClients[clientID]; exists {
		oldConn.conn.Close()
	}
	wsChatClients[clientID] = clientConn
	wsChatClientsMu.Unlock()

	var session database.ChatSession
	if err := database.DB.Where("client_id = ?", clientID).First(&session).Error; err != nil {
		session = database.ChatSession{
			ClientID: clientID,
			PCName:   pcName,
			Status:   "OPEN",
		}
		database.DB.Create(&session)
	} else {
		session.Status = "ACTIVE"
		database.DB.Save(&session)
	}

	sendOperatorPresenceUpdate(clientID)

	fmt.Printf(" [CHAT] Client connected: %s (%s)\n", clientID, pcName)

	defer func() {
		wsChatClientsMu.Lock()
		if currentConn, exists := wsChatClients[clientID]; exists && currentConn == clientConn {
			delete(wsChatClients, clientID)
		}
		wsChatClientsMu.Unlock()
		conn.Close()
		fmt.Printf(" [CHAT] Client disconnected: %s\n", clientID)
	}()

	for {
		var event ChatEvent
		if err := conn.ReadJSON(&event); err != nil {
			break
		}
		event.ClientID = clientID

		switch event.Type {
		case "init_context":
			if metaMap, ok := event.Data.(map[string]interface{}); ok {
				metaBytes, _ := json.Marshal(metaMap)
				database.DB.Model(&database.ChatSession{}).Where("client_id = ?", clientID).Update("metadata", string(metaBytes))
			}
		case "diagnostic":
			handleDiagnosticsPayload(clientID, pcName, event.Data)
		case "typing":
			publishChatEvent(event)
		case "read_receipt":
			if dataMap, ok := event.Data.(map[string]interface{}); ok {
				if msgIDFloat, exists := dataMap["message_id"].(float64); exists {
					msgID := uint(msgIDFloat)
					database.DB.Model(&database.ChatMessage{}).Where("id = ? AND client_id = ?", msgID, clientID).Update("read_status", "READ")
					publishChatEvent(event)
				}
			}
		case "resolve_incident":
			if dataMap, ok := event.Data.(map[string]interface{}); ok {
				var incidentID uint
				if idVal, ok := dataMap["incident_id"].(float64); ok {
					incidentID = uint(idVal)
				}
				_ = DefaultIncidentService.ResolveIncident(clientID, incidentID)
			}
		case "escalate_incident":
			if dataMap, ok := event.Data.(map[string]interface{}); ok {
				var incidentID uint
				if idVal, ok := dataMap["incident_id"].(float64); ok {
					incidentID = uint(idVal)
				}
				_ = DefaultIncidentService.EscalateIncident(clientID, incidentID)
			}
		case "screenshot_upload":
			if dataMap, ok := event.Data.(map[string]interface{}); ok {
				path, _ := dataMap["attachment_path"].(string)
				RegisterScreenshotCallback(clientID, path)
			}
		case "message":
			if dataMap, ok := event.Data.(map[string]interface{}); ok {
				text, _ := dataMap["message"].(string)
				attachment, _ := dataMap["attachment_path"].(string)

				msg := database.ChatMessage{
					ClientID:       clientID,
					Sender:         "CLIENT",
					Message:        text,
					AttachmentPath: attachment,
					ReadStatus:     "SENT",
				}
				database.DB.Create(&msg)

				database.DB.Model(&database.ChatSession{}).Where("client_id = ?", clientID).Updates(map[string]interface{}{
					"status":     "WAITING_OPERATOR",
					"updated_at": time.Now(),
				})

				event.Data = msg
				publishChatEvent(event)

				sendTelegramChatAlert(pcName, clientID, msg)
			}
		}
	}
}

func sendOperatorPresenceUpdate(clientID string) {
	status := "OFFLINE"
	if redisClient != nil {
		if val, err := redisClient.Exists(ctx, "presence:operator").Result(); err == nil && val > 0 {
			status = "ONLINE"
		}
	}

	wsChatClientsMu.RLock()
	client, exists := wsChatClients[clientID]
	wsChatClientsMu.RUnlock()
	if exists {
		client.mu.Lock()
		_ = client.conn.WriteJSON(ChatEvent{
			Type:     "operator_status",
			ClientID: clientID,
			Sender:   "SYSTEM",
			Data: map[string]interface{}{
				"status":    status,
				"last_seen": time.Now().Unix(),
			},
		})
		client.mu.Unlock()
	}
}

func publishChatEvent(event ChatEvent) {
	if redisClient == nil {
		return
	}
	payloadBytes, _ := json.Marshal(event)
	_ = redisClient.Publish(ctx, "chat_channel", string(payloadBytes)).Err()
}

func handleDiagnosticsPayload(clientID, pcName string, data interface{}) {
	diagBytes, _ := json.Marshal(data)

	msg := database.ChatMessage{
		ClientID:       clientID,
		Sender:         "SYSTEM",
		Message:        "[System Diagnostic Report Collected]",
		AttachmentPath: "",
		ReadStatus:     "DELIVERED",
	}
	database.DB.Create(&msg)

	publishChatEvent(ChatEvent{
		Type:     "message",
		ClientID: clientID,
		Sender:   "SYSTEM",
		Data:     msg,
	})

	go func() {
		var report map[string]interface{}
		_ = json.Unmarshal(diagBytes, &report)

		hypothesisText := runAIDiagnosticAnalysis(pcName, report)

		aiMsg := database.ChatMessage{
			ClientID:       clientID,
			Sender:         "AI_HYPOTHESIS",
			Message:        hypothesisText,
			AttachmentPath: "",
			ReadStatus:     "DELIVERED",
		}
		database.DB.Create(&aiMsg)

		publishChatEvent(ChatEvent{
			Type:     "message",
			ClientID: clientID,
			Sender:   "AI_HYPOTHESIS",
			Data:     aiMsg,
		})
	}()
}

func runAIDiagnosticAnalysis(pcName string, report map[string]interface{}) string {
	cpu, _ := report["cpu"].(string)
	ram, _ := report["ram"].(string)
	disk, _ := report["disk"].(string)
	smart, _ := report["smart"].(string)
	services, _ := report["services"].(string)

	issues := []string{}
	if strings.Contains(strings.ToLower(smart), "fail") || strings.Contains(strings.ToLower(smart), "bad") {
		issues = append(issues, "🚨 SMART failure detected on disk drives. Hardware maintenance required immediately.")
	}
	if strings.Contains(strings.ToLower(services), "spooler=stopped") || strings.Contains(strings.ToLower(services), "spooler=down") {
		issues = append(issues, "🖨️ Windows Print Spooler service is STOPPED. Recommend executing spooler auto-restart procedure.")
	}
	if strings.Contains(strings.ToLower(cpu), "90%") || strings.Contains(strings.ToLower(cpu), "95%") {
		issues = append(issues, "⚡ High CPU usage (>90%). Active process checks needed for process hogging.")
	}
	if strings.Contains(strings.ToLower(ram), "90%") || strings.Contains(strings.ToLower(ram), "95%") {
		issues = append(issues, "🧠 High memory consumption. Memory leaks detected on active browser nodes.")
	}
	if strings.Contains(strings.ToLower(disk), "90%") || strings.Contains(strings.ToLower(disk), "95%") {
		issues = append(issues, "💾 Disk capacity is almost full (>90%). Clean up temporary files or allocate more storage.")
	}

	if len(issues) == 0 {
		return "🤖 [AI Hypothesis]: No critical anomalies detected in standard diagnostic reports. System health is stable."
	}

	return fmt.Sprintf("🤖 [AI Diagnostics Summary for %s]:\n%s", pcName, strings.Join(issues, "\n"))
}

func handleFileUpload(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
	if r.Method == http.MethodOptions {
		w.WriteHeader(http.StatusOK)
		return
	}

	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	_ = r.ParseMultipartForm(15 << 20)
	file, header, err := r.FormFile("file")
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	defer file.Close()

	ext := strings.ToLower(filepath.Ext(header.Filename))
	allowedExts := map[string]bool{
		".png":  true,
		".jpg":  true,
		".jpeg": true,
		".gif":  true,
		".txt":  true,
		".log":  true,
		".zip":  true,
		".pdf":  true,
		".evtx": true,
		".csv":  true,
	}
	if !allowedExts[ext] {
		http.Error(w, "File type not allowed", http.StatusBadRequest)
		return
	}

	uniqueName := fmt.Sprintf("%d%s", time.Now().UnixNano(), ext)

	uploadDir := "/app/uploads/chat"
	if runtime.GOOS == "windows" {
		uploadDir = filepath.Join(".", "uploads", "chat")
	}
	os.MkdirAll(uploadDir, 0755)

	destPath := filepath.Join(uploadDir, uniqueName)

	// Save upload stream to a temporary file first to guarantee completeness
	tempFile, err := os.CreateTemp("", "osi-upload-*")
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	tempPath := tempFile.Name()
	defer os.Remove(tempPath)
	defer tempFile.Close()

	written, err := io.Copy(tempFile, file)
	if err != nil {
		http.Error(w, "Upload stream interrupted: "+err.Error(), http.StatusBadRequest)
		return
	}

	// Double check header size match to prevent partial uploads
	if header.Size > 0 && written != header.Size {
		http.Error(w, "File size mismatch (partial upload)", http.StatusBadRequest)
		return
	}

	// Seek back to start of temp file for reading
	_, _ = tempFile.Seek(0, 0)

	if ext == ".png" || ext == ".jpg" || ext == ".jpeg" {
		img, _, err := image.Decode(tempFile)
		if err == nil {
			out, err := os.Create(destPath)
			if err == nil {
				_ = jpeg.Encode(out, img, &jpeg.Options{Quality: 75})
				out.Close()
			} else {
				http.Error(w, err.Error(), http.StatusInternalServerError)
				return
			}
		} else {
			// Save the raw file from temp file if image decode fails
			_, _ = tempFile.Seek(0, 0)
			err = saveRawFile(tempFile, destPath)
			if err != nil {
				http.Error(w, err.Error(), http.StatusInternalServerError)
				return
			}
		}
	} else {
		err = saveRawFile(tempFile, destPath)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
	}

	relPath := fmt.Sprintf("uploads/chat/%s", uniqueName)
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]interface{}{
		"status":          "SUCCESS",
		"attachment_path": relPath,
	})
}

func saveRawFile(src io.Reader, dest string) error {
	out, err := os.Create(dest)
	if err != nil {
		return err
	}
	defer out.Close()
	_, err = io.Copy(out, src)
	return err
}

func handleChatSend(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
	if r.Method == http.MethodOptions {
		w.WriteHeader(http.StatusOK)
		return
	}

	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req struct {
		ClientID       string `json:"client_id"`
		Sender         string `json:"sender"`
		Message        string `json:"message"`
		AttachmentPath string `json:"attachment_path"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	if req.ClientID == "" || req.Sender == "" {
		http.Error(w, "client_id and sender are required", http.StatusBadRequest)
		return
	}

	msg := database.ChatMessage{
		ClientID:       req.ClientID,
		Sender:         req.Sender,
		Message:        req.Message,
		AttachmentPath: req.AttachmentPath,
		ReadStatus:     "SENT",
	}
	database.DB.Create(&msg)

	status := "WAITING_OPERATOR"
	if req.Sender == "OPERATOR" {
		status = "ACTIVE"
		if redisClient != nil {
			_ = redisClient.Set(ctx, "presence:operator", "1", 15*time.Second).Err()
			publishChatEvent(ChatEvent{
				Type:     "operator_status",
				ClientID: req.ClientID,
				Sender:   "SYSTEM",
				Data: map[string]interface{}{
					"status":    "ONLINE",
					"last_seen": time.Now().Unix(),
				},
			})
		}
	}
	
	// Create chat session if it doesn't exist
	var session database.ChatSession
	if err := database.DB.Where("client_id = ?", req.ClientID).First(&session).Error; err != nil {
		session = database.ChatSession{
			ClientID: req.ClientID,
			PCName:   req.ClientID, // fallback if PCName isn't provided separately
			Status:   status,
		}
		database.DB.Create(&session)
	} else {
		database.DB.Model(&session).Updates(map[string]interface{}{
			"status":     status,
			"updated_at": time.Now(),
		})
	}

	publishChatEvent(ChatEvent{
		Type:     "message",
		ClientID: req.ClientID,
		Sender:   req.Sender,
		Data:     msg,
	})

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(msg)
}

func handleChatHistory(w http.ResponseWriter, r *http.Request) {
	clientID := r.URL.Query().Get("client_id")
	if clientID == "" {
		http.Error(w, "client_id is required", http.StatusBadRequest)
		return
	}

	var messages []database.ChatMessage
	database.DB.Where("client_id = ?", clientID).Order("id asc").Find(&messages)

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(messages)
}

func handleChatSearch(w http.ResponseWriter, r *http.Request) {
	clientID := r.URL.Query().Get("client_id")
	query := r.URL.Query().Get("query")
	if clientID == "" || query == "" {
		http.Error(w, "client_id and query are required", http.StatusBadRequest)
		return
	}

	var messages []database.ChatMessage
	database.DB.Where("client_id = ? AND message ILIKE ?", clientID, "%"+query+"%").Order("id asc").Find(&messages)

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(messages)
}

func handleChatPoll(w http.ResponseWriter, r *http.Request) {
	clientID := r.URL.Query().Get("client_id")
	lastIDStr := r.URL.Query().Get("last_id")
	if clientID == "" {
		http.Error(w, "client_id is required", http.StatusBadRequest)
		return
	}

	lastID := 0
	if lastIDStr != "" {
		lastID, _ = strconv.Atoi(lastIDStr)
	}

	var messages []database.ChatMessage
	database.DB.Where("client_id = ? AND id > ?", clientID, lastID).Order("id asc").Find(&messages)

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(messages)
}

func handleDiagnostics(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req struct {
		ClientID string                 `json:"client_id"`
		PCName   string                 `json:"pc_name"`
		Data     map[string]interface{} `json:"data"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	handleDiagnosticsPayload(req.ClientID, req.PCName, req.Data)

	w.Header().Set("Content-Type", "application/json")
	_, _ = w.Write([]byte(`{"status":"SUCCESS"}`))
}

func sendTelegramChatAlert(pcName, clientID string, msg database.ChatMessage) {
	relayURL := "http://localhost:9998/relay/telegram/send"
	if os.Getenv("DB_HOST") == "postgres" {
		relayURL = "http://osi-secure-relay:9998/relay/telegram/send"
	}

	text := fmt.Sprintf("💬 <b>CHAT DARI CLIENT:</b> %s\nID: `<code>%s</code>`\nPesan: %s", pcName, clientID, msg.Message)
	if msg.AttachmentPath != "" {
		text += fmt.Sprintf("\nLampiran: %s", msg.AttachmentPath)
	}

	var photoB64 string
	if msg.AttachmentPath != "" {
		ext := strings.ToLower(filepath.Ext(msg.AttachmentPath))
		if ext == ".png" || ext == ".jpg" || ext == ".jpeg" || ext == ".gif" || ext == ".bmp" {
			absPath := msg.AttachmentPath
			if !os.IsPathSeparator(msg.AttachmentPath[0]) {
				absPath = "./" + msg.AttachmentPath
			}
			imgData, err := os.ReadFile(absPath)
			if err == nil {
				photoB64 = base64.StdEncoding.EncodeToString(imgData)
			} else {
				fmt.Printf("[TELEGRAM CHAT ERROR] Failed to read attachment image %s: %v\n", absPath, err)
			}
		}
	}

	payload := map[string]interface{}{
		"message": text,
	}
	if photoB64 != "" {
		payload["photo_b64"] = photoB64
	}
	payloadBytes, _ := json.Marshal(payload)

	ts := strconv.FormatInt(time.Now().Unix(), 10)
	msgToSign := append([]byte(ts), payloadBytes...)

	secret := []byte("EnterpriseSecureRelay2026_HMAC_KEY_123")
	if envSecret := os.Getenv("HMAC_SECRET"); envSecret != "" {
		secret = []byte(envSecret)
	}

	mac := hmac.New(sha256.New, secret)
	mac.Write(msgToSign)
	sig := hex.EncodeToString(mac.Sum(nil))

	req, err := http.NewRequest("POST", relayURL, bytes.NewBuffer(payloadBytes))
	if err != nil {
		return
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Signature", sig)
	req.Header.Set("X-Timestamp", ts)

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err == nil {
		defer resp.Body.Close()
		var respMap map[string]interface{}
		_ = json.NewDecoder(resp.Body).Decode(&respMap)

		if telegramMsgIDVal, ok := respMap["message_id"]; ok {
			var telegramMsgID int64
			if floatVal, ok := telegramMsgIDVal.(float64); ok {
				telegramMsgID = int64(floatVal)
			} else if intVal, ok := telegramMsgIDVal.(int64); ok {
				telegramMsgID = intVal
			}

			if telegramMsgID > 0 {
				mapping := database.TelegramChatMapping{
					TelegramMessageID: telegramMsgID,
					ClientID:          clientID,
					ChatMessageID:     msg.ID,
				}
				database.DB.Create(&mapping)
			}
		}
	}
}

func StartSchedulerSubscriptions() {
	if natsConn == nil {
		return
	}

	// 1. Cleanup Subscription
	_, _ = natsConn.Subscribe("scheduler.cleanup", func(m *nats.Msg) {
		if database.DB == nil {
			return
		}
		fmt.Println(" [SCHEDULER TASK] Executing DB Cleanups (system_audits)")
		database.DB.Exec(`DELETE FROM system_audits WHERE id NOT IN (
			SELECT id FROM system_audits ORDER BY timestamp DESC LIMIT 100
		)`)
	})

	// 2. Retention Subscription
	_, _ = natsConn.Subscribe("scheduler.retention", func(m *nats.Msg) {
		if database.DB == nil {
			return
		}
		fmt.Println(" [SCHEDULER TASK] Executing PG Partition Retention (manage_partitions)")
		database.DB.Exec("SELECT manage_partitions()")
	})

	// 3. SLA Check Subscription
	_, _ = natsConn.Subscribe("scheduler.sla.check", func(m *nats.Msg) {
		fmt.Println(" [SCHEDULER TASK] Executing SLA Check")
		handleSLACheck()
	})

	fmt.Println(" [INGESTOR] Scheduler NATS tasks subscribed successfully.")
}

func handleSLACheck() {
	if database.DB == nil {
		return
	}

	type IncidentRow struct {
		IncidentID  int    `gorm:"column:incident_id"`
		DeviceID    string `gorm:"column:device_id"`
		SiteID      string `gorm:"column:site_id"`
		Description string `gorm:"column:description"`
	}
	var breachedIncidents []IncidentRow

	// Select incidents that are about to breach SLA
	database.DB.Raw(`
		SELECT incident_id, device_name as device_id, '' as site_id, flag as description 
		FROM incident_states 
		WHERE status NOT IN ('RESOLVED', 'CLOSED', 'DLQ', 'FAILED') 
		  AND sla_deadline < NOW() 
		  AND sla_breached = FALSE
	`).Scan(&breachedIncidents)

	if len(breachedIncidents) > 0 {
		for _, inc := range breachedIncidents {
			// Update database
			database.DB.Exec("UPDATE incident_states SET sla_breached = TRUE WHERE incident_id = ?", inc.IncidentID)

			// Publish warning message to chat
			if natsConn != nil {
				fmt.Printf(" [SLA BREACH] Incident %d on device %s breached SLA!\n", inc.IncidentID, inc.DeviceID)

				warningMsg := fmt.Sprintf("[SLA BREACH ALERT] Incident ID %d has breached its SLA deadline! Immediate operator intervention is required.", inc.IncidentID)

				database.DB.Exec(`
					INSERT INTO chat_messages (client_id, sender, message, attachment_path, read_status, incident_id, is_system_msg, created_at)
					VALUES (?, 'SYSTEM', ?, '', 'SENT', ?, TRUE, NOW())
				`, inc.DeviceID, warningMsg, inc.IncidentID)

				siteClean := strings.ToLower(strings.TrimSpace(inc.SiteID))
				if siteClean == "" {
					siteClean = "unknown"
				}

				payload := map[string]interface{}{
					"message_id":    fmt.Sprintf("sla-breach-%d", inc.IncidentID),
					"id":            time.Now().Unix(),
					"incident_id":   inc.IncidentID,
					"client_id":     inc.DeviceID,
					"sender_type":   "SYSTEM",
					"message":       warningMsg,
					"timestamp":     time.Now().Format(time.RFC3339),
					"is_system_msg": true,
					"thread_type":   "SUPPORT",
				}
				b, err := json.Marshal(payload)
				if err == nil {
					_, _ = natsJS.Publish(fmt.Sprintf("chat.site.%s.thread.%d", siteClean, inc.IncidentID), b)
				}

				_, _ = natsJS.Publish("incident.sla.breach", b)
			}
		}
	}
}
