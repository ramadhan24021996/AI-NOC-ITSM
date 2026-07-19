import os
from datetime import datetime

DOC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../DOCUMENTATION'))
GOV_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../SERVER/python_ai_core/governance'))
os.makedirs(DOC_DIR, exist_ok=True)
os.makedirs(GOV_DIR, exist_ok=True)

freeze_cert = """# V12 ARCHITECTURE FREEZE CERTIFICATE
**System Identity:** OSI AI Master V12 (Governed Autonomous Intelligence Operations Platform)
**Version:** V12
**Status:** ARCHITECTURE FROZEN
**Freeze Date:** 2026-07-19

## Approved Layers:
1. **Operational Layer**: (Go Ingestion, NATS, PostgreSQL, Dashboard, Agent, Incident Engine)
2. **Learning Layer**: (LF-1 to LF-5, Dispatcher Bridge, LOC)
3. **Governance Layer**: (ORR, LRR, ADG, Explainability Contract)
4. **Intelligence Layer**: (Prediction Pack, Recommendation, Consensus)

## Final Architect Declaration:
> "No Intelligence Capability may bypass Governance Layer enforcement."

All future changes to OSI AI Master V12 must pass:
`Change Request ➔ Architecture Impact Review ➔ Governance Review ➔ Implementation ➔ Validation Evidence ➔ Merge Approval`
"""

audit_package = """# V12 ENTERPRISE AUDIT PACKAGE
**System Identity:** OSI AI Master V12
**Date:** 2026-07-19

## 1. Architecture Evidence
*   **Diagram Final**: Tersedia di `PRD_JULI 19 2026.MD` (The 4 Pillars).
*   **Component Ownership**: Layer terisolasi (Ingestion oleh Go, Intelligence oleh Python).
*   **Data Flow**: Terdefinisi melalui RFC V6 dan Dispatcher Bridge.

## 2. Security Evidence
*   **RBAC Enforcement**: Hardened di Go API.
*   **Permission Boundary**: Diatur dalam `approval_matrix.yaml`.
*   **Audit Logging**: Permanen di `system_audits` & `ai_audit_trail`.

## 3. AI Safety Evidence
*   **Confidence Policy**: Diikat dalam runtime `confidence_policy.yaml`.
*   **Risk Policy**: Diikat dalam runtime `risk_policy.yaml`.
*   **HITL Records**: Tercatat dalam database historis persetujuan (`hitl_audit_logs`).

## 4. Operational Evidence
*   **Uptime & Latency**: Dimonitor melalui LOC dan Prometheus.
*   **Incident Resolution Metrics**: Disuplai oleh LF-3 (Success Scoring Engine).
"""

risk_yaml = """risk_levels:
  LOW:
    ai_action: "Auto Execute"
    requires_hitl: false
  MEDIUM:
    ai_action: "AI Recommendation"
    requires_hitl: true
  HIGH:
    ai_action: "HITL Mandatory"
    requires_hitl: true
    min_approvers: 1
  CRITICAL:
    ai_action: "Multi Approval Required"
    requires_hitl: true
    min_approvers: 2
"""

confidence_yaml = """confidence_thresholds:
  auto_execute: 0.95
  recommendation_only: 0.82
  show_warning: 0.70
  reject: 0.55
"""

knowledge_yaml = """knowledge_lifecycle:
  phases:
    - NEW
    - VALIDATED
    - ACTIVE
    - AGING
    - STALE
    - ARCHIVED
    - PURGED
  aging_days: 180
  stale_drift_threshold: 0.3
"""

explainability_yaml = """explainability_contract:
  mandatory_fields:
    - decision
    - reason
    - evidence
    - historical_success
    - temporal_pattern
    - policy_rule
    - risk_assessment
  rejection_rule: "REJECT IF ANY FIELD IS MISSING"
"""

approval_yaml = """approval_matrix:
  roles:
    L1_SUPPORT:
      can_approve_risk: ["LOW", "MEDIUM"]
    L2_ENGINEER:
      can_approve_risk: ["LOW", "MEDIUM", "HIGH"]
    SRE_LEAD:
      can_approve_risk: ["HIGH", "CRITICAL"]
"""

files = {
    os.path.join(DOC_DIR, 'V12_ARCHITECTURE_FREEZE_CERTIFICATE.md'): freeze_cert,
    os.path.join(DOC_DIR, 'V12_ENTERPRISE_AUDIT_PACKAGE.md'): audit_package,
    os.path.join(GOV_DIR, 'risk_policy.yaml'): risk_yaml,
    os.path.join(GOV_DIR, 'confidence_policy.yaml'): confidence_yaml,
    os.path.join(GOV_DIR, 'knowledge_policy.yaml'): knowledge_yaml,
    os.path.join(GOV_DIR, 'explainability_policy.yaml'): explainability_yaml,
    os.path.join(GOV_DIR, 'approval_matrix.yaml'): approval_yaml,
}

for path, content in files.items():
    with open(path, 'w') as f:
        f.write(content)
        print(f"[+] Wrote {os.path.basename(path)}")
