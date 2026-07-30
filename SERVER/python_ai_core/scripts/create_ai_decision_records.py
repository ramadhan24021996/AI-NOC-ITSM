import os
import psycopg2

def create_table():
    db_host = os.environ.get("DB_HOST", "postgres")
    db_port = os.environ.get("DB_PORT", "5432")
    db_name = os.environ.get("DB_NAME", "incident_db")
    db_user = os.environ.get("DB_USER", "postgres")
    db_password = os.environ.get("DB_PASSWORD", "postgres")

    conn = psycopg2.connect(
        host=db_host,
        port=db_port,
        dbname=db_name,
        user=db_user,
        password=db_password
    )
    conn.autocommit = True
    
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS autonomous_decision_records (
                decision_id UUID PRIMARY KEY,
                incident_id VARCHAR(50) NOT NULL,
                agent_id VARCHAR(50),
                policy_version VARCHAR(20),
                prompt_version VARCHAR(20),
                reasoning_version VARCHAR(20),
                knowledge_version VARCHAR(20),
                evidence_hash VARCHAR(64),
                evidence_timestamp TIMESTAMP WITH TIME ZONE,
                evidence_freshness_sec FLOAT,
                confidence FLOAT,
                expected_version INT,
                execution_id VARCHAR(50),
                execution_token_hash VARCHAR(64),
                verification_result VARCHAR(50),
                average_confidence FLOAT,
                final_outcome VARCHAR(50),
                reasoning_summary JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_ai_decision_incident ON autonomous_decision_records(incident_id);
            CREATE INDEX IF NOT EXISTS idx_ai_decision_agent ON autonomous_decision_records(agent_id);
        """)
        
    print("Table autonomous_decision_records created successfully.")
    conn.close()

if __name__ == "__main__":
    create_table()
