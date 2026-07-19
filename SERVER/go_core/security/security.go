package security

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"time"

	"github.com/fernet/fernet-go"
)

// Custom error definitions
var (
	ErrDecryptionError        = errors.New("decryption failed on ciphertext")
	ErrKeyFingerprintMismatch = errors.New("key fingerprint mismatch")
	ErrCatastrophicKeyLoss    = errors.New("catastrophic key loss: initialized system has no keys")
)

// SecurityManager manages Fernet encryption and decryption.
type SecurityManager struct {
	keyFile         string
	backupKeyFile   string
	initializedFile string
	fingerprintFile string
	key             []byte
	fernetKeys      []*fernet.Key
}

var globalSM *SecurityManager

// GetSecurityManager returns or initializes the global SecurityManager.
func GetSecurityManager() (*SecurityManager, error) {
	if globalSM != nil {
		return globalSM, nil
	}

	// Try to locate project root dynamically.
	_, filename, _, _ := runtime.Caller(0)
	// security.go is in SERVER/go_core/security/
	// We want projectRoot to be the SERVER directory:
	projectRoot := filepath.Dir(filepath.Dir(filepath.Dir(filename)))
	if projectRoot == "." || projectRoot == "" {
		projectRoot = "."
	}

	keyFile := filepath.Join(projectRoot, ".key")
	fingerprintFile := filepath.Join(projectRoot, ".key_fingerprint")
	initializedFile := filepath.Join(projectRoot, ".initialized")

	homeDir, _ := os.UserHomeDir()
	backupKeyFile := filepath.Join(homeDir, ".osi_security_key")

	sm := &SecurityManager{
		keyFile:         keyFile,
		backupKeyFile:   backupKeyFile,
		initializedFile: initializedFile,
		fingerprintFile: fingerprintFile,
	}

	key, err := sm.loadOrVerifyKey()
	if err != nil {
		return nil, err
	}
	sm.key = key

	// Parse Fernet Key
	parsedKey, err := fernet.DecodeKey(string(key))
	if err != nil {
		return nil, fmt.Errorf("failed to parse Fernet key: %w", err)
	}
	sm.fernetKeys = []*fernet.Key{parsedKey}

	globalSM = sm
	return sm, nil
}

// GetKey returns the raw security key bytes.
func (sm *SecurityManager) GetKey() []byte {
	return sm.key
}

func (sm *SecurityManager) getFingerprint(keyBytes []byte) string {
	hash := sha256.Sum256(keyBytes)
	return hex.EncodeToString(hash[:])
}

func (sm *SecurityManager) saveKeyToFile(path string, keyBytes []byte) error {
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}

	// Write key file
	if err := os.WriteFile(path, keyBytes, 0600); err != nil {
		return err
	}

	return nil
}

func (sm *SecurityManager) verifyFingerprintOrSave(keyBytes []byte) error {
	fp := sm.getFingerprint(keyBytes)
	if _, err := os.Stat(sm.fingerprintFile); err == nil {
		storedBytes, err := os.ReadFile(sm.fingerprintFile)
		if err != nil {
			return err
		}
		storedFP := strings.TrimSpace(string(storedBytes))
		if storedFP != fp {
			return fmt.Errorf("%w: key fp %s, expected %s", ErrKeyFingerprintMismatch, fp, storedFP)
		}
		return nil
	}

	// Save new fingerprint
	return sm.saveKeyToFile(sm.fingerprintFile, []byte(fp))
}

func (sm *SecurityManager) cleanKey(keyBytes []byte) []byte {
	cleaned := strings.TrimSpace(string(keyBytes))
	cleaned = strings.Trim(cleaned, `"'`)
	return []byte(cleaned)
}

func (sm *SecurityManager) loadOrVerifyKey() ([]byte, error) {
	// 1. Env check
	if envKey := os.Getenv("OSI_SECURITY_KEY"); envKey != "" {
		keyBytes := []byte(envKey)
		if err := sm.verifyFingerprintOrSave(keyBytes); err == nil {
			_ = sm.saveKeyToFile(sm.keyFile, keyBytes)
			_ = sm.saveKeyToFile(sm.backupKeyFile, keyBytes)
			_ = sm.saveKeyToFile(sm.initializedFile, []byte("1"))
			return sm.cleanKey(keyBytes), nil
		}
	}

	// 2. Primary key check
	if _, err := os.Stat(sm.keyFile); err == nil {
		keyBytes, err := os.ReadFile(sm.keyFile)
		if err == nil {
			// Verify fingerprint on RAW key bytes (including quotes)
			if err := sm.verifyFingerprintOrSave(keyBytes); err == nil {
				_ = sm.saveKeyToFile(sm.backupKeyFile, keyBytes)
				return sm.cleanKey(keyBytes), nil
			}
		}
	}

	// 3. Backup key check
	if _, err := os.Stat(sm.backupKeyFile); err == nil {
		keyBytes, err := os.ReadFile(sm.backupKeyFile)
		if err == nil {
			// Verify fingerprint on RAW key bytes (including quotes)
			if err := sm.verifyFingerprintOrSave(keyBytes); err == nil {
				_ = sm.saveKeyToFile(sm.keyFile, keyBytes)
				return sm.cleanKey(keyBytes), nil
			}
		}
	}

	// 4. Initialized marker check -> Catastrophic loss
	if _, err := os.Stat(sm.initializedFile); err == nil {
		return nil, ErrCatastrophicKeyLoss
	}

	// 5. New Installation
	// Generate random 32-byte key for Fernet
	randBytes := make([]byte, 32)
	if _, err := rand.Read(randBytes); err != nil {
		return nil, err
	}
	newKeyStr := base64.URLEncoding.EncodeToString(randBytes)
	// We save without quotes for new installs, but Python might have written it with quotes.
	// Since we verify fingerprint on whatever we save, this is fine.
	keyBytes := []byte(newKeyStr)
	if err := sm.saveKeyToFile(sm.keyFile, keyBytes); err != nil {
		return nil, err
	}
	_ = sm.saveKeyToFile(sm.backupKeyFile, keyBytes)
	_ = sm.verifyFingerprintOrSave(keyBytes)
	_ = sm.saveKeyToFile(sm.initializedFile, []byte("1"))

	return sm.cleanKey(keyBytes), nil
}

// Encrypt encrypts a plaintext string to a Fernet token.
func (sm *SecurityManager) Encrypt(plainText string) (string, error) {
	if plainText == "" {
		return "", nil
	}
	token, err := fernet.EncryptAndSign([]byte(plainText), sm.fernetKeys[0])
	if err != nil {
		return "", err
	}
	return string(token), nil
}

// Decrypt decrypts a Fernet token back to plaintext.
func (sm *SecurityManager) Decrypt(encryptedText string) (string, error) {
	if encryptedText == "" {
		return "", nil
	}

	isFernetToken := strings.HasPrefix(encryptedText, "gAAAAA")

	// Decrypt
	msg := fernet.VerifyAndDecrypt([]byte(encryptedText), time.Duration(0), sm.fernetKeys)
	if msg == nil {
		if isFernetToken {
			return "", fmt.Errorf("%w: failed to verify/decrypt Fernet token", ErrDecryptionError)
		}
		// Fallback for plaintext non-ciphertext
		return encryptedText, nil
	}

	return string(msg), nil
}

// DataMasker redacts PII data (IP, Email, User path, Auth tokens, Passwords).
type DataMasker struct {
	ipRegex       *regexp.Regexp
	emailRegex    *regexp.Regexp
	pathRegex     *regexp.Regexp
	tokenRegex    *regexp.Regexp
	passwordRegex *regexp.Regexp
}

var globalMasker = &DataMasker{
	ipRegex:       regexp.MustCompile(`\b(?:\d{1,3}\.){3}\d{1,3}\b`),
	emailRegex:    regexp.MustCompile(`[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+`),
	pathRegex:     regexp.MustCompile(`(?i)[C-Z]:\\Users\\[^\s]+`),
	tokenRegex:    regexp.MustCompile(`(?i)Bearer\s+[A-Za-z0-9\-\._~+\/]+`),
	passwordRegex: regexp.MustCompile(`(?i)(password|passwd|pwd)\s*[:=]\s*[^\s]+`),
}

// Redact sanitizes a string from PII info.
func (dm *DataMasker) Redact(text string) string {
	if text == "" {
		return ""
	}
	text = dm.ipRegex.ReplaceAllString(text, "[IP_REDACTED]")
	text = dm.emailRegex.ReplaceAllString(text, "[EMAIL_REDACTED]")
	text = dm.pathRegex.ReplaceAllString(text, "[PATH_REDACTED]")
	text = dm.tokenRegex.ReplaceAllString(text, "Bearer [TOKEN_REDACTED]")
	text = dm.passwordRegex.ReplaceAllString(text, "$1: [PASSWORD_REDACTED]")
	return text
}

// Masker exposes the global DataMasker instance.
func Masker() *DataMasker {
	return globalMasker
}
