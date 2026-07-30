-- Production Seed Data for AI Decision Logs & Reflection Trails

INSERT INTO ai_reflection_logs (
    incident_id, stage_version, first_hypothesis, second_hypothesis, final_decision,
    confidence_score, ai_models_used, decision_time_ms, trace_id, span_id, parent_span, timestamp
)
VALUES 
(370, 'V2.4 Enterprise', 'High CPU Spike on Core Router (Layer 3 Routing Anomaly)', 'BGP Route Flapping & Buffer Bloat', 'EXECUTE_PLAYBOOK_L3_ROUTE_FLUSH', 94.5, 'DeepSeek-R1-Distill / Qwen2.5-7B (Consensus)', 1450, 'tr-dec-8f912a7b31c', 'sp-rag-041a9e', 'sp-root-9912', NOW() - INTERVAL '5 minutes'),

(369, 'V2.4 Enterprise', 'PostgreSQL Connection Exhaustion & Transaction Lock Contention', 'Slow Query Index Scan Deficit', 'KILL_IDLE_TRANSACTIONS & AUTO_HEAL_POSTGRES', 98.2, 'Gemini 1.5 Pro / Claude 3.5 Sonnet (RAG Curator)', 1120, 'tr-dec-7d821b5c40a', 'sp-db-1182c0', 'sp-root-9911', NOW() - INTERVAL '12 minutes'),

(368, 'V2.4 Enterprise', 'Root Volume Partition Utilization > 92% (Disk Full Anomaly)', 'Uncleaned Temporary Buffers & Journal Logs', 'EXECUTE_PLAYBOOK_L1_DISK_CLEANUP', 99.0, 'OSI Cognitive Supervisor (Rule + LLM Guard)', 850, 'tr-dec-6c710a4b30f', 'sp-fs-2273d1', 'sp-root-9910', NOW() - INTERVAL '25 minutes'),

(367, 'V2.4 Enterprise', 'TLS Certificate Expiration & Nginx Ingress Reverse Proxy Stalled', 'Upstream Socket Reset (Connection Refused)', 'RELOAD_NGINX_AND_VERIFY_TLS_PROXIES', 96.8, 'Qwen2.5-Coder-32B / DeepSeek-V3', 1680, 'tr-dec-5b609f3a20e', 'sp-proxy-3364e2', 'sp-root-9909', NOW() - INTERVAL '40 minutes'),

(366, 'V2.4 Enterprise', 'NATS JetStream Queue Backpressure & Stalled Stream Consumer', 'Memory Leak in Telemetry Ingestion Worker', 'RESET_INGESTION_BUFFER_STREAMS', 97.5, 'OSI Active Cognitive Engine V3.2', 990, 'tr-dec-4a508e2910d', 'sp-nats-4455f3', 'sp-root-9908', NOW() - INTERVAL '1 hour'),

(6588, 'V2.4 Enterprise', 'TCP Socket Ephemeral Port Exhaustion (Layer 4 Protocol State)', 'SYN Flood / TIME_WAIT Connection Accumulation', 'RECYCLE_TIME_WAIT_SOCKETS & EXPAND_PORTS', 95.8, 'DeepSeek-R1-Distill / Critic Engine', 1340, 'tr-dec-3f407d1800c', 'sp-tcp-5544e4', 'sp-root-9907', NOW() - INTERVAL '2 hours'),

(99999, 'V2.4 Enterprise', 'Redis Distributed Cache Out-Of-Memory Memory Thrashing', 'Stale Session Eviction Policy Deficit', 'FLUSH_EXPIRED_REDIS_SESSIONS & HEAVY_SYNC', 99.1, 'Gemini 1.5 Flash / Active Cognitive Engine', 720, 'tr-dec-2e306c0790b', 'sp-redis-6633d5', 'sp-root-9906', NOW() - INTERVAL '3 hours'),

(888126, 'V2.4 Enterprise', 'ARP Table Corruption & Duplicate IP/MAC Address Conflict', 'VLAN Bridge Interface Disconnect', 'FLUSH_ARP_CACHE & REBIND_V bridge', 93.4, 'Qwen2.5-7B / Security Policy Manager', 1520, 'tr-dec-1d205b9680a', 'sp-arp-7722c6', 'sp-root-9905', NOW() - INTERVAL '4 hours');
