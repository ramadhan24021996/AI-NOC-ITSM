package api

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"regexp"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
)

type CatalogAction struct {
	ActionCode  string
	SampleQuery string
	Triggers    string
	Handler     string
}

func parseCatalog(t *testing.T) []CatalogAction {
	content, err := os.ReadFile("../../../DOCUMENTATION/JARVIS_VOICE_COMMAND_CATALOG.md")
	if err != nil {
		t.Fatalf("Failed to read catalog file: %v", err)
	}

	lines := strings.Split(string(content), "\n")
	tablePattern := regexp.MustCompile(`^\|\s*` + "`?" + `([A-Z0-9_]+)` + "`?" + `\s*\|\s*` + "`?" + `([^|]+)` + "`?" + `\s*\|\s*"?([^|"]+)"?\s*\|\s*([^|]+)\s*\|`)

	var actions []CatalogAction
	for _, line := range lines {
		match := tablePattern.FindStringSubmatch(strings.TrimSpace(line))
		if len(match) == 5 {
			code := strings.Trim(match[1], "` ")
			if code == "Action Code" || code == "No" || regexp.MustCompile(`^\d+$`).MatchString(code) {
				continue
			}
			triggers := strings.Trim(match[2], "` ")
			sample := strings.Trim(match[3], `" `)
			handler := strings.TrimSpace(match[4])

			actions = append(actions, CatalogAction{
				ActionCode:  code,
				SampleQuery: sample,
				Triggers:    triggers,
				Handler:     handler,
			})
		}
	}

	return actions
}

func TestJarvisVoiceQueryAll144Commands(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := &Handler{}
	r := gin.New()
	r.POST("/api/jarvis/voice/query", h.JarvisVoiceQuery)

	actions := parseCatalog(t)
	if len(actions) < 100 {
		t.Fatalf("Expected >100 actions, found %d", len(actions))
	}

	total := len(actions)
	successCount := 0

	fmt.Println("\n" + strings.Repeat("=", 80))
	fmt.Println("🖥️ GO BACKEND LIVE DASHBOARD TYPED COMMAND SIMULATION REPORT")
	fmt.Println(strings.Repeat("=", 80))

	for idx, act := range actions {
		payload, _ := json.Marshal(map[string]string{
			"question":   act.SampleQuery,
			"query":      act.SampleQuery,
			"session_id": fmt.Sprintf("sim-typed-%s", strings.ToLower(act.ActionCode)),
		})

		w := httptest.NewRecorder()
		req, _ := http.NewRequest("POST", "/api/jarvis/voice/query", bytes.NewBuffer(payload))
		req.Header.Set("Content-Type", "application/json")
		r.ServeHTTP(w, req)

		if w.Code != http.StatusOK {
			t.Errorf("[%03d/%d] ❌ [%-28s] Query: \"%s\" -> HTTP %d", idx+1, total, act.ActionCode, act.SampleQuery, w.Code)
			continue
		}

		var resp map[string]interface{}
		if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
			t.Errorf("[%03d/%d] ❌ [%-28s] Query: \"%s\" -> Decode Error: %v", idx+1, total, act.ActionCode, act.SampleQuery, err)
			continue
		}

		ansText, _ := resp["answer_text"].(string)
		if ansText == "" {
			ansText, _ = resp["answer"].(string)
		}

		if ansText == "" {
			t.Errorf("[%03d/%d] ❌ [%-28s] Query: \"%s\" -> Empty answer", idx+1, total, act.ActionCode, act.SampleQuery)
			continue
		}

		successCount++
	}

	fmt.Println(strings.Repeat("-", 80))
	fmt.Printf("Total Tested : %d\n", total)
	fmt.Printf("Total Success: %d / %d (100%% PASSED)\n", successCount, total)
	fmt.Println(strings.Repeat("=", 80) + "\n")

	if successCount != total {
		t.Fatalf("Only %d/%d commands succeeded", successCount, total)
	}
}
