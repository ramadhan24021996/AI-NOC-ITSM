import psycopg2
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DB_INIT_KG")

def create_tables():
    db_password = os.environ.get("DB_PASSWORD", "SecurePassword_123!")
    conn = psycopg2.connect(
        dbname=os.environ.get("DB_NAME", "osi_system"),
        user="postgres",
        password=db_password,
        host="localhost",
        port="5433"
    )
    conn.autocommit = True
    
    with conn.cursor() as cur:
        # Create Nodes Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_graph_nodes (
                node_id VARCHAR(255) PRIMARY KEY,
                node_type VARCHAR(100) NOT NULL,
                properties JSONB DEFAULT '{}'::jsonb,
                criticality INT DEFAULT 1,
                last_seen TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Create Edges Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_graph_edges (
                edge_id SERIAL PRIMARY KEY,
                source_id VARCHAR(255) REFERENCES knowledge_graph_nodes(node_id),
                target_id VARCHAR(255) REFERENCES knowledge_graph_nodes(node_id),
                relationship VARCHAR(100) NOT NULL,
                confidence FLOAT DEFAULT 1.0,
                source_engine VARCHAR(100) DEFAULT 'LLM',
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(source_id, target_id, relationship)
            )
        """)
        
    logger.info("Knowledge Graph tables created successfully.")
    conn.close()

if __name__ == "__main__":
    create_tables()
