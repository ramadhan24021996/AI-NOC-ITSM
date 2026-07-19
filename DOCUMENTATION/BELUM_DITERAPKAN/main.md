Lakukan FULL FUNCTIONAL DISSECTION terhadap dashboard NOC Command Center saya.

Tujuan:
Saya ingin membedah SEMUA menu, sub-menu, widget, tombol, tabel, chart, dan event binding secara detail.

Bukan hanya audit bug.
Saya ingin structural breakdown + functional map + missing implementation map.

==================================================
SCOPE WAJIB
==================================================

Audit semua menu sidebar:

MONITORING
1. Overview
2. Monitoring Live
3. Activity & Issues
4. Server Health

INSIDEN
5. Incident Triage
6. Ground Truth & RCA
7. Causal DAG

INFRASTRUKTUR
8. PC Health
9. Printer Status
10. Fleet Management
11. Storage

AI & LOG
12. AI Panel
13. Training Feedback
14. Live Logs
15. Live Chat Support

KONFIGURASI
16. Governance
17. SOP Lifecycle
18. Model Config
19. RBAC Policies

HITL / EVENT BACKBONE
20. Execution Timeline
21. Event Correlation
22. Approval Queue
23. Pending Verification
24. Rollback History
25. Failed Actions DLQ
26. AI Agent Health
27. NATS Subjects
28. JetStream Streams
29. AI Decision Logs
30. Schema Validation Logs
31. Learning Gate Logs
32. Security Policies
33. Recovery Mode Config
34. Learning Gate Policy

==================================================
UNTUK SETIAP MENU WAJIB BEDAH:
==================================================

A. STRUCTURE MAP
- Panel name
- Internal widgets/cards
- Tables
- Charts
- Action buttons
- Search/filter
- Export buttons
- Modal/dialog
- Child components

B. FUNCTION MAP
Untuk setiap elemen:
- fungsi sebenarnya
- event binding
- onclick
- onchange
- load()
- init()
- websocket listener
- timer
- polling

C. DATA FLOW MAP
Tampilkan flow:
UI
↓
JS handler
↓
DataService
↓
API endpoint
↓
Backend controller
↓
DB table / Queue / Event Bus

D. DEPENDENCY MAP
Cek:
- REST API
- WebSocket
- NATS
- JetStream
- Redis
- PostgreSQL
- AI Supervisor
- Agent RPC
- Verification Engine
- Rollback Engine

E. STATUS MAP
Klasifikasi:
- FULLY WORKING
- PARTIAL
- BROKEN
- UI ONLY
- MOCK ONLY
- BACKEND MISSING
- EVENT NOT CONNECTED
- DATA EMPTY
- RENDER ONLY

F. BUG MAP
Cari:
- undefined object
- broken onclick
- wrong selector
- stale DOM
- null ref
- chart leak
- interval leak
- duplicate listener
- websocket dead state
- fetch race condition
- wrong endpoint
- schema mismatch
- state desync

G. DETAIL OUTPUT
Untuk tiap widget:
- expected payload
- actual payload
- expected render
- actual render
- missing field
- missing backend
- missing event
- missing consumer

==================================================
SPECIAL DEEP AUDIT
==================================================

WAJIB bedah lebih dalam:

1. Overview
Detail:
- KPI source
- health source
- device source
- incident source
- MTTR logic
- AI confidence logic

2. Monitoring Live
Detail:
- chart source
- poll interval
- live metrics
- ping site
- system status
- resource leak

3. Activity & Issues
Detail:
- active app tracker
- browser freeze detector
- issue logs
- websocket telemetry
- extension telemetry

4. Incident Triage
Detail:
- filtering
- sorting
- export CSV/JSON/XLSX
- resolve
- escalate

5. Ground Truth & RCA
Detail:
- why chain
- evidence chain
- feedback to RAG
- confidence pipeline

6. Causal DAG
Detail:
- node generation
- graph edges
- trace relation
- export SVG

7. PC Health
Detail:
- CPU
- RAM
- Disk
- remote action
- restart
- diagnostics

8. Printer Status
Detail:
- ping
- clear queue
- restart spooler
- test print
- printer CRUD

9. AI Panel
Detail:
- inference source
- prediction history
- confidence
- model performance

10. Live Logs
Detail:
- log source
- stream source
- filter
- pause
- copy
- download

11. Live Chat Support
Detail:
- ws/chat
- attachments
- AI suggestion
- client session

12. Approval Queue
Detail:
- approve flow
- reject flow
- queue sync
- audit log
- NATS publish

13. Pending Verification
Detail:
- validation source
- verification result
- health check
- rollback trigger

14. Rollback History
Detail:
- rollback persistence
- rollback source
- replay

15. Failed DLQ
Detail:
- DLQ source
- retry
- replay
- poison event

16. NATS Subjects
Detail:
- real introspection?
- hardcoded?
- active subjects?
- subscribers?

17. JetStream Streams
Detail:
- stream metadata
- consumer count
- retention
- ack policy
- max deliver

18. Learning Gate
Detail:
- gate conditions
- threshold
- embedding pipeline
- knowledge persistence

==================================================
FINAL OUTPUT FORMAT
==================================================

1. Dashboard Tree Structure
(menu → sub menu → widget → button → event)

2. Functional Matrix
| Menu | Widget | Function | Status | Data Source | Bug | Missing |

3. Broken Feature Matrix
List semua fitur broken per menu.

4. Hidden Missing Features
List semua fitur yang secara UI ada tapi backend kosong.

5. Event Backbone Gap Matrix
List:
- missing subject
- missing consumer
- missing publisher
- missing projection
- missing replay

6. Runtime Leak Matrix
List:
- chart leak
- websocket leak
- timer leak
- DOM leak

7. Security Gap Matrix
List:
- weak auth
- RBAC bypass
- exposed token
- unsafe endpoint

8. Production Readiness Score
Per menu.

Jangan beri summary singkat.
Buat detail sampai level widget.
Bongkar semuanya.