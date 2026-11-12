package main

// portal/jarvis_api.go
// --------------------
// FIX-1B: JARVIS Voice API Proxy Routes
//
// Registers Go Gin routes that forward requests to the Python
// JarvisVoiceAPIServer running on localhost:8089.
//
// Architecture:
//   Browser → POST /api/jarvis/voice/query (Go Portal :9999)
//     → HTTP Proxy → Python JarvisVoiceAPIServer (:8089)
//     → JarvisPresentationRuntime (Full Pipeline)
//     → JSON Response { answer_text, audio_b64, intent, ... }
//     → Back to Browser
//
// Design Decisions:
//   - Pure stdlib net/http for proxy (no new Go deps)
//   - JARVIS_VOICE_API_URL env var for flexible deployment (Docker, bare metal)
//   - Timeout: 45s (voice pipeline can take up to 30s for complex queries)
//   - Health check forwarded transparently
//   - WebSocket broadcast of JARVIS avatar state after each query

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/gorilla/websocket"
)

var (
	proactiveAnnounceMu        sync.Mutex
	proactiveAnnounceCooldowns = make(map[string]time.Time)
)

// getJarvisInternalBearerToken returns a non-empty internal service token for Go Portal -> Python JARVIS Voice Server calls.
func getJarvisInternalBearerToken() string {
	for _, envKey := range []string{"JWT_SECRET_KEY", "JWT_SECRET", "OSI_SECURITY_KEY", "JARVIS_INTERNAL_TOKEN"} {
		if val := strings.TrimSpace(os.Getenv(envKey)); val != "" {
			return val
		}
	}
	return "osi-internal-portal-bridge-token"
}

// buildJarvisProxyHeaders constructs authenticated headers with operator identity & RBAC role.
func buildJarvisProxyHeaders(c *gin.Context) http.Header {
	h := http.Header{}
	h.Set("X-Forwarded-From", "go-portal")
	if c != nil {
		if authHeader := strings.TrimSpace(c.GetHeader("Authorization")); authHeader != "" {
			h.Set("Authorization", authHeader)
		} else {
			h.Set("Authorization", "Bearer "+getJarvisInternalBearerToken())
		}
		if sessionID := strings.TrimSpace(c.GetHeader("X-Session-ID")); sessionID != "" {
			h.Set("X-Session-ID", sessionID)
		}
		if username := strings.TrimSpace(c.GetString("username")); username != "" {
			h.Set("X-Operator-User", username)
		} else if hdrUser := strings.TrimSpace(c.GetHeader("X-Operator-User")); hdrUser != "" {
			h.Set("X-Operator-User", hdrUser)
		}
		if role := strings.TrimSpace(c.GetString("role")); role != "" {
			h.Set("X-Operator-Role", role)
		} else if hdrRole := strings.TrimSpace(c.GetHeader("X-Operator-Role")); hdrRole != "" {
			h.Set("X-Operator-Role", hdrRole)
		}
	} else {
		h.Set("Authorization", "Bearer "+getJarvisInternalBearerToken())
	}
	return h
}

// jarvisVoiceAPIURL is the base URL of the Python JARVIS Voice API Server.
// Configurable via JARVIS_VOICE_API_URL environment variable.
// Default: osi-jarvis-voice-server:8089 (Docker container hostname on osi-backend network)
// Bare-metal fallback: set JARVIS_VOICE_API_URL=http://127.0.0.1:8089
func getJarvisVoiceAPIURL() string {
	u := os.Getenv("JARVIS_VOICE_API_URL")
	if u == "" {
		// Default: Docker container hostname. Override to http://127.0.0.1:8089 for bare-metal.
		u = "http://osi-jarvis-voice-server:8089"
	}
	return u
}

// jarvisHTTPClient is a shared HTTP client with production timeouts.
// 45s timeout: voice pipeline STT+LLM+TTS can take up to 30s on first call.
var jarvisHTTPClient = &http.Client{
	Timeout: 45 * time.Second,
}

// RegisterJarvisAPIRoutes wires all JARVIS Voice API proxy routes into the Gin router.
// Called from runPortal() in dashboard_server.go.
//
// Routes registered:
//
//	POST /api/jarvis/voice/query   — Main voice command processing endpoint
//	GET  /api/jarvis/voice/duplex  — Real-time full-duplex WebSocket voice streaming (<300ms)
//	GET  /api/jarvis/health        — Liveness probe for Python runtime
func RegisterJarvisAPIRoutes(r *gin.Engine) {
	jarvis := r.Group("/api/jarvis")

	// ── POST /api/jarvis/voice/query ─────────────────────────────────────────
	// Main JARVIS voice command endpoint.
	// Accepts: { "question": string, "session_id": string, "urgency": string }
	// Returns: { "answer_text": string, "audio_b64": string, "intent": string, ... }
	jarvis.POST("/voice/query", func(c *gin.Context) {
		proxyToJarvisVoiceServer(c, "POST", "/jarvis/voice/query")
	})

	// ── GET /api/jarvis/voice/duplex ──────────────────────────────────────────
	// Real-time Full-Duplex WebSocket voice streaming + Barge-in Interruption.
	jarvis.GET("/voice/duplex", handleJarvisVoiceDuplexWS)

	// ── GET /api/jarvis/health ────────────────────────────────────────────────
	// Health probe — checks if Python JARVIS Runtime is initialized & ready.
	// Used by: monitoring, load balancer, frontend startup check.
	jarvis.GET("/health", func(c *gin.Context) {
		proxyToJarvisVoiceServer(c, "GET", "/jarvis/health")
	})

	// ── POST /api/jarvis/proactive/announce ──────────────────────────────────
	// Proactive alert proxy route.
	jarvis.POST("/proactive/announce", func(c *gin.Context) {
		proxyToJarvisVoiceServer(c, "POST", "/jarvis/proactive/announce")
	})

	// ── GET  /api/jarvis/voice/config ────────────────────────────────────────
	// Read current JARVIS Voice & Gender configuration (persona, voice_name, rate, pitch, engine).
	jarvis.GET("/voice/config", func(c *gin.Context) {
		proxyToJarvisVoiceServer(c, "GET", "/jarvis/voice/config")
	})

	// ── POST /api/jarvis/voice/config ────────────────────────────────────────
	// Update JARVIS Voice & Gender config at runtime — no server restart needed.
	// Accepts: { "voice_name": "id-ID-GadisNeural", "active_persona": "executive", ... }
	jarvis.POST("/voice/config", func(c *gin.Context) {
		proxyToJarvisVoiceServer(c, "POST", "/jarvis/voice/config")
	})

	fmt.Println("[BOOT] JARVIS Voice API routes registered: POST /api/jarvis/voice/query | GET /api/jarvis/voice/duplex | GET /api/jarvis/health | POST /api/jarvis/proactive/announce | GET+POST /api/jarvis/voice/config")
}

// handleJarvisVoiceDuplexWS proxies full-duplex WebSocket voice stream between Browser & Python JARVIS Voice Server.
func handleJarvisVoiceDuplexWS(c *gin.Context) {
	clientConn, err := upgrader.Upgrade(c.Writer, c.Request, nil)
	if err != nil {
		fmt.Printf("[JARVIS-WS] ❌ Client WebSocket upgrade failed: %v\n", err)
		return
	}
	defer clientConn.Close()

	// Convert http(s) URL to ws(s) URL
	pyBase := getJarvisVoiceAPIURL()
	wsURL := strings.Replace(pyBase, "http://", "ws://", 1)
	wsURL = strings.Replace(wsURL, "https://", "wss://", 1) + "/jarvis/voice/duplex"

	wsHeaders := buildJarvisProxyHeaders(c)
	pyConn, _, err := websocket.DefaultDialer.Dial(wsURL, wsHeaders)
	if err != nil {
		fmt.Printf("[JARVIS-WS] ❌ Python JARVIS Voice Server WebSocket dial error (%s): %v\n", wsURL, err)
		errResp := map[string]interface{}{
			"avatar_state": "ERROR",
			"error":        fmt.Sprintf("Sistem otak JARVIS (Python Voice WS) tidak dapat dijangkau di %s", wsURL),
		}
		jsonBytes, _ := json.Marshal(errResp)
		clientConn.WriteMessage(websocket.TextMessage, jsonBytes)
		return
	}
	defer pyConn.Close()

	fmt.Printf("[JARVIS-WS] ⚡ Full-Duplex WebSocket Proxy Established: Client <-> %s\n", wsURL)

	errChan := make(chan error, 2)

	// Goroutine 1: Client -> Python Server
	go func() {
		for {
			msgType, data, err := clientConn.ReadMessage()
			if err != nil {
				errChan <- err
				return
			}
			if err := pyConn.WriteMessage(msgType, data); err != nil {
				errChan <- err
				return
			}
		}
	}()

	// Goroutine 2: Python Server -> Client
	go func() {
		for {
			msgType, data, err := pyConn.ReadMessage()
			if err != nil {
				errChan <- err
				return
			}
			if err := clientConn.WriteMessage(msgType, data); err != nil {
				errChan <- err
				return
			}
			// Non-blocking avatar state broadcast to other UI components
			if msgType == websocket.TextMessage {
				go broadcastJarvisAvatarState(data)
			}
		}
	}()

	<-errChan
	fmt.Println("[JARVIS-WS] Full-Duplex WebSocket Proxy Closed")
}

// proxyToJarvisVoiceServer forwards a Gin request to the Python JARVIS Voice API Server.
// Handles:
//   - Request body forwarding
//   - Response streaming back to client
//   - Error handling with meaningful JSON error responses
//   - WebSocket broadcast of avatar state on successful queries
func proxyToJarvisVoiceServer(c *gin.Context, method, pyPath string) {
	baseURL := getJarvisVoiceAPIURL()
	targetURL := baseURL + pyPath

	// Read original request body
	var bodyBytes []byte
	if c.Request.Body != nil {
		var err error
		bodyBytes, err = io.ReadAll(c.Request.Body)
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"error":       "Failed to read request body",
				"detail":      err.Error(),
				"answer_text": "Terjadi kesalahan saat memproses permintaan suara. Silakan coba lagi.",
			})
			return
		}
	}

	// Build proxy request
	proxyReq, err := http.NewRequest(method, targetURL, bytes.NewReader(bodyBytes))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":       "Failed to create proxy request",
			"detail":      err.Error(),
			"answer_text": "Sistem JARVIS tidak dapat dijangkau. Pastikan Python AI Core berjalan.",
		})
		return
	}

	// Forward content-type, authorization, and operator RBAC headers [WS-J1 / WS-J4]
	for k, vals := range buildJarvisProxyHeaders(c) {
		for _, v := range vals {
			proxyReq.Header.Set(k, v)
		}
	}
	proxyReq.Header.Set("Content-Type", "application/json")

	// Execute proxy request
	resp, err := jarvisHTTPClient.Do(proxyReq)
	if err != nil {
		// Python server unreachable — return meaningful error (not 502 crash)
		errMsg := fmt.Sprintf("JARVIS Python Runtime tidak dapat dijangkau di %s: %v", targetURL, err)
		fmt.Printf("[JARVIS-PROXY] ❌ Proxy error: %v\n", err)
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"error": errMsg,
			"answer_text": fmt.Sprintf(
				"Sistem otak JARVIS (Python AI Core) tidak dapat dijangkau. "+
					"Pastikan python_ai_core berjalan pada port 8089. Detail: %v", err),
			"source":      "PROXY_ERROR",
			"runtime_url": targetURL,
		})
		return
	}
	defer resp.Body.Close()

	// Read response body from Python server
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":       "Failed to read Python response",
			"detail":      err.Error(),
			"answer_text": "Respons dari JARVIS tidak dapat dibaca. Silakan coba lagi.",
		})
		return
	}

	// Parse response to broadcast avatar state via WebSocket (non-blocking)
	if method == "POST" && resp.StatusCode == http.StatusOK {
		go broadcastJarvisAvatarState(respBody)
	}

	// Forward status code and response body back to browser
	c.Data(resp.StatusCode, "application/json; charset=utf-8", respBody)
}

// broadcastJarvisAvatarState parses a JARVIS voice query response and
// broadcasts the avatar state + intent to all connected WebSocket clients.
// This enables real-time UI synchronization (LISTENING → THINKING → SPEAKING → IDLE).
// Runs in a goroutine — non-blocking.
func broadcastJarvisAvatarState(respBody []byte) {
	defer func() {
		if r := recover(); r != nil {
			fmt.Printf("[JARVIS-PROXY] WebSocket broadcast panic (non-fatal): %v\n", r)
		}
	}()

	var result map[string]interface{}
	if err := json.Unmarshal(respBody, &result); err != nil {
		return // Not JSON — skip broadcast
	}

	avatarState, _ := result["avatar_state"].(string)
	intent, _ := result["intent"].(string)
	intentConf, _ := result["intent_confidence"].(float64)
	sessionID, _ := result["session_id"].(string)
	latency, _ := result["latency_ms"].(float64)

	if avatarState == "" {
		return // Nothing meaningful to broadcast
	}

	// Broadcast via global WebSocket event (wsPkg.BroadcastWSEvent)
	broadcastWSEvent("jarvis_avatar_state", map[string]interface{}{
		"state":             avatarState,
		"intent":            intent,
		"intent_confidence": intentConf,
		"session_id":        sessionID,
		"latency_ms":        latency,
		"timestamp":         time.Now().Unix(),
	})

	// Check if target_panel is specified for automatic frontend UI navigation
	if targetPanel, ok := result["target_panel"].(string); ok && targetPanel != "" {
		broadcastWSEvent("jarvis_navigate_panel", map[string]interface{}{
			"panel_id":  targetPanel,
			"timestamp": time.Now().Unix(),
		})
	}
}

// TriggerJarvisProactiveAnnounce sends an event payload asynchronously to Python JARVIS Voice API Server
// (/jarvis/proactive/announce). If JARVIS returns audio and text (not skipped), it broadcasts a
// "jarvis_proactive_alert" event to all connected WebSocket clients. Non-blocking goroutine.
func TriggerJarvisProactiveAnnounce(eventType, severity, title, details, device, incidentID, siteID string, extra map[string]interface{}) {
	// [WS-J7] Cooldown & Deduplication Gate (15s window per eventType+device) to prevent overlapping audio alert storms
	cooldownKey := fmt.Sprintf("%s:%s", strings.ToLower(strings.TrimSpace(eventType)), strings.ToLower(strings.TrimSpace(device)))
	proactiveAnnounceMu.Lock()
	if lastTime, exists := proactiveAnnounceCooldowns[cooldownKey]; exists && time.Since(lastTime) < 15*time.Second {
		proactiveAnnounceMu.Unlock()
		return
	}
	proactiveAnnounceCooldowns[cooldownKey] = time.Now()
	proactiveAnnounceMu.Unlock()

	go func() {
		defer func() {
			if r := recover(); r != nil {
				log.Printf("[JARVIS-PROACTIVE] Recovered from panic in proactive announce: %v", r)
			}
		}()

		log.Printf("[JARVIS-PROACTIVE] 📢 Triggering proactive announce: type=%s, sev=%s, device=%s", eventType, severity, device)

		payload := map[string]interface{}{
			"event_type":  eventType,
			"severity":    severity,
			"title":       title,
			"details":     details,
			"device":      device,
			"incident_id": incidentID,
			"site_id":     siteID,
		}
		for k, v := range extra {
			if k != "event_type" && k != "severity" && k != "title" && k != "details" && k != "device" && k != "incident_id" && k != "site_id" {
				payload[k] = v
			}
		}

		bodyBytes, err := json.Marshal(payload)
		if err != nil {
			log.Printf("[JARVIS-PROACTIVE] ❌ JSON marshal error: %v", err)
			return
		}

		targetURL := getJarvisVoiceAPIURL() + "/jarvis/proactive/announce"
		req, err := http.NewRequest("POST", targetURL, bytes.NewBuffer(bodyBytes))
		if err != nil {
			log.Printf("[JARVIS-PROACTIVE] ❌ Request build error: %v", err)
			return
		}
		for k, vals := range buildJarvisProxyHeaders(nil) {
			for _, v := range vals {
				req.Header.Set(k, v)
			}
		}
		req.Header.Set("Content-Type", "application/json")

		client := &http.Client{Timeout: 8 * time.Second}
		resp, err := client.Do(req)
		if err != nil {
			log.Printf("[JARVIS-PROACTIVE] ⚠️ Voice server HTTP error: %v", err)
			return
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			log.Printf("[JARVIS-PROACTIVE] ⚠️ Voice server returned status %d", resp.StatusCode)
			return
		}

		respBytes, err := io.ReadAll(resp.Body)
		if err != nil {
			log.Printf("[JARVIS-PROACTIVE] ❌ Read response body error: %v", err)
			return
		}

		var resMap map[string]interface{}
		if err := json.Unmarshal(respBytes, &resMap); err != nil {
			log.Printf("[JARVIS-PROACTIVE] ❌ JSON unmarshal response error: %v", err)
			return
		}

		skipped, _ := resMap["skipped"].(bool)
		skipReason, _ := resMap["skip_reason"].(string)
		if skipped {
			log.Printf("[JARVIS-PROACTIVE] ℹ️ Voice announcement skipped by Python server: %s", skipReason)
			return
		}

		text, _ := resMap["text"].(string)
		audioB64, _ := resMap["audio_b64"].(string)
		audioFmt, _ := resMap["audio_format"].(string)

		if text == "" {
			log.Printf("[JARVIS-PROACTIVE] ⚠️ Empty announcement text returned")
			return
		}

		// Broadcast proactive voice alert to browser UI via WebSocket
		broadcastWSEvent("jarvis_proactive_alert", map[string]interface{}{
			"text":         text,
			"audio_b64":    audioB64,
			"audio_format": audioFmt,
			"severity":     severity,
			"event_type":   eventType,
			"device":       device,
			"incident_id":  incidentID,
			"timestamp":    time.Now().Unix(),
		})

		log.Printf("[JARVIS-PROACTIVE] ✅ Proactive voice alert broadcasted via WebSocket! Device: %s, Text: %.60s..., Audio: %d bytes", device, text, len(audioB64))
	}()
}
