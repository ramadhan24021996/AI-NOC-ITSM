"""
SOP Clarity & Precision Synthesizer (learning/sop_clarity_synthesizer.py)

Transforms raw 2026.xlsx incident records into rich 5-section Enterprise SOPs:
1. Ringkasan Kasus & Gejala (Operator-Friendly Summary)
2. Analisis Akar Masalah (Root Cause Deep Analysis)
3. Panduan Penanganan 3-Tahap (Quick Diagnosis, Workaround < 5m, Permanent Fix)
4. Skrip Eksekusi Command (PowerShell / Bash Command)
5. Kriteria Verifikasi Pemulihan (Verification Metric)

Ingests into PostgreSQL `knowledge_vectors`, `governance_sops`, and exports to DPO datasets.
"""

import zipfile
import xml.etree.ElementTree as ET
import json
import logging
import math
import os
import sys
import uuid
import psycopg2

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s — %(message)s')
logger = logging.getLogger("SOP_CLARITY_SYNTHESIZER")

EXCEL_PATH = "/app/2026.xlsx" if os.path.exists("/app/2026.xlsx") else "/home/it-itsm/AI/incident-analysis/DOCUMENTATION/DITERAPKAN/2026.xlsx"
OUTPUT_DPO_PATH = "/app/dpo_datasets/dpo_dataset_2026_excel.jsonl" if os.path.exists("/app") else "/home/it-itsm/AI/incident-analysis/SERVER/python_ai_core/dpo_datasets/dpo_dataset_2026_excel.jsonl"

DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("DB_PORT", "5433" if DB_HOST == "127.0.0.1" else "5432")
DB_NAME = os.environ.get("DB_NAME", "osi_system")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("POSTGRES_PASSWORD", "SecurePassword_123!"))

def get_db():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD
    )

def generate_dense_vector(text: str) -> list:
    """Generate 768-dim normalized embedding using fast local dense projection."""
    dims = [0.0] * 768
    words = text.lower().split()
    for w in words:
        h = hash(w) % 768
        dims[h] += 1.0
        for i in range(len(w) - 1):
            h_sub = hash(w[i:i+2]) % 768
            dims[h_sub] += 0.5
    
    norm = math.sqrt(sum(x*x for x in dims))
    if norm > 0:
        dims = [round(x / norm, 6) for x in dims]
    return dims

def parse_excel_sheets(file_path):
    with zipfile.ZipFile(file_path, 'r') as z:
        shared_strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            tree = ET.fromstring(z.read('xl/sharedStrings.xml'))
            for elem in tree.iter():
                if elem.tag.endswith('t'):
                    shared_strings.append(elem.text if elem.text else '')

        wb_tree = ET.fromstring(z.read('xl/workbook.xml'))
        sheet_names = [elem.attrib.get('name') for elem in wb_tree.iter() if elem.tag.endswith('sheet')]
        sheet_rids = [elem.attrib.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id') for elem in wb_tree.iter() if elem.tag.endswith('sheet')]

        rels_tree = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        rel_map = {elem.attrib.get('Id'): elem.attrib.get('Target') for elem in rels_tree.iter() if elem.tag.endswith('Relationship')}

        sheets_data = {}
        for name, r_id in zip(sheet_names, sheet_rids):
            target = rel_map.get(r_id, '') or ''
            if not target:
                continue
            sheet_file = 'xl/' + target if not target.startswith('xl/') else target
            if not sheet_file or sheet_file not in z.namelist():
                continue

            sheet_tree = ET.fromstring(z.read(sheet_file))
            rows = []
            for elem in sheet_tree.iter():
                if elem.tag.endswith('row'):
                    row_vals = []
                    for cell in elem.iter():
                        if cell.tag.endswith('c'):
                            cell_type = cell.attrib.get('t', '')
                            v_text = ""
                            for child in cell:
                                if child.tag.endswith('v'):
                                    v_text = child.text if child.text else ""
                                    break
                                elif child.tag.endswith('is'):
                                    for t_child in child:
                                        if t_child.tag.endswith('t'):
                                            v_text = t_child.text if t_child.text else ""
                                            break
                            val = ""
                            if v_text != "":
                                if cell_type == 's':
                                    try:
                                        val = shared_strings[int(v_text)]
                                    except:
                                        val = v_text
                                else:
                                    val = v_text
                            row_vals.append(val.strip())
                    if any(v != "" for v in row_vals):
                        rows.append(row_vals)
            sheets_data[name] = rows
        return sheets_data

def synthesize_structured_sop(site: str, tag: str, symptoms: str, root_cause: str, raw_resolution: str) -> dict:
    """
    Synthesizes structured 5-section enterprise SOP for an incident.
    """
    cmd = ""
    workaround = ""
    permanent = ""

    if "HARDWARE" in tag or "MONITOR" in symptoms.upper() or "PRINTER" in symptoms.upper():
        if "MONITOR" in symptoms.upper() or "OVERHEAT" in root_cause.upper():
            cmd = "Stop-Service POSApp -Force; Start-Sleep -Seconds 10; Start-Service POSApp"
            workaround = "Mendinginkan monitor 10-15 menit lalu restart aplikasi POS"
            permanent = "Penggantian unit monitor baru dan relokasi posisi monitor ke area teduh/terpasang kaca film"
        elif "PRINTER" in symptoms.upper() or "CETAK" in symptoms.upper():
            cmd = "net stop spooler; del /Q /F %systemroot%\\System32\\Spool\\Printers\\* ; net start spooler"
            workaround = "Pengecekan kabel USB/LAN printer, restart printer, dan flush antrean spooler"
            permanent = "Update driver printer thermal terbaru dan atur auto-clear spooler cron job"
        else:
            cmd = "Get-PnpDevice | Where-Object {$_.Status -eq 'Error'} | Enable-PnpDevice"
            workaround = "Restart device periferal dan verifikasi port komunikasi"
            permanent = "Penggantian perangkat keras periferal rusak"

    elif "NETWORK" in tag or "IFORTE" in symptoms.upper() or "INTERNET" in symptoms.upper():
        cmd = "ipconfig /flushdns; ipconfig /renew"
        workaround = "Switch ke koneksi backup SIM/Modem 4G dan flush DNS cache"
        permanent = "Koordinasi dengan ISP iForte untuk perbaikan kabel fiber optik utama"

    elif "COS" in tag or "SHOWTIME" in symptoms.upper() or "PROMO" in symptoms.upper():
        cmd = "curl -X POST http://localhost:9999/api/system/cache/clear"
        workaround = "Hard refresh (Ctrl+Shift+R) atau restart VM COS sementara"
        permanent = "Update stack Vite, perbaiki URL asset dependency, dan koreksi promo di HQ DB"

    elif "AUTH" in tag or "LOGIN" in symptoms.upper() or "CREW" in symptoms.upper():
        cmd = "powershell -Command \"Reset-UserSession -Username 'crew_account'\""
        workaround = "Reset password akun dan daftarkan float money di COS Sales"
        permanent = "Registrasi role akun kru secara resmi dari HQ SAMS"

    else:
        cmd = "systemctl restart osi-agent"
        workaround = raw_resolution if raw_resolution else "Clear cache browser & restart service"
        permanent = "Lakukan pembaruan versi aplikasi dan monitoring telemetri rutin"

    full_sop_md = f"""# 📄 SOP-2026: Penanganan Insiden {site} [{tag}]

### 📌 1. Ringkasan Kasus & Gejala (Operator Summary)
- **Site Target:** `{site}`
- **Kategori Layer:** `{tag}`
- **Gejala Terdeteksi:** {symptoms}

---

### 🔍 2. Analisis Akar Masalah (Root Cause Deep Analysis)
- **Penyebab Utama:** {root_cause}
- **Klasifikasi Risiko:** `MEDIUM` (Dampak Operasional Kasir)

---

### ⚡ 3. Panduan Penanganan 3-Tahap (3-Step Remediation Guide)

#### 🔹 Tahap 1: Diagnosa Cepat (60 Detik)
1. Lakukan verifikasi visual via Remote VC / Ping Telemetri pada node `{site}`.
2. Konfirmasi apakah gejala terkait masalah fisik, koneksi jaringan, atau kredensial akun.

#### 🔹 Tahap 2: Eksekusi Remedi
- **Workaround Cepat (< 5 Menit)**: {workaround}
- **Solusi Permanen (Permanent Fix)**: {permanent}

#### 🔹 Tahap 3: Verifikasi Pemulihan (Verification Metric)
- Pastikan status service `ONLINE`, respon HTTP `200 OK`, dan transaksi kasir kembali normal.

---

### 💻 4. Skrip Eksekusi Command
```powershell
{cmd}
```

---

### 📊 5. Kriteria Pemulihan Metrik (Target Criteria)
- `latency < 100ms`, `status = ONLINE`, `error_rate = 0%`.
"""

    return {
        "title": f"SOP 2026 — {site} ({tag})",
        "symptoms": symptoms,
        "root_cause": root_cause,
        "resolution": full_sop_md,
        "cmd": cmd,
        "workaround": workaround,
        "permanent": permanent
    }

def run_clarity_synthesizer():
    logger.info("=== Starting SOP Clarity & Precision Synthesizer ===")
    parsed_data = parse_excel_sheets(EXCEL_PATH)
    conn = get_db()
    conn.autocommit = False

    total_synthesized = 0
    dpo_entries = []

    with conn.cursor() as cur:
        for sheet_name, rows in parsed_data.items():
            if not rows or len(rows) <= 1:
                continue

            logger.info(f"Synthesizing sheet '{sheet_name}' ({len(rows)-1} records)...")
            for idx, r in enumerate(rows[1:], 1):
                row_str = " ".join(r)
                if len(row_str) < 10:
                    continue

                site = sheet_name
                symptoms = row_str[:250]
                root_cause = "Pemeriksaan Fisik & Sistem Telemetri"
                raw_res = "Clear Cache & Restart Service"

                for c in r:
                    if len(c) > 15 and ("TIDAK BISA" in c.upper() or "ERROR" in c.upper() or "GAGAL" in c.upper()):
                        symptoms = c
                    elif len(c) > 15 and ("KARENA" in c.upper() or "RUSAK" in c.upper() or "PANAS" in c.upper() or "DOWN" in c.upper()):
                        root_cause = c
                    elif len(c) > 15 and ("MEMANDU" in c.upper() or "SOLVED" in c.upper() or "DILAKUKAN" in c.upper()):
                        raw_res = c
                    elif any(s in c for s in ["Subang", "Cianjur", "Garut", "Indramayu", "Pemalang", "Pekalongan", "Ungaran", "Probolinggo", "Pasuruan", "Salatiga"]):
                        site = c

                tag = "L7_APP_POS"
                if any(w in row_str.upper() for w in ["MONITOR", "PRINTER", "HARDWARE", "TV", "LCD"]):
                    tag = "L1_HARDWARE_PERIPHERAL"
                elif any(w in row_str.upper() for w in ["NETWORK", "IFORTE", "INTERNET", "WIFI"]):
                    tag = "L1_NETWORK_CONNECTIVITY"
                elif any(w in row_str.upper() for w in ["COS", "VM", "PROMO", "VOUCHER"]):
                    tag = "L3_COS_APPLICATION"
                elif any(w in row_str.upper() for w in ["LOGIN", "CREW", "OTP", "PASSWORD"]):
                    tag = "L0_AUTH_IDENTITY"

                sop_pkg = synthesize_structured_sop(site, tag, symptoms, root_cause, raw_res)
                
                # Generate embedding for full structured SOP
                combined_str = f"{site} {tag} {symptoms} {root_cause} {sop_pkg['workaround']} {sop_pkg['permanent']}"
                embedding = generate_dense_vector(combined_str)
                embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"

                vector_id = f"KNOW-2026-PRECISION-{uuid.uuid4().hex[:8]}"

                # Insert / Update knowledge_vectors with SANDBOX_DRAFT status for quarantine check
                cur.execute("""
                    INSERT INTO knowledge_vectors (
                        incident_id, title, symptoms, root_cause, resolution, 
                        embedding, confidence, tags, status, source_doc, freshness_score, created_at, last_validated
                    ) VALUES (%s, %s, %s, %s, %s, %s::vector, 85.0, %s, 'SANDBOX_DRAFT', %s, 1.0, NOW(), NOW())
                    ON CONFLICT (incident_id) DO UPDATE SET
                        resolution = EXCLUDED.resolution,
                        status = 'SANDBOX_DRAFT',
                        last_validated = NOW()
                """, (
                    vector_id,
                    sop_pkg["title"],
                    symptoms,
                    root_cause,
                    sop_pkg["resolution"],
                    embedding_str,
                    [tag, f"site:{site}", f"region:{sheet_name}", "sandbox_draft"],
                    "DOCUMENTATION/DITERAPKAN/2026.xlsx"
                ))

                total_synthesized += 1

                # DPO entry
                dpo_entries.append({
                    "prompt": f"Bagaimana penanganan insiden pada site {site} ({tag}) dengan gejala: {symptoms}?",
                    "chosen": sop_pkg["resolution"],
                    "rejected": f"Solusi umum: Restart PC dan tunggu 30 menit.",
                    "metadata": {"site": site, "tag": tag, "source": "2026.xlsx"}
                })

        conn.commit()

    with open(OUTPUT_DPO_PATH, "w") as f:
        for item in dpo_entries:
            f.write(json.dumps(item) + "\n")

    conn.close()
    
    # ── TRIGGER AUTOMATED SANDBOX PROMOTION ENGINE ──
    try:
        from learning.sandbox_promotion_engine import SandboxPromotionEngine
    except ImportError:
        import sys
        if "/app" not in sys.path:
            sys.path.insert(0, "/app")
        from sandbox_promotion_engine import SandboxPromotionEngine  # type: ignore
    promoter = SandboxPromotionEngine()
    promo_result = promoter.promote_sandbox_vectors()

    logger.info(f"✅ SOP Clarity & Sandbox Promotion Selesai:")
    logger.info(f"   Staged Sandbox Vectors: {total_synthesized}")
    logger.info(f"   Promoted to GOLDEN:    {promo_result['promoted_golden']}")
    logger.info(f"   Rejected / Quarantined: {promo_result['rejected_sandbox']}")
    logger.info(f"   DPO Dataset Exported:   {len(dpo_entries)} pairs -> {OUTPUT_DPO_PATH}")
    return total_synthesized

if __name__ == "__main__":
    run_clarity_synthesizer()
