package security

import (
	"crypto/hmac"
	"crypto/sha256"
	"crypto/tls"
	"crypto/x509"
	"encoding/hex"
	"errors"
	"fmt"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
)

// CertReloader dynamically reloads TLS certificates without service downtime (Fase 14)
type CertReloader struct {
	mu       sync.RWMutex
	certPath string
	keyPath  string
	cert     *tls.Certificate
	modTime  time.Time
}

// NewCertReloader creates a new certificate reloader that watches files on request
func NewCertReloader(certPath, keyPath string) (*CertReloader, error) {
	reloader := &CertReloader{
		certPath: certPath,
		keyPath:  keyPath,
	}
	if err := reloader.reload(); err != nil {
		return nil, err
	}
	return reloader, nil
}

func (cr *CertReloader) reload() error {
	info, err := os.Stat(cr.certPath)
	if err != nil {
		return err
	}

	cr.mu.Lock()
	defer cr.mu.Unlock()

	// If file has not changed, do nothing
	if info.ModTime().Equal(cr.modTime) && cr.cert != nil {
		return nil
	}

	cert, err := tls.LoadX509KeyPair(cr.certPath, cr.keyPath)
	if err != nil {
		return fmt.Errorf("failed to load x509 key pair: %w", err)
	}

	cr.cert = &cert
	cr.modTime = info.ModTime()
	return nil
}

// GetCertificate implements tls.Config.GetCertificate
func (cr *CertReloader) GetCertificate(clientHello *tls.ClientHelloInfo) (*tls.Certificate, error) {
	// Try reloading if cert modified
	_ = cr.reload()

	cr.mu.RLock()
	defer cr.mu.RUnlock()
	return cr.cert, nil
}

// GetServerTLSConfig returns a tls.Config supporting mTLS and dynamic certificate reloading
func GetServerTLSConfig(certPath, keyPath, caPath string) (*tls.Config, error) {
	reloader, err := NewCertReloader(certPath, keyPath)
	if err != nil {
		return nil, err
	}

	tlsConfig := &tls.Config{
		GetCertificate: reloader.GetCertificate,
		MinVersion:     tls.VersionTLS12,
		CipherSuites: []uint16{
			tls.TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,
			tls.TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,
			tls.TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256,
			tls.TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256,
		},
	}

	// Add client verification for mTLS if CA cert is provided
	if caPath != "" {
		caCert, err := os.ReadFile(caPath)
		if err != nil {
			return nil, fmt.Errorf("failed to read client CA certificate: %w", err)
		}
		caCertPool := x509.NewCertPool()
		if !caCertPool.AppendCertsFromPEM(caCert) {
			return nil, errors.New("failed to parse client CA certificate")
		}
		tlsConfig.ClientCAs = caCertPool
		tlsConfig.ClientAuth = tls.RequireAndVerifyClientCert
	}

	return tlsConfig, nil
}

// GetClientTLSConfig returns a tls.Config for client agents to verify servers with CA
func GetClientTLSConfig(caPath, certPath, keyPath string) (*tls.Config, error) {
	tlsConfig := &tls.Config{
		MinVersion: tls.VersionTLS12,
	}

	if caPath != "" {
		caCert, err := os.ReadFile(caPath)
		if err != nil {
			return nil, fmt.Errorf("failed to read CA certificate: %w", err)
		}
		caCertPool := x509.NewCertPool()
		if !caCertPool.AppendCertsFromPEM(caCert) {
			return nil, errors.New("failed to parse CA certificate")
		}
		tlsConfig.RootCAs = caCertPool
	}

	if certPath != "" && keyPath != "" {
		cert, err := tls.LoadX509KeyPair(certPath, keyPath)
		if err != nil {
			return nil, fmt.Errorf("failed to load client key pair: %w", err)
		}
		tlsConfig.Certificates = []tls.Certificate{cert}
	}

	return tlsConfig, nil
}

// SecurityHeadersMiddleware injects secure HTTP headers to comply with Phase 14
func SecurityHeadersMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Writer.Header().Set("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self' ws: wss: http://127.0.0.1:44600 http://localhost:44600;")
		c.Writer.Header().Set("X-Content-Type-Options", "nosniff")
		c.Writer.Header().Set("X-Frame-Options", "SAMEORIGIN")
		c.Writer.Header().Set("X-XSS-Protection", "1; mode=block")
		c.Writer.Header().Set("Referrer-Policy", "strict-origin-when-cross-origin")
		c.Writer.Header().Set("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload")
		c.Next()
	}
}

// WAFMiddleware screens requests for typical SQL injection and Path Traversal indicators
func WAFMiddleware() gin.HandlerFunc {
	badPatterns := []string{
		"union select",
		"select * from",
		"insert into",
		"delete from",
		"drop table",
		"' or 1=1",
		"\" or 1=1",
		"' or '1'='1",
		"\" or \"1\"=\"1",
		"../",
		"..\\",
		"/etc/passwd",
		"boot.ini",
	}

	return func(c *gin.Context) {
		// Check URL path
		path := strings.ToLower(c.Request.URL.Path)
		for _, p := range badPatterns {
			if strings.Contains(path, p) {
				c.JSON(http.StatusBadRequest, gin.H{"error": "Security violation", "message": "Malicious payload detected in URL"})
				c.Abort()
				return
			}
		}

		// Check Query Parameters
		for _, val := range c.Request.URL.Query() {
			for _, v := range val {
				vLower := strings.ToLower(v)
				for _, p := range badPatterns {
					if strings.Contains(vLower, p) {
						c.JSON(http.StatusBadRequest, gin.H{"error": "Security violation", "message": "Malicious payload detected in parameters"})
						c.Abort()
						return
					}
				}
			}
		}
		c.Next()
	}
}

// SignAuditPayload signs an audit log entry with HMAC-SHA256 using the global security key
func SignAuditPayload(payload string) (string, error) {
	sm, err := GetSecurityManager()
	if err != nil {
		return "", err
	}
	key := sm.GetKey()
	mac := hmac.New(sha256.New, key)
	mac.Write([]byte(payload))
	return hex.EncodeToString(mac.Sum(nil)), nil
}

// VerifyAuditPayload verifies if the signature matches the payload
func VerifyAuditPayload(payload, signature string) (bool, error) {
	expectedSign, err := SignAuditPayload(payload)
	if err != nil {
		return false, err
	}
	return hmac.Equal([]byte(expectedSign), []byte(signature)), nil
}

// WrapHTTPHandler applies WAF and Security Headers to a standard http.Handler
func WrapHTTPHandler(handler http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Basic WAF
		badPatterns := []string{
			"union select", "select * from", "insert into", "delete from", "drop table",
			"' or 1=1", "\" or 1=1", "' or '1'='1", "\" or \"1\"=\"1",
			"../", "..\\", "/etc/passwd", "boot.ini",
		}
		path := strings.ToLower(r.URL.Path)
		for _, p := range badPatterns {
			if strings.Contains(path, p) {
				http.Error(w, "Security violation: Malicious payload detected", http.StatusBadRequest)
				return
			}
		}
		for _, val := range r.URL.Query() {
			for _, v := range val {
				vLower := strings.ToLower(v)
				for _, p := range badPatterns {
					if strings.Contains(vLower, p) {
						http.Error(w, "Security violation: Malicious payload detected", http.StatusBadRequest)
						return
					}
				}
			}
		}

		// Security Headers
		w.Header().Set("Content-Security-Policy", "default-src 'self';")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("X-Frame-Options", "SAMEORIGIN")
		w.Header().Set("X-XSS-Protection", "1; mode=block")
		w.Header().Set("Referrer-Policy", "strict-origin-when-cross-origin")
		w.Header().Set("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload")

		handler.ServeHTTP(w, r)
	})
}

// IPRateLimiter manages request rates per IP address (Fase 14 API Rate Protection)
type IPRateLimiter struct {
	ips map[string]int
	mu  sync.Mutex
}

func NewIPRateLimiter() *IPRateLimiter {
	return &IPRateLimiter{ips: make(map[string]int)}
}

func (rl *IPRateLimiter) Limit() gin.HandlerFunc {
	// Clean map periodically in background
	go func() {
		for {
			time.Sleep(1 * time.Minute)
			rl.mu.Lock()
			rl.ips = make(map[string]int)
			rl.mu.Unlock()
		}
	}()

	return func(c *gin.Context) {
		ip := c.ClientIP()
		rl.mu.Lock()
		rl.ips[ip]++
		count := rl.ips[ip]
		rl.mu.Unlock()

		if count > 100000 { // Max 100000 requests per minute to avoid accidental UI blocks
			c.JSON(http.StatusTooManyRequests, gin.H{"error": "Too many requests", "message": "Rate limit exceeded"})
			c.Abort()
			return
		}
		c.Next()
	}
}
