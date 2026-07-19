#!/usr/bin/env python3
import psycopg2
import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [RETENTION] %(levelname)s: %(message)s')

DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "osi_production")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        return conn
    except Exception as e:
        # Fallback for local docker mapping if 5432 fails
        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                port="5433",
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
            )
            return conn
        except Exception as e2:
            logging.error(f"Failed to connect to database: {e2}")
            sys.exit(1)

def run_retention_policy():
    conn = get_db_connection()
    conn.autocommit = False
    cur = conn.cursor()
    
    try:
        logging.info("Starting automated data retention and housekeeping...")
        
        # 1. Telemetry Logs Retention: Delete raw telemetry older than 24 hours
        logging.info("Cleaning up telemetry_logs older than 24 hours...")
        cur.execute("""
            DELETE FROM telemetry_logs 
            WHERE timestamp < NOW() - INTERVAL '24 hours';
        """)
        deleted_telemetry = cur.rowcount
        logging.info(f"Deleted {deleted_telemetry} rows from telemetry_logs.")
        
        # 2. Incident Archival: Mark incidents older than 14 days as ARCHIVED
        # Only archive incidents that are already RESOLVED
        logging.info("Archiving RESOLVED incidents older than 14 days...")
        cur.execute("""
            UPDATE fleet_incidents 
            SET status = 'ARCHIVED' 
            WHERE created_at < NOW() - INTERVAL '14 days' 
              AND status = 'RESOLVED';
        """)
        archived_incidents = cur.rowcount
        logging.info(f"Archived {archived_incidents} incidents.")
        
        # 3. Data Pruning (1 Month): Delete heavy audit/event logs older than 30 days
        # We DO NOT delete from fleet_incidents or incident_post_mortems
        # to ensure AI cognitive memory is retained indefinitely for resolved issues.
        logging.info("Pruning heavy audit and event logs older than 30 days (keeping cognitive memory)...")
        
        heavy_tables = [
            "incident_events", 
            "ai_audit_trail", 
            "verification_logs", 
            "chat_messages",
            "rollback_logs"
        ]
        
        for table in heavy_tables:
            try:
                cur.execute(f"""
                    DELETE FROM {table} 
                    WHERE created_at < NOW() - INTERVAL '30 days';
                """)
                logging.info(f"Deleted {cur.rowcount} rows from {table}.")
            except psycopg2.Error as e:
                # If table doesn't exist or column doesn't match, ignore and rollback the sub-transaction
                conn.rollback()
                logging.warning(f"Could not prune {table}: {e.pgerror.strip() if e.pgerror else e}")
            else:
                conn.commit() # Commit each table pruning separately to avoid massive transaction locks
        
        # 4. Optional: Clean up OLD partitions created by partition_migration.py if they are totally empty
        # This is a bit advanced, but typically deleting the rows is enough to free up logical space,
        # followed by a VACUUM which should be handled by postgres autovacuum.
        
        logging.info("Data retention policy applied successfully.")
        
    except Exception as e:
        conn.rollback()
        logging.error(f"An error occurred during retention execution: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    run_retention_policy()
