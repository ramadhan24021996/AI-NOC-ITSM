"""
supervisor/handlers/background_loops.py
----------------------------------------
Autonomous background daemons & loop workers for AI Supervisor.
Includes:
- autonomous_data_retention
- heartbeat_loop
- trust_evaluator_loop
- sync_human_rejections_loop
- world_model_loop_async
- predictive_loop_async
"""
import asyncio
import json
import logging
import os
import time

logger = logging.getLogger("AI_SUPERVISOR.background_loops")


async def autonomous_data_retention():
    """Background task to enforce data retention policy directly inside the AI agent."""
    import psycopg2
    db_host = os.environ.get("DB_HOST", "127.0.0.1")
    db_port = os.environ.get("DB_PORT", "5432")
    db_name = os.environ.get("DB_NAME", "osi_system")
    db_user = os.environ.get("DB_USER", "postgres")
    db_pass = os.environ.get("DB_PASSWORD", "")

    while True:
        logger.info("[RETENTION_DAEMON] Waking up to execute autonomous data retention policy...")
        try:
            conn = psycopg2.connect(host=db_host, port=db_port, dbname=db_name, user=db_user, password=db_pass)
            conn.autocommit = False
            cur = conn.cursor()
            
            # 1. Telemetry
            cur.execute("DELETE FROM telemetry_logs WHERE timestamp < NOW() - INTERVAL '24 hours';")
            
            # 2. Archival
            cur.execute("UPDATE fleet_incidents SET status = 'ARCHIVED' WHERE created_at < NOW() - INTERVAL '14 days' AND status = 'RESOLVED';")
            
            # 3. Pruning [WS-10 / S-07]
            # ai_audit_trail, verification_logs, and rollback_logs are APPEND-ONLY and NEVER pruned.
            transient_tables = ["chat_messages"]
            for table in transient_tables:
                try:
                    cur.execute(f"DELETE FROM {table} WHERE created_at < NOW() - INTERVAL '30 days';")
                except Exception:
                    conn.rollback()
                else:
                    conn.commit()
            
            conn.commit()
            cur.close()
            conn.close()
            logger.info("[RETENTION_DAEMON] DB retention policy executed successfully.")

            # 4. Autonomous Vacuum & Index Optimization for pgvector & High-Throughput Tables
            # VACUUM cannot run inside an explicit transaction block, so autocommit=True is mandated.
            try:
                conn_vac = psycopg2.connect(host=db_host, port=db_port, dbname=db_name, user=db_user, password=db_pass)
                conn_vac.autocommit = True
                cur_vac = conn_vac.cursor()
                for tbl in ["knowledge_vectors", "fleet_incidents", "telemetry_logs"]:
                    try:
                        cur_vac.execute(f"VACUUM (ANALYZE) {tbl};")
                    except Exception as tbl_err:
                        logger.debug(f"[RETENTION_DAEMON] Table {tbl} vacuum skipped: {tbl_err}")
                cur_vac.close()
                conn_vac.close()
                logger.info("[RETENTION_DAEMON] pgvector & telemetry VACUUM (ANALYZE) completed successfully.")
            except Exception as vac_err:
                logger.warning(f"[RETENTION_DAEMON] Autonomous vacuum notice (non-fatal): {vac_err}")
        except Exception as e:
            logger.error(f"[RETENTION_DAEMON] DB retention failed: {e}")

        # ── FIX: SOP File Cleanup — konsolidasi legacy files & hapus duplikat ──
        # (sebelumnya tidak ada — 248 file tidak pernah dibersihkan!)
        try:
            await _cleanup_sop_sprawl()
        except Exception as e:
            logger.warning("[RETENTION_DAEMON] SOP cleanup error (non-fatal): %s", e)

        logger.info("[RETENTION_DAEMON] Retention cycle complete. Sleeping for 12 hours.")
        await asyncio.sleep(12 * 3600)


async def _cleanup_sop_sprawl() -> None:
    """
    FIX: Bersihkan SOP file sprawl di auto_generated_sops/.
    - Panggil KnowledgeAutoBuilder.migrate_legacy_files() untuk konsolidasi
    - Hapus file legacy sop_auto_*.md yang sudah di-merge ke canonical
    - Log ringkasan cleanup
    """
    try:
        try:
            from python_ai_core.knowledge.knowledge_auto_builder import KnowledgeAutoBuilder
        except ImportError:
            from knowledge.knowledge_auto_builder import KnowledgeAutoBuilder

        builder = KnowledgeAutoBuilder()

        # Hitung legacy files sebelum cleanup
        sop_dir = builder.output_dir
        legacy_before = len([
            f for f in os.listdir(sop_dir)
            if f.startswith("sop_auto_") and f.endswith(".md")
               and os.path.isfile(os.path.join(sop_dir, f))
        ])

        if legacy_before == 0:
            logger.info("[RETENTION_DAEMON][SOP] Tidak ada legacy SOP files untuk dibersihkan.")
            return

        logger.info("[RETENTION_DAEMON][SOP] Ditemukan %d legacy SOP files. Memulai konsolidasi...", legacy_before)

        # Jalankan migration (konsolidasi ke canonical + hapus duplikat)
        result = builder.migrate_legacy_files(dry_run=False)

        # Hitung legacy files setelah cleanup
        legacy_after = len([
            f for f in os.listdir(sop_dir)
            if f.startswith("sop_auto_") and f.endswith(".md")
               and os.path.isfile(os.path.join(sop_dir, f))
        ])

        logger.info(
            "[RETENTION_DAEMON][SOP] Cleanup selesai: %d → %d files "
            "(merged=%d, skip_dup=%d, errors=%d). Canonical SOPs: %d.",
            legacy_before, legacy_after,
            result.get("merged", 0),
            result.get("skipped_duplicate", 0),
            result.get("errors", 0),
            len(builder.get_canonical_sop_index()),
        )
    except Exception as e:
        logger.warning("[RETENTION_DAEMON][SOP] migrate_legacy_files error: %s", e)




async def heartbeat_loop(nc):
    """Sends heartbeat status metrics to NATS for all agents."""
    uptime_start = time.time()
    import psutil
    while True:
        try:
            uptime = int(time.time() - uptime_start)
            cpu = psutil.cpu_percent()
            agents = ["incident", "security", "verify", "recovery"]
            for agent in agents:
                payload = {
                    "agent": agent,
                    "status": "ONLINE",
                    "uptime": uptime,
                    "queue_depth": 0,
                    "cpu": cpu / 100.0
                }
                subject = f"agent.status.site.global.{agent}"
                await nc.publish(subject, json.dumps(payload).encode())
        except Exception as hb_err:
            logger.error(f"Error sending heartbeat: {hb_err}")
        await asyncio.sleep(5)


async def trust_evaluator_loop():
    """Background Trust Engine Evaluator (Phase 6)."""
    from engines.trust_engine import TrustEngine
    from engines.rag_engine import get_rag_engine
    te = TrustEngine()
    while True:
        rag = None
        try:
            rag = get_rag_engine()
            rag.connect()
            if rag.conn:
                te.evaluate_trust_scores(rag.conn)
        except Exception as eval_err:
            logger.error(f"Error in trust evaluation loop: {eval_err}")
        finally:
            if rag and rag.conn:
                try:
                    rag.close()
                except Exception:
                    pass
        await asyncio.sleep(10)


async def sync_human_rejections_loop():
    """Background Human Rejection Embedding Sync to Knowledge Store."""
    from engines.rag_engine import get_rag_engine
    from engines.llm_router import get_router
    while True:
        db = None
        try:
            db = get_rag_engine()
            db.connect()
            if db.conn:
                router = get_router()
                with db.conn.cursor() as cur:
                    cur.execute("""
                        SELECT pm.incident_id, pm.device_name, pm.rca_summary, pm.report_data, pm.created_at
                        FROM incident_post_mortems pm
                        LEFT JOIN knowledge_vectors kv ON kv.incident_id = CONCAT('KB-REJ-', pm.incident_id::text)
                        WHERE pm.flag = 'HUMAN_REJECTION' 
                          AND (pm.remediation_effectiveness = 'CURATED_REJECTION' OR (pm.report_data->>'is_curated') = 'true')
                          AND kv.incident_id IS NULL
                    """)
                    unmapped = cur.fetchall()
                    for row in unmapped:
                        inc_id, device, rca_summary, report_data, created_at = row
                        logger.info(f"[REJECTION SYNC] Found unsynced human rejection for Incident ID: {inc_id}")
                        
                        why_failed = "Unknown reason"
                        failed_action = "Unknown action"
                        if report_data:
                            why_failed = report_data.get("why_failed") or report_data.get("why_rejected") or "Unknown"
                            failed_action = report_data.get("failed_action") or "Unknown"
                        
                        text_to_embed = (
                            f"Human Operator Rejection Memory. Device: {device}. "
                            f"Failed/Rejected Action: {failed_action}. "
                            f"Why Rejected: {why_failed}. RCA Summary: {rca_summary}"
                        )
                        
                        embedding = router.embed_text_768(text_to_embed) or [0.0] * 768
                        if all(x == 0.0 for x in embedding):
                            embedding = db._local_embedding_fallback(text_to_embed)
                            
                        vector_str = "[" + ",".join(map(str, embedding)) + "]"
                        
                        cur.execute("""
                            INSERT INTO knowledge_vectors (incident_id, title, symptoms, root_cause, resolution, embedding, confidence, created_at, tags)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s)
                        """, (
                            f"KB-REJ-{inc_id}",
                            f"Operator Rejection of {failed_action}",
                            f"Mitigation action rejected by operator due to high risk on {device}",
                            why_failed,
                            f"Alternative chosen: {report_data.get('alternative_chosen') or 'Manual NOC Triage'}",
                            vector_str,
                            0.50,
                            ["rejection", "hitl", failed_action]
                        ))
                        db.conn.commit()
                        logger.info(f"[REJECTION SYNC] Successfully embedded and saved KB-REJ-{inc_id} to knowledge_vectors.")
        except Exception as loop_err:
            logger.error(f"[REJECTION SYNC] Error in rejection sync loop: {loop_err}")
        finally:
            if db and db.conn:
                try:
                    db.close()
                except Exception:
                    pass
        await asyncio.sleep(8)


def world_model_loop_sync():
    """Sync step for World Model updater."""
    from engines.rag_engine import get_rag_engine
    from world_model.world_model_updater import WorldModelUpdater
    try:
        db = get_rag_engine()
        db.connect()
        if db.conn:
            updater = WorldModelUpdater(db.conn)
            updater.run_all_engines()
            db.close()
    except Exception as e:
        logger.error(f"[WORLD MODEL LOOP] Error: {e}")


async def world_model_loop_async():
    """Async background task for World Model updates."""
    while True:
        await asyncio.to_thread(world_model_loop_sync)
        await asyncio.sleep(300)


def predictive_loop_sync():
    """Sync step for Predictive Engine."""
    from engines.rag_engine import get_rag_engine
    from predictive.predictive_engine import PredictiveEngine
    try:
        db = get_rag_engine()
        db.connect()
        if db.conn:
            pred_engine = PredictiveEngine(db.conn)
            with db.conn.cursor() as cur:
                cur.execute("SELECT asset_id, criticality, last_telemetry FROM assets WHERE last_telemetry IS NOT NULL LIMIT 50")
                assets = cur.fetchall()
                for asset in assets:
                    asset_id, criticality, telemetry = asset
                    if isinstance(telemetry, str):
                        telemetry = json.loads(telemetry)
                    
                    historical_telemetry = {}
                    cur.execute("""
                        SELECT metric_name, metric_value, EXTRACT(EPOCH FROM timestamp) as ts
                        FROM telemetry_logs
                        WHERE device_name = %s 
                          AND metric_name IN ('disk_usage', 'cpu_usage', 'memory_usage')
                        ORDER BY timestamp DESC LIMIT 20
                    """, (asset_id,))
                    hist_rows = cur.fetchall()
                    
                    for row in reversed(hist_rows):
                        m_name, m_val, m_ts = row
                        if m_name not in historical_telemetry:
                            historical_telemetry[m_name] = []
                        historical_telemetry[m_name].append([m_ts, float(m_val)])
                        
                    pred_engine.predict_incident(asset_id, telemetry, historical_telemetry, criticality)
            db.close()
    except Exception as e:
        logger.error(f"[PREDICTIVE LOOP] Error: {e}")


async def predictive_loop_async():
    """Async background task for Predictive Engine updates."""
    while True:
        await asyncio.to_thread(predictive_loop_sync)
        await asyncio.sleep(60)
