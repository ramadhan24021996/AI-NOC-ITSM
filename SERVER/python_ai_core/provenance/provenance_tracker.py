"""
Canonical Provenance Tracker Engine (provenance/provenance_tracker.py)

Provides end-to-end bi-directional forensic traceability across the 13-stage pipeline:
Incident → Telemetry → Curiosity → Gap → RAG/SOP → AI Decision → HITL → Playbook → Execution → Outcome → Feedback → DPO Pair → Learning

Ensures zero fabricated IDs: stages without a real runtime identifier remain NULL / UNRESOLVED.
"""

import logging
import psycopg2
import psycopg2.extras
import os
import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, UTC

logger = logging.getLogger("PROVENANCE_TRACKER")

DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("DB_PORT", "5433" if DB_HOST == "127.0.0.1" else "5432")
DB_NAME = os.environ.get("DB_NAME", "osi_system")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("POSTGRES_PASSWORD", "[REDACTED_DB_PASS]"))

ALL_STAGE_IDS = [
    "incident_id", "trace_id", "telemetry_id", "gap_id",
    "knowledge_vector_id", "sop_id", "decision_id", "hitl_decision_id",
    "playbook_id", "execution_id", "outcome_id", "feedback_id",
    "dpo_pair_id", "learning_job_id"
]


class ProvenanceTracker:
    def __init__(self):
        pass

    def _get_connection(self):
        return psycopg2.connect(
            host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
            user=DB_USER, password=DB_PASSWORD
        )

    def create_provenance_chain(
        self,
        trace_id: str,
        incident_id: Optional[str] = None,
        telemetry_id: Optional[int] = None
    ) -> Optional[str]:
        """
        Initializes a new canonical provenance chain row for a trace_id.
        """
        if not trace_id:
            logger.warning("[PROVENANCE] Cannot create chain without valid trace_id")
            return None

        conn = None
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO incident_provenance_chain (
                        trace_id, incident_id, telemetry_id, chain_status, created_at, updated_at
                    ) VALUES (%s, %s, %s, 'IN_PROGRESS', NOW(), NOW())
                    ON CONFLICT (trace_id) DO UPDATE SET
                        incident_id = COALESCE(EXCLUDED.incident_id, incident_provenance_chain.incident_id),
                        telemetry_id = COALESCE(EXCLUDED.telemetry_id, incident_provenance_chain.telemetry_id),
                        updated_at = NOW();
                """, (trace_id, incident_id, telemetry_id))
            conn.commit()
            logger.info(f"[PROVENANCE] Initialized canonical chain for trace_id '{trace_id}' (Incident: {incident_id})")
            return trace_id
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"[PROVENANCE] Error initializing chain for trace_id '{trace_id}': {e}")
            return None
        finally:
            if conn:
                try: conn.close()
                except Exception: pass

    def update_stage_id(
        self,
        trace_id: str,
        stage_name: str,
        stage_value: Any
    ) -> bool:
        """
        Updates a specific stage ID in the canonical provenance chain.
        Validates stage_name against canonical 13-stage identifiers.
        Refuses to inject mock/dummy values.
        """
        if not trace_id or not stage_name:
            return False

        if stage_name not in ALL_STAGE_IDS:
            logger.error(f"[PROVENANCE] Invalid stage name '{stage_name}'")
            return False

        if stage_value is None:
            # Keep as NULL / UNRESOLVED
            return True

        conn = None
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                query = f"""
                    UPDATE incident_provenance_chain 
                    SET {stage_name} = %s, updated_at = NOW()
                    WHERE trace_id = %s;
                """
                cur.execute(query, (stage_value, trace_id))
            conn.commit()
            logger.info(f"[PROVENANCE] Chain '{trace_id}' updated stage '{stage_name}' = '{stage_value}'")
            return True
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"[PROVENANCE] Error updating stage '{stage_name}' for trace '{trace_id}': {e}")
            return False
        finally:
            if conn:
                try: conn.close()
                except Exception: pass

    def get_provenance_chain_by_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the full bi-directional canonical provenance chain by trace_id.
        """
        conn = None
        try:
            conn = self._get_connection()
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT provenance_id, trace_id, incident_id, telemetry_id, gap_id,
                           knowledge_vector_id, sop_id, decision_id, hitl_decision_id,
                           playbook_id, execution_id, outcome_id, feedback_id, dpo_pair_id,
                           learning_job_id, chain_status, created_at, updated_at
                    FROM incident_provenance_chain
                    WHERE trace_id = %s;
                """, (trace_id,))
                row = cur.fetchone()
                if row:
                    return dict(row)
                return None
        except Exception as e:
            logger.error(f"[PROVENANCE] Error fetching chain for trace '{trace_id}': {e}")
            return None
        finally:
            if conn:
                try: conn.close()
                except Exception: pass

    def get_provenance_chain_by_dpo_pair(self, dpo_pair_id: int) -> Optional[Dict[str, Any]]:
        """
        Bi-directional Forensic Query: Traces back from a DPO pair ID to its root incident and evidence.
        """
        conn = None
        try:
            conn = self._get_connection()
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT provenance_id, trace_id, incident_id, telemetry_id, gap_id,
                           knowledge_vector_id, sop_id, decision_id, hitl_decision_id,
                           playbook_id, execution_id, outcome_id, feedback_id, dpo_pair_id,
                           learning_job_id, chain_status, created_at, updated_at
                    FROM incident_provenance_chain
                    WHERE dpo_pair_id = %s;
                """, (dpo_pair_id,))
                row = cur.fetchone()
                if row:
                    return dict(row)
                return None
        except Exception as e:
            logger.error(f"[PROVENANCE] Error fetching chain for DPO pair '{dpo_pair_id}': {e}")
            return None
        finally:
            if conn:
                try: conn.close()
                except Exception: pass

    def evaluate_chain_completeness(self, trace_id: str) -> Dict[str, Any]:
        """
        Evaluates stage resolution completeness for a provenance chain.
        Returns percentage resolved, list of resolved stage IDs, and list of missing/unresolved stage IDs.
        """
        chain = self.get_provenance_chain_by_trace(trace_id)
        if not chain:
            return {
                "status": "NOT_FOUND",
                "completeness_pct": 0.0,
                "resolved_stages": [],
                "unresolved_stages": ALL_STAGE_IDS
            }

        resolved = []
        unresolved = []

        for stage_id in ALL_STAGE_IDS:
            val = chain.get(stage_id)
            if val is not None and str(val).strip() != "":
                resolved.append(stage_id)
            else:
                unresolved.append(stage_id)

        pct = round((len(resolved) / len(ALL_STAGE_IDS)) * 100.0, 2)

        return {
            "status": "EVALUATED",
            "trace_id": trace_id,
            "completeness_pct": pct,
            "resolved_count": len(resolved),
            "unresolved_count": len(unresolved),
            "resolved_stages": resolved,
            "unresolved_stages": unresolved
        }
