import psycopg2
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RAG_SCHEMA_V2")

def create_sprint_q_tables():
    # Gunakan port 5433 karena ini berjalan di host dan di-map ke docker postgres
    db_host = os.environ.get("DB_HOST", "127.0.0.1")
    db_port = os.environ.get("DB_PORT", "5433") 
    db_name = os.environ.get("DB_NAME", "osi_system")
    db_user = os.environ.get("DB_USER", "postgres")
    db_pass = os.environ.get("DB_PASSWORD", "postgres")

    conn = psycopg2.connect(host=db_host, port=db_port, dbname=db_name, user=db_user, password=db_pass)
    conn.autocommit = True
    cur = conn.cursor()

    try:
        logger.info("Membangun Arsitektur Relational RAG V2 (Enterprise Knowledge OS)...")

        # 1. Base Knowledge Table (V2)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_v2_documents (
                doc_id VARCHAR(50) PRIMARY KEY,
                domain_layer VARCHAR(50) NOT NULL, 
                category VARCHAR(50) NOT NULL, 
                title VARCHAR(255) NOT NULL,
                osi_layer INTEGER,
                multimodal_type VARCHAR(50), 
                automation_allowed BOOLEAN DEFAULT FALSE,
                status VARCHAR(20) DEFAULT 'DRAFT', -- DRAFT, REVIEW, APPROVED, REJECTED, ARCHIVED
                severity VARCHAR(20),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 2. Knowledge Versioning & Lineage
        cur.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_v2_versions (
                id SERIAL PRIMARY KEY,
                doc_id VARCHAR(50) REFERENCES knowledge_v2_documents(doc_id) ON DELETE CASCADE,
                version VARCHAR(20) NOT NULL,
                effective_from TIMESTAMP NOT NULL,
                effective_until TIMESTAMP,
                valid_for_vendor VARCHAR(100),
                valid_for_os VARCHAR(100),
                valid_for_model VARCHAR(100),
                approved_by VARCHAR(100),
                change_reason TEXT,
                checksum VARCHAR(256),
                lineage_trace JSONB, 
                is_active BOOLEAN DEFAULT TRUE
            );
        """)

        # 3. Confidence History & Statistics
        cur.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_v2_statistics (
                doc_id VARCHAR(50) PRIMARY KEY REFERENCES knowledge_v2_documents(doc_id) ON DELETE CASCADE,
                success_rate FLOAT DEFAULT 0.0,
                failure_rate FLOAT DEFAULT 0.0,
                false_positive_count INTEGER DEFAULT 0,
                false_negative_count INTEGER DEFAULT 0,
                usage_count INTEGER DEFAULT 0,
                average_mttr_seconds INTEGER DEFAULT 0,
                last_used TIMESTAMP,
                dynamic_weight FLOAT DEFAULT 1.0 
            );
        """)

        # 4. Evidence Weight
        cur.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_v2_evidence (
                id SERIAL PRIMARY KEY,
                doc_id VARCHAR(50) REFERENCES knowledge_v2_documents(doc_id) ON DELETE CASCADE,
                evidence_type VARCHAR(20), 
                condition_rule TEXT NOT NULL,
                weight FLOAT DEFAULT 1.0, 
                certainty VARCHAR(20), 
                source VARCHAR(50),
                priority INTEGER
            );
        """)

        # 5. Root Cause Pattern & Failure Signature
        cur.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_v2_patterns (
                id SERIAL PRIMARY KEY,
                pattern_name VARCHAR(100) NOT NULL,
                signature_id VARCHAR(100) UNIQUE NOT NULL, 
                required_evidence JSONB,
                optional_evidence JSONB,
                counter_evidence JSONB,
                expected_root_cause TEXT,
                doc_id VARCHAR(50) REFERENCES knowledge_v2_documents(doc_id) ON DELETE CASCADE
            );
        """)

        # 6. Dependency Graph
        cur.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_v2_dependencies (
                id SERIAL PRIMARY KEY,
                doc_id VARCHAR(50) REFERENCES knowledge_v2_documents(doc_id) ON DELETE CASCADE,
                upstream_component VARCHAR(100),
                downstream_component VARCHAR(100),
                dependency_type VARCHAR(50),
                blast_radius_desc TEXT
            );
        """)

        # 7. Device Taxonomy
        cur.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_v2_taxonomy (
                id SERIAL PRIMARY KEY,
                doc_id VARCHAR(50) REFERENCES knowledge_v2_documents(doc_id) ON DELETE CASCADE,
                category VARCHAR(50), 
                vendor VARCHAR(50),
                os_family VARCHAR(50),
                role VARCHAR(50) 
            );
        """)

        # 8. Vector Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_v2_embeddings (
                id SERIAL PRIMARY KEY,
                doc_id VARCHAR(50) REFERENCES knowledge_v2_documents(doc_id) ON DELETE CASCADE,
                embedding vector(768), 
                embedding_model VARCHAR(50), 
                chunk_text TEXT,
                domain_layer VARCHAR(50) 
            );
        """)

        # 9. Knowledge Validation (New)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_v2_validation (
                validation_id SERIAL PRIMARY KEY,
                doc_id VARCHAR(50) REFERENCES knowledge_v2_documents(doc_id) ON DELETE CASCADE,
                validator_type VARCHAR(50), -- human, critic, benchmark, replay
                validation_result VARCHAR(50), -- PASSED, FAILED, NEEDS_REVIEW
                confidence FLOAT,
                notes TEXT,
                validated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 10. Remediation Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_v2_remediation (
                id SERIAL PRIMARY KEY,
                doc_id VARCHAR(50) REFERENCES knowledge_v2_documents(doc_id) ON DELETE CASCADE,
                action_name VARCHAR(100),
                action_payload JSONB,
                verification_rule TEXT, 
                rollback_rule TEXT,
                risk_level VARCHAR(20) 
            );
        """)

        # 11. Experiment Registry & Retrieval Audit
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rag_experiments (
                experiment_id VARCHAR(50) PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                started_at TIMESTAMP DEFAULT NOW(),
                ended_at TIMESTAMP,
                retrieval_model VARCHAR(50),
                embedding_model VARCHAR(50),
                is_active BOOLEAN DEFAULT FALSE,
                traffic_percentage INTEGER DEFAULT 0,
                owner VARCHAR(50)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rag_retrieval_log (
                id SERIAL PRIMARY KEY,
                incident_id VARCHAR(100),
                experiment_id VARCHAR(50),
                query TEXT,
                retrieved_docs JSONB,
                latency_ms INTEGER,
                similarity_score FLOAT,
                accepted_by_critic BOOLEAN,
                critic_score FLOAT,
                human_score FLOAT, 
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS embedding_models (
                model_name VARCHAR(100) PRIMARY KEY,
                dimension INTEGER,
                provider VARCHAR(50),
                cost_per_token FLOAT,
                status VARCHAR(20),
                effective_date TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_health (
                domain VARCHAR(50) PRIMARY KEY,
                coverage_percent FLOAT DEFAULT 0.0,
                total_docs INTEGER DEFAULT 0,
                last_calculated TIMESTAMP DEFAULT NOW()
            );
        """)

        # ---------------------------------------------------------
        # INDEX CREATION
        # ---------------------------------------------------------
        logger.info("Creating B-Tree, GIN, and HNSW indexes...")
        
        # B-Tree Indexes for fast filtering and joins
        cur.execute("CREATE INDEX IF NOT EXISTS idx_kdoc_category ON knowledge_v2_documents(category);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_kdoc_status ON knowledge_v2_documents(status);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_kdoc_layer ON knowledge_v2_documents(osi_layer);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_kdoc_severity ON knowledge_v2_documents(severity);")
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_kver_dates ON knowledge_v2_versions(effective_from, effective_until);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_kver_vendor ON knowledge_v2_versions(valid_for_vendor);")
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ktax_category ON knowledge_v2_taxonomy(category);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ktax_vendor ON knowledge_v2_taxonomy(vendor);")
        
        # GIN Indexes for JSONB columns
        cur.execute("CREATE INDEX IF NOT EXISTS idx_kver_lineage ON knowledge_v2_versions USING GIN (lineage_trace);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_kpat_req_ev ON knowledge_v2_patterns USING GIN (required_evidence);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_kpat_opt_ev ON knowledge_v2_patterns USING GIN (optional_evidence);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_kpat_ctr_ev ON knowledge_v2_patterns USING GIN (counter_evidence);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_krem_payload ON knowledge_v2_remediation USING GIN (action_payload);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_raglog_docs ON rag_retrieval_log USING GIN (retrieved_docs);")
        
        # HNSW Index for pgvector (optimizing cosine distance similarity)
        # Using vector_cosine_ops for <=> operator
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_kemb_vector 
            ON knowledge_v2_embeddings 
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64);
        """)

        logger.info("SUCCESS: Schema Relational RAG V2 & Indexes berhasil diterapkan di database produksi!")

    except Exception as e:
        logger.error(f"Gagal membuat schema V2: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    create_sprint_q_tables()
