# JARVIS VOICE COMMAND CATALOG
**OSI Enterprise NOC AI Autonomous Voice & Intent Command Catalog Specification**

## 1. OPERATIONAL REMEDIATION & INFRASTRUCTURE ACTIONS
| Action Code | Triggers | Sample Query | Handler |
|---|---|---|---|
| `ACT_CLEAR_CACHE` | `bersihkan cache, clear cache` | "bersihkan cache di pc-01" | JarvisActionCatalogValidator |
| `ACT_CLEAR_PRINT_QUEUE` | `clear print queue, bersihkan antrian cetak, kosongkan queue cetak` | "clear print queue di pc-01" | JarvisActionCatalogValidator |
| `ACT_CLEAR_QUEUE` | `clear queue, kosongkan antrian` | "clear queue di pc-01" | JarvisActionCatalogValidator |
| `ACT_CREATE_RBAC_USER` | `tambah user, buat user` | "tambah user di pc-01" | JarvisActionCatalogValidator |
| `ACT_CREATE_SOP` | `buat prosedur, buat sop` | "buat prosedur di pc-01" | JarvisActionCatalogValidator |
| `ACT_DELETE_DEVICE` | `hapus device, delete device` | "hapus device di pc-01" | JarvisActionCatalogValidator |
| `ACT_DELETE_RBAC_USER` | `hapus user, delete user` | "hapus user di pc-01" | JarvisActionCatalogValidator |
| `ACT_DELETE_SOP` | `hapus sop, hapus prosedur` | "hapus sop di pc-01" | JarvisActionCatalogValidator |
| `ACT_DISABLE_PORT` | `disable port, shutdown interface, nonaktifkan port` | "disable port di pc-01" | JarvisActionCatalogValidator |
| `ACT_DRAIN_REPLICA` | `drain replica, kill query, terminate backend` | "drain replica di pc-01" | JarvisActionCatalogValidator |
| `ACT_ENABLE_PORT` | `aktifkan port, enable port` | "aktifkan port di pc-01" | JarvisActionCatalogValidator |
| `ACT_EXECUTE_SOP` | `execute sop, jalankan sop, eksekusi sop, terapkan sop` | "execute sop di pc-01" | JarvisActionCatalogValidator |
| `ACT_FAILOVER_ISP` | `failover, pindah isp, backup isp, switch over` | "failover di pc-01" | JarvisActionCatalogValidator |
| `ACT_FLUSH_DNS` | `flush dns, bersihkan dns, clear arp, bersihkan arp` | "flush dns di pc-01" | JarvisActionCatalogValidator |
| `ACT_IMPORT_KNOWLEDGE` | `import knowledge, masukkan pengetahuan` | "import knowledge di pc-01" | JarvisActionCatalogValidator |
| `ACT_N8N_PUBLISH_POSTMORTEM` | `publish postmortem, kirim postmortem` | "publish postmortem di pc-01" | JarvisActionCatalogValidator |
| `ACT_N8N_VAULT_SYNC` | `sync vault, sinkronisasi vault` | "sync vault di pc-01" | JarvisActionCatalogValidator |
| `ACT_REANALYZE_RCA` | `reanalisa, reanalisis` | "reanalisa di pc-01" | JarvisActionCatalogValidator |
| `ACT_REBOOT_SERVER` | `reboot server, restart server, reboot` | "reboot server di pc-01" | JarvisActionCatalogValidator |
| `ACT_RECOVER_POS_LOCK` | `pos db lock, unlock kasir, fix pos database lock` | "pos db lock di pc-01" | JarvisActionCatalogValidator |
| `ACT_REGISTER_DEVICE` | `tambah device, daftarkan device` | "tambah device di pc-01" | JarvisActionCatalogValidator |
| `ACT_RESET_PRINTER_DRIVER` | `reset printer driver, fix driver printer, reset driver` | "reset printer driver di pc-01" | JarvisActionCatalogValidator |
| `ACT_RESTART_NATS` | `restart nats, restart messaging` | "restart nats di pc-01" | JarvisActionCatalogValidator |
| `ACT_RESTART_NETWORK_SERVICE` | `restart jaringan, restart network` | "restart jaringan di pc-01" | JarvisActionCatalogValidator |
| `ACT_RESTART_POSTGRESQL` | `restart postgresql, restart database, restart postgres, restart db` | "restart postgresql di pc-01" | JarvisActionCatalogValidator |
| `ACT_RESTART_PRINTER_SERVICE` | `restart printer, restart printer service, printer service` | "restart printer di pc-01" | JarvisActionCatalogValidator |
| `ACT_RESTART_REDIS` | `restart redis, flush redis, clear cache redis` | "restart redis di pc-01" | JarvisActionCatalogValidator |
| `ACT_RESTART_SERVICE` | `restart service, restart aplikasi` | "restart service di pc-01" | JarvisActionCatalogValidator |
| `ACT_RESTART_SPOOLER` | `restart spooler, restart printer service` | "restart spooler di pc-01" | JarvisActionCatalogValidator |
| `ACT_ROLLBACK_CONFIG` | `rollback, kembalikan konfigurasi, revert config` | "rollback di pc-01" | JarvisActionCatalogValidator |
| `ACT_RUN_SANDBOX_TEST` | `uji sandbox, jalankan sandbox, paksa pengujian, uji di sandbox` | "uji sandbox di pc-01" | JarvisActionCatalogValidator |
| `ACT_SCALE_POD` | `scale pod, scale container, kubectl scale` | "scale pod di pc-01" | JarvisActionCatalogValidator |
| `ACT_TRIGGER_N8N_WORKFLOW` | `trigger workflow, jalankan workflow` | "trigger workflow di pc-01" | JarvisActionCatalogValidator |
| `ACT_TRIGGER_OTA` | `trigger ota, update agent, update firmware` | "trigger ota di pc-01" | JarvisActionCatalogValidator |
| `ACT_UPDATE_RBAC_ROLE` | `update role, ubah role` | "update role di pc-01" | JarvisActionCatalogValidator |
| `ACT_VPN_RECONNECT` | `reconnect vpn, reset vpn tunnel, vpn reconnect` | "reconnect vpn di pc-01" | JarvisActionCatalogValidator |

## 2. DASHBOARD MENU & PANEL ACTIONS
| Action Code | Triggers | Sample Query | Handler |
|---|---|---|---|
| `TRIGGER_OTA_UPDATE` | `trigger_ota_update, agent health, trigger update binary ota ke seluruh agent` | "trigger update binary ota ke seluruh agent" | JarvisMenuActionHandler |
| `RESET_AI_CACHE_STATS` | `reset_ai_cache_stats, ai, bersihkan statistik performa cache ai` | "bersihkan statistik performa cache ai" | JarvisMenuActionHandler |
| `FILTER_DECISION_LOGS` | `filter_decision_logs, ai decision logs, filter log keputusan ai berdasarkan id insiden` | "filter log keputusan ai berdasarkan id insiden" | JarvisMenuActionHandler |
| `RELOAD_PIPELINE_TOPOLOGY` | `reload_pipeline_topology, ai lifecycle topology, muat ulang topologi node alur kerja ai` | "muat ulang topologi node alur kerja ai" | JarvisMenuActionHandler |
| `BROADCAST_OPERATOR_MESSAGE` | `broadcast_operator_message, chat, kirim pesan broadcast ke semua operator noc` | "kirim pesan broadcast ke semua operator noc" | JarvisMenuActionHandler |
| `MERGE_CORRELATED_EVENTS` | `merge_correlated_events, event correlation, gabungkan event ter-korelasi menjadi satu insiden` | "gabungkan event ter-korelasi menjadi satu insiden" | JarvisMenuActionHandler |
| `GENERATE_EVIDENCE_BUNDLE` | `generate_evidence_bundle, evidence, buatkan paket bukti forensik digital untuk insiden` | "buatkan paket bukti forensik digital untuk insiden" | JarvisMenuActionHandler |
| `FILTER_TIMELINE_BY_STATUS` | `filter_timeline_by_status, exec timeline, filter timeline berdasarkan status failed/success` | "filter timeline berdasarkan status failed/success" | JarvisMenuActionHandler |
| `ADD_FLEET_DEVICE` | `add_fleet_device, fleet, daftarkan perangkat baru ke fleet` | "daftarkan perangkat baru ke fleet" | JarvisMenuActionHandler |
| `DELETE_FLEET_DEVICE` | `delete_fleet_device, fleet, hapus perangkat dari inventaris fleet` | "hapus perangkat dari inventaris fleet" | JarvisMenuActionHandler |
| `REBOOT_REMOTE_DEVICE` | `reboot_remote_device, fleet, restart perangkat remote` | "restart perangkat remote" | JarvisMenuActionHandler |
| `UPDATE_FLEET_THRESHOLD` | `update_fleet_threshold, fleet config, ubah ambang batas alarm cpu/ram global` | "ubah ambang batas alarm cpu/ram global" | JarvisMenuActionHandler |
| `APPROVE_HITL_ITEM` | `approve_hitl_item, gov, setujui aksi pemulihan insiden di hitl queue` | "setujui aksi pemulihan insiden di hitl queue" | JarvisMenuActionHandler |
| `REJECT_HITL_ITEM` | `reject_hitl_item, gov, tolak persetujuan aksi pemulihan di hitl queue` | "tolak persetujuan aksi pemulihan di hitl queue" | JarvisMenuActionHandler |
| `UPDATE_INCIDENT_STATUS` | `update_incident_status, incident, ubah status insiden (open -> in_progress -> resolved)` | "ubah status insiden (open -> in_progress -> resolved)" | JarvisMenuActionHandler |
| `ASSIGN_INCIDENT_OPERATOR` | `assign_incident_operator, incident, tugaskan insiden ke tim/operator noc` | "tugaskan insiden ke tim/operator noc" | JarvisMenuActionHandler |
| `TEST_AUDIO_SYNTHESIS` | `test_audio_synthesis, jarvis voice overview, uji coba sintesis suara jarvis` | "uji coba sintesis suara jarvis" | JarvisMenuActionHandler |
| `CHANGE_VOICE_PERSONA` | `change_voice_persona, jarvis voice overview, ganti karakter/persona suara jarvis` | "ganti karakter/persona suara jarvis" | JarvisMenuActionHandler |
| `REINDEX_KNOWLEDGE_GRAPH` | `reindex_knowledge_graph, kgraph, re-index vector embeddings pada knowledge graph` | "re-index vector embeddings pada knowledge graph" | JarvisMenuActionHandler |
| `SYNC_OBSIDIAN_VAULT` | `sync_obsidian_vault, knowledge center, jalankan sinkronisasi obsidian sop vault sekarang` | "jalankan sinkronisasi obsidian sop vault sekarang" | JarvisMenuActionHandler |
| `SET_PRIMARY_LLM_MODEL` | `set_primary_llm_model, models, ganti model llm utama yang digunakan sistem` | "ganti model llm utama yang digunakan sistem" | JarvisMenuActionHandler |
| `UPDATE_LLM_TEMPERATURE` | `update_llm_temperature, models, ubah batas suhu (temperature) kreativitas llm` | "ubah batas suhu (temperature) kreativitas llm" | JarvisMenuActionHandler |
| `SET_TELEMETRY_POLLING_RATE` | `set_telemetry_polling_rate, monitoring, ubah interval polling telemetri live` | "ubah interval polling telemetri live" | JarvisMenuActionHandler |
| `PURGE_NATS_SUBJECT_STREAM` | `purge_nats_subject_stream, nats subjects, bersihkan antrean pesan di subject nats tertentu` | "bersihkan antrean pesan di subject nats tertentu" | JarvisMenuActionHandler |
| `REFRESH_OVERVIEW_METRICS` | `refresh_overview_metrics, overview, muat ulang metrik overview real-time` | "muat ulang metrik overview real-time" | JarvisMenuActionHandler |
| `EXPORT_OVERVIEW_REPORT` | `export_overview_report, overview, ekspor laporan ringkasan sistem ke pdf/json` | "ekspor laporan ringkasan sistem ke pdf/json" | JarvisMenuActionHandler |
| `KILL_PROCESS` | `kill_process, pchealth, hentikan proses abnormal di pc remote` | "hentikan proses abnormal di pc remote" | JarvisMenuActionHandler |
| `TOGGLE_USB_LOCK` | `toggle_usb_lock, pchealth, kunci atau buka port usb di pc remote` | "kunci atau buka port usb di pc remote" | JarvisMenuActionHandler |
| `RUN_SOP_CANARY_TEST` | `run_sop_canary_test, playbooks, jalankan pengujian canary deployment untuk sop tertentu` | "jalankan pengujian canary deployment untuk sop tertentu" | JarvisMenuActionHandler |
| `RESTART_PRINT_SPOOLER` | `restart_print_spooler, printer, restart service print spooler di target host` | "restart service print spooler di target host" | JarvisMenuActionHandler |
| `CLEAR_PRINT_QUEUE` | `clear_print_queue, printer, bersihkan antrean cetak yang stuck` | "bersihkan antrean cetak yang stuck" | JarvisMenuActionHandler |
| `UPDATE_USER_ROLE` | `update_user_role, rbac, ubah peran/role hak akses pengguna` | "ubah peran/role hak akses pengguna" | JarvisMenuActionHandler |
| `TRIGGER_RCA_ANALYSIS` | `trigger_rca_analysis, rca, jalankan engine analisis rca untuk insiden tertentu` | "jalankan engine analisis rca untuk insiden tertentu" | JarvisMenuActionHandler |
| `TOGGLE_PII_REDACTION` | `toggle_pii_redaction, security policies, aktifkan atau nonaktifkan mode pii redactor` | "aktifkan atau nonaktifkan mode pii redactor" | JarvisMenuActionHandler |
| `RESTART_INTERNAL_SERVICE` | `restart_internal_service, server, restart service server internal` | "restart service server internal" | JarvisMenuActionHandler |
| `SET_SMART_LOG_FILTER` | `set_smart_log_filter, smart stream, terapkan filter log kata kunci pada smart stream` | "terapkan filter log kata kunci pada smart stream" | JarvisMenuActionHandler |
| `PURGE_DISTRIBUTED_CACHE` | `purge_distributed_cache, storage, bersihkan cache log terdistribusi` | "bersihkan cache log terdistribusi" | JarvisMenuActionHandler |
| `OPTIMIZE_VECTOR_INDEX` | `optimize_vector_index, storage, optimalkan indeks vector pgvector` | "optimalkan indeks vector pgvector" | JarvisMenuActionHandler |
| `TRIGGER_DPO_SYNTHESIS` | `trigger_dpo_synthesis, training, jalankan pipeline sintesis dpo dataset` | "jalankan pipeline sintesis dpo dataset" | JarvisMenuActionHandler |
| `HIGHLIGHT_BLAST_RADIUS` | `highlight_blast_radius, unified dag, sorot rute dampak kegagalan pada graf ketergantungan` | "sorot rute dampak kegagalan pada graf ketergantungan" | JarvisMenuActionHandler |

## 3. LIVE QUERY & TELEMETRY COMMANDS
| Action Code | Triggers | Sample Query | Handler |
|---|---|---|---|
| `CMD_PC_HEALTH` | `cek status perangkat, cek pc health, kondisi komputer` | "cek status perangkat kasir 1" | JarvisVoiceQueryHandler |
| `CMD_INCIDENT_SUMMARY` | `ada insiden apa, status insiden, cek gangguan` | "ada insiden apa hari ini" | JarvisVoiceQueryHandler |
| `CMD_PRINTER_STATUS` | `cek status printer, kondisi printer, status spooler` | "cek status printer gudang" | JarvisVoiceQueryHandler |
| `CMD_SOP_LIST` | `daftar sop, list sop, prosedur penanganan` | "tampilkan daftar sop aktif" | JarvisVoiceQueryHandler |
| `CMD_SLA_REPORT` | `laporan sla, status sla, uptime sistem` | "laporan sla bulan ini" | JarvisVoiceQueryHandler |
| `CMD_AUDIT_LOG` | `tampilkan audit log, cek riwayat, log audit` | "tampilkan audit log sistem" | JarvisVoiceQueryHandler |
| `CMD_WORK_ORDER` | `assign teknisi, tugaskan teknisi, kirim bantuan` | "assign teknisi ke budi" | JarvisVoiceQueryHandler |
| `CMD_N8N_STATUS` | `status n8n, n8n workflow, engine n8n` | "cek status workflow n8n" | JarvisVoiceQueryHandler |
| `CMD_NATS_CLUSTER` | `status nats, nats cluster, cluster status` | "cek status nats cluster" | JarvisVoiceQueryHandler |
| `CMD_KAFKA_STREAM` | `status kafka, kafka stream, antrian event` | "cek status antrian kafka" | JarvisVoiceQueryHandler |
| `CMD_DATABASE_HEALTH` | `kesehatan database, postgres status, status db` | "cek kesehatan database postgres" | JarvisVoiceQueryHandler |
| `CMD_REDIS_HEALTH` | `kesehatan redis, cache status, status redis` | "cek kesehatan memory redis" | JarvisVoiceQueryHandler |
| `CMD_RCA_EXPLANATION` | `penjelasan rca, analisis root cause, kenapa error` | "jelaskan rca insiden terakhir" | JarvisVoiceQueryHandler |
| `CMD_NAVIGATE_PANEL` | `buka panel, tampilkan menu, navigasi panel` | "buka panel execution timeline" | JarvisVoiceQueryHandler |
| `CMD_REMOTE_RUSTDESK` | `remote pc, remot rustdesk, buka remote` | "remot kasir 1 via rustdesk" | JarvisVoiceQueryHandler |
| `CMD_HITL_APPROVE` | `approve hitl, setujui aksi, konfirmasi remedi` | "approve hitl keputusan 42" | JarvisVoiceQueryHandler |
| `CMD_HITL_REJECT` | `reject hitl, tolak remedi, batalkan aksi` | "reject hitl keputusan 42" | JarvisVoiceQueryHandler |
| `CMD_EXPLAIN_FEATURE` | `apa itu, jelaskan fungsi, fungsi menu` | "fungsi ground truth rca apa" | JarvisVoiceQueryHandler |
| `ACT_RESTART_DOCKER_CONTAINER` | `restart docker, restart container` | "restart container osi-python-ai-core" | JarvisActionCatalogValidator |
| `ACT_RESTART_NGINX_PROXY` | `restart nginx, restart proxy` | "restart nginx load balancer" | JarvisActionCatalogValidator |
| `ACT_RESTART_PORTAINER` | `restart portainer, restart management ui` | "restart service portainer" | JarvisActionCatalogValidator |
| `ACT_FLUSH_SYSTEMD_RESOLVED` | `flush systemd-resolved, restart systemd dns` | "flush systemd resolved dns" | JarvisActionCatalogValidator |
| `ACT_CLEAR_TEMP_FILES` | `clear temp files, hapus file temporary, bersihkan tmp` | "bersihkan file temp di server" | JarvisActionCatalogValidator |
| `ACT_ROTATE_LOGS` | `rotate logs, rotasi log file, arsipkan log` | "jalankan rotasi log harian" | JarvisActionCatalogValidator |
| `ACT_RELOAD_FIREWALL_RULES` | `reload firewall, update iptables, refresh firewall` | "reload aturan firewall iptables" | JarvisActionCatalogValidator |
| `ACT_VERIFY_SSL_CERT` | `cek sertifikat ssl, verify ssl, cek masa berlaku https` | "cek status sertifikat ssl portal" | JarvisActionCatalogValidator |
| `ACT_SYNC_OBSIDIAN_VAULT` | `sync obsidian, sinkronisasi vault, sync sop vault` | "sinkronisasi vault obsidian" | JarvisActionCatalogValidator |
| `ACT_BACKUP_POSTGRES_DB` | `backup database, dump postgres, backup pgvector` | "buat backup database postgres" | JarvisActionCatalogValidator |
| `ACT_RESTORE_POSTGRES_DB` | `restore database, pulihkan db, import sql backup` | "pulihkan database dari backup" | JarvisActionCatalogValidator |
| `ACT_RESTART_CRON_DAEMON` | `restart cron, restart scheduler, restart crond` | "restart daemon cron scheduler" | JarvisActionCatalogValidator |
| `ACT_CHECK_DISK_SPACE` | `cek sisa disk, kapasitas harddisk, free storage` | "cek sisa kapasitas disk storage" | JarvisActionCatalogValidator |
| `ACT_CHECK_MEMORY_LEAK` | `cek kebocoran memori, memory leak check, cek ram` | "cek memory leak pada service ai" | JarvisActionCatalogValidator |
| `ACT_RESTART_WEBSOCKET_HUB` | `restart websocket, refresh ws hub, reset ws` | "restart websocket hub server" | JarvisActionCatalogValidator |
| `ACT_DRAIN_NATS_CONSUMER` | `drain nats, pause consumer, drain queue` | "drain queue consumer nats" | JarvisActionCatalogValidator |
| `ACT_RESUME_NATS_CONSUMER` | `resume nats, aktifkan consumer, unpause queue` | "aktifkan kembali nats consumer" | JarvisActionCatalogValidator |
| `ACT_RECALCULATE_SLA` | `hitung ulang sla, recalculate sla metrics` | "hitung ulang sla ketersediaan" | JarvisActionCatalogValidator |
| `ACT_PURGE_TELEMETRY_OLD` | `purge telemetry, hapus telemetri lama, prune data` | "hapus data telemetri lebih dari 30 hari" | JarvisActionCatalogValidator |
| `ACT_GENERATE_POSTMORTEM_PDF` | `generate postmortem, buat pdf insiden, ekspor laporan` | "buat pdf laporan insiden terakhir" | JarvisActionCatalogValidator |
| `ACT_TRIGGER_PROBE_SUITE` | `jalankan probe, active diagnostic probe, probing suite` | "jalankan active probing pada pc kasir" | JarvisActionCatalogValidator |
| `ACT_REINDEX_PGVECTOR` | `reindex pgvector, rebuild vector index, rebuild rag` | "reindex pgvector database embedding" | JarvisActionCatalogValidator |
| `ACT_TEST_TELEGRAM_NOTIFY` | `test telegram, uji notifikasi bot, kirim tes pesan` | "kirim tes notifikasi ke telegram" | JarvisActionCatalogValidator |
| `ACT_TOGGLE_MAINTENANCE_MODE` | `maintenance mode, aktifkan mode perawatan, toggle maintenance` | "aktifkan mode maintenance jaringan" | JarvisActionCatalogValidator |
| `ACT_RESTART_NETDATA_AGENT` | `restart netdata, restart monitoring agent, reset netdata` | "restart netdata monitoring di node 1" | JarvisActionCatalogValidator |
| `ACT_RUN_LATENCY_BENCHMARK` | `benchmark latensi, uji throughput, cek rtt gateway` | "jalankan latency benchmark ke seluruh site" | JarvisActionCatalogValidator |
| `ACT_KILL_ZOMBIE_PROCESSES` | `kill zombie, bersihkan proses mati, terminate hanging` | "bersihkan zombie process pada host" | JarvisActionCatalogValidator |
| `ACT_RENEW_AUTH_TOKENS` | `renew tokens, refresh jwt secret, rotasi auth token` | "perbarui auth token sesi aktif" | JarvisActionCatalogValidator |
| `ACT_CHECK_BANDWIDTH_USAGE` | `cek bandwidth, utilisasi link, cek throughput internet` | "cek utilisasi bandwidth link utama" | JarvisActionCatalogValidator |
| `ACT_FORCE_STEP_CONSENSUS` | `force consensus, paksa konsensus ai, re-evaluasi model` | "paksa evaluasi konsensus multi-agent" | JarvisActionCatalogValidator |
| `ACT_EXT_CAPABILITY_001` | `capability 1, ext action 1` | "eksekusi capability 1 sistem" | JarvisActionCatalogValidator |
| `ACT_EXT_CAPABILITY_002` | `capability 2, ext action 2` | "eksekusi capability 2 sistem" | JarvisActionCatalogValidator |
| `ACT_EXT_CAPABILITY_003` | `capability 3, ext action 3` | "eksekusi capability 3 sistem" | JarvisActionCatalogValidator |
| `ACT_EXT_CAPABILITY_004` | `capability 4, ext action 4` | "eksekusi capability 4 sistem" | JarvisActionCatalogValidator |
| `ACT_EXT_CAPABILITY_005` | `capability 5, ext action 5` | "eksekusi capability 5 sistem" | JarvisActionCatalogValidator |
| `ACT_EXT_CAPABILITY_006` | `capability 6, ext action 6` | "eksekusi capability 6 sistem" | JarvisActionCatalogValidator |
| `ACT_EXT_CAPABILITY_007` | `capability 7, ext action 7` | "eksekusi capability 7 sistem" | JarvisActionCatalogValidator |
| `ACT_EXT_CAPABILITY_008` | `capability 8, ext action 8` | "eksekusi capability 8 sistem" | JarvisActionCatalogValidator |
| `ACT_EXT_CAPABILITY_009` | `capability 9, ext action 9` | "eksekusi capability 9 sistem" | JarvisActionCatalogValidator |
| `ACT_EXT_CAPABILITY_010` | `capability 10, ext action 10` | "eksekusi capability 10 sistem" | JarvisActionCatalogValidator |
| `ACT_EXT_CAPABILITY_011` | `capability 11, ext action 11` | "eksekusi capability 11 sistem" | JarvisActionCatalogValidator |
| `ACT_EXT_CAPABILITY_012` | `capability 12, ext action 12` | "eksekusi capability 12 sistem" | JarvisActionCatalogValidator |
| `ACT_EXT_CAPABILITY_013` | `capability 13, ext action 13` | "eksekusi capability 13 sistem" | JarvisActionCatalogValidator |
| `ACT_EXT_CAPABILITY_014` | `capability 14, ext action 14` | "eksekusi capability 14 sistem" | JarvisActionCatalogValidator |
| `ACT_EXT_CAPABILITY_015` | `capability 15, ext action 15` | "eksekusi capability 15 sistem" | JarvisActionCatalogValidator |
| `ACT_EXT_CAPABILITY_016` | `capability 16, ext action 16` | "eksekusi capability 16 sistem" | JarvisActionCatalogValidator |
| `ACT_EXT_CAPABILITY_017` | `capability 17, ext action 17` | "eksekusi capability 17 sistem" | JarvisActionCatalogValidator |
| `ACT_EXT_CAPABILITY_018` | `capability 18, ext action 18` | "eksekusi capability 18 sistem" | JarvisActionCatalogValidator |
| `ACT_EXT_CAPABILITY_019` | `capability 19, ext action 19` | "eksekusi capability 19 sistem" | JarvisActionCatalogValidator |
| `ACT_EXT_CAPABILITY_020` | `capability 20, ext action 20` | "eksekusi capability 20 sistem" | JarvisActionCatalogValidator |
| `ACT_EXT_CAPABILITY_021` | `capability 21, ext action 21` | "eksekusi capability 21 sistem" | JarvisActionCatalogValidator |
| `ACT_EXT_CAPABILITY_022` | `capability 22, ext action 22` | "eksekusi capability 22 sistem" | JarvisActionCatalogValidator |
