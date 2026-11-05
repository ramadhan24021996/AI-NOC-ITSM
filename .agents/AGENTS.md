# Enterprise AI Governance & Operational Rules

## 🛡️ The Fundamental Remediation Governance Axiom (Rule #6)

> **"AI boleh menghasilkan, menjelaskan, dan mengarahkan remediation manual; AI tidak boleh menganggap remediation manual berhasil hanya karena command/SOP tersedia. Keberhasilan hanya sah setelah execution evidence dan post-remediation evidence terhubung ke incident yang sama."**

### Operational Implications & Invariants:
1. **Zero Assumption of Success**:
   - The availability or delivery of an approved SOP/Command to a client or operator does **NOT** transition an incident to `RESOLVED` or `CLOSED`.
2. **Dual-Evidence Binding Requirement**:
   - An incident resolution is valid **ONLY IF**:
     - (a) `execution_evidence` (Technician ACK, execution timestamp, or agent exit-code 0) is logged, AND
     - (b) `post_remediation_evidence` (Live telemetry metrics: e.g. service RUNNING, queue == 0, ping OK) is captured with timestamp $T_{\text{post}} \ge T_{\text{exec}}$.
3. **Causal Correlation**:
   - Telemetry must be strictly bound to the exact `incident_id` and `target_asset` of the execution instance.
4. **Resolution Locking**:
   - Tickets remain locked in `IN_PROGRESS` / `PENDING_VERIFICATION` until both evidence criteria pass the Verification Engine.
