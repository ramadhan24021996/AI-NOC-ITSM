package incident

import (
	"fmt"
	"time"

	"gorm.io/gorm"
)

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

type TransitionResult struct {
	Allowed    bool
	FromState  string
	ToState    string
	Reason     string
	IncidentID int64
	Actor      string
	Timestamp  time.Time
}

func GuardTransition(tx *gorm.DB, incidentID uint, fromState, toState string) (bool, string) {
	if fromState == toState {
		return true, "NO_OP"
	}

	if reason, forbidden := forbiddenTransitions[transitionKey{fromState, toState}]; forbidden {
		return false, fmt.Sprintf("FORBIDDEN: %s", reason)
	}

	allowed, ok := allowedTransitions[fromState]
	if !ok {
		return false, fmt.Sprintf("UNKNOWN_SOURCE_STATE: %s", fromState)
	}
	if !allowed[toState] {
		return false, fmt.Sprintf("ILLEGAL_TRANSITION: %s -> %s", fromState, toState)
	}

	if tx != nil && incidentID != 0 {
		if toState == StateApproved {
			var qCount int64
			tx.Table("approval_queue").Where("incident_id = ?", incidentID).Count(&qCount)
			var lCount int64
			tx.Table("ai_approval_logs").Where("incident_id = ? AND approval_status = 'APPROVED'", incidentID).Count(&lCount)
			if qCount == 0 && lCount == 0 {
				return false, "APPROVED without approval record is invalid"
			}
		}

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

type TransitionMatrixEntry struct {
	FromState string   `json:"from"`
	AllowedTo []string `json:"allowed_to"`
}

type StateMachineMatrix struct {
	States      []string                `json:"states"`
	Transitions []TransitionMatrixEntry `json:"transitions"`
	Forbidden   []map[string]string     `json:"forbidden"`
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
