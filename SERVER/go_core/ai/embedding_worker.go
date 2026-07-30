package ai

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"

	"gorm.io/gorm"
)

// EmbeddingWorker runs in the background to convert newly validated knowledge into pgvector embeddings
type EmbeddingWorker struct {
	db     *gorm.DB
	apiKey string
}

func NewEmbeddingWorker(db *gorm.DB) *EmbeddingWorker {
	return &EmbeddingWorker{
		db:     db,
		apiKey: os.Getenv("GEMINI_API_KEY"),
	}
}

func (w *EmbeddingWorker) Start(interval time.Duration) {
	go func() {
		log.Println("[EmbeddingWorker] Started RLOF Vector Sync Pipeline...")
		for {
			w.processPendingKnowledge()
			time.Sleep(interval)
		}
	}()
}

func (w *EmbeddingWorker) processPendingKnowledge() {
	if w.apiKey == "" {
		// Cannot generate embeddings without API key
		return
	}

	var pending []struct {
		ID       uint
		Issue    string `gorm:"column:issue_type"`
		Symptoms string `gorm:"column:symptoms"`
		Root     string `gorm:"column:root_cause"`
	}

	// Find knowledge rows that don't have an embedding yet
	err := w.db.Table("validated_knowledge_base").
		Select("id, issue_type, symptoms, root_cause").
		Where("embedding_vector IS NULL").
		Limit(10).
		Scan(&pending).Error

	if err != nil || len(pending) == 0 {
		return
	}

	log.Printf("[EmbeddingWorker] Found %d knowledge items missing vector embeddings. Processing...", len(pending))

	for _, p := range pending {
		// Construct the context string
		contextText := fmt.Sprintf("Issue: %s. Symptoms: %s. Root Cause: %s.", p.Issue, p.Symptoms, p.Root)
		vector, err := w.generateEmbedding(contextText)
		if err != nil {
			log.Printf("[EmbeddingWorker] Error generating embedding for KB ID %d: %v", p.ID, err)
			continue
		}

		// pgvector string representation: "[0.1, 0.2, ...]"
		vectorStr := w.floatSliceToString(vector)
		
		err = w.db.Exec("UPDATE validated_knowledge_base SET embedding_vector = ?::vector WHERE id = ?", vectorStr, p.ID).Error
		if err == nil {
			log.Printf("[EmbeddingWorker] Successfully updated Vector Embedding for KB ID %d", p.ID)
		}
	}
}

func (w *EmbeddingWorker) generateEmbedding(text string) ([]float32, error) {
	// Use text-embedding-004 model
	url := fmt.Sprintf("https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key=%s", w.apiKey)
	
	reqBody := map[string]interface{}{
		"model": "models/text-embedding-004",
		"content": map[string]interface{}{
			"parts": []map[string]interface{}{
				{"text": text},
			},
		},
	}
	
	jsonData, _ := json.Marshal(reqBody)
	resp, err := http.Post(url, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("gemini api returned status: %d", resp.StatusCode)
	}

	var res struct {
		Embedding struct {
			Values []float32 `json:"values"`
		} `json:"embedding"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&res); err != nil {
		return nil, err
	}
	
	return res.Embedding.Values, nil
}

func (w *EmbeddingWorker) floatSliceToString(values []float32) string {
	b, _ := json.Marshal(values)
	return string(b)
}
