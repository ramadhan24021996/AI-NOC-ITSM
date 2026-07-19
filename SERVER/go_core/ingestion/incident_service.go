package ingestion

import (
	"encoding/json"
	"fmt"
	"net"
	"strings"
	"sync"
	"time"

	"github.com/google/uuid"
	"go_incident_analysis/SERVER/go_core/database"
)

// sendBypassCommandToAgent mengirimkan perintah TCP langsung ke agent.exe di PC klien.
// Mencoba port 10000 lalu 10001 sebagai fallback.
func sendBypassCommandToAgent(clientIP string, payload map[string]interface{}) {
	payloadBytes, err := json.Marshal(payload)
	if err != nil {
		return
	}
	for _, port := range []int{10000, 10001} {
		conn, err := net.DialTimeout("tcp", fmt.Sprintf("%s:%d", clientIP, port), 3*time.Second)
		if err == nil {
			_ = conn.SetWriteDeadline(time.Now().Add(3 * time.Second))
			_, _ = conn.Write(append(payloadBytes, '\n'))
			conn.Close()
			return
		}
	}
	fmt.Printf("[INCIDENT WORKFLOW] WARNING: Could not reach agent at %s on ports 10000/10001\n", clientIP)
}

var (
	pendingScreenshots   = make(map[string]chan string) // clientID -> channel
	pendingScreenshotsMu sync.Mutex
)

type IncidentService struct{}

var DefaultIncidentService = &IncidentService{}

// RegisterScreenshotCallback records an uploaded screenshot path for a waiting incident workflow.
func RegisterScreenshotCallback(clientID string, path string) {
	pendingScreenshotsMu.Lock()
	ch, exists := pendingScreenshots[clientID]
	pendingScreenshotsMu.Unlock()
	if exists {
		select {
		case ch <- path:
		default:
		}
	}
}

// TriggerIncidentWorkflow starts the whole modular workflow when a new anomaly/issue is detected.
func (s *IncidentService) TriggerIncidentWorkflow(pcName string, severity string, description string) {
	fmt.Printf("[INCIDENT WORKFLOW] Starting for PC %s, severity %s, desc: %s\n", pcName, severity, description)

	// 1. Get or create chat session
	var session database.ChatSession
	err := database.DB.Where("pc_name = ?", pcName).First(&session).Error
	if err != nil {
		clientID := uuid.New().String()
		session = database.ChatSession{
			ClientID:  clientID,
			PCName:    pcName,
			Status:    "OPEN",
			CreatedAt: time.Now(),
			UpdatedAt: time.Now(),
		}
		database.DB.Create(&session)
	}

	clientID := session.ClientID

	// 2. Create the ticket/incident in fleet_incidents
	var dbSiteID interface{} = nil
	database.DB.Exec("INSERT INTO fleet_incidents (site_id, pc_name, severity, status, description, created_at) VALUES (?, ?, ?, 'OPEN', ?, NOW())",
		dbSiteID, pcName, severity, description)

	// Get the last inserted incident_id
	var incidentID uint
	database.DB.Raw("SELECT LASTVAL()").Scan(&incidentID)
	if incidentID == 0 {
		// Fallback query if lastval fails
		database.DB.Raw("SELECT incident_id FROM fleet_incidents WHERE pc_name = ? ORDER BY created_at DESC LIMIT 1", pcName).Scan(&incidentID)
	}

	database.DB.Exec("INSERT INTO incident_events (incident_id, event_type, payload) VALUES (?, 'CREATED', ?)",
		fmt.Sprintf("%d", incidentID), fmt.Sprintf(`{"pc_name": "%s", "severity": "%s", "description": "%s"}`, pcName, severity, description))

	// 3. Send Message 1: "Saya mendeteksi gangguan..."
	msg1Text := "🤖 <b>OSI AI</b>\nSaya mendeteksi gangguan pada komputer Anda.\nSedang melakukan analisa...\nMohon tunggu beberapa saat."
	msg1, _ := DefaultChatService.SaveChatMessage(clientID, "SYSTEM", msg1Text, "", "DELIVERED")
	DefaultChatService.PublishChatEvent(ChatEvent{
		Type:     "message",
		ClientID: clientID,
		Sender:   "SYSTEM",
		Data:     msg1,
	})

	// 4. Perform AI Analysis
	diagResult, reportText := DefaultAIAnalysisService.Analyze(description, "")

	// 5. Send Message 2: "🧠 Analisa Selesai"
	msg2Text := fmt.Sprintf("🧠 <b>Analisa Selesai</b>\n\n%s", reportText)
	msg2, _ := DefaultChatService.SaveChatMessage(clientID, "SYSTEM", msg2Text, "", "DELIVERED")
	DefaultChatService.PublishChatEvent(ChatEvent{
		Type:     "message",
		ClientID: clientID,
		Sender:   "SYSTEM",
		Data:     msg2,
	})

	// 6. Send Message 3: "🚨 INCIDENT TERDETEKSI" (Incident Card)
	recomm := diagResult.Action
	if recomm == "" {
		recomm = "• Restart router atau adapter jaringan\n• Cek koneksi kabel LAN\n• Hubungi NOC jika masalah tetap ada"
	}
	msg3Text := fmt.Sprintf(
		"🚨 <b>INCIDENT TERDETEKSI</b>\n\n"+
			"<b>Incident ID:</b> %d\n"+
			"<b>Incident:</b> %s\n"+
			"<b>Severity:</b> %s\n\n"+
			"<b>Analisa AI:</b>\n%s\n\n"+
			"<b>Rekomendasi:</b>\n%s",
		incidentID, diagResult.PrimaryCause, diagResult.Severity, diagResult.Reason, recomm,
	)
	msg3, _ := DefaultChatService.SaveChatMessage(clientID, "SYSTEM", msg3Text, "", "DELIVERED")
	DefaultChatService.PublishChatEvent(ChatEvent{
		Type:     "message",
		ClientID: clientID,
		Sender:   "SYSTEM",
		Data:     msg3,
	})

	// 6b. Push SHOW_NOTIFICATION ke PC klien (agar kasir tidak perlu klik manual)
	//     Ini mengirimkan perintah via bypass TCP ke agent.exe yang sudah berjalan di PC klien.
	go func() {
		// Ambil IP klien dari database devices
		var clientIP string
		_ = database.DB.Raw("SELECT ip FROM devices WHERE name = ?", pcName).Row().Scan(&clientIP)
		if clientIP == "" {
			fmt.Printf("[INCIDENT WORKFLOW] Client IP not found for %s, skipping SHOW_NOTIFICATION push\n", pcName)
			return
		}

		// Pesan singkat yang mudah dipahami kasir awam
		notifTitle := "⚠️ Perhatian - Komputer Anda"
		notifMsg := fmt.Sprintf("Sistem mendeteksi masalah: %s\n\nSeverity: %s\n\nRekomendasi: %s\n\nSilakan lihat chat untuk panduan lengkap.",
			diagResult.PrimaryCause, severity, recomm)

		// Kirim SHOW_NOTIFICATION
		notifPayload := map[string]interface{}{
			"command":   "SHOW_NOTIFICATION",
			"params":    map[string]interface{}{"title": notifTitle, "message": notifMsg, "severity": severity},
			"timestamp": fmt.Sprintf("%d", time.Now().Unix()),
			"token":     "", // token handling di agent sudah ada fallback key
		}
		sendBypassCommandToAgent(clientIP, notifPayload)
		time.Sleep(1 * time.Second)

		// Kirim SHOW_CHAT (buka jendela chat otomatis di PC klien)
		chatPayload := map[string]interface{}{
			"command":   "SHOW_CHAT",
			"params":    map[string]interface{}{"server_ip": clientIP},
			"timestamp": fmt.Sprintf("%d", time.Now().Unix()),
			"token":     "",
		}
		sendBypassCommandToAgent(clientIP, chatPayload)
		fmt.Printf("[INCIDENT WORKFLOW] SHOW_NOTIFICATION + SHOW_CHAT pushed to %s (%s)\n", pcName, clientIP)
	}()

	// 7. Request automatic screenshot from C# client agent via WebSocket
	screenshotChan := make(chan string, 1)
	pendingScreenshotsMu.Lock()
	pendingScreenshots[clientID] = screenshotChan
	pendingScreenshotsMu.Unlock()

	// Send screenshot request command over WebSocket
	_ = DefaultChatService.SendWSCommand(clientID, "capture_screenshot", map[string]interface{}{
		"incident_id": incidentID,
	})

	// 8. Wait for screenshot callback asynchronously (timeout after 4 seconds)
	go func(incID uint, cID string, pName string) {
		var screenshotPath string
		select {
		case path := <-screenshotChan:
			screenshotPath = path
		case <-time.After(4 * time.Second):
			// Timeout
		}

		pendingScreenshotsMu.Lock()
		delete(pendingScreenshots, cID)
		pendingScreenshotsMu.Unlock()

		// Save screenshot to fleet_evidence if received
		if screenshotPath != "" {
			database.DB.Exec("INSERT INTO fleet_evidence (incident_id, evidence_type, s3_path, timestamp) VALUES (?, 'SCREENSHOT', ?, NOW())",
				incID, screenshotPath)
			fmt.Printf("[INCIDENT WORKFLOW] Screenshot received & saved to evidence: %s\n", screenshotPath)
		} else {
			fmt.Println("[INCIDENT WORKFLOW] Screenshot timeout or not received.")
		}
	}(incidentID, clientID, pcName)
}

// EscalateIncident routes the incident to the NOC: updates status, broadcasts to dashboard, and alerts Telegram NOC.
func (s *IncidentService) EscalateIncident(clientID string, incidentID uint) error {
	fmt.Printf("[INCIDENT WORKFLOW] Escalating incident %d for client %s\n", incidentID, clientID)

	// Update the Incident Card status text in chat messages
	updateIncidentCardStatus(clientID, incidentID, "WAITING NOC")

	// 1. Ask Python EventBus to Escalate the incident
	if natsConn != nil {
		var siteID string
		database.DB.Table("fleet_incidents").Select("site_id").Where("incident_id = ?", incidentID).Scan(&siteID)
		if siteID == "" {
			siteID = "global"
		}
		
		escalateReq := map[string]interface{}{
			"incident_id":   incidentID,
			"current_level": 1,
			"next_level":    2,
			"operator_note": "Escalated by user via Dashboard",
		}
		escBytes, _ := json.Marshal(escalateReq)
		_ = natsConn.Publish(fmt.Sprintf("incident.site.%s.escalate.request", siteID), escBytes)
	}

	// 2. Set chat session status to WAITING_OPERATOR
	database.DB.Exec("UPDATE chat_sessions SET status = 'WAITING_OPERATOR', updated_at = NOW() WHERE client_id = ?", clientID)

	// 3. Fetch incident details
	var incident struct {
		PCName      string
		Severity    string
		Description string
	}
	err := database.DB.Raw("SELECT pc_name, severity, description FROM fleet_incidents WHERE incident_id = ?", incidentID).Scan(&incident).Error
	if err != nil {
		return err
	}

	// 4. Check for screenshot in evidence
	var screenshotPath string
	database.DB.Raw("SELECT s3_path FROM fleet_evidence WHERE incident_id = ? AND evidence_type = 'SCREENSHOT' ORDER BY timestamp DESC LIMIT 1", incidentID).Scan(&screenshotPath)

	// 5. Query AI diagnosis details
	diagResult, _ := DefaultAIAnalysisService.Analyze(incident.Description, "")
	recomm := diagResult.Action
	if recomm == "" {
		recomm = "• Restart router or network adapter\n• Check LAN cable connection\n• Contact NOC if the issue persists"
	}

	// 6. Notify NOC via Telegram
	_, err = DefaultTelegramService.SendIncidentAlert(
		clientID, incident.PCName, incidentID,
		diagResult.PrimaryCause, incident.Severity,
		diagResult.Reason, recomm, screenshotPath,
	)

	// 7. Send Chat confirmation to user
	msgText := "⏳ <b>NOC Dihubungi</b>\nMasalah Anda telah dilaporkan ke NOC. Operator NOC akan segera menghubungi Anda di chat ini."
	msg, _ := DefaultChatService.SaveChatMessage(clientID, "SYSTEM", msgText, "", "DELIVERED")
	DefaultChatService.PublishChatEvent(ChatEvent{
		Type:     "message",
		ClientID: clientID,
		Sender:   "SYSTEM",
		Data:     msg,
	})

	return err
}

// ResolveIncident closes the incident (Self-healing).
func (s *IncidentService) ResolveIncident(clientID string, incidentID uint) error {
	fmt.Printf("[INCIDENT WORKFLOW] Resolving incident %d for client %s\n", incidentID, clientID)

	// Update the Incident Card status text in chat messages
	updateIncidentCardStatus(clientID, incidentID, "RESOLVED")

	// 1. Ask Python EventBus to Resolve the incident
	if natsConn != nil {
		var siteID string
		database.DB.Table("fleet_incidents").Select("site_id").Where("incident_id = ?", incidentID).Scan(&siteID)
		if siteID == "" {
			siteID = "global"
		}
		
		closeReq := map[string]interface{}{
			"incident_id":        incidentID,
			"actor":              "Self-Healing",
			"resolution_summary": "Resolved by user via Chat Dashboard",
			"resolution_proof":   "Resolved via Chat Interface",
		}
		closeBytes, _ := json.Marshal(closeReq)
		_ = natsConn.Publish(fmt.Sprintf("incident.site.%s.close.request", siteID), closeBytes)
	}

	// 2. Set chat session status to CLOSED
	database.DB.Exec("UPDATE chat_sessions SET status = 'CLOSED', updated_at = NOW() WHERE client_id = ?", clientID)

	// 3. Fetch PC name
	var pcName string
	database.DB.Raw("SELECT pc_name FROM chat_sessions WHERE client_id = ?", clientID).Scan(&pcName)
	if pcName == "" {
		pcName = "unknown-device"
	}

	// 4. Send Telegram notification to NOC
	telMsg := fmt.Sprintf("✅ <b>SELF-HEALING BERHASIL</b>\n\nUser pada komputer <b>%s</b> berhasil mengatasi masalah secara mandiri (Self-Healing) untuk Incident ID: <code>%d</code>.", pcName, incidentID)
	_, _ = DefaultTelegramService.SendIncidentAlert(clientID, pcName, incidentID, "Self-Healing Success", "INFO", telMsg, "", "")

	// 5. Send Chat confirmation to user
	msgText := "✅ <b>Terima Kasih</b>\nAnda melaporkan bahwa masalah telah diselesaikan. Sesi ini ditutup. Status ticket diupdate menjadi Resolved."
	msg, _ := DefaultChatService.SaveChatMessage(clientID, "SYSTEM", msgText, "", "DELIVERED")
	DefaultChatService.PublishChatEvent(ChatEvent{
		Type:     "message",
		ClientID: clientID,
		Sender:   "SYSTEM",
		Data:     msg,
	})

	return nil
}

// updateIncidentCardStatus modifies the stored incident message card and broadcasts the update.
func updateIncidentCardStatus(clientID string, incidentID uint, status string) {
	var msg database.ChatMessage
	searchIDStr := fmt.Sprintf("<b>Incident ID:</b> %d", incidentID)
	err := database.DB.Where("client_id = ? AND sender = 'SYSTEM' AND message LIKE ?", clientID, "%"+searchIDStr+"%").First(&msg).Error
	if err != nil {
		fmt.Printf("[INCIDENT SERVICE] Warning: could not find incident card message for ID %d: %v\n", incidentID, err)
		return
	}

	// Split message into lines, remove any existing Status line, and append the new one
	lines := strings.Split(msg.Message, "\n")
	var newLines []string
	for _, line := range lines {
		if !strings.HasPrefix(line, "<b>Status:</b>") {
			newLines = append(newLines, line)
		}
	}
	newLines = append(newLines, fmt.Sprintf("<b>Status:</b> %s", status))
	msg.Message = strings.Join(newLines, "\n")

	database.DB.Save(&msg)

	// Broadcast message update so the client tray receives it
	DefaultChatService.PublishChatEvent(ChatEvent{
		Type:     "message_update",
		ClientID: clientID,
		Sender:   "SYSTEM",
		Data:     msg,
	})
}
