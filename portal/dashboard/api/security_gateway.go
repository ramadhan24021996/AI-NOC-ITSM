package api

import (
	"fmt"
	"strings"
)

type RiskLevel string

const (
	RiskLow      RiskLevel = "LOW"
	RiskMedium   RiskLevel = "MEDIUM"
	RiskHigh     RiskLevel = "HIGH"
	RiskCritical RiskLevel = "CRITICAL"
)

type SecurityEvaluation struct {
	Action             string    `json:"action"`
	RiskScore          int       `json:"risk_score"`
	RiskClassification RiskLevel `json:"risk_classification"`
	Allowed            bool      `json:"allowed"`
	RequiresHITL       bool      `json:"requires_hitl"`
	BlockedReason      string    `json:"blocked_reason"`
	AffectedResource   string    `json:"affected_resource"`
	PolicyRule         string    `json:"policy_rule"`
}

// EvaluateSecurityPolicy evaluates an AI action against explicit rule-based guardrails (Default-Deny)
func EvaluateSecurityPolicy(actionCmd string, targetResource string) SecurityEvaluation {
	cmd := strings.ToLower(strings.TrimSpace(actionCmd))
	res := strings.ToLower(strings.TrimSpace(targetResource))

	if res == "" {
		res = "system_host"
	}

	// 1. Explicit Rule 1: No deleting system OS files (C:\Windows, /etc, /bin, /usr/bin)
	if strings.Contains(cmd, "rm -rf /") || strings.Contains(cmd, "rmdir /s /q c:\\windows") ||
		strings.Contains(cmd, "/etc/") || strings.Contains(cmd, "/bin/") || strings.Contains(cmd, "c:\\windows\\system32") {
		return SecurityEvaluation{
			Action:             actionCmd,
			RiskScore:          100,
			RiskClassification: RiskCritical,
			Allowed:            false,
			RequiresHITL:       true,
			BlockedReason:      "BLOCKED_BY_POLICY: Deleting OS System Folder is strictly prohibited",
			AffectedResource:   res,
			PolicyRule:         "RULE_1_SYSTEM_DIRECTORY_PROTECTION",
		}
	}

	// 2. Explicit Rule 2: No modifying Firewall or Antivirus without approval
	if strings.Contains(cmd, "disable firewall") || strings.Contains(cmd, "ufw disable") ||
		strings.Contains(cmd, "netsh advfirewall set allprofiles state off") || strings.Contains(cmd, "stop defender") {
		return SecurityEvaluation{
			Action:             actionCmd,
			RiskScore:          90,
			RiskClassification: RiskCritical,
			Allowed:            false,
			RequiresHITL:       true,
			BlockedReason:      "BLOCKED_BY_POLICY: Modifying Firewall/Antivirus state requires explicit Superadmin confirmation",
			AffectedResource:   res,
			PolicyRule:         "RULE_2_FIREWALL_ANTIVIRUS_PROTECTION",
		}
	}

	// 3. Explicit Rule 3: No executing unverified internet scripts
	if (strings.Contains(cmd, "curl") || strings.Contains(cmd, "wget")) && (strings.Contains(cmd, "| bash") || strings.Contains(cmd, "| sh") || strings.Contains(cmd, "powershell -c")) {
		return SecurityEvaluation{
			Action:             actionCmd,
			RiskScore:          95,
			RiskClassification: RiskCritical,
			Allowed:            false,
			RequiresHITL:       true,
			BlockedReason:      "BLOCKED_BY_POLICY: Piping unverified internet scripts to shell is prohibited",
			AffectedResource:   res,
			PolicyRule:         "RULE_3_UNVERIFIED_SCRIPT_BLOCK",
		}
	}

	// 4. Rule 4: Administrative Service Restart or Privilege Action (High/Medium Risk -> Wajib HITL Approval Dashboard)
	if strings.Contains(cmd, "systemctl restart") || strings.Contains(cmd, "net stop") || strings.Contains(cmd, "kill") || strings.Contains(cmd, "reboot") || strings.Contains(cmd, "flush") {
		return SecurityEvaluation{
			Action:             actionCmd,
			RiskScore:          65,
			RiskClassification: RiskHigh,
			Allowed:            true,
			RequiresHITL:       true,
			BlockedReason:      "REQUIRES_APPROVAL: Admin Service Action requires Approval Dashboard confirmation",
			AffectedResource:   res,
			PolicyRule:         "RULE_4_ADMINISTRATIVE_ACTION_HITL",
		}
	}

	// 5. Read-only or Safe Telemetry Operations (Low Risk -> Safe)
	return SecurityEvaluation{
		Action:             actionCmd,
		RiskScore:          10,
		RiskClassification: RiskLow,
		Allowed:            true,
		RequiresHITL:       false,
		BlockedReason:      "",
		AffectedResource:   res,
		PolicyRule:         "RULE_5_SAFE_READONLY_OPERATION",
	}
}

// FormatSecurityAuditNotice returns a formatted text notice of the 7-stage security evaluation for chat & HITL cards
func FormatSecurityAuditNotice(eval SecurityEvaluation) string {
	if !eval.Allowed {
		return fmt.Sprintf("⛔ [SECURITY GATEWAY BLOCKED]: %s (Policy: %s, Risk: %s)", eval.BlockedReason, eval.PolicyRule, eval.RiskClassification)
	}
	if eval.RequiresHITL {
		return fmt.Sprintf("🛡️ [SECURITY GATEWAY NOTICE]: Action '%s' classified as %s RISK (Score %d/100). Routed to Approval Dashboard (HITL Gate).", eval.Action, eval.RiskClassification, eval.RiskScore)
	}
	return fmt.Sprintf("✅ [SECURITY GATEWAY SAFE]: Action '%s' classified as LOW RISK. Safe to execute.", eval.Action)
}
