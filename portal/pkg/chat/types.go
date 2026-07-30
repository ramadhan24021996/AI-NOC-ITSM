// Package chat menyediakan tipe-tipe data dan helper untuk
// Chat Engine & WebSocket Portal. Dipindahkan dari chat_engine.go
// agar dapat diimpor secara independen oleh handler lain.
package chat

import "time"

// ChatEvent merepresentasikan event chat yang dipublikasikan antar
// operator dan klien melalui NATS/Redis.
type ChatEvent struct {
	Type      string      `json:"type"`
	SessionID string      `json:"session_id"`
	ClientID  string      `json:"client_id,omitempty"`
	Operator  string      `json:"operator,omitempty"`
	Message   string      `json:"message,omitempty"`
	Data      interface{} `json:"data,omitempty"`
	Timestamp time.Time   `json:"timestamp"`
}

// IngestorChatEvent merepresentasikan event dari Go Ingestion Server.
type IngestorChatEvent struct {
	Type    string      `json:"type"`
	SiteID  string      `json:"site_id"`
	Payload interface{} `json:"payload"`
}

// ChatSession merepresentasikan sesi chat antara klien dan operator.
type ChatSession struct {
	SessionID  string    `json:"session_id"`
	ClientID   string    `json:"client_id"`
	OperatorID string    `json:"operator_id"`
	Status     string    `json:"status"` // "open", "closed", "waiting"
	CreatedAt  time.Time `json:"created_at"`
	UpdatedAt  time.Time `json:"updated_at"`
}

// ChatMessage merepresentasikan satu pesan dalam sesi chat.
type ChatMessage struct {
	ID         uint      `json:"id"`
	SessionID  string    `json:"session_id"`
	SenderType string    `json:"sender_type"` // "client", "operator", "ai"
	SenderID   string    `json:"sender_id"`
	Content    string    `json:"content"`
	IsRead     bool      `json:"is_read"`
	CreatedAt  time.Time `json:"created_at"`
}

// MetricBucket menyimpan metric rolling window untuk dashboard chat.
type MetricBucket struct {
	WindowSize  int
	CPUPoints   []float64
	RAMPoints   []float64
	CurrentIdx  int
	IsFull      bool
}

// NewMetricBucket membuat metric bucket baru dengan window tertentu.
func NewMetricBucket(windowSize int) *MetricBucket {
	return &MetricBucket{
		WindowSize: windowSize,
		CPUPoints:  make([]float64, windowSize),
		RAMPoints:  make([]float64, windowSize),
	}
}

// AddMetricPoint menambahkan data point CPU/RAM dan menghitung rata-rata.
func (mb *MetricBucket) AddMetricPoint(cpu, ram float64) (avgCPU, avgRAM float64, isAnomaly bool) {
	mb.CPUPoints[mb.CurrentIdx] = cpu
	mb.RAMPoints[mb.CurrentIdx] = ram
	mb.CurrentIdx = (mb.CurrentIdx + 1) % mb.WindowSize
	if mb.CurrentIdx == 0 {
		mb.IsFull = true
	}

	count := mb.WindowSize
	if !mb.IsFull {
		count = mb.CurrentIdx
	}
	if count == 0 {
		return 0, 0, false
	}

	var sumCPU, sumRAM float64
	for i := 0; i < count; i++ {
		sumCPU += mb.CPUPoints[i]
		sumRAM += mb.RAMPoints[i]
	}
	avgCPU = sumCPU / float64(count)
	avgRAM = sumRAM / float64(count)
	isAnomaly = cpu > avgCPU*1.5 || ram > avgRAM*1.5
	return avgCPU, avgRAM, isAnomaly
}

// DegradedResponse membuat response standar ketika chat service degraded.
func DegradedResponse(reason string) map[string]interface{} {
	return map[string]interface{}{
		"status":  "degraded",
		"message": "Chat service temporarily unavailable",
		"reason":  reason,
	}
}
