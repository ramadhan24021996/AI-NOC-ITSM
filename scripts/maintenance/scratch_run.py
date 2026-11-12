import sys, traceback
sys.path.append('/home/it-itsm/AI/incident-analysis/SERVER/python_ai_core')
from evaluation.cognitive_kpi_engine import CognitiveKPIEngine

import os
db_pass = os.environ.get("DB_PASSWORD", os.environ.get("POSTGRES_PASSWORD", ""))
e = CognitiveKPIEngine(db_params={
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": os.environ.get("DB_PORT", "15432"),
    "database": os.environ.get("DB_NAME", "osi_system"),
    "user": os.environ.get("DB_USER", "postgres"),
    "password": db_pass
})

try:
    e.generate_all_reports(24)
except Exception as ex:
    traceback.print_exc()
