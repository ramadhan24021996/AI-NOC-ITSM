# DEAD CODE AUDIT
## OSI NOC IT AI — Unused Code & Mock Implementations
**Evidence:** Source code analysis — grep for mock patterns, placeholder comments  
**Status:** VERIFIED findings from source code review

---

## DEAD CODE / PLACEHOLDER SUMMARY

| Category | Count |
|----------|-------|
| Mock implementations (return hardcoded data) | 7 |
| Placeholder / TODO stubs | 5 |
| Feature flags never set | 3 |
| Disabled code (commented/unreachable) | 4 |
| Unused imports / dead paths | 3 |

---

## MOCK IMPLEMENTATIONS

### [MOCK-01] RetrainClassifier() — ai_engine.go
```go
// Lines 116-130
func (s *AISupervisor) RetrainClassifier(ctx context.Context) (ClassifierMetrics, error) {
    fmt.Println("[AI] Simulating offline classifier retraining...")
    time.Sleep(100 * time.Millisecond)  // Fake delay
    return ClassifierMetrics{
        F1Score:  0.985,   // HARDCODED
        Accuracy: 0.991,   // HARDCODED
        Precision: 0.982,  // HARDCODED
        Recall:   0.988,   // HARDCODED
        AUCScore: 0.996,   // HARDCODED
    }, nil
}
```
**Risk:** Any caller of RetrainClassifier() receives fake metrics. CI/CD may show 0.985 F1 always.

---

### [MOCK-02] _handle_analyze() — api_router.py
```python
# Lines 196-204
def _handle_analyze(self, body):
    device_name = body.get("device_name", "UNKNOWN")
    return 200, {
        "root_cause_hypothesis": f"Elevated latency detected on {device_name}",  # FAKE
        "confidence": 0.94,  # FAKE
        "recommended_action": "RESTART_SERVICE"  # FAKE
    }
```

---

### [MOCK-03] _handle_execute_remediation() — api_router.py
```python
# Lines 206-215
def _handle_execute_remediation(self, body):
    return 200, {
        "status": "REMEDIATION_EXECUTED",       # ALWAYS
        "result": "SUCCESS",                     # ALWAYS
        "rollback_snapshot_id": "snap-9901-pre-exec"  # FAKE
    }
```

---

### [MOCK-04] _handle_rag_query() — api_router.py
```python
# Lines 217-228
def _handle_rag_query(self, body):
    return 200, {
        "results": [{
            "doc_id": "sop-dns-01",           # HARDCODED
            "score": 0.96,                     # HARDCODED
            "snippet": "If DNS query fails..."  # HARDCODED
        }]
    }
```

---

### [MOCK-05] _handle_models() — api_router.py
```python
# Lines 230-237
def _handle_models(self):
    return 200, {
        "models": [
            {"model_id": "gemini-1.5-flash", "provider": "Google", "status": "ACTIVE"},
            {"model_id": "deepseek-chat", "provider": "DeepSeek", "status": "CANARY"},
            {"model_id": "llama-3.1-70b-versatile", "provider": "Groq", "status": "ACTIVE"}
        ]
    }
    # Static list — not from actual model registry
```

---

### [MOCK-06] Python AI Health Subcomponents
```python
# api_router.py lines 162-173
"ai_supervisor": "ONLINE",    # Always
"rag_engine": "ONLINE",       # Always
"auth_guard": "ACTIVE",       # Always
"causal_dag": "ACTIVE",       # Always
"nlu_engine": "ACTIVE",       # Always
"semantic_cache": "ACTIVE",   # Always
"event_correlation": "ACTIVE",# Always
"planner_critic": "ACTIVE"    # Always
```

---

### [MOCK-07] LoRA Training Pipeline — Placeholder
**File:** SERVER/python_ai_core/learning/lora_training_pipeline_orchestrator.py  
**Evidence:** File named "orchestrator" but based on directory analysis, actual training logic not implemented  
**Status:** PLACEHOLDER — file exists, real training not connected

---

## DISABLED / UNREACHABLE CODE

### [DEAD-01] DB Read Replica (Prepared but Disabled)
```go
// database.go lines 269-274
readHost := getEnv("DB_READ_HOST", "")
if readHost != "" && readHost != host {
    readDSN := fmt.Sprintf("host=%s ...", readHost, ...)
    _ = readDSN  // Read replica DSN ready for DBResolver plugin
    // NEVER USED — DBResolver plugin not activated
}
```

### [DEAD-02] LDAP Auth Stub
**File:** portal/ldap_auth.go (600 bytes)  
**Evidence:** Very small file — almost certainly a stub with empty implementation

### [DEAD-03] cognitive_memory.db at Root Level
**File:** /home/it-itsm/AI/incident-analysis/cognitive_memory.db  
**Evidence:** SQLite file at root — not referenced in docker-compose, possibly orphaned development artifact

### [DEAD-04] n8n Integration — Class Exists, Never Called
**File:** SERVER/integration/n8n/n8n_dispatcher.py  
**Evidence:** Imported in noc_bridge.py with `get_n8n_dispatcher = None` fallback if import fails  
**Status:** Class exists but trigger from incident lifecycle not found

---

## UNUSED FEATURE FLAGS

| Flag | Default | Used | Notes |
|------|---------|------|-------|
| DEV_MODE | true | Unknown usage | Set in .env but handler code not verified |
| MIGRATE_DB | false | database.go L279 | Schema migration gate — requires manual set |
| DB_READ_HOST | "" | database.go L269 | Read replica — never activated |

---

## RECOMMENDATIONS

1. **Remove RetrainClassifier mock** — return error "not implemented" until real training
2. **Replace api_router.py mock handlers** with real implementations
3. **Either implement or remove** lora_training_pipeline_orchestrator.py
4. **Activate or remove** DB read replica code
5. **Complete or remove** ldap_auth.go
6. **Wire or remove** n8n_dispatcher.py from incident lifecycle
7. **Delete** cognitive_memory.db from root if not needed
