package core

import (
	"time"
)

type FleetIncident struct {
	IncidentID  uint       `gorm:"primaryKey;column:incident_id;autoIncrement" json:"incident_id"`
	SiteID      *string    `gorm:"column:site_id" json:"site_id"`
	PCName      *string    `gorm:"column:pc_name" json:"pc_name"`
	Severity    string     `gorm:"column:severity;default:'LOW'" json:"severity"`
	Status      string     `gorm:"column:status;default:'OPEN'" json:"status"`
	Description string     `gorm:"column:description" json:"description"`
	CreatedAt   time.Time  `gorm:"column:created_at;autoCreateTime" json:"created_at"`
	ResolvedAt  *time.Time `gorm:"column:resolved_at" json:"resolved_at"`
}

func (FleetIncident) TableName() string {
	return "fleet_incidents"
}

type SystemAudit struct {
	ID               uint      `gorm:"primaryKey;column:id;autoIncrement" json:"id"`
	Timestamp        time.Time `gorm:"column:timestamp;autoCreateTime" json:"timestamp"`
	HealthScore      int       `gorm:"column:health_score" json:"health_score"`
	Status           string    `gorm:"column:status" json:"status"`
	FailedComponents string    `gorm:"column:failed_components" json:"failed_components"`
	RootCause        string    `gorm:"column:root_cause" json:"root_cause"`
	Confidence       int       `gorm:"column:confidence" json:"confidence"`
	Recommendation   string    `gorm:"column:recommendation" json:"recommendation"`
	RawJSON          string    `gorm:"column:raw_json" json:"raw_json"`
	AuditDurationMs  int       `gorm:"column:audit_duration_ms" json:"audit_duration_ms"`
	AuditorVersion   string    `gorm:"column:auditor_version" json:"auditor_version"`
}

func (SystemAudit) TableName() string {
	return "system_audits"
}

type ApprovalOutbox struct {
	ID          uint64     `gorm:"primaryKey;column:id;autoIncrement"`
	EventType   string     `gorm:"column:event_type"`
	AggregateID int64      `gorm:"column:aggregate_id"`
	Payload     string     `gorm:"column:payload;type:jsonb"`
	Status      string     `gorm:"column:status;default:'PENDING'"`
	CreatedAt   time.Time  `gorm:"column:created_at;autoCreateTime"`
	SentAt      *time.Time `gorm:"column:sent_at"`
}

func (ApprovalOutbox) TableName() string {
	return "approval_outbox"
}

type OperatorPresence struct {
	OperatorID string    `gorm:"primaryKey;column:operator_id" json:"operator_id"`
	Status     string    `gorm:"column:status" json:"status"` // ONLINE, OFFLINE, BUSY, TYPING
	LastSeen   time.Time `gorm:"column:last_seen" json:"last_seen"`
	TypingTo   string    `gorm:"column:typing_to" json:"typing_to"`
}

func (OperatorPresence) TableName() string { return "operator_presence" }

type ChatFeedback struct {
	ID                    uint      `gorm:"primaryKey;autoIncrement" json:"id"`
	SessionClientID       string    `gorm:"column:session_client_id" json:"session_client_id"`
	ResolutionStatus      string    `gorm:"column:resolution_status" json:"resolution_status"`
	OperatorNotes         string    `gorm:"column:operator_notes" json:"operator_notes"`
	AIRecommendationUsed  bool      `gorm:"column:ai_recommendation_used" json:"ai_recommendation_used"`
	Successful            bool      `gorm:"column:successful" json:"successful"`
	EscalationLevel       string    `gorm:"column:escalation_level" json:"escalation_level"`
	CreatedAt             time.Time `gorm:"column:created_at;autoCreateTime" json:"created_at"`
}

func (ChatFeedback) TableName() string { return "chat_feedback" }

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
	ThreadType  string                 `json:"thread_type"` // SUPPORT, INCIDENT, ESCALATION
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
}
