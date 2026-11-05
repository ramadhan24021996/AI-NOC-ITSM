-- =============================================================================
-- Migration: 012_add_enterprise_aiops_tools.sql
-- Description: Register 17 Enterprise AIOps Diagnostic & Operational Tools
-- Pattern: Capability-Based Command Gateway (Whitelist, RBAC, HITL, Audit Log)
-- Author: Principal AI Architect
-- =============================================================================

INSERT INTO jarvis_tools_registry (
    tool_id, tool_name, category, description, risk_level, requires_approval, requires_hitl, parameter_schema, rollback_procedure
) VALUES
(
    'ping',
    'ICMP Ping Diagnostics',
    'NETWORK',
    'Uji latensi konektivitas jaringan dan persentase packet loss ke IP/hostname tujuan (contoh: 8.8.8.8 atau google.com).',
    'LOW', FALSE, FALSE,
    '{"target": "string", "count": "int"}'::jsonb,
    'N/A (Tool diagnostik read-only)'
),
(
    'dir',
    'Directory Listing Diagnostics',
    'FILE_SYSTEM',
    'Menampilkan daftar berkas, direktori, ukuran, dan tanggal modifikasi pada path tertentu.',
    'LOW', FALSE, FALSE,
    '{"path": "string"}'::jsonb,
    'N/A (Tool diagnostik read-only)'
),
(
    'type',
    'View File Content',
    'FILE_SYSTEM',
    'Membaca dan menampilkan isi berkas teks (log insiden, berkas konfigurasi) secara aman.',
    'LOW', FALSE, FALSE,
    '{"filepath": "string", "lines": "int"}'::jsonb,
    'N/A (Tool diagnostik read-only)'
),
(
    'findstr',
    'Search String Pattern in Files',
    'FILE_SYSTEM',
    'Mencari kata kunci atau string pattern (error code, IP) di dalam berkas teks atau log.',
    'LOW', FALSE, FALSE,
    '{"pattern": "string", "filepath": "string"}'::jsonb,
    'N/A (Tool diagnostik read-only)'
),
(
    'where',
    'Locate Command Executable Path',
    'SYSTEM_OPS',
    'Menemukan lokasi path biner eksekusi dari suatu perintah sistem.',
    'LOW', FALSE, FALSE,
    '{"command_name": "string"}'::jsonb,
    'N/A (Tool diagnostik read-only)'
),
(
    'whoami',
    'Query Current Execution Identity',
    'SECURITY',
    'Menampilkan identitas pengguna/service akun yang sedang menjalankan eksekusi.',
    'LOW', FALSE, FALSE,
    '{}'::jsonb,
    'N/A (Tool diagnostik read-only)'
),
(
    'hostname',
    'Query System Hostname Identity',
    'SYSTEM_OPS',
    'Menampilkan nama node host/server yang sedang aktif.',
    'LOW', FALSE, FALSE,
    '{}'::jsonb,
    'N/A (Tool diagnostik read-only)'
),
(
    'systeminfo',
    'Query System Hardware & OS Baseline',
    'SYSTEM_OPS',
    'Mengumpulkan informasi arsitektur sistem operasi, memori, CPU, uptime, dan baseline hardware.',
    'LOW', FALSE, FALSE,
    '{}'::jsonb,
    'N/A (Tool diagnostik read-only)'
),
(
    'ver',
    'Query OS Kernel Version',
    'SYSTEM_OPS',
    'Menampilkan rincian versi kernel OS yang berjalan.',
    'LOW', FALSE, FALSE,
    '{}'::jsonb,
    'N/A (Tool diagnostik read-only)'
),
(
    'echo',
    'Echo Text Output',
    'UTILITY',
    'Menampilkan pesan teks atau mengevaluasi variabel lingkungan secara terisolasi.',
    'LOW', FALSE, FALSE,
    '{"text": "string"}'::jsonb,
    'N/A (Tool utilitas)'
),
(
    'cd',
    'Display / Inspect Working Directory Context',
    'FILE_SYSTEM',
    'Menampilkan path direktori kerja aktif dalam konteks eksekusi.',
    'LOW', FALSE, FALSE,
    '{}'::jsonb,
    'N/A (Tool read-only)'
),
(
    'tasklist',
    'Inspect Active System Processes',
    'SYSTEM_OPS',
    'Menampilkan daftar proses sistem yang sedang berjalan beserta PID, penggunaan memori, dan status.',
    'LOW', FALSE, FALSE,
    '{"filter": "string"}'::jsonb,
    'N/A (Tool diagnostik read-only)'
),
(
    'ipconfig',
    'Query Network Interface Configuration',
    'NETWORK',
    'Menampilkan konfigurasi antarmuka jaringan, alokasi IP address, subnet mask, dan default gateway.',
    'LOW', FALSE, FALSE,
    '{}'::jsonb,
    'N/A (Tool diagnostik read-only)'
),
(
    'netstat',
    'Inspect Active Network Connections & Ports',
    'NETWORK',
    'Menampilkan koneksi jaringan aktif, listening ports, tabel socket, dan status protokol TCP/UDP.',
    'LOW', FALSE, FALSE,
    '{"filter_port": "int"}'::jsonb,
    'N/A (Tool diagnostik read-only)'
),
(
    'route_print',
    'Inspect IP Routing Table',
    'NETWORK',
    'Menampilkan tabel routing IP sistem, gateway aktif, dan nilai metrik rute.',
    'LOW', FALSE, FALSE,
    '{}'::jsonb,
    'N/A (Tool diagnostik read-only)'
),
(
    'wmic',
    'Query WMI System Baseline',
    'SYSTEM_OPS',
    'Mengueri antarmuka instrumentasi sistem untuk status disk, memori, prosessor, dan layanan.',
    'MEDIUM', FALSE, FALSE,
    '{"query_target": "string"}'::jsonb,
    'N/A (Tool read-only)'
),
(
    'sc_query',
    'Inspect Service Control Manager Daemon Status',
    'SERVER',
    'Memeriksa status daemon service sistem (RUNNING, STOPPED, PAUSED) dan dependensinya.',
    'LOW', FALSE, FALSE,
    '{"service_name": "string"}'::jsonb,
    'N/A (Tool diagnostik read-only)'
)
ON CONFLICT (tool_id) DO UPDATE SET
    tool_name = EXCLUDED.tool_name,
    category = EXCLUDED.category,
    description = EXCLUDED.description,
    risk_level = EXCLUDED.risk_level,
    parameter_schema = EXCLUDED.parameter_schema,
    updated_at = CURRENT_TIMESTAMP;
