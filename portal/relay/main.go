package main

import (
	"bytes"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"mime/multipart"
	"net/http"
	"os"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
)

var (
	TelegramBotToken string
	TelegramChatID   string
	HMACSecret       []byte
)

type RelayPayload struct {
	Message     string `json:"message"`
	PhotoB64    string `json:"photo_b64,omitempty"`
	ReplyMarkup string `json:"reply_markup,omitempty"`
}

func initEnv() {
	TelegramBotToken = getEnv("TELEGRAM_BOT_TOKEN", "8685494518:AAHvhd8K3nmgCDy23dHTXsj9K0jSV0YT5lU")
	TelegramChatID = getEnv("TELEGRAM_CHAT_ID", "7794987703")
	HMACSecret = []byte(getEnv("HMAC_SECRET", "EnterpriseSecureRelay2026_HMAC_KEY_123"))
}

func getEnv(key, fallback string) string {
	if value, exists := os.LookupEnv(key); exists {
		return value
	}
	return fallback
}

func verifySignature(c *gin.Context, body []byte) (bool, string) {
	sig := c.GetHeader("X-Signature")
	ts := c.GetHeader("X-Timestamp")

	if sig == "" || ts == "" {
		return false, "Missing HMAC Headers"
	}

	tsInt, err := strconv.ParseInt(ts, 10, 64)
	if err != nil {
		return false, "Invalid Timestamp Format"
	}

	// 24-hour clock drift tolerance
	now := time.Now().Unix()
	if math.Abs(float64(now-tsInt)) > 86400 {
		return false, "Request Timestamp Expired"
	}

	// Calculate signature
	msgToSign := append([]byte(ts), body...)
	mac := hmac.New(sha256.New, HMACSecret)
	mac.Write(msgToSign)
	expectedMAC := hex.EncodeToString(mac.Sum(nil))

	if !hmac.Equal([]byte(expectedMAC), []byte(sig)) {
		return false, "Invalid Signature"
	}

	return true, "OK"
}

func sendTelegramTextMessage(text string, replyMarkup string) (int64, error) {
	url := fmt.Sprintf("https://api.telegram.org/bot%s/sendMessage", TelegramBotToken)
	payload := map[string]interface{}{
		"chat_id":    TelegramChatID,
		"text":       text,
		"parse_mode": "HTML",
	}

	if replyMarkup != "" {
		var markup map[string]interface{}
		if err := json.Unmarshal([]byte(replyMarkup), &markup); err == nil {
			payload["reply_markup"] = markup
		}
	}

	jsonBytes, err := json.Marshal(payload)
	if err != nil {
		return 0, err
	}

	resp, err := http.Post(url, "application/json", bytes.NewBuffer(jsonBytes))
	if err != nil {
		return 0, err
	}
	defer resp.Body.Close()

	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return 0, err
	}

	if resp.StatusCode != http.StatusOK {
		return 0, fmt.Errorf("telegram api error: status=%d body=%s", resp.StatusCode, string(bodyBytes))
	}

	var tgResp struct {
		Ok     bool `json:"ok"`
		Result struct {
			MessageID int64 `json:"message_id"`
		} `json:"result"`
	}
	if err := json.Unmarshal(bodyBytes, &tgResp); err != nil {
		return 0, err
	}
	return tgResp.Result.MessageID, nil
}

func sendTelegramPhotoMessage(photoBytes []byte, caption string, replyMarkup string) (int64, error) {
	url := fmt.Sprintf("https://api.telegram.org/bot%s/sendPhoto", TelegramBotToken)

	bodyBuf := &bytes.Buffer{}
	bodyWriter := multipart.NewWriter(bodyBuf)

	// chat_id field
	err := bodyWriter.WriteField("chat_id", TelegramChatID)
	if err != nil {
		return 0, err
	}

	// caption field
	err = bodyWriter.WriteField("caption", caption)
	if err != nil {
		return 0, err
	}

	// parse_mode field
	err = bodyWriter.WriteField("parse_mode", "HTML")
	if err != nil {
		return 0, err
	}

	// reply_markup field
	if replyMarkup != "" {
		err = bodyWriter.WriteField("reply_markup", replyMarkup)
		if err != nil {
			return 0, err
		}
	}

	// photo file field
	fileWriter, err := bodyWriter.CreateFormFile("photo", "screenshot.png")
	if err != nil {
		return 0, err
	}

	_, err = fileWriter.Write(photoBytes)
	if err != nil {
		return 0, err
	}

	bodyWriter.Close()

	req, err := http.NewRequest("POST", url, bodyBuf)
	if err != nil {
		return 0, err
	}
	req.Header.Set("Content-Type", bodyWriter.FormDataContentType())

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
		return 0, fmt.Errorf("telegram api error: status=%d body=%s", resp.StatusCode, string(bodyBytes))
	}

	var tgResp struct {
		Ok     bool `json:"ok"`
		Result struct {
			MessageID int64 `json:"message_id"`
		} `json:"result"`
	}
	if err := json.Unmarshal(bodyBytes, &tgResp); err != nil {
		return 0, err
	}
	return tgResp.Result.MessageID, nil
}

func main() {
	initEnv()
	gin.SetMode(gin.ReleaseMode)

	r := gin.New()
	r.Use(gin.Logger(), gin.Recovery())

	r.POST("/relay/telegram/send", func(c *gin.Context) {
		// Read raw body for HMAC signature verification
		bodyBytes, err := io.ReadAll(c.Request.Body)
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "error": "Failed to read request body"})
			return
		}

		isValid, errMsg := verifySignature(c, bodyBytes)
		if !isValid {
			fmt.Printf("[SECURITY ALERT] Permintaan tidak sah ditolak: %s\n", errMsg)
			c.JSON(http.StatusUnauthorized, gin.H{"success": false, "error": errMsg})
			return
		}

		// Parse bodyBytes to Payload struct
		var payload RelayPayload
		if err := json.Unmarshal(bodyBytes, &payload); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "error": "Invalid JSON structure"})
			return
		}

		if payload.Message == "" {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "error": "Empty payload"})
			return
		}

		var messageID int64

		// Process Telegram notification
		if payload.PhotoB64 != "" {
			photoBytes, err := base64.StdEncoding.DecodeString(payload.PhotoB64)
			if err != nil {
				// Try raw decoding if it fails
				photoBytes, err = base64.RawStdEncoding.DecodeString(payload.PhotoB64)
			}
			if err != nil {
				c.JSON(http.StatusBadRequest, gin.H{"success": false, "error": "Invalid base64 photo data"})
				return
			}

			// Telegram caption limit is 1024 characters
			if len(payload.Message) > 1000 {
				// Send message text first
				if id, err := sendTelegramTextMessage(payload.Message, payload.ReplyMarkup); err != nil {
					fmt.Printf("[FAIL] Gagal kirim teks Telegram: %v\n", err)
				} else {
					messageID = id
				}
				// Send photo with generic caption
				caption := "📸 <b>Screenshot Lampiran Terkait</b> (Detail insiden terlampir di atas)"
				if _, err := sendTelegramPhotoMessage(photoBytes, caption, ""); err != nil {
					fmt.Printf("[FAIL] Kegagalan dari API Telegram: %v\n", err)
					c.JSON(http.StatusBadGateway, gin.H{"success": false, "error": err.Error()})
					return
				}
			} else {
				if id, err := sendTelegramPhotoMessage(photoBytes, payload.Message, payload.ReplyMarkup); err != nil {
					fmt.Printf("[FAIL] Kegagalan dari API Telegram: %v\n", err)
					c.JSON(http.StatusBadGateway, gin.H{"success": false, "error": err.Error()})
					return
				} else {
					messageID = id
				}
			}
		} else {
			// Text only message
			if id, err := sendTelegramTextMessage(payload.Message, payload.ReplyMarkup); err != nil {
				fmt.Printf("[FAIL] Kegagalan dari API Telegram: %v\n", err)
				c.JSON(http.StatusBadGateway, gin.H{"success": false, "error": err.Error()})
				return
			} else {
				messageID = id
			}
		}

		fmt.Println("[OK] Relay berhasil mengirim ke Telegram.")
		c.JSON(http.StatusOK, gin.H{"success": true, "message_id": messageID})
	})

	fmt.Println("==================================================")
	fmt.Println("[SECURE] SECURE RELAY API (EDGE WORKER) STARTED (Go)")
	fmt.Println("[SECURE] Zero-Trust HMAC Endpoint Protection: ACTIVE")
	fmt.Println("==================================================")

	port := getEnv("RELAY_PORT", "9998")
	r.Run(":" + port)
}
