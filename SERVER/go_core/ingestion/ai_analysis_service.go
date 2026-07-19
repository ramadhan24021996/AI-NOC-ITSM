package ingestion

import (
	"go_incident_analysis/SERVER/go_core/ai"
	"go_incident_analysis/SERVER/go_core/database"
)

// AIAnalysisService wraps calls to the AI Supervisor engine.
type AIAnalysisService struct {
	supervisor *ai.AISupervisor
}

var DefaultAIAnalysisService = &AIAnalysisService{}

// Init initializes the supervisor.
func (s *AIAnalysisService) Init() {
	if s.supervisor == nil && database.DB != nil {
		s.supervisor = ai.NewAISupervisor(database.DB)
	}
}

// Analyze runs the incident diagnosis logic and returns both the structured struct and the formatted string report.
func (s *AIAnalysisService) Analyze(issue string, details string) (ai.DiagnosisResult, string) {
	s.Init()
	if s.supervisor == nil {
		// Fallback if DB is not yet initialized
		return ai.DiagnosisResult{
			Issue:    issue,
			Severity: "LOW",
		}, "AI Supervisor not initialized yet"
	}
	return s.supervisor.DiagnoseIncident(issue, details)
}
