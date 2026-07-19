package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"os"
	"os/exec"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"time"

	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"

	"go_incident_analysis/SERVER/go_core/security"

	"github.com/google/uuid"
	"github.com/nats-io/nats.go"
)

var (
	TelegramBotToken string
	TelegramApiUrl   string
	AuthorizedAdmins []int64
	DB               *gorm.DB
	natsConn         *nats.Conn
)

type PendingRemediation struct {
	ActionID    string    `gorm:"type:text;primaryKey;column:action_id"`
	Command     string    `gorm:"type:text;not null;column:command"`
	Description string    `gorm:"type:text;column:description"`
	Status      string    `gorm:"type:text;default:'PENDING';column:status"`
	CreatedAt   time.Time `gorm:"column:created_at;autoCreateTime"`
}

func (PendingRemediation) TableName() string {
	return "pending_remediations"
}

type LiveThreadMessage struct {
	MessageID   string                 `json:"message_id,omitempty"`
	ID          int64                  `json:"id"`
	IncidentID  int                    `json:"incident_id"`
	ClientID    string                 `json:"client_id"`
	SenderType  string                 `json:"sender_type"` // CLIENT, OPERATOR, SYSTEM, AI
	Message     string                 `json:"message"`
	Attachment  string                 `json:"attachment,omitempty"`
	Timestamp   string                 `json:"timestamp"`
	IsSystemMsg bool                   `json:"is_system_msg"`
	ThreadType  string                 `json:"thread_type"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
}

var (
	processedNatsMessages sync.Map
)

func isDuplicateNatsMessage(messageID string) bool {
	if messageID == "" {
		return false
	}
	_, loaded := processedNatsMessages.LoadOrStore(messageID, time.Now())
	return loaded
}

func getEnv(key, fallback string) string {
	if value, exists := os.LookupEnv(key); exists {
		return value
	}
	return fallback
}

func initEnv() {
	TelegramBotToken = getEnv("TELEGRAM_BOT_TOKEN", "8685494518:AAHvhd8K3nmgCDy23dHTXsj9K0jSV0YT5lU")
	TelegramApiUrl = fmt.Sprintf("https://api.telegram.org/bot%s", TelegramBotToken)

	adminsStr := getEnv("AUTHORIZED_ADMINS", "7794987703")
	parts := strings.Split(adminsStr, ",")
	for _, p := range parts {
		if id, err := strconv.ParseInt(strings.TrimSpace(p), 10, 64); err == nil {
			AuthorizedAdmins = append(AuthorizedAdmins, id)
		}
	}
}

func initDatabase() {
	host := getEnv("DB_HOST", "postgres")
	port := getEnv("DB_PORT", "5432")
	dbname := getEnv("DB_NAME", "osi_system")

	sm, err := security.GetSecurityManager()
	if err != nil {
		fmt.Printf("[DB ERROR] Failed to init security manager: %v. Fallback to standard connection.\n", err)
	}

	var decUser, decPass string
	if sm != nil {
		encUser := "gAAAAABqBKK7az-y_l5fNA2vSgnwxIN0eaZWvqXhTwjWTXhGxXtzff4_iHYcL1u5VrmlwwnSxvwWNnlscwcn0Ph81c7PUGS9Ag=="
		encPass := "gAAAAABqBKK743cBIrvwAdYBl3yM1HSNi6UQaekLxv2PM9FW7VPWDMf0e08beTFA1iQmTpU5QTX0quOcbEf7pLjuArG4jwZp7g=="
		decUser, _ = sm.Decrypt(encUser)
		decPass, _ = sm.Decrypt(encPass)
	}

	if decUser == "" {
		decUser = "postgres"
	}
	if decPass == "" {
		decPass = "postgres"
	}
	
	if getEnv("DB_USER", "") != "" {
		decUser = getEnv("DB_USER", "")
	}
	if getEnv("DB_PASSWORD", "") != "" {
		decPass = getEnv("DB_PASSWORD", "")
	}

	dsn := fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=disable TimeZone=UTC",
		host, port, decUser, decPass, dbname)

	var db *gorm.DB
	for i := 0; i < 5; i++ {
		db, err = gorm.Open(postgres.Open(dsn), &gorm.Config{
			Logger: logger.Default.LogMode(logger.Warn),
		})
		if err == nil {
			break
		}
		fmt.Printf("[DB INFO] Waiting for database connection... retry %d/5\n", i+1)
		time.Sleep(3 * time.Second)
	}

	if err != nil {
		fmt.Printf("[DB FATAL] Failed to connect to database: %v\n", err)
		os.Exit(1)
	}

	err = db.AutoMigrate(&PendingRemediation{})
	if err != nil {
		fmt.Printf("[DB ERROR] Auto migration failed: %v\n", err)
	}

	DB = db
	fmt.Println("[DB] Database connected and schema migrated.")
}

func initNats() {
	natsHost := getEnv("NATS_HOST", "nats")
	natsPort := getEnv("NATS_PORT", "4222")
	natsToken := getEnv("OSI_SECURITY_KEY", "")
	var err error

	for retries := 0; retries < 5; retries++ {
		natsURL := fmt.Sprintf("nats://%s:%s", natsHost, natsPort)
		if natsToken != "" {
			natsURL = fmt.Sprintf("nats://%s@%s:%s", natsToken, natsHost, natsPort)
		}
		natsConn, err = nats.Connect(natsURL)
		if err == nil {
			break
		}
		fmt.Printf("[NATS INFO] Waiting for NATS connection... retry %d/5\n", retries+1)
		time.Sleep(3 * time.Second)
	}

	if err != nil {
		fmt.Printf("[NATS ERROR] Failed to connect to NATS: %v\n", err)
	} else {
		fmt.Println("[NATS] Connected to NATS.")
		_, _ = natsConn.QueueSubscribe("chat.site.*.thread.*", "telegram-bot-group", func(m *nats.Msg) {
			handleNatsThreadMessage(m)
		})
	}
}

func handleNatsThreadMessage(m *nats.Msg) {
	var msg LiveThreadMessage
	if err := json.Unmarshal(m.Data, &msg); err != nil {
		return
	}

	if isDuplicateNatsMessage(msg.MessageID) {
		return
	}

	if msg.Metadata != nil {
		if src, ok := msg.Metadata["source_channel"].(string); ok && src == "telegram" {
			return
		}
	}

	tgText := fmt.Sprintf("💬 <b>Incident #%d Chat Thread Update</b>\n\n", msg.IncidentID)
	if msg.IsSystemMsg {
		tgText += fmt.Sprintf("⚙️ <b>SYSTEM:</b> %s", msg.Message)
	} else {
		tgText += fmt.Sprintf("👤 <b>%s:</b> %s", msg.SenderType, msg.Message)
	}

	chatID, _ := strconv.ParseInt(getEnv("TELEGRAM_CHAT_ID", "7794987703"), 10, 64)
	sentMsgID := sendTelegramMessage(chatID, tgText)

	if sentMsgID > 0 {
		mapping := map[string]interface{}{
			"telegram_message_id": sentMsgID,
			"client_id":           msg.ClientID,
			"chat_message_id":     msg.ID,
			"created_at":          time.Now(),
		}
		DB.Table("telegram_chat_mappings").Create(&mapping)
	}
}

func validateTelegramOperator(telegramUserID int64, incidentID int) (string, string, bool) {
	var opID string
	err := DB.Table("telegram_chat_mappings").
		Select("operator_id").
		Where("telegram_user_id = ? AND verified = true", telegramUserID).
		Row().Scan(&opID)

	if err != nil || opID == "" {
		for _, adminID := range AuthorizedAdmins {
			if adminID == telegramUserID {
				return "admin", "ADMIN", true
			}
		}
		return "", "", false
	}

	var siteAccessStr string
	var role string
	err = DB.Table("operator_profiles").
		Select("role, array_to_string(site_access, ',') as site_access").
		Where("operator_id = ?", opID).
		Row().Scan(&role, &siteAccessStr)
	if err != nil {
		return "", "", false
	}

	siteAccess := []string{}
	if siteAccessStr != "" {
		siteAccess = strings.Split(siteAccessStr, ",")
	}

	if incidentID > 0 && len(siteAccess) > 0 {
		var incident struct {
			SiteID string `gorm:"column:site_id"`
		}
		if err := DB.Table("fleet_incidents").Select("site_id").Where("incident_id = ?", incidentID).First(&incident).Error; err == nil {
			if incident.SiteID != "" {
				allowed := false
				for _, sa := range siteAccess {
					if sa == incident.SiteID {
						allowed = true
						break
					}
				}
				if !allowed {
					return "", "", false
				}
			}
		}
	}
	if role == "" {
		role = "L1"
	}
	return opID, role, true
}

func writeAuditLog(db *gorm.DB, actionType, actor, target string, payload interface{}) error {
	payloadBytes, _ := json.Marshal(payload)
	payloadStr := string(payloadBytes)

	var lastRow struct {
		HashSignature string `gorm:"column:hash_signature"`
	}
	prevHash := "0"
	if err := db.Raw("SELECT hash_signature FROM immutable_audit_log ORDER BY log_id DESC LIMIT 1").Scan(&lastRow).Error; err == nil && lastRow.HashSignature != "" {
		prevHash = lastRow.HashSignature
	}

	dataToHash := fmt.Sprintf("%s|%s|%s|%s|%s", prevHash, actionType, actor, target, payloadStr)
	hash := sha256.Sum256([]byte(dataToHash))
	hashSig := fmt.Sprintf("%x", hash)

	return db.Exec(`
		INSERT INTO immutable_audit_log (action_type, actor, target, payload, prev_hash, hash_signature, timestamp)
		VALUES (?, ?, ?, ?, ?, ?, NOW())
	`, actionType, actor, target, payloadStr, prevHash, hashSig).Error
}

func isAdminAuthorized(senderID int64) bool {
	for _, adminID := range AuthorizedAdmins {
		if adminID == senderID {
			return true
		}
	}
	return false
}

func sendTelegramMessage(chatID int64, text string) int64 {
	url := fmt.Sprintf("%s/sendMessage", TelegramApiUrl)
	payload := map[string]interface{}{
		"chat_id":    chatID,
		"text":       text,
		"parse_mode": "HTML",
	}
	jsonBytes, err := json.Marshal(payload)
	if err != nil {
		return 0
	}

	resp, err := http.Post(url, "application/json", bytes.NewBuffer(jsonBytes))
	if err != nil {
		return 0
	}
	defer resp.Body.Close()

	var tgResp struct {
		Ok     bool `json:"ok"`
		Result struct {
			MessageID int64 `json:"message_id"`
		} `json:"result"`
	}
	bodyBytes, _ := io.ReadAll(resp.Body)
	if json.Unmarshal(bodyBytes, &tgResp) == nil && tgResp.Ok {
		return tgResp.Result.MessageID
	}
	return 0
}

func editMessageText(chatID int64, messageID int64, text string, replyMarkup interface{}) {
	url := fmt.Sprintf("%s/editMessageText", TelegramApiUrl)
	payload := map[string]interface{}{
		"chat_id":    chatID,
		"message_id": messageID,
		"text":       text,
		"parse_mode": "HTML",
	}
	if replyMarkup != nil {
		payload["reply_markup"] = replyMarkup
	}

	jsonBytes, err := json.Marshal(payload)
	if err != nil {
		return
	}

	resp, err := http.Post(url, "application/json", bytes.NewBuffer(jsonBytes))
	if err == nil {
		resp.Body.Close()
	}
}

func answerCallbackQuery(callbackQueryID string, text string, showAlert bool) {
	url := fmt.Sprintf("%s/answerCallbackQuery", TelegramApiUrl)
	payload := map[string]interface{}{
		"callback_query_id": callbackQueryID,
	}
	if text != "" {
		payload["text"] = text
		payload["show_alert"] = showAlert
	}

	jsonBytes, err := json.Marshal(payload)
	if err != nil {
		return
	}

	resp, err := http.Post(url, "application/json", bytes.NewBuffer(jsonBytes))
	if err == nil {
		resp.Body.Close()
	}
}

func executeAction(actionID string) string {
	var action PendingRemediation
	if err := DB.First(&action, "action_id = ?", actionID).Error; err != nil {
		return "ERROR: Action ID tidak ditemukan atau sudah kadaluarsa."
	}

	if action.Status != "PENDING" {
		return "ERROR: Action sudah dieksekusi sebelumnya."
	}

	action.Status = "EXECUTING"
	DB.Save(&action)

	command := action.Command

	var cmd *exec.Cmd
	if runtime.GOOS == "windows" {
		cmd = exec.Command("powershell", "-NoProfile", "-NonInteractive", "-Command", command)
		setHideWindow(cmd)
	} else {
		cmd = exec.Command("bash", "-c", command)
	}

	var out bytes.Buffer
	cmd.Stdout = &out
	cmd.Stderr = &out

	err := cmd.Run()
	output := out.String()

	if err != nil {
		action.Status = "FAILED"
		action.Command = command
	} else {
		action.Status = "SUCCESS"
	}
	DB.Save(&action)

	statusStr := action.Status
	limit := 500
	if len(output) < limit {
		limit = len(output)
	}

	return fmt.Sprintf("EKSEKUSI SELESAI (%s).\nOutput:\n%s", statusStr, output[:limit])
}

func handleCallbackQuery(callback map[string]interface{}) {
	callbackQueryID, _ := callback["id"].(string)
	data, _ := callback["data"].(string)
	message, _ := callback["message"].(map[string]interface{})
	chatID := int64(0)
	messageID := int64(0)
	originalText := ""

	if message != nil {
		if chat, ok := message["chat"].(map[string]interface{}); ok {
			if idVal, ok := chat["id"].(float64); ok {
				chatID = int64(idVal)
			}
		}
		if idVal, ok := message["message_id"].(float64); ok {
			messageID = int64(idVal)
		}
		originalText, _ = message["text"].(string)
	}

	from, _ := callback["from"].(map[string]interface{})
	senderID := int64(0)
	if from != nil {
		if idVal, ok := from["id"].(float64); ok {
			senderID = int64(idVal)
		}
	}

	if strings.HasPrefix(data, "approve_") {
		if !isAdminAuthorized(senderID) {
			answerCallbackQuery(callbackQueryID, "AKSES DITOLAK: Anda tidak memiliki wewenang (Bukan Admin Level 3).", true)
			return
		}

		actionID := strings.TrimPrefix(data, "approve_")
		updatedText := originalText + "\n\n🚀 <b>ADMIN APPROVED:</b> Mengeksekusi perintah penyembuhan (Self-Healing) secara otomatis..."
		editMessageText(chatID, messageID, updatedText, nil)

		result := executeAction(actionID)

		finalText := updatedText + fmt.Sprintf("\n\n<b>[HASIL EKSEKUSI]:</b>\n<pre>%s</pre>", result)
		editMessageText(chatID, messageID, finalText, nil)
		answerCallbackQuery(callbackQueryID, "", false)
		return
	}

	if strings.HasPrefix(data, "already_checked_") {
		issueFlag := strings.TrimPrefix(data, "already_checked_")
		updatedText := originalText + "\n\n🔍 <b>Operator:</b> Semua sudah dicek secara manual."
		replyMarkup := map[string]interface{}{
			"inline_keyboard": [][]map[string]string{
				{
					{"text": "✅ Solved", "callback_data": "solved_" + issueFlag},
					{"text": "❌ Belum Selesai", "callback_data": "recheck_" + issueFlag},
				},
			},
		}
		editMessageText(chatID, messageID, updatedText, replyMarkup)
		answerCallbackQuery(callbackQueryID, "", false)
		return
	}

	if strings.HasPrefix(data, "recheck_") || strings.HasPrefix(data, "solved_") {
		updatedText := originalText + "\n\n⏳ <b>AI AGEN:</b> Menjalankan pengecekan ulang sistem secara langsung..."
		editMessageText(chatID, messageID, updatedText, nil)
		answerCallbackQuery(callbackQueryID, "", false)
		return
	}

	if strings.HasPrefix(data, "reject_") {
		agentNameVal := strings.TrimPrefix(data, "reject_")
		updatedText := originalText + fmt.Sprintf("\n\n❌ <b>ADMIN REJECT:</b> Hasil analisis untuk %s ditolak. Mengirim umpan balik ke AI untuk pembelajaran ulang...", agentNameVal)
		editMessageText(chatID, messageID, updatedText, nil)
		answerCallbackQuery(callbackQueryID, "", false)
		return
	}

	if strings.HasPrefix(data, "chat_user_") {
		clientID := strings.TrimPrefix(data, "chat_user_")

		var session struct {
			PCName string `gorm:"column:pc_name"`
		}
		err := DB.Table("chat_sessions").Select("pc_name").Where("client_id = ?", clientID).First(&session).Error
		pcName := "Unknown PC"
		if err == nil {
			pcName = session.PCName
		}

		DB.Table("chat_sessions").Where("client_id = ?", clientID).Update("status", "ACTIVE")

		url := fmt.Sprintf("%s/sendMessage", TelegramApiUrl)
		instructionText := fmt.Sprintf("💬 <b>OPERATOR CHAT ROOM: %s</b>\nSesi chat dua arah aktif. Silakan balas/reply pesan ini untuk mulai mengirim pesan ke user.", pcName)
		payload := map[string]interface{}{
			"chat_id":    chatID,
			"text":       instructionText,
			"parse_mode": "HTML",
		}
		jsonBytes, err := json.Marshal(payload)
		if err == nil {
			resp, err := http.Post(url, "application/json", bytes.NewBuffer(jsonBytes))
			if err == nil {
				defer resp.Body.Close()
				var tgResp struct {
					Ok     bool `json:"ok"`
					Result struct {
						MessageID int64 `json:"message_id"`
					} `json:"result"`
				}
				bodyBytes, _ := io.ReadAll(resp.Body)
				if json.Unmarshal(bodyBytes, &tgResp) == nil && tgResp.Ok {
					mapping := map[string]interface{}{
						"telegram_message_id": tgResp.Result.MessageID,
						"client_id":           clientID,
						"created_at":          time.Now(),
					}
					DB.Table("telegram_chat_mappings").Create(&mapping)
				}
			}
		}

		answerCallbackQuery(callbackQueryID, "Room Chat Aktif! Silakan balas pesan instruksi untuk chatting.", false)
		return
	}

	answerCallbackQuery(callbackQueryID, "", false)
}

func handleMessageUpdate(msg map[string]interface{}) {
	text, _ := msg["text"].(string)
	caption, _ := msg["caption"].(string)

	if text == "" && caption != "" {
		text = caption
	}

	from, _ := msg["from"].(map[string]interface{})
	senderID := int64(0)
	if from != nil {
		if idVal, ok := from["id"].(float64); ok {
			senderID = int64(idVal)
		}
	}

	chatID := int64(0)
	if chat, ok := msg["chat"].(map[string]interface{}); ok {
		if idVal, ok := chat["id"].(float64); ok {
			chatID = int64(idVal)
		}
	}

	if text == "" {
		return
	}

	// Handle Slash Command first
	if strings.HasPrefix(text, "/") {
		handleSlashCommand(chatID, senderID, text)
		return
	}

	var attachmentPath string

	if photoList, ok := msg["photo"].([]interface{}); ok && len(photoList) > 0 {
		if photoItem, ok := photoList[len(photoList)-1].(map[string]interface{}); ok {
			if fileID, ok := photoItem["file_id"].(string); ok {
				attPath, err := downloadAndUploadTelegramFile(fileID, "photo.jpg")
				if err == nil {
					attachmentPath = attPath
				} else {
					fmt.Printf("[BOT ERROR] Failed to download/upload photo from Telegram: %v\n", err)
				}
			}
		}
	} else if doc, ok := msg["document"].(map[string]interface{}); ok {
		if fileID, ok := doc["file_id"].(string); ok {
			fileName, _ := doc["file_name"].(string)
			if fileName == "" {
				fileName = "file"
			}
			attPath, err := downloadAndUploadTelegramFile(fileID, fileName)
			if err == nil {
				attachmentPath = attPath
			} else {
				fmt.Printf("[BOT ERROR] Failed to download/upload document from Telegram: %v\n", err)
			}
		}
	}

	replyTo, ok := msg["reply_to_message"].(map[string]interface{})
	if !ok {
		return
	}

	parentMsgIDFloat, ok := replyTo["message_id"].(float64)
	if !ok {
		return
	}
	parentMsgID := int64(parentMsgIDFloat)

	var mapping struct {
		ClientID      string `gorm:"column:client_id"`
		ChatMessageID int64  `gorm:"column:chat_message_id"`
	}
	err := DB.Table("telegram_chat_mappings").Where("telegram_message_id = ?", parentMsgID).First(&mapping).Error
	if err != nil {
		return
	}

	var incidentID int
	if mapping.ChatMessageID > 0 {
		var chatMsg struct {
			IncidentID int `gorm:"column:incident_id"`
		}
		if err := DB.Table("chat_messages").Select("incident_id").Where("id = ?", mapping.ChatMessageID).First(&chatMsg).Error; err == nil {
			incidentID = chatMsg.IncidentID
		}
	}
	if incidentID == 0 && mapping.ClientID != "" {
		var session struct {
			PCName string `gorm:"column:pc_name"`
		}
		DB.Table("chat_sessions").Select("pc_name").Where("client_id = ?", mapping.ClientID).Scan(&session)
		
		lookupName := mapping.ClientID
		if session.PCName != "" {
			lookupName = session.PCName
		}

		var incident struct {
			IncidentID int `gorm:"column:incident_id"`
		}
		if err := DB.Table("fleet_incidents").Select("incident_id").Where("pc_name = ? AND status != 'RESOLVED'", lookupName).Order("incident_id DESC").First(&incident).Error; err == nil {
			incidentID = incident.IncidentID
		}
	}

	if incidentID == 0 {
		return
	}

	operatorID, role, ok := validateTelegramOperator(senderID, incidentID)
	if !ok {
		sendTelegramMessage(chatID, "❌ <b>UNAUTHORIZED:</b> Akun Telegram Anda tidak terdaftar atau tidak memiliki akses ke incident ini.")
		return
	}

	var inc struct {
		OwnerID         string `gorm:"column:owner_id"`
		EscalationLevel int    `gorm:"column:escalation_level"`
	}
	if err := DB.Table("fleet_incidents").
		Select("owner_id, escalation_level").
		Where("incident_id = ?", incidentID).
		First(&inc).Error; err == nil {

		opLevelVal := 1
		switch role {
		case "L2":
			opLevelVal = 2
		case "L3":
			opLevelVal = 3
		case "ADMIN":
			opLevelVal = 4
		}

		if inc.OwnerID != "" && inc.OwnerID != operatorID {
			isEscalatedOperator := inc.EscalationLevel > 0 && opLevelVal >= inc.EscalationLevel
			if !isEscalatedOperator {
				sendTelegramMessage(chatID, fmt.Sprintf("❌ <b>ERROR:</b> Kepemilikan Terkunci. Incident ini dimiliki oleh operator lain (%s). Hanya Owner atau Operator Eskalasi Level L%d ke atas yang dapat membalas/menyelesaikan.", inc.OwnerID, inc.EscalationLevel))
				return
			}
		}

		if inc.OwnerID == "" {
			DB.Table("fleet_incidents").
				Where("incident_id = ?", incidentID).
				Updates(map[string]interface{}{
					"owner_id":    operatorID,
					"assigned_at": time.Now(),
					"status":      "ASSIGNED",
				})

			DB.Table("incident_assignments").Create(&map[string]interface{}{
				"incident_id": incidentID,
				"operator_id": operatorID,
				"assigned_at": time.Now(),
				"is_current":  true,
			})
			sendTelegramMessage(chatID, fmt.Sprintf("📝 Incident #%d otomatis ditugaskan ke Anda (%s).", incidentID, operatorID))
		}
	}

	var clientID string
	DB.Table("fleet_incidents").Select("pc_name").Where("incident_id = ?", incidentID).Scan(&clientID)

	newMsg := map[string]interface{}{
		"incident_id":     incidentID,
		"client_id":       clientID,
		"sender":          "OPERATOR",
		"message":         text,
		"attachment_path": attachmentPath,
		"thread_type":     "SUPPORT",
		"is_system_msg":   false,
		"created_at":      time.Now(),
	}
	if err := DB.Table("chat_messages").Create(&newMsg).Error; err != nil {
		fmt.Printf("[BOT ERROR] Failed to save chat message: %v\n", err)
		return
	}

	var lastMsg struct {
		ID int64
	}
	DB.Table("chat_messages").Select("id").Where("incident_id = ? AND message = ?", incidentID, text).Order("id DESC").Limit(1).Scan(&lastMsg)

	liveMsg := LiveThreadMessage{
		MessageID:   uuid.New().String(),
		ID:          lastMsg.ID,
		IncidentID:  incidentID,
		ClientID:    clientID,
		SenderType:  "OPERATOR",
		Message:     text,
		Attachment:  attachmentPath,
		Timestamp:   time.Now().Format(time.RFC3339),
		IsSystemMsg: false,
		ThreadType:  "SUPPORT",
		Metadata: map[string]interface{}{
			"source_channel": "telegram",
			"operator_id":    operatorID,
		},
	}
	liveBytes, _ := json.Marshal(liveMsg)
	if natsConn != nil {
		siteID := getIncidentSiteID(DB, int64(incidentID))
		_ = natsConn.Publish(fmt.Sprintf("chat.site.%s.thread.%d", siteID, incidentID), liveBytes)
	}

	_ = writeAuditLog(DB, "TELEGRAM_REPLY_SENT", operatorID, fmt.Sprintf("incident:%d", incidentID), map[string]interface{}{
		"message_id": lastMsg.ID,
		"channel":    "telegram",
	})
}

func handleSlashCommand(chatID int64, senderID int64, text string) {
	parts := strings.Fields(text)
	if len(parts) < 2 {
		sendTelegramMessage(chatID, "💡 <b>Petunjuk Penggunaan Command:</b>\n"+
			"- <code>/status &lt;incident_id&gt;</code>\n"+
			"- <code>/reply &lt;incident_id&gt; &lt;pesan&gt;</code>\n"+
			"- <code>/resolve &lt;incident_id&gt; &lt;summary&gt; [--force]</code>\n"+
			"- <code>/escalate &lt;incident_id&gt; &lt;note&gt;</code>\n"+
			"- <code>/assign &lt;incident_id&gt; &lt;operator_id&gt;</code>")
		return
	}

	cmd := parts[0]
	incidentIDStr := parts[1]
	incidentIDStr = strings.TrimPrefix(strings.ToUpper(incidentIDStr), "INC-")
	incidentID, err := strconv.Atoi(incidentIDStr)
	if err != nil {
		sendTelegramMessage(chatID, "❌ <b>ERROR:</b> ID Incident tidak valid. Format harus angka atau INC-&lt;angka&gt;.")
		return
	}

	operatorID, role, ok := validateTelegramOperator(senderID, incidentID)
	if !ok {
		sendTelegramMessage(chatID, "❌ <b>UNAUTHORIZED:</b> Akun Telegram Anda tidak terdaftar atau tidak memiliki akses ke incident ini.")
		return
	}

	var incident struct {
		IncidentID      int
		DeviceID        string `gorm:"column:pc_name"`
		OwnerID         string `gorm:"column:owner_id"`
		EscalationLevel int    `gorm:"column:escalation_level"`
		Severity        string `gorm:"column:severity"`
	}
	if err := DB.Table("fleet_incidents").
		Select("incident_id, pc_name, owner_id, escalation_level, severity").
		Where("incident_id = ?", incidentID).
		First(&incident).Error; err != nil {
		sendTelegramMessage(chatID, fmt.Sprintf("❌ <b>ERROR:</b> Incident #%d tidak ditemukan di database.", incidentID))
		return
	}

	// Calculate operator level value
	opLevelVal := 1
	switch role {
	case "L2":
		opLevelVal = 2
	case "L3":
		opLevelVal = 3
	case "ADMIN":
		opLevelVal = 4
	}

	// Ownership lock: only owner or escalated operator may reply/resolve
	if cmd == "/reply" || cmd == "/resolve" {
		if incident.OwnerID != "" && incident.OwnerID != operatorID {
			isEscalatedOperator := incident.EscalationLevel > 0 && opLevelVal >= incident.EscalationLevel
			if !isEscalatedOperator {
				sendTelegramMessage(chatID, fmt.Sprintf("❌ <b>ERROR:</b> Kepemilikan Terkunci. Incident ini dimiliki oleh operator lain (%s). Hanya Owner atau Operator Eskalasi Level L%d ke atas yang dapat membalas/menyelesaikan.", incident.OwnerID, incident.EscalationLevel))
				return
			}
		}
	}

	switch cmd {
	case "/status":
		var details struct {
			IncidentID  int       `gorm:"column:incident_id"`
			DeviceID    string    `gorm:"column:pc_name"`
			Title       string    `gorm:"column:title"`
			Severity    string    `gorm:"column:severity"`
			Status      string    `gorm:"column:status"`
			Owner       string    `gorm:"column:owner"`
			SlaDeadline time.Time `gorm:"column:sla_deadline"`
			EscLevel    int       `gorm:"column:escalation_level"`
		}
		if err := DB.Table("fleet_incidents").
			Select("incident_id, pc_name, title, severity, status, owner_id as owner, sla_deadline, escalation_level").
			Where("incident_id = ?", incidentID).
			Scan(&details).Error; err != nil {
			sendTelegramMessage(chatID, "❌ Gagal mengambil status incident.")
			return
		}

		var blast struct {
			BlastScore float64 `gorm:"column:blast_score"`
		}
		DB.Table("blast_radius_registry").Select("blast_score").Where("root_device = ?", details.DeviceID).Scan(&blast)

		slaLeft := time.Until(details.SlaDeadline).Round(time.Second)
		slaStr := slaLeft.String()
		if slaLeft < 0 {
			slaStr = fmt.Sprintf("BREACHED (%s ago)", (-slaLeft).String())
		}

		statusMsg := fmt.Sprintf("📊 <b>INCIDENT STATUS REPORT: INC-%d</b>\n\n"+
			"<b>Title:</b> %s\n"+
			"<b>Device/Host:</b> %s\n"+
			"<b>Severity:</b> %s\n"+
			"<b>Status:</b> %s\n"+
			"<b>Owner:</b> %s\n"+
			"<b>SLA Time Remaining:</b> %s\n"+
			"<b>Escalation Level:</b> L%d\n"+
			"<b>Blast Radius Score:</b> %.2f",
			details.IncidentID, details.Title, details.DeviceID, details.Severity,
			details.Status, details.Owner, slaStr, details.EscLevel, blast.BlastScore)

		sendTelegramMessage(chatID, statusMsg)
		_ = writeAuditLog(DB, "TELEGRAM_STATUS_REQUEST", operatorID, fmt.Sprintf("incident:%d", incidentID), nil)

	case "/reply":
		if len(parts) < 3 {
			sendTelegramMessage(chatID, "❌ <b>ERROR:</b> Format salah. Gunakan: <code>/reply &lt;incident_id&gt; &lt;pesan&gt;</code>")
			return
		}
		msgContent := strings.Join(parts[2:], " ")

		// Auto-assign owner if unassigned
		if incident.OwnerID == "" {
			DB.Table("fleet_incidents").
				Where("incident_id = ?", incidentID).
				Updates(map[string]interface{}{
					"owner_id":    operatorID,
					"assigned_at": time.Now(),
					"status":      "ASSIGNED",
				})

			DB.Table("incident_assignments").Create(&map[string]interface{}{
				"incident_id": incidentID,
				"operator_id": operatorID,
				"assigned_at": time.Now(),
				"is_current":  true,
			})
			sendTelegramMessage(chatID, fmt.Sprintf("📝 Incident #%d otomatis ditugaskan ke Anda (%s).", incidentID, operatorID))
		}

		newMsg := map[string]interface{}{
			"incident_id":   incidentID,
			"client_id":     incident.DeviceID,
			"sender":        "OPERATOR",
			"message":       msgContent,
			"thread_type":   "SUPPORT",
			"is_system_msg": false,
			"created_at":    time.Now(),
		}
		if err := DB.Table("chat_messages").Create(&newMsg).Error; err != nil {
			sendTelegramMessage(chatID, "❌ Gagal menyimpan pesan.")
			return
		}

		var lastMsg struct {
			ID int64
		}
		DB.Table("chat_messages").Select("id").Where("incident_id = ? AND message = ?", incidentID, msgContent).Order("id DESC").Limit(1).Scan(&lastMsg)

		liveMsg := LiveThreadMessage{
			MessageID:   uuid.New().String(),
			ID:          lastMsg.ID,
			IncidentID:  incidentID,
			ClientID:    incident.DeviceID,
			SenderType:  "OPERATOR",
			Message:     msgContent,
			Timestamp:   time.Now().Format(time.RFC3339),
			IsSystemMsg: false,
			ThreadType:  "SUPPORT",
			Metadata: map[string]interface{}{
				"source_channel": "telegram",
				"operator_id":    operatorID,
			},
		}
		liveBytes, _ := json.Marshal(liveMsg)
		if natsConn != nil {
			siteID := getIncidentSiteID(DB, int64(incidentID))
			_ = natsConn.Publish(fmt.Sprintf("chat.site.%s.thread.%d", siteID, incidentID), liveBytes)
		}

		sendTelegramMessage(chatID, fmt.Sprintf("✅ Pesan berhasil dikirim ke thread Incident #%d.", incidentID))
		_ = writeAuditLog(DB, "TELEGRAM_REPLY_SENT", operatorID, fmt.Sprintf("incident:%d", incidentID), map[string]interface{}{
			"message_id": lastMsg.ID,
			"channel":    "telegram",
		})

	case "/resolve":
		if opLevelVal < 3 {
			sendTelegramMessage(chatID, "❌ <b>FORBIDDEN:</b> Hanya Operator Level L3 atau ADMIN yang diperbolehkan untuk menyelesaikan (resolve) incident.")
			return
		}
		if len(parts) < 3 {
			sendTelegramMessage(chatID, "❌ <b>ERROR:</b> Format salah. Gunakan: <code>/resolve &lt;incident_id&gt; &lt;summary&gt; [--force]</code>")
			return
		}

		// Check force close flag
		isForce := false
		summaryParts := []string{}
		for _, p := range parts[2:] {
			if p == "--force" {
				isForce = true
			} else {
				summaryParts = append(summaryParts, p)
			}
		}
		summary := strings.Join(summaryParts, " ")

		closeReq := map[string]interface{}{
			"incident_id":        incidentID,
			"actor":              operatorID,
			"resolution_summary": summary,
			"resolution_proof":   "Resolved via Telegram command",
		}
		if isForce {
			closeReq["emergency_skip"] = true
			closeReq["skip_reason"] = "Force closed via Telegram by L3 operator"
		}

		closeBytes, _ := json.Marshal(closeReq)
		if natsConn != nil {
			siteID := getIncidentSiteID(DB, int64(incidentID))
			_ = natsConn.Publish(fmt.Sprintf("incident.site.%s.close.request", siteID), closeBytes)
		}

		if isForce {
			sendTelegramMessage(chatID, fmt.Sprintf("⚡️ Permintaan FORCE CLOSE untuk Incident #%d telah dikirim.", incidentID))
		} else {
			sendTelegramMessage(chatID, fmt.Sprintf("⏳ Permintaan resolusi untuk Incident #%d telah dikirim.", incidentID))
		}
		_ = writeAuditLog(DB, "TELEGRAM_RESOLVE_REQUEST", operatorID, fmt.Sprintf("incident:%d", incidentID), closeReq)

	case "/escalate":
		if opLevelVal < 2 {
			sendTelegramMessage(chatID, "❌ <b>FORBIDDEN:</b> Operator Level L1 tidak memiliki izin untuk mengeskalasi incident. (Minimal L2)")
			return
		}
		if len(parts) < 3 {
			sendTelegramMessage(chatID, "❌ <b>ERROR:</b> Format salah. Gunakan: <code>/escalate &lt;incident_id&gt; &lt;note&gt;</code>")
			return
		}
		note := strings.Join(parts[2:], " ")

		var details struct {
			EscLevel int `gorm:"column:escalation_level"`
		}
		DB.Table("fleet_incidents").Select("escalation_level").Where("incident_id = ?", incidentID).Scan(&details)

		nextLevel := details.EscLevel + 1
		if nextLevel > 3 {
			nextLevel = 3
		}

		escalateReq := map[string]interface{}{
			"incident_id":   incidentID,
			"current_level": details.EscLevel,
			"next_level":    nextLevel,
			"operator_note": note,
		}
		escBytes, _ := json.Marshal(escalateReq)
		if natsConn != nil {
			siteID := getIncidentSiteID(DB, int64(incidentID))
			_ = natsConn.Publish(fmt.Sprintf("incident.site.%s.escalate.request", siteID), escBytes)
		}

		sendTelegramMessage(chatID, fmt.Sprintf("⏳ Permintaan eskalasi ke L%d untuk Incident #%d telah dikirim.", nextLevel, incidentID))
		_ = writeAuditLog(DB, "TELEGRAM_ESCALATION_REQUEST", operatorID, fmt.Sprintf("incident:%d", incidentID), escalateReq)

	case "/assign":
		if opLevelVal < 2 {
			sendTelegramMessage(chatID, "❌ <b>FORBIDDEN:</b> Operator Level L1 tidak memiliki izin untuk menugaskan (assign) incident. (Minimal L2)")
			return
		}
		if len(parts) < 3 {
			sendTelegramMessage(chatID, "❌ <b>ERROR:</b> Format salah. Gunakan: <code>/assign &lt;incident_id&gt; &lt;operator_id&gt;</code>")
			return
		}
		targetOpID := parts[2]

		var targetOp struct {
			OperatorID string `gorm:"column:operator_id"`
		}
		if err := DB.Table("operator_profiles").Select("operator_id").Where("operator_id = ?", targetOpID).First(&targetOp).Error; err != nil {
			sendTelegramMessage(chatID, fmt.Sprintf("❌ <b>ERROR:</b> Operator '%s' tidak ditemukan.", targetOpID))
			return
		}

		DB.Table("incident_assignments").
			Where("incident_id = ? AND is_current = true", incidentID).
			Updates(map[string]interface{}{
				"released_at":    time.Now(),
				"release_reason": fmt.Sprintf("Reassigned by %s via Telegram", operatorID),
				"is_current":     false,
			})

		DB.Table("fleet_incidents").
			Where("incident_id = ?", incidentID).
			Updates(map[string]interface{}{
				"owner_id":    targetOpID,
				"assigned_at": time.Now(),
				"status":      "ASSIGNED",
			})

		DB.Table("incident_assignments").Create(&map[string]interface{}{
			"incident_id": incidentID,
			"operator_id": targetOpID,
			"assigned_at": time.Now(),
			"is_current":  true,
		})

		if natsConn != nil {
			assignEvent := map[string]interface{}{
				"incident_id": incidentID,
				"operator_id": targetOpID,
				"assigned_by": operatorID,
				"timestamp":   time.Now().Format(time.RFC3339),
			}
			b, _ := json.Marshal(assignEvent)
			siteID := getIncidentSiteID(DB, int64(incidentID))
			_ = natsConn.Publish(fmt.Sprintf("operator.assignment.site.%s.created", siteID), b)
		}

		sendTelegramMessage(chatID, fmt.Sprintf("✅ Incident #%d berhasil ditugaskan ke operator '%s'.", incidentID, targetOpID))
		_ = writeAuditLog(DB, "TELEGRAM_ASSIGNMENT_EXECUTED", operatorID, fmt.Sprintf("incident:%d", incidentID), map[string]interface{}{
			"assigned_operator": targetOpID,
		})
	}
}

func downloadAndUploadTelegramFile(fileID string, originalFileName string) (string, error) {
	getFileURL := fmt.Sprintf("%s/getFile?file_id=%s", TelegramApiUrl, fileID)
	resp, err := http.Get(getFileURL)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	var getFileResp struct {
		Ok     bool `json:"ok"`
		Result struct {
			FilePath string `json:"file_path"`
		} `json:"result"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&getFileResp); err != nil || !getFileResp.Ok {
		return "", fmt.Errorf("failed to parse getFile response: %v", err)
	}

	filePath := getFileResp.Result.FilePath
	if filePath == "" {
		return "", fmt.Errorf("file path is empty")
	}

	downloadURL := fmt.Sprintf("https://api.telegram.org/file/bot%s/%s", TelegramBotToken, filePath)
	fileResp, err := http.Get(downloadURL)
	if err != nil {
		return "", err
	}
	defer fileResp.Body.Close()

	bodyBuf := &bytes.Buffer{}
	bodyWriter := multipart.NewWriter(bodyBuf)

	filePart, err := bodyWriter.CreateFormFile("file", originalFileName)
	if err != nil {
		return "", err
	}
	_, err = io.Copy(filePart, fileResp.Body)
	if err != nil {
		return "", err
	}
	bodyWriter.Close()

	uploadURL := "http://localhost:18800/api/chat/upload"
	if getEnv("DB_HOST", "") == "postgres" {
		uploadURL = "http://osi-ingestion-server:18800/api/chat/upload"
	}

	req, err := http.NewRequest("POST", uploadURL, bodyBuf)
	if err != nil {
		return "", err
	}
	req.Header.Set("Content-Type", bodyWriter.FormDataContentType())

	client := &http.Client{Timeout: 30 * time.Second}
	uploadResp, err := client.Do(req)
	if err != nil {
		return "", err
	}
	defer uploadResp.Body.Close()

	if uploadResp.StatusCode != http.StatusOK {
		bodyBytes, _ := io.ReadAll(uploadResp.Body)
		return "", fmt.Errorf("failed to upload file, status: %d, body: %s", uploadResp.StatusCode, string(bodyBytes))
	}

	var uploadResult struct {
		Status         string `json:"status"`
		AttachmentPath string `json:"attachment_path"`
	}
	if err := json.NewDecoder(uploadResp.Body).Decode(&uploadResult); err != nil {
		return "", err
	}

	return uploadResult.AttachmentPath, nil
}

func startPolling() {
	fmt.Println("[BOT] Telegram Bot Listener ACTIVE (Waiting for commands)...")
	lastUpdateID := int64(0)

	// Use a 30-second client timeout
	client := &http.Client{Timeout: 30 * time.Second}

	for {
		// Use a 15-second polling timeout to leave a comfortable 15-second margin before the client timeout
		url := fmt.Sprintf("%s/getUpdates?offset=%d&timeout=15", TelegramApiUrl, lastUpdateID+1)
		resp, err := client.Get(url)
		if err != nil {
			errMsg := err.Error()
			isTimeout := strings.Contains(errMsg, "timeout") || strings.Contains(errMsg, "deadline") || strings.Contains(errMsg, "Client.Timeout")

			if isTimeout {
				// Quietly ignore expected connection idle/timeout events without spamming stdout with errors
				time.Sleep(1 * time.Second)
			} else {
				fmt.Printf("Error polling: %v\n", err)
				time.Sleep(5 * time.Second)
			}
			continue
		}

		bodyBytes, err := io.ReadAll(resp.Body)
		resp.Body.Close()
		if err != nil {
			time.Sleep(5 * time.Second)
			continue
		}

		var updateResp map[string]interface{}
		if err := json.Unmarshal(bodyBytes, &updateResp); err != nil {
			time.Sleep(5 * time.Second)
			continue
		}

		results, ok := updateResp["result"].([]interface{})
		if !ok {
			time.Sleep(5 * time.Second)
			continue
		}

		for _, item := range results {
			update, ok := item.(map[string]interface{})
			if !ok {
				continue
			}

			if upID, ok := update["update_id"].(float64); ok {
				lastUpdateID = int64(upID)
			}

			if callback, ok := update["callback_query"].(map[string]interface{}); ok {
				handleCallbackQuery(callback)
			}
			if msg, ok := update["message"].(map[string]interface{}); ok {
				handleMessageUpdate(msg)
			}
		}
	}
}

func main() {
	initEnv()
	initDatabase()
	initNats()
	startPolling()
}

func cleanSiteID(siteID string) string {
	if siteID == "" {
		return "global"
	}
	s := strings.ToLower(siteID)
	s = strings.ReplaceAll(s, " ", "_")
	s = strings.ReplaceAll(s, ".", "_")
	return s
}

func getIncidentSiteID(db *gorm.DB, incidentID int64) string {
	var siteID string
	db.Table("fleet_incidents").Select("site_id").Where("incident_id = ?", incidentID).Scan(&siteID)
	return cleanSiteID(siteID)
}
