package security

import (
	"testing"
)

func TestSecurityManagerDecryptPostgres(t *testing.T) {
	// Initialize security manager
	sm, err := GetSecurityManager()
	if err != nil {
		t.Fatalf("Failed to get security manager: %v", err)
	}

	t.Logf("Project KeyFile Path: %s", sm.keyFile)
	t.Logf("Loaded Key string: '%s'", string(sm.key))

	// Ciphertext from config.py: DB_USER
	encUser := "gAAAAABqBKK7az-y_l5fNA2vSgnwxIN0eaZWvqXhTwjWTXhGxXtzff4_iHYcL1u5VrmlwwnSxvwWNnlscwcn0Ph81c7PUGS9Ag=="

	// Decrypt
	decUser, err := sm.Decrypt(encUser)
	if err != nil {
		t.Fatalf("Failed to decrypt: %v", err)
	}

	t.Logf("Decrypted user: '%s'", decUser)

	expected := "postgres"
	if decUser != expected {
		t.Errorf("Decrypted user mismatch. Expected: '%s', Got: '%s'", expected, decUser)
	} else {
		t.Logf("Success! Decrypted matches expected '%s'", expected)
	}
}

func TestSecurityManagerEncryptDecryptRoundtrip(t *testing.T) {
	sm, err := GetSecurityManager()
	if err != nil {
		t.Fatalf("Failed to get security manager: %v", err)
	}

	testData := "This is a secret message 123!"
	enc, err := sm.Encrypt(testData)
	if err != nil {
		t.Fatalf("Failed to encrypt: %v", err)
	}

	dec, err := sm.Decrypt(enc)
	if err != nil {
		t.Fatalf("Failed to decrypt: %v", err)
	}

	if dec != testData {
		t.Errorf("Mismatch in roundtrip. Expected: '%s', Got: '%s'", testData, dec)
	}
}

func TestDataMasker(t *testing.T) {
	masker := Masker()

	input := "User logged in with password=secret123 on IP 192.168.1.50 and email user@test.com. Path: C:\\Users\\Administrator\\Desktop"
	expected := "User logged in with password: [PASSWORD_REDACTED] on IP [IP_REDACTED] and email [EMAIL_REDACTED] Path: [PATH_REDACTED]"

	redacted := masker.Redact(input)
	if redacted != expected {
		t.Errorf("Data masking failure.\nGot:  '%s'\nWant: '%s'", redacted, expected)
	}
}
