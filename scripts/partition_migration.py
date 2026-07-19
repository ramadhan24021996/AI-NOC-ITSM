import psycopg2
import sys
import os
import datetime

# Database connection credentials
DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("DB_PORT", "5433") # Expose port is 5433
DB_NAME = os.environ.get("DB_NAME", "osi_system")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")

def get_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def execute_sql(conn, query, args=None):
    with conn.cursor() as cur:
        cur.execute(query, args)
    conn.commit()

def migrate_table_to_partitioned(conn, table_name, partition_key, columns_def, select_columns, indexes_def):
    print(f"Migrating table: {table_name}...")
    with conn.cursor() as cur:
        # Check if table is already partitioned
        cur.execute(f"""
            SELECT relkind FROM pg_class 
            WHERE relname = '{table_name}' AND relnamespace = 'public'::regnamespace
        """)
        row = cur.fetchone()
        if not row:
            print(f"Table {table_name} does not exist. Skipping.")
            return
        
        relkind = row[0]
        if relkind == 'p':
            print(f"Table {table_name} is already partitioned. Skipping migration.")
            return

        # 1. Rename existing table
        print(f"Renaming {table_name} to {table_name}_old...")
        cur.execute(f"ALTER TABLE {table_name} RENAME TO {table_name}_old")
        
        # 2. Create the partitioned table
        print(f"Creating partitioned table {table_name}...")
        cur.execute(f"""
            CREATE TABLE {table_name} (
                {columns_def}
            ) PARTITION BY RANGE ({partition_key})
        """)

        # 3. Create partitions for May, June, July, August, September 2026
        now = datetime.datetime.now()
        months = [now + datetime.timedelta(days=30*i) for i in range(-2, 4)]
        # ensure uniqueness of year-month pairs
        ym_pairs = sorted(list({(m.year, m.month) for m in months}))
        
        for y, m in ym_pairs:
            part_name = f"{table_name}_y{y}m{m:02d}"
            start_date = f"{y}-{m:02d}-01 00:00:00"
            if m == 12:
                end_date = f"{y+1}-01-01 00:00:00"
            else:
                end_date = f"{y}-{m+1:02d}-01 00:00:00"
            
            print(f"Creating partition {part_name} from {start_date} to {end_date}...")
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {part_name} 
                PARTITION OF {table_name}
                FOR VALUES FROM ('{start_date}') TO ('{end_date}')
            """)

        # 4. Copy data from old table to new partitioned table
        print(f"Copying data from {table_name}_old to {table_name}...")
        cur.execute(f"""
            INSERT INTO {table_name} ({select_columns})
            SELECT {select_columns} FROM {table_name}_old
        """)

        # 5. Recreate indexes
        print(f"Creating indexes for {table_name}...")
        for idx_sql in indexes_def:
            cur.execute(idx_sql)

        # 6. Drop old table
        print(f"Dropping {table_name}_old...")
        cur.execute(f"DROP TABLE {table_name}_old CASCADE")
        
    conn.commit()
    print(f"Migration of {table_name} completed successfully.\n")

def main():
    try:
        conn = get_conn()
        print("Connected to PostgreSQL successfully.")
    except Exception as e:
        print(f"Failed to connect to database: {e}")
        # Try default container port if running inside docker network
        global DB_PORT
        DB_PORT = "5432"
        try:
            conn = get_conn()
            print("Connected to PostgreSQL successfully (on port 5432).")
        except Exception as e2:
            print(f"Failed on both ports: {e2}")
            sys.exit(1)

    # 1. chat_messages
    chat_cols_def = """
        id SERIAL,
        client_id TEXT NOT NULL,
        sender TEXT NOT NULL,
        message TEXT,
        attachment_path TEXT,
        read_status TEXT DEFAULT 'SENT',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        delivered_at TIMESTAMP,
        read_at TIMESTAMP,
        attachment_type TEXT DEFAULT '',
        attachment_url TEXT DEFAULT '',
        incident_id INTEGER,
        thread_type TEXT DEFAULT 'OPERATOR',
        PRIMARY KEY (id, created_at)
    """
    chat_select = "client_id, sender, message, attachment_path, read_status, created_at, delivered_at, read_at, attachment_type, attachment_url, incident_id, thread_type"
    chat_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_chat_messages_client_id ON chat_messages (client_id)",
        "CREATE INDEX IF NOT EXISTS idx_chat_messages_client_created ON chat_messages(client_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_chat_messages_read_status ON chat_messages(read_status)",
        "CREATE INDEX IF NOT EXISTS idx_chat_messages_incident ON chat_messages(incident_id) WHERE incident_id IS NOT NULL",
        "CREATE INDEX IF NOT EXISTS idx_chat_messages_thread_type ON chat_messages(thread_type)"
    ]
    migrate_table_to_partitioned(conn, "chat_messages", "created_at", chat_cols_def, chat_select, chat_indexes)

    # 2. incident_events
    events_cols_def = """
        event_id SERIAL,
        incident_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        payload JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        trace_id TEXT,
        causal_chain TEXT[],
        site_id TEXT DEFAULT 'global',
        PRIMARY KEY (event_id, created_at)
    """
    events_select = "incident_id, event_type, payload, created_at, trace_id, causal_chain, site_id"
    events_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_incident_events_incident ON incident_events(incident_id)",
        "CREATE INDEX IF NOT EXISTS idx_incident_events_type ON incident_events(event_type)",
        "CREATE INDEX IF NOT EXISTS idx_incident_events_trace ON incident_events(trace_id) WHERE trace_id IS NOT NULL"
    ]
    migrate_table_to_partitioned(conn, "incident_events", "created_at", events_cols_def, events_select, events_indexes)

    # 3. verification_logs
    vlogs_cols_def = """
        id SERIAL,
        incident_id INTEGER,
        verification_status TEXT,
        service_alive BOOLEAN DEFAULT TRUE,
        port_open BOOLEAN DEFAULT TRUE,
        cpu_normalized BOOLEAN DEFAULT TRUE,
        memory_normalized BOOLEAN DEFAULT TRUE,
        logs_clean BOOLEAN DEFAULT TRUE,
        rollback_needed BOOLEAN DEFAULT FALSE,
        response_latency_ms INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (id, created_at)
    """
    vlogs_select = "incident_id, verification_status, service_alive, port_open, cpu_normalized, memory_normalized, logs_clean, rollback_needed, response_latency_ms, created_at"
    vlogs_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_verification_logs_incident ON verification_logs(incident_id)"
    ]
    migrate_table_to_partitioned(conn, "verification_logs", "created_at", vlogs_cols_def, vlogs_select, vlogs_indexes)

    # 4. ai_audit_trail
    audit_cols_def = """
        audit_id SERIAL,
        incident_id INTEGER,
        event_id TEXT NOT NULL,
        reasoning_dag JSONB,
        rag_vectors_retrieved JSONB,
        raw_prompt TEXT,
        llm_response TEXT,
        confidence_score REAL,
        action_executed TEXT,
        operator_feedback TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (audit_id, created_at)
    """
    audit_select = "incident_id, event_id, reasoning_dag, rag_vectors_retrieved, raw_prompt, llm_response, confidence_score, action_executed, operator_feedback, created_at"
    audit_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_ai_audit_trail_incident ON ai_audit_trail(incident_id)",
        "CREATE INDEX IF NOT EXISTS idx_ai_audit_trail_event_id ON ai_audit_trail(event_id)"
    ]
    migrate_table_to_partitioned(conn, "ai_audit_trail", "created_at", audit_cols_def, audit_select, audit_indexes)

    # 5. Create the automated partition management stored procedure and view
    print("Creating partition management helper objects...")
    execute_sql(conn, """
        CREATE OR REPLACE FUNCTION manage_partitions() RETURNS void AS $$
        DECLARE
            t_month TIMESTAMP;
            y INTEGER;
            m INTEGER;
            part_name TEXT;
            start_val TEXT;
            end_val TEXT;
            tables_to_partition TEXT[] := ARRAY['chat_messages', 'incident_events', 'verification_logs', 'ai_audit_trail'];
            tbl TEXT;
        BEGIN
            -- Create partition for next month
            t_month := NOW() + INTERVAL '1 month';
            y := EXTRACT(YEAR FROM t_month);
            m := EXTRACT(MONTH FROM t_month);
            
            start_val := y || '-' || LPAD(m::text, 2, '0') || '-01 00:00:00';
            IF m = 12 THEN
                end_val := (y+1) || '-01-01 00:00:00';
            ELSE
                end_val := y || '-' || LPAD((m+1)::text, 2, '0') || '-01 00:00:00';
            END IF;

            FOREACH tbl IN ARRAY tables_to_partition LOOP
                part_name := tbl || '_y' || y || 'm' || LPAD(m::text, 2, '0');
                EXECUTE 'CREATE TABLE IF NOT EXISTS ' || part_name || 
                        ' PARTITION OF ' || tbl || 
                        ' FOR VALUES FROM (' || quote_literal(start_val) || ') TO (' || quote_literal(end_val) || ')';
            END LOOP;
        END;
        $$ LANGUAGE plpgsql;
    """)

    execute_sql(conn, """
        CREATE OR REPLACE VIEW v_incident_retention_audit AS
        SELECT
            schemaname,
            tablename,
            pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS partition_size,
            CASE
                WHEN tablename ~ 'y(\d{4})m(\d{2})' THEN
                    to_date(
                        substring(tablename from 'y(\d{4})') || '-' ||
                        substring(tablename from 'm(\d{2})') || '-01',
                        'YYYY-MM-DD'
                    )
                ELSE NULL
            END AS partition_month,
            CASE
                WHEN to_date(
                    substring(tablename from 'y(\d{4})') || '-' ||
                    substring(tablename from 'm(\d{2})') || '-01',
                    'YYYY-MM-DD'
                ) < NOW() - INTERVAL '6 months'
                THEN 'ELIGIBLE_FOR_DROP'
                ELSE 'RETAIN'
            END AS retention_status
        FROM pg_tables
        WHERE schemaname = 'public' 
          AND (tablename LIKE 'chat_messages_y%' 
               OR tablename LIKE 'incident_events_y%' 
               OR tablename LIKE 'verification_logs_y%' 
               OR tablename LIKE 'ai_audit_trail_y%')
        ORDER BY tablename ASC;
    """)
    print("Partition helper objects created successfully.")

    conn.close()
    print("Database migration completed.")

if __name__ == "__main__":
    main()
