# AI GOVERNANCE CONSTITUTION
**Status:** FROZEN (Master Blueprint V12)
**Scope:** Learning Foundation & Intelligence Layer

Dokumen ini adalah "Konstitusi AI". Sebelum *Prediction Pack* (Phase 3) dan modul-modul cerdas lainnya diizinkan beroperasi, mereka harus tunduk mutlak pada regulasi tata kelola dalam dokumen ini. Tujuan konstitusi ini adalah memastikan bahwa AI dapat diaudit, terukur, dapat dijelaskan, dan selalu berada di bawah kendali manusia (*Human-in-the-Loop*).

## 1. AI Decision Governance (ADG)
Setiap insiden yang ditangkap akan melalui penilaian risiko (*Risk Score*) yang menentukan batas wewenang AI.

| Risk Level | Impact | AI Action Limits |
| :--- | :--- | :--- |
| **LOW** | Minor/Terisolasi | **Auto Execute** (Otonomi penuh diizinkan) |
| **MEDIUM** | Terbatas | **AI Recommendation** (Saran saja, butuh 1 Approval) |
| **HIGH** | Area Kritis | **HITL Mandatory** (Validasi manual mutlak) |
| **CRITICAL** | Core Infrastructure | **Multi Approval** (Dibutuhkan ≥ 2 Supervisor) |

## 2. AI Confidence Policy
Semua metrik *Confidence* (baik dari LF-2, LF-3, maupun Prediction Engine) merujuk pada standar baku berikut:

| Confidence Score | Engine Action |
| :---: | :--- |
| **≥ 0.95** | **Prediction Allowed / Auto** (Otonomi diizinkan bila Risiko LOW) |
| **0.82 - 0.94** | **Recommendation Only** (Sistem hanya memberi saran) |
| **0.70 - 0.81** | **Show Warning** (Tampilkan peringatan pada LOC/NOC) |
| **≤ 0.69** | **Reject** (Fitur/Prediksi dibuang agar tidak mencemari data) |

## 3. Knowledge Lifecycle
Pengetahuan (Knowledge) yang dipelajari AI tidak abadi. Ia tunduk pada siklus masa hidup untuk menghindari *Knowledge Drift*.

**Lifecycle Flow:**
`NEW` ➔ `VALIDATED` ➔ `ACTIVE` ➔ `AGING` ➔ `STALE` ➔ `ARCHIVED` ➔ `PURGED`

*   **NEW**: Baru ditangkap oleh ekstrator.
*   **VALIDATED**: Lolos validasi *Confidence* dan Skema.
*   **ACTIVE**: Sedang digunakan aktif oleh *Consensus* / *Prediction Engine*.
*   **AGING**: Usia data mulai mendekati akhir siklus (misal: 6 bulan).
*   **STALE**: Telah terjadi pergeseran pola (*Drift*). Pola sudah usang.
*   **ARCHIVED**: Dipindahkan ke *Cold Storage* untuk audit historis.
*   **PURGED**: Musnah secara kriptografis (jika data PII).

## 4. AI Explainability Contract
AIOps ini tidak menolerir logika *Black-Box*. Setiap tindakan otonom maupun saran (Recommendation) yang dilempar ke dasbor **WAJIB** mengandung 7 pilar *Explainability*.

**Contoh Output Wajib:**
*   **Decision**: `Restart service nginx on host-xyz`
*   **Reason**: `Confidence 94% - Memory Leak Detected`
*   **Evidence**: `CPU 99% (P95 Baseline 40%), Connection Refused (port 80)`
*   **Historical Success**: `91% success rate over 45 similar past incidents (LF-3)`
*   **Temporal Pattern**: `Not in Maintenance Window. Valid Business Hour (LF-5)`
*   **Policy**: `Auto Approved (Risk: LOW)`
*   **Risk**: `Medium (Blast radius isolated to single web node)`

---
*Konstitusi ini adalah pedoman tertinggi yang membedakan platform AIOps Enterprise dengan sekadar sistem prediksi cerdas.*
