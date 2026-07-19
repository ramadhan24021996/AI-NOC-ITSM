package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestRunDetectionSchema(t *testing.T) {
	res := runDetection()
	t.Logf("Detection timestamp: %v", res.Timestamp)
	t.Logf("AnyDesk status: installed=%v, path=%s", res.AnyDesk.Installed, res.AnyDesk.ExePath)
	t.Logf("RustDesk status: installed=%v, path=%s", res.RustDesk.Installed, res.RustDesk.ExePath)
}

func TestCacheSerialization(t *testing.T) {
	tempDir, err := os.MkdirTemp("", "launcher-test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	cacheFile := filepath.Join(tempDir, "test_cache.json")
	res := runDetection()

	err = saveCache(cacheFile, res)
	if err != nil {
		t.Fatalf("Failed to save cache: %v", err)
	}

	loaded, err := loadCache(cacheFile)
	if err != nil {
		t.Fatalf("Failed to load cache: %v", err)
	}

	if loaded == nil {
		t.Fatal("Loaded cache was nil")
	}

	if loaded.CacheTTL != res.CacheTTL {
		t.Errorf("Mismatch in CacheTTL: expected %d, got %d", res.CacheTTL, loaded.CacheTTL)
	}
}

func TestRouterHealth(t *testing.T) {
	gin.SetMode(gin.TestMode)
	r := gin.New()

	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status": "healthy",
		})
	})

	req, _ := http.NewRequest("GET", "/health", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("Expected status 200, got %d", w.Code)
	}

	var resp map[string]interface{}
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	if err != nil {
		t.Fatalf("Failed to parse response body: %v", err)
	}

	if resp["status"] != "healthy" {
		t.Errorf("Expected status 'healthy', got '%v'", resp["status"])
	}
}
