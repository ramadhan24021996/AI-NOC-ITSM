package ingestion

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net"
	"strings"
	"sync"
	"time"

	"github.com/google/uuid"
	"go_incident_analysis/SERVER/go_core/database"
	"go_incident_analysis/portal/dashboard/knowledge"
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
	msg1, _ := DefaultChatService.SaveChatMessage(clientID, "AI_HYPOTHESIS", msg1Text, "", "DELIVERED")
	DefaultChatService.PublishChatEvent(ChatEvent{
		Type:     "message",
		ClientID: clientID,
		Sender:   "AI_HYPOTHESIS",
		Data:     msg1,
	})

	// 4. Perform AI Analysis
	diagResult, reportText := DefaultAIAnalysisService.Analyze(description, "")

	// 5. Send Message 2: "🧠 Analisa Selesai"
	msg2Text := fmt.Sprintf("🧠 <b>Analisa Selesai</b>\n\n%s", reportText)
	msg2, _ := DefaultChatService.SaveChatMessage(clientID, "AI_HYPOTHESIS", msg2Text, "", "DELIVERED")
	DefaultChatService.PublishChatEvent(ChatEvent{
		Type:     "message",
		ClientID: clientID,
		Sender:   "AI_HYPOTHESIS",
		Data:     msg2,
	})

	// 6. Send Message 3: "🚨 INCIDENT TERDETEKSI" (RAG AI Assist Standardized Format)
	causeIndo := TranslateCauseToIndo(diagResult.PrimaryCause)
	var msg3Text string
	if kbMatch := knowledge.GlobalEngine.Match(description + " " + diagResult.PrimaryCause); kbMatch != nil {
		var stepsBuilder strings.Builder
		for idx, st := range kbMatch.RemediationSteps {
			stepsBuilder.WriteString(fmt.Sprintf("   %d. %s\n", idx+1, st))
		}
		msg3Text = fmt.Sprintf(
			"🤖 <b>AI ASSIST (NOC Operator Bot)</b>\n\n"+
				"Saya menemukan panduan penanganan resmi untuk kendala <b>%s</b>:\n\n"+
				"💡 <b>Langkah Penanganan (Remediation):</b>\n%s\n"+
				"---------------------------------------------------\n"+
				"<i>Bila kendala belum terselesaikan, silakan klik <b>Hubungi NOC</b> untuk tersambung ke Teknisi IT.</i>\n\n"+
				"<b>Incident ID:</b> %d",
			kbMatch.Symptom, stepsBuilder.String(), incidentID,
		)
	} else {
		remediationGuide := BuildUserFriendlyRemediation(diagResult.PrimaryCause, diagResult.Reason, diagResult.Action, severity)

		msg3Text = fmt.Sprintf(
			"🤖 <b>AI ASSIST (NOC Operator Bot)</b>\n\n"+
				"Saya menemukan panduan penanganan untuk kendala <b>%s</b>:\n\n"+
				"💡 <b>Langkah Penanganan (Remediation):</b>\n%s\n"+
				"---------------------------------------------------\n"+
				"<i>Bila kendala belum terselesaikan, silakan klik <b>Hubungi NOC</b> untuk tersambung ke Teknisi IT.</i>\n\n"+
				"<b>Incident ID:</b> %d",
			causeIndo, remediationGuide, incidentID,
		)
	}
	msg3, _ := DefaultChatService.SaveChatMessage(clientID, "AI_HYPOTHESIS", msg3Text, "", "DELIVERED")
	DefaultChatService.PublishChatEvent(ChatEvent{
		Type:     "message",
		ClientID: clientID,
		Sender:   "AI_HYPOTHESIS",
		Data:     msg3,
	})

	// 6b. Push SHOW_NOTIFICATION ke PC klien (agar kasir/user mendapat notifikasi jelas)
	go func() {
		var clientIP string
		_ = database.DB.Raw("SELECT ip FROM devices WHERE name = ?", pcName).Row().Scan(&clientIP)
		if clientIP == "" {
			fmt.Printf("[INCIDENT WORKFLOW] Client IP not found for %s, skipping SHOW_NOTIFICATION push\n", pcName)
			return
		}

		// Pesan notifikasi desktop yang sangat jelas & mudah dipahami
		notifTitle := "⚠️ Perhatian - Insiden Sistem Terdeteksi"
		notifMsg := fmt.Sprintf("Masalah: %s\n\nPanduan: Cek kabel LAN / restart adapter jaringan.\nSilakan buka OSI Support Chat untuk panduan lengkap.", causeIndo)

		timestamp := time.Now().Unix()

		// Generate HMAC token for SHOW_NOTIFICATION
		mac1 := hmac.New(sha256.New, []byte("SIAP_DISTRIBUSI_SECRET_KEY"))
		mac1.Write([]byte(fmt.Sprintf("SHOW_NOTIFICATION:%d", timestamp)))
		tokenNotif := hex.EncodeToString(mac1.Sum(nil))

		notifPayload := map[string]interface{}{
			"command":   "SHOW_NOTIFICATION",
			"params":    map[string]interface{}{"title": notifTitle, "message": notifMsg, "severity": severity},
			"timestamp": timestamp,
			"token":     tokenNotif,
		}
		sendBypassCommandToAgent(clientIP, notifPayload)
		time.Sleep(1 * time.Second)

		// Generate HMAC token for SHOW_CHAT
		mac2 := hmac.New(sha256.New, []byte("SIAP_DISTRIBUSI_SECRET_KEY"))
		mac2.Write([]byte(fmt.Sprintf("SHOW_CHAT:%d", timestamp)))
		tokenChat := hex.EncodeToString(mac2.Sum(nil))

		chatPayload := map[string]interface{}{
			"command":   "SHOW_CHAT",
			"params":    map[string]interface{}{"server_ip": clientIP},
			"timestamp": timestamp,
			"token":     tokenChat,
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
	err := database.DB.Where("client_id = ? AND (sender = 'SYSTEM' OR sender = 'AI_HYPOTHESIS') AND message LIKE ?", clientID, "%"+searchIDStr+"%").First(&msg).Error
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

// TranslateCauseToIndo converts technical English cause strings to clear Indonesian terms
func TranslateCauseToIndo(cause string) string {
	if cause == "" {
		return "Gangguan Sistem / Jarkan Terdeteksi"
	}
	lower := strings.ToLower(cause)
	if strings.Contains(lower, "network") || strings.Contains(lower, "gateway") || strings.Contains(lower, "ping") {
		return "Koneksi Jaringan Terputus / Gateway Router Tidak Merespons"
	}
	if strings.Contains(lower, "database") || strings.Contains(lower, "postgres") || strings.Contains(lower, "exhausted") {
		return "Koneksi Database Server Terhenti / Beban Antrean Tinggi"
	}
	if strings.Contains(lower, "agent") || strings.Contains(lower, "service") || strings.Contains(lower, "stopped") {
		return "Service Agent Pemantau Terhenti pada PC Klien"
	}
	if strings.Contains(lower, "cpu") || strings.Contains(lower, "memory") || strings.Contains(lower, "ram") {
		return "Beban Penggunaan Memori RAM / CPU Sangat Tinggi"
	}
	if strings.Contains(lower, "unrecognized") || strings.Contains(lower, "telemetry") {
		return "Anomali Sinyal Telemetri Terdeteksi pada Komputer Klien"
	}
	return cause
}

// BuildUserFriendlyRemediation creates clear, numbered step-by-step remediation instructions
func BuildUserFriendlyRemediation(cause string, reason string, rawAction string, severity string) string {
	lower := strings.ToLower(cause + " " + reason + " " + rawAction + " " + severity)

	if strings.Contains(lower, "network") || strings.Contains(lower, "gateway") || strings.Contains(lower, "ping") || strings.Contains(lower, "koneksi") || strings.Contains(lower, "unreachable") || strings.Contains(lower, "telemetry") {
		return "1️⃣ <b>Periksa Kabel LAN & Wi-Fi:</b>\n" +
			"   • Pastikan kabel LAN terpasang erat di belakang PC Klien Anda.\n" +
			"   • Periksa lampu port LAN (harus berkedip hijau/kuning).\n\n" +
			"2️⃣ <b>Restart Network Adapter / PC:</b>\n" +
			"   • Matikan Wi-Fi/LAN selama 5 detik lalu aktifkan kembali.\n" +
			"   • Jika belum pulih, lakukan Restart pada PC Klien Anda.\n\n" +
			"3️⃣ <b>Bantuan Otomatis AI & NOC:</b>\n" +
			"   • Klik <b>Selesaikan Masalah</b> di bawah jika jaringan pulih.\n" +
			"   • Klik <b>Hubungi NOC</b> untuk bantuan teknisi IT langsung."
	}

	if strings.Contains(lower, "memory") || strings.Contains(lower, "ram") || strings.Contains(lower, "cpu") || strings.Contains(lower, "resource") {
		return "1️⃣ <b>Tutup Aplikasi Berat:</b>\n" +
			"   • Tutup tab browser atau aplikasi yang tidak digunakan.\n" +
			"   • Periksa Task Manager untuk melihat penggunaan RAM.\n\n" +
			"2️⃣ <b>Restart Komputer Klien:</b>\n" +
			"   • Lakukan restart sistem untuk membersihkan alokasi RAM.\n\n" +
			"3️⃣ <b>Bantuan Teknisi IT:</b>\n" +
			"   • Klik <b>Hubungi NOC</b> jika PC masih terasa sangat lambat."
	}

	if strings.Contains(lower, "service") || strings.Contains(lower, "process") || strings.Contains(lower, "stopped") || strings.Contains(lower, "agent") {
		return "1️⃣ <b>Verifikasi Status Service OSI Agent:</b>\n" +
			"   • Pastikan icon perisai OSI di taskbar dalam kondisi aktif.\n" +
			"   • Jalankan `INSTALL_AGENT.bat` (Run as Administrator) jika terhenti.\n\n" +
			"2️⃣ <b>Bantuan Otomatis:</b>\n" +
			"   • Klik <b>Selesaikan Masalah</b> untuk merestart service otomatis."
	}

	return "1️⃣ <b>Pemeriksaan Mandiri:</b>\n" +
		"   • Periksa koneksi jaringan dan status aplikasi di komputer Anda.\n" +
		"   • Tutup dan buka kembali aplikasi jika mengalami kendala.\n\n" +
		"2️⃣ <b>Restart Komputer:</b>\n" +
		"   • Lakukan restart pada PC Klien jika kendala berlanjut.\n\n" +
		"3️⃣ <b>Eskalasi Teknisi IT:</b>\n" +
		"   • Klik <b>Hubungi NOC</b> untuk ditangani langsung oleh Teknisi."
}
