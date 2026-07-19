# Metabase Dashboard: Cognitive Memory Evolution

This document specifies the SQL queries needed to build the Cognitive Memory Evolution dashboard in Metabase.

## 1. Proposal Success Rate
```sql
SELECT 
    DATE_TRUNC('day', created_at) AS date, 
    status, 
    COUNT(*) 
FROM knowledge_proposal 
GROUP BY date, status 
ORDER BY date DESC;
```

## 2. Engineer Feedback Override
```sql
SELECT 
    engineer_id, 
    action, 
    COUNT(*) 
FROM feedback_history 
GROUP BY engineer_id, action;
```

## 3. Playbook Accuracy
```sql
SELECT 
    playbook_id, 
    AVG(success_rate) AS avg_success_rate, 
    AVG(rollback_rate) AS avg_rollback_rate 
FROM playbook_history 
GROUP BY playbook_id 
ORDER BY avg_success_rate DESC;
```

## 4. Knowledge Confidence Decay
```sql
SELECT 
    knowledge_type, 
    AVG(confidence) AS avg_confidence, 
    AVG(decay_score) AS avg_decay 
FROM semantic_memory 
GROUP BY knowledge_type;
```
