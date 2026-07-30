package ingestion

import (
	"fmt"
	"regexp"
	"strings"
)

// SitePartitionRoute defines the site-partitioned NATS subject structure (allsite.md)
type SitePartitionRoute struct {
	SiteID     string `json:"site_id"`
	Subject    string `json:"subject"`
	Category   string `json:"category"`   // telemetry, incident, approval
	Severity   string `json:"severity"`   // critical, warning, normal
	OrderKey   string `json:"order_key"`  // per-site ordering key
}

var nonAlphaNumRegex = regexp.MustCompile(`[^a-zA-Z0-9_-]`)

// NormalizeSiteID cleanses and standardizes raw site identifiers into NATS-compliant subject tokens
func NormalizeSiteID(rawSite string) string {
	rawSite = strings.TrimSpace(rawSite)
	if rawSite == "" {
		return "default-site"
	}
	
	// Convert spaces to hyphens and remove invalid characters
	clean := strings.ReplaceAll(strings.ToLower(rawSite), " ", "-")
	clean = nonAlphaNumRegex.ReplaceAllString(clean, "")
	if clean == "" {
		return "default-site"
	}
	return clean
}

// GetPartitionedSubject resolves the exact NATS JetStream subject name per site & severity
func GetPartitionedSubject(category string, siteID string, severity string) string {
	cleanSite := NormalizeSiteID(siteID)
	cleanSev := strings.ToLower(strings.TrimSpace(severity))

	switch strings.ToLower(category) {
	case "telemetry":
		if cleanSev == "critical" || cleanSev == "error" || cleanSev == "fatal" {
			return fmt.Sprintf("telemetry.site.%s.critical", cleanSite)
		} else if cleanSev == "warning" || cleanSev == "warn" {
			return fmt.Sprintf("telemetry.site.%s.warning", cleanSite)
		} else {
			return fmt.Sprintf("telemetry.site.%s.normal", cleanSite)
		}
	case "incident":
		if cleanSev == "update" {
			return fmt.Sprintf("incident.site.%s.update", cleanSite)
		}
		return fmt.Sprintf("incident.site.%s.create", cleanSite)
	case "approval":
		return fmt.Sprintf("approval.site.%s", cleanSite)
	default:
		return fmt.Sprintf("telemetry.site.%s.normal", cleanSite)
	}
}

// GetPartitionWildcards returns wildcard subjects for NATS consumers and metrics monitoring
func GetPartitionWildcards() []map[string]string {
	return []map[string]string{
		{"subject": "telemetry.site.*.critical", "role": "Site Critical Ingest Stream", "category": "Telemetry"},
		{"subject": "telemetry.site.*.warning", "role": "Site Warning Ingest Stream", "category": "Telemetry"},
		{"subject": "telemetry.site.*.normal", "role": "Site Normal Ingest Stream", "category": "Telemetry"},
		{"subject": "incident.site.*.create", "role": "Site Incident Creation Queue", "category": "Incident"},
		{"subject": "incident.site.*.update", "role": "Site Incident Update Channel", "category": "Incident"},
		{"subject": "approval.site.*", "role": "Site HITL Approval Channel", "category": "Approval"},
	}
}
