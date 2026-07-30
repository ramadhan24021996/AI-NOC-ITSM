"""
DLQ Batch Processor — Membersihkan entry PENDING lama dengan error spesifik.

Strategi:
- error "name 'models_used' is not defined" → RESOLVED (bug sudah dipatch)  
- error "connection already closed"           → RESOLVED (transient DB conn error)
- error "nats: timeout"                       → RETRY (kirim ulang ke NATS)

Jalankan satu kali setelah patch ai_supervisor.py:
  python3 /app/services/dlq_batch_processor.py
"""

import asyncio
import json
import logging
import os
import sys
import psycopg2
import psycopg2.extras

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s — %(message)s'
)
logger = logging.getLogger("DLQ_BATCH_PROCESSOR")

DB_HOST     = os.environ.get("DB_HOST", "postgres")
DB_PORT     = os.environ.get("DB_PORT", "5432")
DB_NAME     = os.environ.get("DB_NAME", "osi_system")
DB_USER     = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("POSTGRES_PASSWORD", "SecurePassword_123!"))

NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")

# Errors that are permanently resolved now that the patch is applied
RESOLVED_ERRORS = [
    "name 'models_used' is not defined",   # Bug fixed in ai_supervisor.py
    "connection already closed",            # Transient DB conn — safe to discard
    "object NoneType can't be used in 'await' expression",
]

# Errors that should be retried
RETRY_ERRORS = [
    "nats: timeout",
    "timeout",
]

def get_db():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD
    )

async def process_dlq():
    conn = get_db()
    conn.autocommit = False
    resolved = 0
    retried  = 0
    skipped  = 0

    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        # Fetch all PENDING items
        cur.execute("""
            SELECT dlq_id, payload, reason, retry_count, error_code
            FROM dlq_hybrid
            WHERE status IN ('PENDING', 'PROCESSING')
            ORDER BY dlq_id ASC
        """)
        rows = cur.fetchall()
        total = len(rows)
        logger.info(f"Found {total} PENDING/PROCESSING DLQ entries to process.")

        for row in rows:
            dlq_id     = row["dlq_id"]
            reason     = (row["reason"] or "").lower()
            retry_cnt  = row["retry_count"] or 0
            error_code = row["error_code"] or ""

            # Check if error is permanently resolved
            is_resolved = any(err.lower() in reason for err in RESOLVED_ERRORS)
            is_retry    = any(err.lower() in reason for err in RETRY_ERRORS)

            if is_resolved:
                # Mark as RESOLVED — bug has been patched
                cur.execute("""
                    UPDATE dlq_hybrid
                    SET status      = 'RESOLVED',
                        resolved_at = NOW(),
                        replayed_by = 'dlq_batch_processor_v1',
                        stack_trace = 'Auto-resolved: bug patched in ai_supervisor.py (models_used fix)'
                    WHERE dlq_id = %s
                """, (dlq_id,))
                resolved += 1
                if resolved % 50 == 0:
                    conn.commit()
                    logger.info(f"  → Resolved {resolved} entries so far...")

            elif is_retry and retry_cnt < 3:
                # Only retry if under max retry threshold
                cur.execute("""
                    UPDATE dlq_hybrid
                    SET status       = 'PENDING',
                        retry_count  = retry_count + 1,
                        last_attempt = NOW()
                    WHERE dlq_id = %s
                """, (dlq_id,))
                retried += 1

            else:
                # Mark as FAILED (poison pill or max retry exceeded)
                cur.execute("""
                    UPDATE dlq_hybrid
                    SET status       = 'FAILED',
                        is_poison    = true,
                        resolved_at  = NOW(),
                        stack_trace  = 'Max retries exceeded or unresolvable error'
                    WHERE dlq_id = %s AND retry_count >= 3
                """, (dlq_id,))
                skipped += 1

        conn.commit()

    conn.close()
    logger.info(f"✅ DLQ Batch Processing selesai:")
    logger.info(f"   Resolved (bug patched):  {resolved}")
    logger.info(f"   Retried (transient err): {retried}")
    logger.info(f"   Skipped (poison/max):    {skipped}")
    logger.info(f"   Total processed:         {total}")
    return resolved, retried, skipped

async def verify_remaining():
    """Verify how many PENDING entries remain after cleanup."""
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT status, COUNT(*) FROM dlq_hybrid 
            GROUP BY status ORDER BY status
        """)
        rows = cur.fetchall()
    conn.close()
    logger.info("=== DLQ Status After Cleanup ===")
    for row in rows:
        logger.info(f"  {row[0]:15s}: {row[1]}")

async def main():
    logger.info("=== DLQ Batch Processor v1.0 ===")
    logger.info(f"DB: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    
    resolved, retried, skipped = await process_dlq()
    await verify_remaining()
    
    return resolved

if __name__ == "__main__":
    asyncio.run(main())
