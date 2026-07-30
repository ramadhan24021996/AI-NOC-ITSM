# Enterprise AIOps Architecture Roadmap

Berdasarkan evaluasi arsitektur dan kebutuhan skala *Enterprise*, berikut adalah *roadmap* pengembangan OSI AI Ops untuk fase selanjutnya.

## Sprint P: Enterprise Evidence Fabric (Priority 1)
Fokus utama: Membangun kepastian data sebelum proses penalaran AI (*Reasoning*) dimulai.
*   **Evidence Validation:** Deteksi kelengkapan telemetri, sinkronisasi *timestamp*, dan validitas host. Menghasilkan status `Need More Evidence` jika data tidak cukup.
*   **Evidence Quality Score:** Perhitungan skor reliabilitas bukti (Source Reliability, Timestamp Accuracy, Completeness, Cross Validation, Freshness).
*   **Evidence Conflict Detection:** Sistem deteksi kontradiksi antar-agen (misal: SNMP bilang DOWN, Log bilang UP).
*   **Evidence Graph & Timeline:** Rekonstruksi urutan kejadian (kronologi) dan hubungan kausalitas antar bukti sebelum disuapkan ke *Causal Engine*.
*   **Evidence Explorer Dashboard:** Antarmuka khusus di NOC Dashboard untuk mengaudit seluruh bukti mentah dan tervalidasi.

## Sprint Q: Dynamic Knowledge Graph
Fokus utama: Konteks infrastruktur dan relasi antar aset.
*   **CMDB Integration:** Sinkronisasi dengan *Configuration Management Database*.
*   **Asset Relationship Engine:** Pemetaan ketergantungan dinamis (Server A terhubung ke Switch B dan berimbas ke Layanan C).
*   **Root Cause Traversal:** Rekonstruksi visual jalur kegagalan dari ujung ke ujung.

## Sprint Q.5: Enterprise Topology Discovery
Fokus utama: Penemuan aset dan topologi secara otonom (Discovery Engine).
*   **Multi-Protocol Discovery:** LLDP, CDP, SNMP Walk.
*   **Platform Discovery:** VMware, Hyper-V, Kubernetes, Docker.
*   **Service Discovery:** Windows AD, PostgreSQL, DNS, Service Mesh.
*   **Continuous Updates:** Sinkronisasi dan versi graph secara real-time.

## Sprint R: Predictive Analytics & Time-Series AI
Fokus utama: Mencegah insiden sebelum terjadi.
*   **Failure Prediction:** Analisa pola kerusakan dari data historis.
*   **Capacity Forecasting:** Prediksi kehabisan memori, penyimpanan, atau *bandwidth*.

## Sprint S: AI Evaluation Platform
Fokus utama: Validasi model dan dataset.
*   **Offline Benchmark:** Pengujian model LLM terhadap dataset statis.
*   **Replay Engine:** Simulasi ulang insiden masa lalu untuk menguji respons AI.
*   **Gold Dataset Testing:** Validasi performa menggunakan dataset standar emas.

## Sprint T: Multi-Agent Orchestrator
Fokus utama: Desentralisasi spesialisasi kognitif.
*   **Specialized AI Agents:** Pemisahan *agent* berdasarkan domain (Network Agent, Database Agent, Security Agent, Cloud Agent).
*   **Final Consensus Layer:** Lapisan dewan juri tempat para *specialized agents* berdebat dan mengambil keputusan mutlak.
