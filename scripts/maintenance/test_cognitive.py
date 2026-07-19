import sys
import json
import psycopg2
import os

sys.path.append('SERVER/python_ai_core')
from knowledge.world_model import WorldModel
from planning.goal_engine import GoalEngine

try:
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "postgres"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "osi_system"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "postgres")
    )
    print("DB Connected")
    wm = WorldModel(conn)
    print("World Model Summary:", wm.get_infrastructure_summary())
    
    ge = GoalEngine(conn)
    print("Goals:", ge.get_active_goals())
except Exception as e:
    print("Error:", e)
