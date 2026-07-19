import psycopg2
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SprintO_Migration")

DDL_QUERIES = [
    """
    CREATE TABLE IF NOT EXISTS ai_engineer_benchmark (
        id SERIAL PRIMARY KEY,
        incident_id VARCHAR(50),
        ai_diagnosis TEXT,
        human_diagnosis TEXT,
        ai_rca TEXT,
        human_rca TEXT,
        ai_solution TEXT,
        human_solution TEXT,
        final_resolution TEXT,
        ai_diagnosis_correct BOOLEAN,
        ai_rca_correct BOOLEAN,
        ai_solution_correct BOOLEAN,
        false_positive BOOLEAN,
        false_negative BOOLEAN,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_drift_metrics (
        id SERIAL PRIMARY KEY,
        metric_type VARCHAR(50), 
        target_name VARCHAR(255), 
        baseline_success_rate FLOAT,
        current_success_rate FLOAT,
        drift_percentage FLOAT,
        detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_recommendation_benchmark (
        id SERIAL PRIMARY KEY,
        incident_id VARCHAR(50),
        recommendation TEXT,
        was_selected BOOLEAN,
        was_successful BOOLEAN,
        downtime_minutes FLOAT,
        mttr_minutes FLOAT,
        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_gold_dataset (
        id SERIAL PRIMARY KEY,
        incident_data JSONB,
        evidence JSONB,
        final_rca TEXT,
        engineer_action TEXT,
        verification_steps TEXT,
        outcome TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_governance_audit (
        id SERIAL PRIMARY KEY,
        asset_type VARCHAR(50), 
        asset_name VARCHAR(255),
        version_tag VARCHAR(50),
        author VARCHAR(100),
        approval_status VARCHAR(50),
        change_payload JSONB,
        rollback_payload JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
]

def run_migration():
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=os.getenv("DB_PORT", "5432"),
            database=os.getenv("DB_NAME", "osi_system"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "postgres")
        )
        cur = conn.cursor()
        for q in DDL_QUERIES:
            cur.execute(q)
        conn.commit()
        logger.info("Sprint O Tables Created Successfully!")
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Migration Failed: {e}")

if __name__ == "__main__":
    run_migration()
