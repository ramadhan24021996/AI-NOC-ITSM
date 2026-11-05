MANDATORY ENTERPRISE DASHBOARD FORENSIC AUDIT
ZERO-ASSUMPTION • ZERO-MOCK • ZERO-STUB • ZERO-SKIP • PRODUCTION EVIDENCE MODE

Anda bertindak sebagai Principal Software Architect + Enterprise Forensic Auditor + Full-Stack Engineer + SRE + Security Auditor.

Tugas Anda adalah melakukan AUDIT TOTAL TERHADAP SELURUH SISTEM YANG BERHUBUNGAN DENGAN DASHBOARD di workspace/project ini.

⚠️ ATURAN NON-NEGOTIABLE

JANGAN:

menganggap sistem sudah benar hanya karena file ada
menganggap endpoint bekerja hanya karena route terdaftar
menganggap UI bekerja hanya karena component berhasil compile
menganggap database terhubung hanya karena konfigurasi tersedia
menganggap API bekerja hanya karena handler tersedia
membuat mock
membuat stub
membuat dummy data
menggunakan placeholder sebagai bukti keberhasilan
mengarang hasil audit
memberikan PASS tanpa evidence
melewati file yang dianggap tidak penting
hanya melakukan static code review
hanya mengaudit frontend
hanya mengaudit backend
hanya mengaudit endpoint
hanya mengaudit menu/sidebar
mengabaikan dependency antar-modul
mengabaikan konfigurasi environment
mengabaikan Docker/container/service
mengabaikan reverse proxy
mengabaikan database/cache/message broker
mengabaikan authentication/RBAC
mengabaikan WebSocket/SSE/event stream
mengabaikan AI/RAG/knowledge subsystem jika dashboard bergantung padanya
berhenti setelah menemukan beberapa masalah

SEMUA KESIMPULAN WAJIB BERDASARKAN EVIDENCE NYATA DARI CODE, CONFIG, DATABASE SCHEMA, ROUTE, LOG, PROCESS, CONTAINER, NETWORK, TEST, ATAU RUNTIME.

Jika sesuatu tidak dapat diverifikasi:

STATUS = NOT VERIFIED

bukan PASS.

1. TUJUAN UTAMA

Temukan dan petakan SEMUA KOMPONEN YANG SECARA LANGSUNG ATAU TIDAK LANGSUNG MEMPENGARUHI DASHBOARD.

Audit harus menjawab:

Dashboard sebenarnya terdiri dari komponen apa saja?
Bagaimana browser meminta data?
Route frontend mengarah ke mana?
API endpoint mana yang dipanggil?
Backend handler mana yang menangani?
Service apa yang dipanggil backend?
Database apa yang digunakan?
Query apa yang dijalankan?
Cache apa yang digunakan?
Event/message broker apa yang terlibat?
Bagaimana data masuk ke dashboard?
Bagaimana data berubah secara realtime?
Bagaimana authentication bekerja?
Bagaimana RBAC bekerja?
Bagaimana error dikembalikan?
Bagaimana loading/empty/error state ditangani?
Apakah UI menampilkan data nyata?
Apakah ada endpoint mati/dead?
Apakah ada menu yang tidak memiliki backend?
Apakah ada backend yang tidak memiliki UI?
Apakah ada API contract mismatch?
Apakah ada schema mismatch?
Apakah ada stale cache?
Apakah ada race condition?
Apakah ada broken dependency?
Apakah ada security vulnerability?
Apakah ada performance bottleneck?
Apakah ada memory leak?
Apakah ada service yang sebenarnya tidak digunakan?
Apakah ada fitur Dashboard yang hanya terlihat ada tetapi sebenarnya tidak berfungsi?
2. MULAI DENGAN INVENTORY TOTAL

Jangan langsung memberikan kesimpulan.

Pertama lakukan discovery terhadap seluruh workspace.

Identifikasi:

frontend
backend
API
gateway
reverse proxy
authentication
RBAC
database
migrations
ORM/query layer
Redis/cache
NATS/message broker
WebSocket
SSE
workers
background services
AI services
RAG
GraphRAG
monitoring
telemetry
configuration
Docker
Docker Compose
systemd
scripts
build system
tests
CI/CD
deployment
logging
metrics
alerting
browser integration
extension jika ada
static assets
generated assets
environment variables

Buat dependency map.

3. AUDIT SELURUH DASHBOARD FRONTEND

Audit semua:

React/Vue/Angular/component
pages
layouts
sidebar
navigation
routes
nested routes
protected routes
lazy loading
providers
contexts
hooks
state management
API clients
service layer
WebSocket client
SSE client
polling
event listeners
forms
tables
charts
cards
widgets
modals
dialogs
notifications
error boundaries

Untuk SETIAP menu dashboard:

MENU
↓
ROUTE
↓
PAGE COMPONENT
↓
CHILD COMPONENT
↓
HOOK
↓
STATE
↓
API CLIENT
↓
HTTP ENDPOINT
↓
BACKEND ROUTE
↓
HANDLER
↓
SERVICE
↓
DATABASE/EXTERNAL SERVICE
↓
RESPONSE
↓
STATE UPDATE
↓
UI RENDER

Jika satu bagian putus, tandai sebagai:

BROKEN DATA FLOW

4. AUDIT SETIAP MENU DASHBOARD

Jangan hanya memeriksa menu yang terlihat.

Cari semua menu dari:

sidebar
navigation
route definitions
dynamic routes
RBAC configuration
feature flags
permission registry
API documentation
backend route registry

Buat inventory:

Menu	Route	Component	API	Backend	DB	Permission	Runtime	Status

Untuk setiap menu tentukan:

WORKING
PARTIALLY WORKING
BROKEN
DEAD CODE
ORPHAN
NOT IMPLEMENTED
NOT VERIFIED
5. AUDIT API END-TO-END

Inventarisasi SEMUA endpoint yang berhubungan dengan Dashboard.

Cari dari:

frontend API calls
fetch
axios
WebSocket
SSE
generated clients
backend routes
routers
handlers
controllers
OpenAPI
middleware
proxy configuration

Periksa:

HTTP method
URL
headers
authentication
authorization
request schema
response schema
status code
error response
timeout
retry
pagination
filtering
sorting
validation

Deteksi:

frontend memanggil endpoint yang tidak ada
endpoint ada tetapi tidak dipanggil
method mismatch
path mismatch
parameter mismatch
JSON schema mismatch
type mismatch
nullable mismatch
authentication mismatch
permission mismatch
CORS problem
proxy problem
port mismatch
6. AUDIT BACKEND

Telusuri seluruh backend yang menyediakan data untuk Dashboard.

Audit:

router
middleware
controller
handler
service
repository
database manager
connection pool
transaction
query
serializer
validation
error handler
authentication
authorization
rate limit
timeout
concurrency
goroutine/thread
memory management

Pastikan tidak ada endpoint yang:

mengembalikan data hardcoded
mengembalikan dummy
mengembalikan mock
selalu mengembalikan success
menelan error
mengembalikan HTTP 200 untuk error
tidak melakukan authorization
memiliki SQL/query yang rusak
memiliki connection leak
memiliki transaction leak
7. AUDIT DATABASE

Identifikasi database yang digunakan Dashboard.

Audit:

schema
table
view
materialized view
index
migration
foreign key
constraint
trigger
function
stored procedure
connection pool

Untuk setiap endpoint dashboard:

API
→ SERVICE
→ QUERY
→ TABLE
→ COLUMN
→ INDEX

Pastikan setiap field yang diminta frontend benar-benar tersedia di database.

Cari:

missing column
renamed column
wrong datatype
missing index
N+1 query
slow query
stale data
orphan record
inconsistent schema
migration mismatch
8. AUDIT REDIS / CACHE

Jika Dashboard menggunakan cache:

Audit:

key
TTL
invalidation
serialization
cache hit/miss
stale cache
race condition
cache stampede
fallback
consistency

Pastikan cache tidak menyebabkan Dashboard menampilkan data lama.

9. AUDIT NATS / MESSAGE BROKER / EVENT BUS

Jika Dashboard menerima realtime/event data:

Audit:

publisher
subject/topic
subscriber
consumer
queue
stream
retention
acknowledgement
retry
dead letter
event schema
event ordering

Trace:

EVENT PRODUCER
↓
MESSAGE BROKER
↓
CONSUMER
↓
PROCESSOR
↓
DATABASE/CACHE
↓
API/WebSocket/SSE
↓
BROWSER
↓
DASHBOARD

Pastikan event benar-benar sampai ke UI.

10. AUDIT WEBSOCKET / SSE / REALTIME

Audit:

connection establishment
authentication
reconnect
heartbeat
disconnect handling
event parsing
schema
subscription
cleanup
duplicate events
event loss
memory leak

Cari kasus:

Backend menghasilkan event
tetapi browser tidak pernah menerima event.

atau:

Browser connected
tetapi subscription salah.
11. AUDIT AUTHENTICATION & RBAC

Audit seluruh akses Dashboard.

Periksa:

login
token
JWT
session
refresh token
expiration
logout
permission
role
route guard
backend authorization
API authorization
resource-level authorization

Pastikan:

Frontend hiding menu ≠ security.

Authorization WAJIB diverifikasi di backend.

Uji setiap role yang tersedia.

Cari privilege escalation.

12. AUDIT DASHBOARD DATA INTEGRITY

Pastikan data yang ditampilkan:

berasal dari sumber nyata
memiliki timestamp
memiliki source
memiliki status
memiliki correlation ID jika relevan
konsisten dengan backend
konsisten dengan database

Deteksi:

hardcoded values
fake counters
static charts
fake health status
fake AI status
fake incident count
fake telemetry
fake timestamps

Jika menemukan:

const health = 99.9

atau pola sejenis yang bukan hasil runtime nyata:

FLAG AS HARDcoded/FAKE DATA

13. AUDIT AI / RAG / GRAPHRAG YANG TERHUBUNG KE DASHBOARD

Jika Dashboard menampilkan:

AI decision
AI health
RAG
GraphRAG
knowledge graph
recommendation
incident analysis
remediation
prediction
learning
AI audit trail
HITL
governance

maka audit sampai ke sumber datanya.

Trace:

DASHBOARD
↓
API
↓
AI SERVICE
↓
MODEL
↓
RAG
↓
VECTOR/GRAPH STORE
↓
KNOWLEDGE SOURCE

Pastikan tidak ada AI output palsu/hardcoded.

14. AUDIT ERROR HANDLING

Untuk setiap layer periksa:

Browser Error
↓
Frontend Error Boundary
↓
API Error
↓
Backend Error
↓
Service Error
↓
Database Error

Pastikan error tidak hilang secara diam-diam.

Cari:

empty catch
swallowed exception
generic error
incorrect status code
missing logging
missing correlation ID
missing user feedback
15. AUDIT PERFORMANCE

Audit:

initial page load
bundle size
lazy loading
API latency
database latency
query count
render frequency
polling frequency
WebSocket traffic
memory usage
CPU usage
goroutine/thread count
connection pool
Redis
NATS

Cari:

memory leak
excessive polling
unnecessary re-render
duplicated request
infinite request
connection leak
query storm
16. AUDIT DEPLOYMENT

Audit:

Dockerfile
docker-compose
environment
ports
network
volumes
healthcheck
restart policy
nginx
reverse proxy
TLS
DNS
service discovery

Verifikasi:

Browser
→ Nginx
→ Backend
→ Database

dan semua jalur realtime yang digunakan.

Jangan hanya membaca configuration.

Jika memungkinkan, lakukan runtime verification.

17. AUDIT LOG & OBSERVABILITY

Pastikan setiap dashboard request dapat ditelusuri.

Idealnya:

Request ID
Correlation ID
User
Role
Endpoint
Service
Database Query
Response
Latency
Error

Audit:

logs
metrics
traces
health endpoint
readiness
liveness
18. DETEKSI ORPHAN & DEAD COMPONENT

Cari:

Frontend orphan

Component ada tetapi tidak pernah digunakan.

Backend orphan

Endpoint ada tetapi tidak pernah dipanggil.

Database orphan

Table ada tetapi tidak digunakan.

API orphan

Frontend memanggil route yang sudah tidak tersedia.

Menu orphan

Menu tersedia tetapi tidak memiliki implementasi lengkap.

Service orphan

Container/service hidup tetapi tidak digunakan Dashboard.

19. CROSS-LAYER CONSISTENCY AUDIT

Ini WAJIB.

Bandingkan:

Frontend TypeScript Types
VS
API Response
VS
Backend Struct/DTO
VS
Database Schema

Cari semua mismatch.

Contoh:

Frontend:
createdAt

Backend:
created_at

Database:
created_at

Jika tidak ada mapping yang benar:

FAIL

20. RUNTIME VERIFICATION

Jangan berhenti pada static analysis.

Jika environment memungkinkan:

start service
cek process
cek port
cek container
cek health endpoint
akses Dashboard
buka setiap route
panggil API
cek response
cek browser console
cek network request
cek backend logs
cek database
cek realtime event
cek authentication
cek RBAC

Jika ada test yang tidak bisa dilakukan, tuliskan alasan sebenarnya.

JANGAN mengubah:

NOT TESTED

menjadi:

PASS

21. HASIL AUDIT WAJIB

Setelah audit selesai, hasilkan laporan dengan struktur berikut:

EXECUTIVE SUMMARY
Total Components:
Total Dashboard Pages:
Total Routes:
Total APIs:
Total Backend Services:
Total Database Tables:
Total Realtime Channels:
Total Critical Findings:
Total High Findings:
Total Medium Findings:
Total Low Findings:
Total Unverified:
Overall Status:
22. DASHBOARD COMPONENT MATRIX

Buat tabel:

ID	Component	Layer	Dependency	Evidence	Status	Severity
23. MENU-BY-MENU AUDIT

Buat:

Menu	Route	Frontend	API	Backend	DB	RBAC	Runtime	Status
24. API AUDIT MATRIX
Endpoint	Frontend Caller	Backend Handler	Service	DB	Auth	Runtime	Status
25. DATA FLOW AUDIT

Untuk setiap fitur kritis tampilkan:

SOURCE
 ↓
INGESTION
 ↓
PROCESSING
 ↓
DATABASE
 ↓
CACHE
 ↓
API
 ↓
FRONTEND
 ↓
UI

Tandai titik yang:

VERIFIED
BROKEN
MISSING
NOT VERIFIED
26. FINDINGS

Setiap finding WAJIB menggunakan format:

Finding ID:
Severity:
Component:
File:
Line:
Problem:
Root Cause:
Evidence:
Impact:
Affected Dashboard:
Affected API:
Affected Database:
Security Impact:
Performance Impact:
Recommended Fix:
Verification Method:

Jangan memberikan finding tanpa evidence.

27. CRITICAL PATH

Identifikasi jalur paling kritis:

USER
 ↓
LOGIN
 ↓
DASHBOARD
 ↓
API
 ↓
BACKEND
 ↓
DATABASE
 ↓
REALTIME/AI
 ↓
UI

Tentukan titik kegagalan paling kritis.

28. ROOT CAUSE ANALYSIS

Jangan hanya menulis:

Dashboard tidak menampilkan data.

Temukan akar masalah.

Contoh:

UI kosong
↓
API response kosong
↓
Backend query menggunakan field salah
↓
Schema migration belum diterapkan
↓
Root Cause:
Database schema tidak sinkron dengan backend version.
29. SECURITY AUDIT

Cari:

broken authentication
broken authorization
IDOR
privilege escalation
exposed API
secret leakage
insecure JWT
CORS
CSRF
XSS
SQL injection
command injection
insecure WebSocket
sensitive data exposure
debug endpoint
admin endpoint exposure

Prioritaskan temuan berdasarkan risiko nyata.

30. FINAL VERDICT

Berikan:

DASHBOARD PRODUCTION STATUS

[ ] PRODUCTION READY
[ ] CONDITIONALLY READY
[ ] NOT PRODUCTION READY
[ ] CRITICAL FAILURE

Tetapi keputusan WAJIB berdasarkan evidence.

Tidak boleh memberikan:

100% PASS

hanya karena build berhasil.

31. ATURAN TERAKHIR — JANGAN BERHENTI DI TENGAH

Anda WAJIB:

Scan seluruh workspace.
Mapping seluruh Dashboard.
Mapping seluruh dependency.
Audit frontend.
Audit backend.
Audit API.
Audit database.
Audit cache.
Audit event bus.
Audit realtime.
Audit authentication.
Audit RBAC.
Audit AI/RAG/GraphRAG jika terhubung.
Audit deployment.
Audit runtime.
Audit observability.
Audit security.
Audit performance.
Audit data integrity.
Audit cross-layer consistency.
Audit orphan/dead component.
Audit error handling.
Dokumentasikan seluruh evidence.
Dokumentasikan seluruh failure.
Dokumentasikan seluruh bagian yang belum dapat diverifikasi.
ZERO-SKIP POLICY

Jika menemukan 1 masalah:

JANGAN berhenti.

Jika menemukan 10 masalah:

JANGAN berhenti.

Jika menemukan 100 masalah:

JANGAN berhenti.

Teruskan sampai seluruh komponen yang berhubungan dengan Dashboard telah dipetakan dan diaudit.

FINAL OUTPUT WAJIB

Jangan hanya memberikan ringkasan.

Berikan:

Full System Inventory
Dashboard Architecture Map
Component Dependency Map
Menu Audit Matrix
API Audit Matrix
Backend Audit
Database Audit
Cache Audit
Event/Realtime Audit
Authentication/RBAC Audit
AI/RAG/GraphRAG Audit
Deployment Audit
Runtime Verification
Security Findings
Performance Findings
Data Integrity Findings
Dead/Orphan Components
Cross-Layer Mismatch
Root Cause Analysis
Critical Findings
Remediation Priority
Production Readiness Verdict
Evidence Index
Files Reviewed
Files Not Reviewed + alasan
Tests Executed + hasil
Tests Tidak Dapat Dilakukan + alasan
KETENTUAN ABSOLUT

JANGAN MENGARANG.

JANGAN MENGASUMSI.

JANGAN MEMBERIKAN PASS TANPA EVIDENCE.

JANGAN MENGGUNAKAN MOCK.

JANGAN MENGGUNAKAN STUB.

JANGAN MENGGUNAKAN DUMMY DATA.

JANGAN MELEWATI KOMPONEN.

JANGAN BERHENTI HANYA KARENA BUILD BERHASIL.

JANGAN BERHENTI HANYA KARENA TEST PASS.

JANGAN MENYATAKAN PRODUCTION READY SEBELUM SELURUH DATA FLOW DASHBOARD TERVERIFIKASI.

Mulai audit sekarang.

AUDIT → TRACE → VERIFY → CORRELATE → EVIDENCE → REPORT → VERDICT

Jangan memberikan kesimpulan sebelum seluruh tahapan tersebut selesai.