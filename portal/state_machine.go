package main

// ============================================================
// Phase 4: Orchestrator Hardening — State Machine Guard (Go)
// NOC IT AI v3.0
//
// Implements deterministic transition validation for all
// incident state changes in the dashboard/portal layer.
// ============================================================

import (
	"fmt"
	"time"

	"gorm.io/gorm"
)

// ─────────────────────────────────────────────────────────────
// 1. CANONICAL STATES
// ─────────────────────────────────────────────────────────────
const (
	StateNew              = "NEW"
	StateOpen             = "OPEN"
	StateAnalyzing        = "ANALYZING"
	StateApprovalPending  = "APPROVAL_PENDING"
	StateWaitingApproval  = "WAITING_APPROVAL"
	StateApproved         = "APPROVED"
	StateExecuting        = "EXECUTING"
	StateVerifying        = "VERIFYING"
	StateSuccess          = "SUCCESS"
	StateRollbackPending  = "ROLLBACK_PENDING"
	StateRolledBack       = "ROLLED_BACK"
	StateFailed           = "FAILED"
	StateDLQ              = "DLQ"
	StateEscalated        = "ESCALATED"
	StateResolved         = "RESOLVED"
)

// ─────────────────────────────────────────────────────────────
// 2. TRANSITION MATRIX
// ─────────────────────────────────────────────────────────────
var allowedTransitions = map[string]map[string]bool{
	StateNew: {
		StateAnalyzing: true,
		StateDLQ:       true,
	},
	StateOpen: {
		StateAnalyzing: true,
		StateEscalated: true,
		StateDLQ:       true,
		StateResolved:  true,
	},
	StateAnalyzing: {
		StateApprovalPending: true,
		StateWaitingApproval: true,
		StateExecuting:       true,
		StateFailed:          true,
		StateDLQ:             true,
	},
	StateApprovalPending: {
		StateApproved:  true,
		StateFailed:    true,
		StateDLQ:       true,
		StateEscalated: true,
	},
	StateWaitingApproval: {
		StateApproved:  true,
		StateFailed:    true,
		StateDLQ:       true,
		StateEscalated: true,
	},
	StateApproved: {
		StateExecuting: true,
		StateFailed:    true,
	},
	StateExecuting: {
		StateVerifying:       true,
		StateRollbackPending: true,
		StateFailed:          true,
		StateDLQ:             true,
	},
	StateVerifying: {
		StateSuccess:         true,
		StateRollbackPending: true,
		StateFailed:          true,
	},
	StateRollbackPending: {
		StateRolledBack: true,
		StateFailed:     true,
	},
	StateRolledBack: {
		StateOpen:   true,
		StateFailed: true,
	},
	// Terminal states
	StateSuccess:  {},
	StateFailed:   {StateDLQ: true, StateOpen: true},
	StateDLQ:      {StateOpen: true},
	StateEscalated: {StateResolved: true, StateAnalyzing: true},
	StateResolved: {},
}

// ─────────────────────────────────────────────────────────────
// 3. FORBIDDEN TRANSITIONS (explicit hard rejects)
// ─────────────────────────────────────────────────────────────
type transitionKey struct{ From, To string }

var forbiddenTransitions = map[transitionKey]string{
	{StateVerifying, StateExecuting}:    "VERIFYING cannot precede EXECUTING",
	{StateSuccess, StateVerifying}:      "SUCCESS before VERIFYING is invalid",
	{StateSuccess, StateExecuting}:      "SUCCESS before EXECUTING is invalid",
	{StateApproved, StateAnalyzing}:     "Cannot re-analyze after APPROVED",
	{StateRolledBack, StateExecuting}:   "Cannot EXECUTE after ROLLED_BACK without re-approval",
	{StateResolved, StateExecuting}:     "RESOLVED incidents cannot be executed",
	{StateResolved, StateAnalyzing}:     "RESOLVED incidents cannot be re-analyzed",
}

// ─────────────────────────────────────────────────────────────
// 4. TRANSITION RESULT
// ─────────────────────────────────────────────────────────────
type TransitionResult struct {
	Allowed    bool
	FromState  string
	ToState    string
	Reason     string
	IncidentID int64
	Actor      string
	Timestamp  time.Time
}

// ─────────────────────────────────────────────────────────────
// 5. GUARD FUNCTION
// ─────────────────────────────────────────────────────────────
// GuardTransition checks if a state transition is valid.
// Returns (allowed bool, reason string).
func GuardTransition(tx *gorm.DB, incidentID uint, fromState, toState string) (bool, string) {
	// No-op
	if fromState == toState {
		return true, "NO_OP"
	}

	// Check forbidden
	if reason, forbidden := forbiddenTransitions[transitionKey{fromState, toState}]; forbidden {
		return false, fmt.Sprintf("FORBIDDEN: %s", reason)
	}

	// Check allowed matrix
	allowed, ok := allowedTransitions[fromState]
	if !ok {
		return false, fmt.Sprintf("UNKNOWN_SOURCE_STATE: %s", fromState)
	}
	if !allowed[toState] {
		return false, fmt.Sprintf("ILLEGAL_TRANSITION: %s -> %s", fromState, toState)
	}

	// 5. INVARIANT CHECKS (Database backed if transaction is available)
	if tx != nil && incidentID != 0 {
		// Invariant: APPROVED without approval record is invalid
		if toState == StateApproved {
			var qCount int64
			tx.Table("approval_queue").Where("incident_id = ?", incidentID).Count(&qCount)
			var lCount int64
			tx.Table("ai_approval_logs").Where("incident_id = ? AND approval_status = 'APPROVED'", incidentID).Count(&lCount)
			if qCount == 0 && lCount == 0 {
				return false, "APPROVED without approval record is invalid"
			}
		}

		// Invariant: ROLLBACK without execution is invalid
		if toState == StateRollbackPending || toState == StateRolledBack {
			var execCount int64
			tx.Table("incident_states").Where("incident_id = ? AND to_state = 'EXECUTING'", incidentID).Count(&execCount)
			if execCount == 0 {
				return false, "ROLLBACK without execution is invalid"
			}
		}
	}

	return true, "ALLOWED"
}

// ─────────────────────────────────────────────────────────────
// 6. TRANSITION MATRIX EXPORT (for API/observability)
// ─────────────────────────────────────────────────────────────
type TransitionMatrixEntry struct {
	FromState    string   `json:"from"`
	AllowedTo    []string `json:"allowed_to"`
}

type StateMachineMatrix struct {
	States      []string                        `json:"states"`
	Transitions []TransitionMatrixEntry          `json:"transitions"`
	Forbidden   []map[string]string              `json:"forbidden"`
}

func GetStateMachineMatrix() StateMachineMatrix {
	states := []string{
		StateNew, StateOpen, StateAnalyzing, StateApprovalPending,
		StateWaitingApproval, StateApproved, StateExecuting, StateVerifying,
		StateSuccess, StateRollbackPending, StateRolledBack, StateFailed,
		StateDLQ, StateEscalated, StateResolved,
	}

	var transitions []TransitionMatrixEntry
	for from, toMap := range allowedTransitions {
		var toList []string
		for to := range toMap {
			toList = append(toList, to)
		}
		transitions = append(transitions, TransitionMatrixEntry{FromState: from, AllowedTo: toList})
	}

	var forbidden []map[string]string
	for k, reason := range forbiddenTransitions {
		forbidden = append(forbidden, map[string]string{
			"from": k.From, "to": k.To, "reason": reason,
		})
	}

	return StateMachineMatrix{States: states, Transitions: transitions, Forbidden: forbidden}
}
