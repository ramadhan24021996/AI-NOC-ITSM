import asyncio
import json
import logging
import os
import sys
import nats
import psycopg2

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DLQ_SERVICE")

NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")

DB_HOST = os.environ.get("DB_HOST", "postgres")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "osi_system")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")

def get_db_connection():
    try:
        return psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return None

async def daemon():
    nc = await nats.connect(NATS_URL)
    logger.info(f"Connected to NATS at {NATS_URL} for DLQ Processing.")

    async def dlq_handler(msg):
        subject = msg.subject
        try:
            data = json.loads(msg.data.decode())
            logger.warning(f"Received DLQ message on {subject}: {data}")
            
            # Persist to database
            conn = get_db_connection()
            if conn:
                try:
                    with conn.cursor() as cur:
                        reason = data.get("error_reason") or f"DLQ event on {subject}"
                        site_id = data.get("site_id") or "global"
                        cur.execute("""
                            INSERT INTO dlq_hybrid (payload, reason, status, site_id, created_at)
                            VALUES (%s, %s, %s, %s, NOW())
                        """, (json.dumps(data), reason, "PENDING", site_id))
                        conn.commit()
                except Exception as db_err:
                    logger.error(f"Failed to insert into dlq_hybrid: {db_err}")
                    conn.rollback()
                finally:
                    conn.close()
                    
            # PENDING_REVIEW: Send Telegram Alert via HTTP request to Telegram Bot API
            
        except Exception as e:
            logger.error(f"Error processing DLQ message: {e}")

    await nc.subscribe("dlq.site.*", cb=dlq_handler)
    logger.info("DLQ Service is active and listening on 'dlq.site.*'.")

    while True:
        await asyncio.sleep(3600)

async def main():
    await daemon()

if __name__ == '__main__':
    asyncio.run(main())
