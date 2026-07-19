package ingestion

import (
	"bytes"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strconv"
	"time"

	"go_incident_analysis/SERVER/go_core/database"
)

// TelegramService handles notifications to the NOC via Telegram relay.
type TelegramService struct{}

var DefaultTelegramService = &TelegramService{}

// SendIncidentAlert sends a formatted incident alert with optional screenshot and a "Chat User" button.
func (s *TelegramService) SendIncidentAlert(clientID string, pcName string, incidentID uint, title string, severity string, analysis string, recommendation string, screenshotPath string) (int64, error) {
	relayURL := "http://localhost:9998/relay/telegram/send"
	if os.Getenv("DB_HOST") == "postgres" {
		relayURL = "http://osi-secure-relay:9998/relay/telegram/send"
	}

	text := fmt.Sprintf(
		"🧠 <b>Analisa Masalah:</b>\n%s\n\n"+
			"🔧 <b>Cara Menangani:</b>\n%s",
		analysis, recommendation,
	)

	// 2. Prepare photo/screenshot if available
	var photoB64 string
	if screenshotPath != "" {
		// Read file from local disk. In docker/local, the uploaded files are saved in uploads/chat/
		// Relative path: uploads/chat/xxx.jpg. Let's make it absolute.
		absPath := screenshotPath
		if !os.IsPathSeparator(screenshotPath[0]) {
			absPath = "./" + screenshotPath
		}
		imgData, err := os.ReadFile(absPath)
		if err == nil {
			photoB64 = base64.StdEncoding.EncodeToString(imgData)
		} else {
			fmt.Printf("[TELEGRAM ERROR] Failed to read screenshot file %s: %v\n", absPath, err)
		}
	}

	// 3. Construct the inline keyboard reply markup
	markup := map[string]interface{}{
		"inline_keyboard": [][]map[string]string{
			{
				{
					"text":          "💬 Chat User",
					"callback_data": "chat_user_" + clientID,
				},
			},
		},
	}
	markupBytes, _ := json.Marshal(markup)
	replyMarkupStr := string(markupBytes)

	// 4. Build secure relay request payload
	payload := map[string]interface{}{
		"message":      text,
		"photo_b64":    photoB64,
		"reply_markup": replyMarkupStr,
	}
	payloadBytes, err := json.Marshal(payload)
	if err != nil {
		return 0, err
	}

	// 5. Calculate HMAC signature
	ts := strconv.FormatInt(time.Now().Unix(), 10)
	msgToSign := append([]byte(ts), payloadBytes...)

	secret := []byte("EnterpriseSecureRelay2026_HMAC_KEY_123")
	if envSecret := os.Getenv("HMAC_SECRET"); envSecret != "" {
		secret = []byte(envSecret)
	}

	mac := hmac.New(sha256.New, secret)
	mac.Write(msgToSign)
	sig := hex.EncodeToString(mac.Sum(nil))

	// 6. POST request to secure relay
	req, err := http.NewRequest("POST", relayURL, bytes.NewBuffer(payloadBytes))
	if err != nil {
		return 0, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Signature", sig)
	req.Header.Set("X-Timestamp", ts)

	client := &http.Client{Timeout: 15 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return 0, err
	}
	defer resp.Body.Close()

	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return 0, err
	}

	if resp.StatusCode != http.StatusOK {
		return 0, fmt.Errorf("relay api error: status=%d body=%s", resp.StatusCode, string(bodyBytes))
	}

	var respMap map[string]interface{}
	if err := json.Unmarshal(bodyBytes, &respMap); err != nil {
		return 0, err
	}

	// 7. Extract returned Telegram message ID and save mapping
	var telegramMsgID int64
	if tgMsgIDVal, ok := respMap["message_id"]; ok {
		if floatVal, ok := tgMsgIDVal.(float64); ok {
			telegramMsgID = int64(floatVal)
		} else if intVal, ok := tgMsgIDVal.(int64); ok {
			telegramMsgID = intVal
		}
	}

	if telegramMsgID > 0 {
		mapping := database.TelegramChatMapping{
			TelegramMessageID: telegramMsgID,
			ClientID:          clientID,
			ChatMessageID:     0, // Associated with incident notification
			CreatedAt:         time.Now(),
		}
		database.DB.Create(&mapping)
		fmt.Printf("[TELEGRAM] Created chat mapping for TelegramMessageID %d -> clientID %s\n", telegramMsgID, clientID)
	}

	return telegramMsgID, nil
}
