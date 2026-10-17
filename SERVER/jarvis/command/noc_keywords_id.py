"""
SERVER.jarvis.command.noc_keywords_id — Bahasa Indonesia NOC Keyword Dictionary
================================================================================
P8 Implementation: 100+ keyword NOC dalam Bahasa Indonesia beserta mapping
ke aksi/entitas NOC standar.

Digunakan oleh JarvisCommandIntentRouter untuk Bahasa Indonesia support.
"""
from typing import Dict, List

# ──────────────────────────────────────────────────────────────────────────────
# KEYWORD → NOC ACTION MAPPING (Bahasa Indonesia)
# ──────────────────────────────────────────────────────────────────────────────

NOC_ACTION_KEYWORDS_ID: Dict[str, str] = {
    # === DIAGNOSIS & MONITORING ===
    "cek status":             "GET_STATUS",
    "cek status kesehatan":   "GET_HEALTH",
    "status kesehatan sistem":"GET_HEALTH",
    "kesehatan sistem":       "GET_HEALTH",
    "cek jaringan":          "GET_NETWORK_STATUS",
    "cek koneksi":           "GET_CONNECTION_STATUS",
    "cek kesehatan":         "GET_HEALTH",
    "cek uptime":            "GET_UPTIME",
    "cek bandwidth":         "GET_BANDWIDTH",
    "cek latency":           "GET_LATENCY",
    "cek ping":              "PING_DEVICE",
    "cek cpu":               "GET_CPU_METRICS",
    "cek ram":               "GET_RAM_METRICS",
    "cek disk":              "GET_DISK_METRICS",
    "cek memory":            "GET_MEMORY_METRICS",
    "metrik cpu dan ram":    "GET_HOST_METRICS",
    "metrik cpu":            "GET_HOST_METRICS",
    "berapa metrik cpu":     "GET_HOST_METRICS",
    "berapa pc":             "GET_PC_DETAILED_STATUS",
    "pc online dan offline":  "GET_PC_DETAILED_STATUS",
    "pc online":             "GET_PC_DETAILED_STATUS",
    "pc offline":            "GET_PC_DETAILED_STATUS",
    "cek pc":                "GET_PC_DETAILED_STATUS",
    "cek status pc":         "GET_PC_DETAILED_STATUS",
    "cek agent":             "GET_PC_DETAILED_STATUS",
    "cek status agent":      "GET_PC_DETAILED_STATUS",
    "berapa printer":        "GET_PRINTERS_DETAILED_STATUS",
    "printer terhubung":     "GET_PRINTERS_DETAILED_STATUS",
    "printer aktif":         "GET_PRINTERS_DETAILED_STATUS",
    "cek printer":           "GET_PRINTERS_DETAILED_STATUS",
    "cek status printer":    "GET_PRINTERS_DETAILED_STATUS",
    "uji sandbox":             "RUN_SANDBOX_TEST",
    "jalankan sandbox":        "RUN_SANDBOX_TEST",
    "paksa pengujian":         "RUN_SANDBOX_TEST",
    "uji di sandbox":          "RUN_SANDBOX_TEST",
    "cek sandbox":             "RUN_SANDBOX_TEST",
    "cek sanbox":              "RUN_SANDBOX_TEST",
    "sanbox":                  "RUN_SANDBOX_TEST",
    "sandbox":                 "RUN_SANDBOX_TEST",
    # hasil sandbox = menampilkan hasil → GET_SANDBOX_RESULTS (lebih presisi dari RUN)
    "hasil sandbox":           "RUN_SANDBOX_TEST",
    "hasil pengujian sandbox": "RUN_SANDBOX_TEST",
    "tampilkan hasil sandbox": "RUN_SANDBOX_TEST",
    "apa saja yang diuji":     "GET_SANDBOX_HISTORY",
    "riwayat sandbox":         "GET_SANDBOX_HISTORY",
    "aktivitas browser":     "GET_BROWSER_MONITOR",

    "lihat aktivitas browser":"GET_BROWSER_MONITOR",
    "causal graph":          "TRAVERSE_CAUSAL_GRAPH",
    "tunjukkan causal graph":"TRAVERSE_CAUSAL_GRAPH",
    "blast radius":          "CALCULATE_BLAST_RADIUS",
    "berapa blast radius":   "CALCULATE_BLAST_RADIUS",
    "criticality score":     "GET_BUSINESS_IMPACT",
    "berapa criticality score":"GET_BUSINESS_IMPACT",
    "skor kritikalitas":     "GET_BUSINESS_IMPACT",
    "catalog aksi":          "LIST_ACTION_CATALOG",
    "daftar catalog aksi":   "LIST_ACTION_CATALOG",
    "aksi pre-approved":     "LIST_ACTION_CATALOG",
    "audit log hari ini":    "GET_AUDIT_LOG",
    "lihat audit log":       "GET_AUDIT_LOG",
    "sop belum direview":    "GET_SOPS",
    "cek traffic":           "GET_TRAFFIC_METRICS",
    "cek sla":               "GET_SLA_COMPLIANCE",
    "cek printer":           "GET_PRINTERS_DETAILED_STATUS",
    "cek storage":           "GET_STORAGE_STATS",
    "cek antrian":           "GET_QUEUE_STATUS",
    "cek n8n":               "GET_N8N_HEALTH",
    "cek launcher":          "GET_LAUNCHER_STATUS",
    "cek site":              "PING_SITES",
    "cek semua site":        "PING_ALL_SITES",
    "monitor sistem":        "GET_RUNTIME_MONITOR",
    "pantau jaringan":       "GET_NETWORK_MONITOR",
    "lihat log":             "GET_ACTIVITY_LOG",
    "lihat insiden":         "GET_ACTIVE_INCIDENTS",
    "insiden apa":           "GET_ACTIVE_INCIDENTS_DETAIL",
    "insiden apa aja":       "GET_ACTIVE_INCIDENTS_DETAIL",
    "sebutkan insiden":      "GET_ACTIVE_INCIDENTS_DETAIL",
    "sebutkan insiden apa aja": "GET_ACTIVE_INCIDENTS_DETAIL",
    "ada insiden apa":       "GET_ACTIVE_INCIDENTS_DETAIL",
    "apa saja insiden":      "GET_ACTIVE_INCIDENTS_DETAIL",
    "list insiden":          "GET_ACTIVE_INCIDENTS_DETAIL",
    "daftar insiden":        "GET_ACTIVE_INCIDENTS_DETAIL",
    "lihat alert":           "GET_ACTIVE_ALERTS",
    "tampilkan issue":       "GET_ISSUES",
    "tampilkan anomali":     "GET_ANOMALIES",
    "tampilkan statistik":   "GET_AI_STATS",
    "laporan sla":           "GET_SLA_REPORT",
    "laporan uptime":        "GET_UPTIME_REPORT",
    "laporan insiden":       "GET_INCIDENT_REPORT",
    "riwayat insiden":       "GET_INCIDENT_HISTORY",
    "post mortem":           "GET_POST_MORTEM",
    "audit trail":           "GET_AUDIT_TRAIL",

    # === INCIDENT MANAGEMENT ===
    "buat insiden":          "CREATE_INCIDENT",
    "tutup insiden":         "CLOSE_INCIDENT",
    "selesaikan insiden":    "RESOLVE_INCIDENT",
    "eskalasi insiden":      "ESCALATE_INCIDENT",
    "assign insiden":        "ASSIGN_INCIDENT",
    "analisa insiden":       "ANALYZE_RCA",
    "analisa incident":      "ANALYZE_RCA",
    "analisis insiden":      "ANALYZE_RCA",
    "analisis incident":      "ANALYZE_RCA",
    "rca insiden":           "ANALYZE_RCA",
    "rca incident":          "ANALYZE_RCA",
    "analisa incident di pc":"ANALYZE_RCA",
    "analisa insiden di pc": "ANALYZE_RCA",
    "analisis incident di pc":"ANALYZE_RCA",
    "analisis insiden di pc":"ANALYZE_RCA",
    "analisa incident di":   "ANALYZE_RCA",
    "analisa insiden di":    "ANALYZE_RCA",
    "analisis incident di":  "ANALYZE_RCA",
    "analisis insiden di":   "ANALYZE_RCA",
    "cek incident di pc":    "ANALYZE_RCA",
    "cek insiden di pc":     "ANALYZE_RCA",
    "analisa incident di printer": "ANALYZE_RCA",
    "analisa insiden di printer":  "ANALYZE_RCA",
    "analisis incident di printer":"ANALYZE_RCA",
    "analisis insiden di printer": "ANALYZE_RCA",
    "analisa incident printer":    "ANALYZE_RCA",
    "analisa insiden printer":     "ANALYZE_RCA",
    "analisis incident printer":   "ANALYZE_RCA",
    "analisis insiden printer":    "ANALYZE_RCA",
    "rca incident di printer":     "ANALYZE_RCA",
    "rca insiden di printer":      "ANALYZE_RCA",
    "cek incident di printer":     "ANALYZE_RCA",
    "cek insiden di printer":      "ANALYZE_RCA",
    "root cause":            "ANALYZE_RCA",
    "simulasi":              "COUNTERFACTUAL_SIMULATION",
    "reanalisa":             "REANALYZE_RCA",

    # === REMEDIATION ACTIONS ===
    "restart spooler":       "RESTART_PRINT_SPOOLER",
    "restart printer":       "RESTART_PRINTER_SERVICE",
    "restart server":        "RESTART_SERVER",
    "restart service":       "RESTART_SERVICE",
    "restart redis":         "RESTART_REDIS",
    "restart postgresql":    "RESTART_POSTGRESQL",
    "restart database":      "RESTART_DATABASE",
    "restart nats":          "RESTART_NATS",
    "restart jaringan":      "RESTART_NETWORK_SERVICE",
    "reboot router":         "REBOOT_ROUTER",
    "reboot switch":         "REBOOT_SWITCH",
    "reboot server":         "REBOOT_SERVER",
    "bersihkan cache":       "CLEAR_CACHE",
    "bersihkan arp":         "CLEAR_ARP_TABLE",
    "kosongkan antrian":     "CLEAR_QUEUE",
    "clear queue":           "CLEAR_QUEUE",
    "clear print queue":     "CLEAR_PRINT_QUEUE",
    "failover":              "FAILOVER_LINK",
    "pindah isp":            "FAILOVER_ISP",
    "backup isp":            "SWITCH_TO_BACKUP_ISP",
    "aktifkan port":         "ENABLE_PORT",
    "nonaktifkan port":      "DISABLE_PORT",
    "rollback":              "ROLLBACK_CONFIG",
    "update firmware":       "UPDATE_FIRMWARE",
    "update agent":          "TRIGGER_OTA_UPDATE",
    "jalankan sop":          "EXECUTE_SOP",
    "eksekusi sop":          "EXECUTE_SOP",
    "terapkan sop":          "EXECUTE_SOP",

    # === REMOTE ACCESS & BROWSER ===
    "buka remote":           "LAUNCH_REMOTE",
    "akses remote":          "LAUNCH_REMOTE",
    "remote ke":             "LAUNCH_REMOTE",
    "sambungkan ke":         "LAUNCH_REMOTE",
    "buka vnc":              "LAUNCH_VNC",
    "buka rdp":              "LAUNCH_RDP",
    "buka ssh":              "LAUNCH_SSH",
    "buka rustdesk":         "LAUNCH_RUSTDESK",
    "buka rust desk":        "LAUNCH_RUSTDESK",
    "akses rustdesk":        "LAUNCH_RUSTDESK",
    "rustdesk":              "LAUNCH_RUSTDESK",
    "tutup remote":          "CLOSE_REMOTE_SESSION",
    "putuskan koneksi":      "DISCONNECT_REMOTE",
    "hentikan sesi remote":  "TERMINATE_REMOTE_SESSION",
    "deteksi remote":        "DETECT_REMOTE_TOOLS",
    "buka youtube":          "OPEN_YOUTUBE",
    "cari di youtube":       "SEARCH_YOUTUBE",
    "play musik":            "PLAY_MUSIC",
    "putar musik":           "PLAY_MUSIC",
    "play lagu":             "PLAY_MUSIC",
    "putar lagu":            "PLAY_MUSIC",
    "jarvis stop":           "STOP_MUSIC",
    "stop musik":            "STOP_MUSIC",
    "stop music":            "STOP_MUSIC",
    "matikan musik":         "STOP_MUSIC",
    "hentikan musik":        "STOP_MUSIC",
    "stop lagu":             "STOP_MUSIC",
    "matikan lagu":          "STOP_MUSIC",
    "hentikan lagu":         "STOP_MUSIC",
    "pause musik":           "STOP_MUSIC",
    "pause music":           "STOP_MUSIC",
    "jeda musik":            "STOP_MUSIC",
    "stop player":           "STOP_MUSIC",
    "matikan player":        "STOP_MUSIC",
    "stop media":            "STOP_MUSIC",
    "jarvis diam":           "STOP_MUSIC",
    "berhenti":              "STOP_MUSIC",
    "buka chatgpt":          "OPEN_CHATGPT",
    "chat gpt":              "OPEN_CHATGPT",
    "gpt.ai":                "OPEN_CHATGPT",
    "gpt ai":                "OPEN_CHATGPT",
    "buka gpt ai":           "OPEN_CHATGPT",
    "buka gpt":              "OPEN_CHATGPT",
    "tanyakan ke chatgpt":   "OPEN_CHATGPT",
    "tanyakan ke gpt ai":    "OPEN_CHATGPT",
    "tanyakan ke gpt":       "OPEN_CHATGPT",
    "buka website":          "OPEN_URL",
    "buka site":             "OPEN_URL",
    "buka tab":              "OPEN_URL",
    "buka dashboard":        "OPEN_DASHBOARD",
    "buka noc":              "OPEN_DASHBOARD",
    "buka portal":           "OPEN_DASHBOARD",
    "tampilan awal":         "OPEN_DASHBOARD",
    "dashboard jarvis":      "OPEN_DASHBOARD",

    # === CHAT MANAGEMENT ===
    "baca chat":             "GET_CHAT_MESSAGES",
    "lihat chat":            "GET_CHAT_MESSAGES",
    "chat terbaru":          "GET_RECENT_CHAT",
    "pesan terbaru":         "GET_RECENT_MESSAGES",
    "kirim pesan":           "SEND_CHAT_MESSAGE",
    "balas chat":            "REPLY_CHAT",
    "saran balasan":         "GET_CHAT_SUGGESTION",
    "suggest balasan":       "GET_CHAT_SUGGESTION",
    "eskalasi chat":         "ESCALATE_CHAT_SESSION",
    "tutup chat":            "CLOSE_CHAT_SESSION",
    "buka chat":             "OPEN_CHAT_SESSION",
    "update status chat":    "UPDATE_CHAT_STATUS",

    # === SOP MANAGEMENT ===
    "buat sop":              "CREATE_SOP",
    "buat prosedur":         "CREATE_SOP",
    "tampilkan sop":         "GET_SOPS",
    "daftar sop":            "GET_SOPS",
    "daftar sop aktif":      "GET_SOPS",
    "semua sop":             "GET_SOPS",
    "list sop":              "GET_SOPS",
    "berapa sop":            "GET_SOPS",
    "promosi sop":           "PROMOTE_SOP",
    "aktifkan sop":          "PROMOTE_SOP",
    "hapus sop":             "DELETE_SOP",
    "cari sop":              "SEARCH_SOP",
    "search sop":            "SEARCH_SOP",
    "cari prosedur":         "SEARCH_SOP",
    # Voice read / bacakan SOP — JARVIS membaca isi SOP canonical
    "baca sop":              "READ_SOP",
    "bacakan sop":           "READ_SOP",
    "baca prosedur":         "READ_SOP",
    "bacakan prosedur":      "READ_SOP",
    "tampilkan prosedur":    "READ_SOP",
    "apa isi sop":           "READ_SOP",
    "isi sop":               "READ_SOP",
    "sop untuk":             "READ_SOP",
    "sop spooler":           "READ_SOP",
    "sop dns":               "READ_SOP",
    "sop printer":           "READ_SOP",
    "sop restart":           "READ_SOP",
    "sop cache":             "READ_SOP",
    # Handling procedure
    "cara penanganan":       "GET_HANDLING_PROCEDURE",
    "prosedur penanganan":   "GET_HANDLING_PROCEDURE",
    "cara atasi":            "GET_HANDLING_PROCEDURE",
    "bagaimana cara":        "GET_HANDLING_PROCEDURE",
    "langkah penanganan":    "GET_HANDLING_PROCEDURE",
    "langkah perbaikan":     "GET_HANDLING_PROCEDURE",
    # Vault management
    "sync vault":            "VAULT_SYNC",
    "sinkronisasi vault":    "VAULT_SYNC",
    "status vault":          "GET_VAULT_STATUS",
    "status sop vault":      "GET_VAULT_STATUS",


    # === HITL ===
    "setujui aksi":          "HITL_APPROVE",
    "approve":               "HITL_APPROVE",
    "tolak aksi":            "HITL_REJECT",
    "reject":                "HITL_REJECT",
    "batalkan aksi":         "HITL_CANCEL",
    "eskalasi ke l2":        "ESCALATE_L2",
    "eskalasi ke l3":        "ESCALATE_L3",
    "override":              "HITL_OVERRIDE",
    "paksa eksekusi":        "FORCE_EXECUTE",
    "antrian approval":      "GET_HITL_QUEUE",
    "tugaskan insiden":      "DISPATCH_FIELD_ENGINEER",
    "kirim work order":      "DISPATCH_FIELD_ENGINEER",
    "kirim ke teknisi":      "DISPATCH_FIELD_ENGINEER",
    "assign teknisi":        "DISPATCH_FIELD_ENGINEER",
    "tugaskan ke teknisi":   "DISPATCH_FIELD_ENGINEER",

    # === FLEET & DEVICE MANAGEMENT ===
    "daftar device":         "GET_FLEET_DEVICES",
    "device online":         "GET_ONLINE_DEVICES",
    "device offline":        "GET_OFFLINE_DEVICES",
    "tambah device":         "REGISTER_DEVICE",
    "hapus device":          "DELETE_DEVICE",
    "diagnostik mendalam":   "DEEP_DIAGNOSTICS",
    "deep diagnostics":      "DEEP_DIAGNOSTICS",
    "trigger ota":           "TRIGGER_OTA_UPDATE",

    # === PRINTER MANAGEMENT ===
    "daftar printer":        "GET_PRINTERS",
    "printer online":        "GET_ONLINE_PRINTERS",
    "printer offline":       "GET_OFFLINE_PRINTERS",
    "ping printer":          "PING_PRINTER",
    "ping semua printer":    "PING_ALL_PRINTERS",
    "bersihkan antrian cetak": "CLEAR_PRINT_QUEUE",

    # === KNOWLEDGE & AI ===
    "cari knowledge":        "SEARCH_KNOWLEDGE",
    "import knowledge":      "IMPORT_KNOWLEDGE",
    "daftar knowledge":      "LIST_KNOWLEDGE",
    "status ai":             "GET_AI_STATUS",
    "konfigurasi ai":        "GET_AI_CONFIG",
    "update konfigurasi ai": "GET_AI_CONFIG",
    "statistik ai":          "GET_AI_STATS",

    # === WORKFLOW n8n ===
    "trigger workflow":      "TRIGGER_N8N_WORKFLOW",
    "sync vault":            "N8N_VAULT_SYNC",
    "publish postmortem":    "N8N_PUBLISH_POSTMORTEM",
    "status n8n":            "GET_N8N_HEALTH",

    # === NOTIFICATIONS ===
    "kirim notifikasi":      "PUSH_NOTIFICATION",
    "notifikasi site":       "PUSH_SITE_NOTIFICATION",
    "alert telegram":        "SEND_TELEGRAM_ALERT",

    # === RBAC & SECURITY ===
    "tambah user":           "CREATE_RBAC_USER",
    "hapus user":            "DELETE_RBAC_USER",
    "update role":           "UPDATE_RBAC_ROLE",
    "izin akses":            "GET_PERMISSIONS",
    "kebijakan":             "GET_POLICY",
}


# ──────────────────────────────────────────────────────────────────────────────
# SEVERITY KEYWORDS
# ──────────────────────────────────────────────────────────────────────────────

SEVERITY_KEYWORDS_ID: Dict[str, str] = {
    "kritis":    "CRITICAL",
    "critical":  "CRITICAL",
    "parah":     "CRITICAL",
    "sangat urgent": "CRITICAL",
    "tinggi":    "HIGH",
    "high":      "HIGH",
    "serius":    "HIGH",
    "urgent":    "HIGH",
    "mendesak":  "HIGH",
    "sedang":    "MEDIUM",
    "medium":    "MEDIUM",
    "moderat":   "MEDIUM",
    "rendah":    "LOW",
    "low":       "LOW",
    "minor":     "LOW",
    "kecil":     "LOW",
}


# ──────────────────────────────────────────────────────────────────────────────
# TIME KEYWORDS (untuk scheduling/maintenance window)
# ──────────────────────────────────────────────────────────────────────────────

TIME_KEYWORDS_ID: Dict[str, str] = {
    "sekarang":           "NOW",
    "segera":             "IMMEDIATE",
    "nanti":              "DEFERRED",
    "malam ini":          "TONIGHT",
    "besok":              "TOMORROW",
    "maintenance window": "MAINTENANCE_WINDOW",
    "jam 02":             "MAINTENANCE_WINDOW",
    "jam 03":             "MAINTENANCE_WINDOW",
    "weekend":            "WEEKEND",
    "hari ini":           "TODAY",
    "minggu ini":         "THIS_WEEK",
    "bulan ini":          "THIS_MONTH",
}


# ──────────────────────────────────────────────────────────────────────────────
# NOCKeywordsID — Helper class
# ──────────────────────────────────────────────────────────────────────────────

class NOCKeywordsID:
    """Helper untuk lookup keyword NOC Bahasa Indonesia."""

    @staticmethod
    def lookup_action(text: str) -> str:
        """Cari action NOC yang paling cocok dari teks bebas."""
        text_lower = text.lower()
        # Try exact match first
        for kw, action in NOC_ACTION_KEYWORDS_ID.items():
            if kw in text_lower:
                return action
        return "UNKNOWN_ACTION"

    @staticmethod
    def extract_severity(text: str) -> str:
        """Ekstrak severity level dari teks."""
        text_lower = text.lower()
        for kw, severity in SEVERITY_KEYWORDS_ID.items():
            if kw in text_lower:
                return severity
        return "MEDIUM"  # Default

    @staticmethod
    def extract_time_context(text: str) -> str:
        """Ekstrak konteks waktu dari teks."""
        text_lower = text.lower()
        for kw, ctx in TIME_KEYWORDS_ID.items():
            if kw in text_lower:
                return ctx
        return "NOW"

    @staticmethod
    def all_actions() -> List[str]:
        """Daftar semua aksi NOC yang tersedia."""
        return sorted(set(NOC_ACTION_KEYWORDS_ID.values()))

    @staticmethod
    def all_keywords() -> List[str]:
        """Daftar semua keyword yang dikenali."""
        return sorted(NOC_ACTION_KEYWORDS_ID.keys())

    @staticmethod
    def keyword_count() -> int:
        return (
            len(NOC_ACTION_KEYWORDS_ID) +
            len(SEVERITY_KEYWORDS_ID) +
            len(TIME_KEYWORDS_ID)
        )
