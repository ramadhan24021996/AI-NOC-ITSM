# Metabase Dashboard: Multi-Agent Collaboration

This document specifies the SQL queries needed to build the Multi-Agent Collaboration dashboard in Metabase.

## 1. Agent Performance Accuracy
```sql
SELECT 
    agent_id, 
    AVG(accuracy) AS avg_accuracy, 
    AVG(success_rate) AS avg_success 
FROM agent_performance 
GROUP BY agent_id 
ORDER BY avg_accuracy DESC;
```

## 2. Agent Health & Watchdog Triggers
```sql
SELECT 
    agent_id, 
    SUM(crash_count) AS total_crashes, 
    AVG(cpu_usage) AS avg_cpu, 
    AVG(ram_usage) AS avg_ram 
FROM agent_health 
GROUP BY agent_id 
ORDER BY total_crashes DESC;
```

## 3. Conflict Resolution Rate
```sql
SELECT 
    DATE_TRUNC('day', created_at) AS date, 
    COUNT(*) AS total_consensus, 
    SUM(CASE WHEN has_conflict = true THEN 1 ELSE 0 END) AS total_conflicts 
FROM consensus_history 
GROUP BY date 
ORDER BY date DESC;
```

## 4. Communication Latency Analysis
```sql
SELECT 
    sender_agent_id, 
    receiver_agent_id, 
    AVG(latency_ms) AS avg_latency 
FROM agent_communication_audit 
GROUP BY sender_agent_id, receiver_agent_id 
ORDER BY avg_latency DESC;
```
