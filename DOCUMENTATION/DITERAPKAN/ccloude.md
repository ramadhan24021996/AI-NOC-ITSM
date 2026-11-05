MASTER IMPLEMENTATION PROMPT
ADAPTIVE AI-NOC + JARVIS CLOSED-LOOP INCIDENT RESPONSE ENGINE

Anda bertindak sebagai Principal AI-NOC Architect dan Production Engineer.

JANGAN hanya menambahkan fitur.
JANGAN membuat workflow statis.
JANGAN membuat response berdasarkan keyword sederhana.
JANGAN membuat daftar action hardcoded yang selalu sama.
JANGAN menganggap semua incident memiliki pola, SOP, tindakan, atau solusi yang sama.

TUJUAN UTAMA:
Mengubah AI-NOC menjadi ADAPTIVE CLOSED-LOOP INCIDENT RESPONSE SYSTEM.

Sistem harus mampu memahami bahwa setiap incident dapat berbeda berdasarkan:
- jenis issue
- device
- service
- OS
- topology
- OSI Layer
- telemetry
- historical incident
- SOP yang tersedia
- severity
- business impact
- current system state
- hasil tindakan sebelumnya
- hasil verification
- confidence
- risk
- HITL decision
- escalation history

============================================================
1. CORE PRINCIPLE
============================================================

Implementasikan prinsip:

ISSUE
  ↓
INGEST EVIDENCE
  ↓
NORMALIZATION
  ↓
CORRELATION
  ↓
OSI 1–7 CLASSIFICATION
  ↓
MULTI-EVIDENCE DIAGNOSIS
  ↓
PROBABILISTIC REASONING
  ↓
ROOT CAUSE CANDIDATES
  ↓
SOP / KNOWLEDGE RETRIEVAL
  ↓
CONTEXT-AWARE PLAN GENERATION
  ↓
RISK + POLICY + COMPLIANCE
  ↓
HITL / AUTONOMOUS DECISION
  ↓
EXECUTION
  ↓
POST-ACTION VERIFICATION
  ↓
SOLVED ?
 ├── YES → CLOSE INCIDENT
 │          ↓
 │       LEARNING
 │
 └── NO
      ↓
   UPDATE EVIDENCE
      ↓
   RE-DIAGNOSE
      ↓
   CHANGE PLAN
      ↓
   NEXT SOP STEP
      ↓
   ESCALATE IF REQUIRED
      ↓
   VERIFY AGAIN

PENTING:

Jika action sebelumnya gagal,
SYSTEM TIDAK BOLEH hanya mengulang action yang sama.

Failure harus menjadi evidence baru.

============================================================
2. ADAPTIVE INCIDENT MODEL
============================================================

Buat Incident State sebagai dynamic state machine.

Minimal state:

NEW
OBSERVING
CLASSIFYING
DIAGNOSING
SOP_MATCHED
PLAN_GENERATED
WAITING_HITL
APPROVED
EXECUTING
VERIFYING
RECOVERY_PARTIAL
RECOVERY_FAILED
ESCALATING
RESOLVED
CLOSED
LEARNING

Incident harus mempunyai:

incident_id
device_id
device_type
service
os
timestamp
severity
business_impact
current_state
osi_layers[]
symptoms[]
telemetry[]
evidence[]
root_cause_candidates[]
probabilities[]
matched_sops[]
selected_sop
current_action
previous_actions[]
failed_actions[]
verification_result
confidence
risk_score
blast_radius
hitl_status
escalation_level
attempt_count
next_action
resolution_status

Jangan menyimpan hanya:
"issue = printer"

Harus mampu menyimpan:

Issue:
Printer gagal mencetak

Evidence:
- spooler stopped
- queue = 17
- printer reachable = true
- port 9100 = open
- CPU normal
- memory normal
- previous incidents similar = 12

OSI:
L7 Application
L4 Transport
L2 Data Link

Root Cause:
Spooler failure = 0.87

Candidate:
Network = 0.08
Printer hardware = 0.05

SOP:
SOP-PRINT-001

Action:
restart spooler

Verification:
spooler running = true
queue decreased = 17 → 0
test print = success

Result:
RESOLVED

============================================================
3. OSI 7-LAYER ADAPTIVE CLASSIFICATION
============================================================

Jangan membuat satu incident hanya memiliki satu layer.

Sistem harus mampu menghasilkan:

primary_layer
secondary_layers[]
layer_confidence

Contoh:

Internet lambat:

L1 Physical       0.12
L2 Data Link      0.21
L3 Network        0.71
L4 Transport      0.43
L5 Session        0.18
L6 Presentation   0.05
L7 Application    0.64

Primary:
L3 Network

Secondary:
L7 Application

Untuk setiap incident, sistem harus membangun
OSI evidence matrix.

JANGAN mengisi layer dengan tebakan.

Setiap layer harus memiliki evidence.

============================================================
4. DYNAMIC SOP ENGINE
============================================================

SOP MANUAL yang dibuat operator harus diperlakukan sebagai
KNOWLEDGE SOURCE.

Jangan menganggap SOP sebagai script statis.

SOP harus memiliki:

sop_id
version
title
category
applicable_devices
applicable_services
applicable_os
osi_layers
preconditions
diagnostic_steps
remediation_steps
verification_steps
rollback_steps
risk_level
required_approval
success_conditions
failure_conditions
escalation_conditions

Sistem harus memilih SOP berdasarkan CONTEXT.

Jangan:

IF issue == printer:
    restart spooler

Gunakan:

retrieve relevant SOPs
+
rank berdasarkan:
- semantic similarity
- device
- service
- OS
- OSI
- telemetry
- historical success
- severity
- current state

============================================================
5. SOP STEP ADAPTATION
============================================================

SOP boleh mempunyai branching.

Contoh:

STEP 1:
Check spooler

IF spooler stopped:
    restart spooler

IF spooler running:
    check print queue

IF queue > threshold:
    inspect queue

IF queue normal:
    inspect driver

IF printer unreachable:
    move diagnosis ke OSI L2/L3

IF port unreachable:
    perform network diagnostics

Jadi SOP menjadi:

DECISION TREE

bukan:

LINEAR SCRIPT.

============================================================
6. ACTION PLANNER HARUS ADAPTIVE
============================================================

AI Planner TIDAK BOLEH memiliki daftar action yang selalu sama.

Action harus dihasilkan berdasarkan:

current evidence
+
DBN belief state
+
causal RCA
+
SOP
+
device context
+
business context
+
previous action result
+
risk
+
policy

Contoh:

Incident A:
Printer spooler stopped

→ restart spooler

Incident B:
Printer unreachable

→ ping
→ ARP
→ port check
→ network diagnosis

Incident C:
Printer reachable tetapi queue stuck

→ inspect queue
→ restart spooler
→ test print

Incident D:
Restart spooler gagal

→ JANGAN ulangi restart spooler tanpa evidence baru

→ collect service logs
→ inspect dependency
→ inspect driver
→ inspect disk
→ escalate

============================================================
7. FAILURE MUST CHANGE THE PLAN
============================================================

INI ADALAH REQUIREMENT WAJIB.

Jika:

Action A
↓
Verification FAILED

Maka:

Evidence += Failure(A)

attempt_count += 1

confidence harus dihitung ulang.

Root cause probability harus dihitung ulang.

Planner harus menghasilkan ACTION B yang berbeda
atau escalation.

Contoh:

Action:
restart spooler

Result:
FAILED

Sistem harus menghasilkan:

New Evidence:
spooler restart unsuccessful

Kemudian:

Possible causes:

driver failure
dependency failure
permission issue
disk issue
service corruption

Planner memilih langkah berikutnya berdasarkan probability
dan SOP.

============================================================
8. VERIFICATION ENGINE
============================================================

JANGAN menganggap command berhasil = incident selesai.

Execution success ≠ Incident resolution.

Contoh:

restart service = SUCCESS

tetapi:

printer masih tidak mencetak

Maka:

incident = NOT_RESOLVED

Verification harus menggunakan:

service state
telemetry
connectivity
application state
business transaction
user/device state
error disappearance
test transaction
test print
health metrics

Setiap SOP harus mempunyai:

success criteria

dan:

failure criteria.

============================================================
9. ESCALATION ENGINE
============================================================

Jika verification gagal:

Level 0:
Retry / next diagnostic

Level 1:
Alternative remediation

Level 2:
Escalate to higher diagnostic

Level 3:
HITL

Level 4:
NOC Engineer

Level 5:
Specialist / vendor

Escalation harus berdasarkan:

severity
business impact
attempt_count
confidence
risk
blast radius
SLA
time elapsed

BUKAN hanya:

attempt_count > 3.

============================================================
10. AGENT PC / TRAY ADAPTIVE MESSAGE
============================================================

Agent PC tidak boleh menerima pesan generik.

Jangan:

"Printer error. Please check printer."

Harus:

INCIDENT #INC-XXXXX

DEVICE:
POS-KASIR-07

ISSUE:
Printer gagal mencetak struk.

OSI:
L7 Application
L4 Transport

EVIDENCE:
✓ Printer reachable
✓ Port 9100 reachable
✗ Spooler service stopped
✓ CPU normal
✓ Memory normal

ROOT CAUSE:
Spooler service failure

CONFIDENCE:
87%

ACTION:
Restart spooler service

STATUS:
WAITING APPROVAL

Jika approved:

ACTION:
Restart spooler service

STATUS:
EXECUTING

Setelah execution:

VERIFICATION:
✓ Spooler running
✓ Queue cleared
✓ Test print successful

STATUS:
RESOLVED

Jika gagal:

VERIFICATION:
✗ Printer still unable to print

NEXT DIAGNOSIS:
Check printer driver and Windows Print Queue

STATUS:
ESCALATED / NEXT ACTION

Pesan harus berubah berdasarkan incident.

============================================================
11. JARVIS INTEGRATION
============================================================

Jarvis bukan decision engine utama.

Jarvis adalah:

PRESENTATION + CONVERSATIONAL INTERFACE.

Semua keputusan tetap berasal dari AI-NOC orchestration.

Flow:

User
 ↓
Jarvis Voice
 ↓
Intent
 ↓
AI-NOC
 ↓
Decision
 ↓
HITL / Execution
 ↓
Verification
 ↓
AI-NOC
 ↓
Jarvis
 ↓
Voice Response

Jarvis harus membaca state aktual.

Jangan membuat Jarvis mengarang status.

Contoh:

AI-NOC:
verification_failed

Jarvis:

"Pak, tindakan restart spooler sudah dijalankan,
tetapi printer masih belum dapat mencetak.
Saya melanjutkan ke pemeriksaan driver dan print queue."

Bukan:

"Masalah sudah diperbaiki."

============================================================
12. HUMAN-IN-THE-LOOP
============================================================

HITL approval harus melekat pada ACTION,
bukan hanya incident.

Approval request harus berisi:

incident
evidence
root cause probability
proposed action
expected impact
risk
blast radius
rollback
verification plan

Operator memilih:

APPROVE
REJECT
MODIFY
ESCALATE

Jika MODIFY:

planner harus membuat ulang execution plan.

============================================================
13. PROBABILISTIC DECISION
============================================================

Gunakan:

DBN
+
Causal DAG
+
RAG similarity
+
historical success
+
telemetry evidence

untuk menghitung:

P(root_cause | evidence)

dan:

P(action_success | context)

Decision:

Expected Utility

tetapi:

PROBABILITY ≠ CERTAINTY.

Confidence rendah:

→ HITL

Risk tinggi:

→ HITL

Business impact tinggi:

→ HITL

Evidence contradictory:

→ additional diagnostics

============================================================
14. RAG / KNOWLEDGE 2
============================================================

Knowledge tidak boleh hanya menjadi:

"search SOP → return document"

Buat:

Knowledge Retrieval
→ reranking
→ contextual grounding
→ historical outcome
→ SOP applicability
→ action success history

Sistem harus mengetahui:

SOP mana yang pernah berhasil
SOP mana yang gagal
pada device apa
pada OS apa
pada service apa
dengan kondisi apa.

Namun JANGAN mengubah knowledge hanya karena satu feedback.

Gunakan evidence threshold dan confidence.

============================================================
15. CLOSED LOOP LEARNING
============================================================

Setiap incident yang selesai menghasilkan:

symptoms
evidence
root cause
selected SOP
actions
approval
execution result
verification result
resolution time
rollback
final outcome

Masukkan ke:

Incident Knowledge
+
RAG
+
Bayesian statistics
+
calibration dataset

Learning harus terkontrol.

JANGAN melakukan self-modification terhadap production policy
tanpa approval/versioning.

============================================================
16. ANTI-STATIC REQUIREMENT
============================================================

WAJIB mendeteksi dan menolak implementasi seperti:

if printer:
    restart spooler

if network:
    restart network

if cpu_high:
    restart service

Karena ini menghasilkan AI-NOC PASIF/STATIS.

Sebagai gantinya:

Incident
→ Evidence
→ Classification
→ Hypothesis
→ Probability
→ SOP
→ Context
→ Action
→ Verification
→ Adaptation

============================================================
17. NO FAKE ADAPTIVITY
============================================================

JANGAN hanya membuat fungsi bernama:

adaptive_engine()
dynamic_planner()
intelligent_decision()

tetapi isinya tetap hardcoded.

Antigravity WAJIB melakukan source-code audit untuk memastikan
adaptive behavior benar-benar memengaruhi:

1. diagnosis
2. SOP selection
3. action selection
4. escalation
5. verification
6. next action

============================================================
18. PRODUCTION SAFETY
============================================================

Tidak boleh:

- mock production execution
- dummy success
- fake telemetry
- hardcoded resolution
- bypass HITL
- bypass policy
- bypass compliance guard
- execute command langsung dari LLM
- menganggap command success = incident resolved
- self-modify production policy
- menghapus audit trail
- mengulang action gagal tanpa evidence baru

SEMUA execution harus melalui:

Policy
→ Compliance Guard
→ Risk
→ HITL / Autonomous Policy
→ Executor
→ Verification
→ Audit

============================================================
19. REQUIRED ARCHITECTURE
============================================================

Implementasikan / gunakan komponen:

incident_context_engine
osi_classifier
evidence_engine
dynamic_bayesian_network
causal_dag_engine
rag_engine
sop_engine
adaptive_planner
decision_network
policy_engine
regulatory_compliance_guard
hitl_engine
executor
verification_engine
escalation_engine
learning_engine
audit_engine
jarvis_interface

Jangan membuat duplikasi engine apabila modul yang setara
sudah ada.

Audit repository terlebih dahulu.

============================================================
20. REQUIRED SOURCE-CODE AUDIT
============================================================

Sebelum coding:

1. Scan seluruh SERVER/python_ai_core/
2. Identifikasi modul existing.
3. Identifikasi duplicate functionality.
4. Identifikasi hardcoded decision.
5. Identifikasi mock/stub.
6. Identifikasi bypass safety.
7. Identifikasi workflow yang statis.
8. Identifikasi existing DBN.
9. Identifikasi existing causal DAG.
10. Identifikasi existing RAG.
11. Identifikasi existing SOP.
12. Identifikasi existing HITL.
13. Identifikasi existing verification.
14. Identifikasi existing escalation.
15. Identifikasi existing Jarvis integration.

JANGAN membuat modul baru jika functionality sudah ada.

============================================================
21. TEST WAJIB
============================================================

Buat test minimal:

CASE 1
Printer spooler stopped
→ restart spooler
→ verification success
→ resolved

CASE 2
Printer unreachable
→ network diagnosis
→ bukan restart spooler

CASE 3
Restart spooler failed
→ evidence updated
→ planner memilih diagnosis berikutnya

CASE 4
Action berhasil tetapi issue tetap ada
→ NOT RESOLVED

CASE 5
POS sedang transaksi
→ dangerous action blocked

CASE 6
Critical issue
→ escalation

CASE 7
Low confidence
→ HITL

CASE 8
SOP tidak cocok
→ jangan execute
→ request additional diagnostics

CASE 9
Two simultaneous incidents
→ context harus terpisah

CASE 10
Same issue pada dua device berbeda
→ planner boleh menghasilkan action berbeda
berdasarkan context device.

============================================================
22. ACCEPTANCE CRITERIA
============================================================

Implementasi dianggap BERHASIL hanya jika:

[ ] Incident menghasilkan OSI classification
[ ] Classification menggunakan evidence
[ ] SOP dipilih secara contextual
[ ] Action tidak selalu sama
[ ] Failure menjadi evidence baru
[ ] Planner berubah setelah failure
[ ] Verification independen dari execution result
[ ] Unresolved incident tidak ditutup
[ ] Escalation adaptive
[ ] HITL terintegrasi
[ ] Compliance Guard wajib dilewati
[ ] Audit trail lengkap
[ ] Jarvis membaca state aktual
[ ] Agent Tray menerima instruksi contextual
[ ] Knowledge menyimpan outcome
[ ] Tidak ada fake adaptive logic
[ ] Tidak ada hardcoded resolution
[ ] Tidak ada production bypass

============================================================
FINAL INSTRUCTION
============================================================

JANGAN langsung coding.

PERTAMA:
audit repository.

KEDUA:
buat GAP MATRIX:

Component
Existing
Missing
Duplicate
Risk
Required Change
File
Priority

KETIGA:
buat implementation plan.

KEEMPAT:
implementasikan secara incremental.

KELIMA:
jalankan test.

KEENAM:
lakukan source-code audit ulang.

KETUJUH:
laporkan:

IMPLEMENTED
PARTIAL
MISSING
RISK
TEST RESULT
REMAINING GAP

Jangan menyatakan "production ready" hanya karena kode berhasil
dijalankan.

Production readiness harus dibuktikan melalui behavior,
verification, safety gates, failure handling, auditability,
dan test coverage.