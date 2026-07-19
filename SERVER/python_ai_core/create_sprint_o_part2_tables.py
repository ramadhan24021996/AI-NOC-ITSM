import psycopg2
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SprintOPart2_Migration")

DDL_QUERIES = [
    """
    CREATE TABLE IF NOT EXISTS ai_prompt_evaluation (
        id SERIAL PRIMARY KEY,
        prompt_version VARCHAR(50),
        diag_accuracy FLOAT,
        rca_accuracy FLOAT,
        hallucination_rate FLOAT,
        engineer_agreement FLOAT,
        latency_sec FLOAT,
        status VARCHAR(50),
        evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_evidence_quality (
        id SERIAL PRIMARY KEY,
        incident_id VARCHAR(50),
        metrics_score FLOAT,
        logs_score FLOAT,
        topology_score FLOAT,
        overall_score FLOAT,
        evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_rca_validation (
        id SERIAL PRIMARY KEY,
        incident_id VARCHAR(50),
        ai_pred TEXT,
        human_rca TEXT,
        layer_difference INT,
        root_cause_match BOOLEAN,
        reason TEXT,
        validated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_knowledge_coverage (
        id SERIAL PRIMARY KEY,
        domain VARCHAR(100),
        coverage_percentage FLOAT,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_capability_score (
        id SERIAL PRIMARY KEY,
        monitoring_score FLOAT,
        reasoning_score FLOAT,
        knowledge_score FLOAT,
        conversation_score FLOAT,
        prediction_score FLOAT,
        trust_score FLOAT,
        evidence_score FLOAT,
        governance_score FLOAT,
        overall_score FLOAT,
        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_continuous_improvement (
        id SERIAL PRIMARY KEY,
        knowledge_gaps INT,
        playbook_failures INT,
        hallucination_rate FLOAT,
        suggestion_payload JSONB,
        report_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        logger.info("Sprint O Part 2 Tables Created Successfully!")
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Migration Failed: {e}")

if __name__ == "__main__":
    run_migration()
