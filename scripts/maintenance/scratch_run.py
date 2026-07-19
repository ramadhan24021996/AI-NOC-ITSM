import sys, traceback
sys.path.append('/home/it-itsm/AI/incident-analysis/SERVER/python_ai_core')
from evaluation.cognitive_kpi_engine import CognitiveKPIEngine

import os
e = CognitiveKPIEngine(db_params={
    "host": "localhost",
    "port": "15432",
    "database": "osi_system",
    "user": "postgres",
    "password": "postgres_password"
})
e.db_params['password'] = 'postgres'

try:
    e.generate_all_reports(24)
except Exception as ex:
    traceback.print_exc()
