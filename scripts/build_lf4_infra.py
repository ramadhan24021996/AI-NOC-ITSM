#!/usr/bin/env python3
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../SERVER/python_ai_core/learning/infrastructure'))

MANAGER_CODE = '''import psycopg2
from typing import Dict, Any, List
from datetime import datetime

class InfrastructureLearningManager:
    def __init__(self, db_config: Dict[str, Any]):
        self.conn = psycopg2.connect(**db_config)
        self.conn.autocommit = True

    def register_device(self, device_id: str, hostname: str, vendor: str, role: str):
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO infra_registry (device_id, hostname, vendor, role)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (device_id) DO NOTHING
        """, (device_id, hostname, vendor, role))
        cur.close()

    def update_baseline(self, device_id: str, metric_name: str, values: List[float]):
        """ Simple mathematical baseline builder """
        if not values: return
        import statistics
        avg_val = sum(values) / len(values)
        std_dev = statistics.stdev(values) if len(values) > 1 else 0.0
        sorted_vals = sorted(values)
        p95 = sorted_vals[int(len(sorted_vals) * 0.95)]
        p99 = sorted_vals[int(len(sorted_vals) * 0.99)] if len(sorted_vals) >= 100 else sorted_vals[-1]
        
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO infra_baseline (device_id, metric_name, p95_value, p99_value, avg_value, std_dev)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (device_id, metric_name) 
            DO UPDATE SET p95_value = EXCLUDED.p95_value, p99_value = EXCLUDED.p99_value,
                          avg_value = EXCLUDED.avg_value, std_dev = EXCLUDED.std_dev,
                          calculated_at = CURRENT_TIMESTAMP
        """, (device_id, metric_name, p95, p99, avg_val, std_dev))
        
        cur.execute("INSERT INTO infra_audit (device_id, event, details) VALUES (%s, %s, %s)",
                    (device_id, "BASELINE_UPDATED", f"Metric {metric_name} updated."))
        cur.close()

    def log_pattern(self, device_id: str, pattern_type: str, description: str, confidence: float):
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO infra_patterns (device_id, pattern_type, description, confidence)
            VALUES (%s, %s, %s, %s)
        """, (device_id, pattern_type, description, confidence))
        cur.close()

    def log_degradation(self, device_id: str, metric_name: str, start: datetime, end: datetime, severity: str, peak: float):
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO infra_degradation_history (device_id, metric_name, start_time, end_time, severity, peak_value)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (device_id, metric_name, start, end, severity, peak))
        cur.execute("INSERT INTO infra_audit (device_id, event, details) VALUES (%s, %s, %s)",
                    (device_id, "DEGRADATION_DETECTED", f"{metric_name} hit {severity} at peak {peak}"))
        cur.close()
'''

DIRS = [
    "registry", "extractor", "timeline", "trend", "seasonality",
    "correlation", "evaluator", "metrics", "audit", "api"
]

def build_lf4_scaffold():
    for d in DIRS:
        dpath = os.path.join(BASE_DIR, d)
        os.makedirs(dpath, exist_ok=True)
        init_file = os.path.join(dpath, "__init__.py")
        if not os.path.exists(init_file):
            open(init_file, 'a').close()
            
    svc_path = os.path.join(BASE_DIR, 'services')
    os.makedirs(svc_path, exist_ok=True)
    with open(os.path.join(svc_path, 'manager.py'), 'w') as f:
        f.write(MANAGER_CODE)
    print("[+] Written LF-4 InfrastructureLearningManager logic")

if __name__ == "__main__":
    build_lf4_scaffold()
