# ==========================================================
# ENTERPRISE AIOPS COGNITIVE RAG ENGINE (V2)
# STATUS: BLUEPRINT / ROADMAP
# ==========================================================

Dokumen ini mendefinisikan arsitektur "Knowledge Retrieval Engine" tingkat lanjut yang bergeser dari sekadar Vector Search menjadi Evidence-Driven, Context-Aware Retrieval.

## 1. DYNAMIC OPERATIONAL METADATA
Metadata statis tidak cukup. RAG V2 harus menyimpan dan memfilter berdasarkan kondisi realitas operasional.

```json
{
  "vendor": "HP",
  "model": "LaserJet M404dn",
  "firmware": "3.9.4",
  "driver": "PCL6",
  "os": "Windows 11",
  "site": "HQ",
  "criticality": "HIGH",
  "device_role": "Accounting Printer",
  "confidence": 0.96,
  "source": "Vendor Manual",
  "last_verified": "2026-07-16"
}
```

## 2. MULTI-STAGE RETRIEVAL PIPELINE
Pencarian harus bertingkat, tidak langsung menebak menggunakan Vector.
`Asset Context -> Intent Classification -> OSI Layer -> Device -> Vendor -> Metadata Filter -> Vector Search -> Graph Search -> Historical Incident -> Playbook -> LLM`

## 3. DEVICE TAXONOMY
Embedding dan pencarian harus dibatasi pada Sub-Tree yang relevan.
```text
Endpoint
 ├── Windows / Linux / MacOS
Printer
 ├── HP / Epson / Canon
Switch
 ├── Cisco / Aruba / Juniper
Firewall
 ├── Fortigate / Palo Alto / Mikrotik
```

## 4. HYBRID RETRIEVAL
Meninggalkan Vector-Only. Menggabungkan:
1. **BM25** (Sangat krusial untuk Exact Match Error Code seperti `0x0000011B`)
2. **Vector Search** (Semantic similarity)
3. **Knowledge Graph** (Relasi Topologi)
4. **Incident Similarity** (Riwayat masa lalu)
5. **Playbook Ranking & Engineer Feedback (RLHF)**

## 5. INCIDENT FINGERPRINTING
Merekam pola insiden secara utuh.
Contoh Fingerprint: `Printer -> TCP9100 Timeout -> Win11 -> HP -> Firmware 4.3 -> Fortigate -> HQ`
Jika fingerprint identik muncul (Similarity 99.6%), sistem tidak perlu berfikir ulang (Zero-Shot Auto-Resolve).

## 6. DEEP GRAPHRAG (DEPENDENCY + PROTOCOL)
Graph bukan sekadar relasi aset, tapi hingga ke level Service dan Protokol.
`Printer -> Driver -> Spooler -> Port9100 -> IPP -> SMB -> SNMP`
Memungkinkan AI menyimpulkan: *"Printer tidak rusak, tetapi Port 9100 diblokir firewall 17 menit lalu."*

## 7. TEMPORAL RAG
RAG harus sadar kronologi (Waktu).
`08:15 Switch Restart -> 08:16 Printer Offline -> 08:17 Spooler Error -> 08:18 User Complaint`

## 8. EVIDENCE-AWARE RETRIEVAL
RAG tidak boleh dipanggil sebelum Evidence matang.
Jika `Evidence = RSSI -89, Link Down, CRC Error` (Layer 1), sistem tidak boleh melakukan retrieval terhadap SOP Windows Print Spooler (Layer 7). Retrieval harus terkunci pada filter Layer 1.

## 9. CONFIDENCE-BASED RETRIEVAL (ADAPTIVE-K)
* Jika Confidence = `0.41` -> Ambil referensi lebih banyak (Vendor docs, graph traversal, riwayat).
* Jika Confidence = `0.98` -> Ambil 1 Playbook terbaik saja.

## 10. MULTI-AGENT RETRIEVAL
Memisahkan RAG besar menjadi domain spesifik:
`RAG OSI L1`, `RAG Windows`, `RAG Cisco`, `RAG Security`.
Diakhiri dengan `Consensus Engine` untuk memilih jawaban terbaik.

---
**KESIMPULAN:**
RAG AIOps berfungsi sebagai `Knowledge Retrieval Engine` yang hanya mengambil informasi yang relevan dengan konteks insiden (Bukti, Topologi, Waktu, dan Fingerprint). Hal ini memusnahkan risiko halusinasi dan meroketkan akurasi diagnosis.
